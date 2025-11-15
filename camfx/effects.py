import cv2
import numpy as np
from .segmentation import FaceDetector


class BackgroundBlur:
	def apply(self, frame: np.ndarray, mask: np.ndarray, strength: int = 25) -> np.ndarray:
		if strength <= 0:
			raise ValueError(f"Strength must be positive, got {strength}")
		if strength % 2 == 0:
			raise ValueError(f"Strength must be odd (Gaussian blur requires odd kernel size), got {strength}. Use an odd number like {strength + 1} or {strength - 1}")
		frame_f = frame.astype(np.float32)
		mask_f = np.clip(mask.astype(np.float32), 0.0, 1.0)
		blurred = cv2.GaussianBlur(frame_f, (strength, strength), 0)
		mask_3d = np.stack((mask_f,) * 3, axis=-1)
		blended = frame_f * mask_3d + blurred * (1.0 - mask_3d)
		return np.clip(blended, 0, 255).astype(np.uint8)


class BackgroundReplace:
	def apply(self, frame: np.ndarray, mask: np.ndarray, background: np.ndarray) -> np.ndarray:
		if background is None:
			raise ValueError("Background image is not loaded or invalid.")
		frame_f = frame.astype(np.float32)
		mask_f = np.clip(mask.astype(np.float32), 0.0, 1.0)
		bg = cv2.resize(background, (frame.shape[1], frame.shape[0])).astype(np.float32)
		mask_3d = np.stack((mask_f,) * 3, axis=-1)
		blended = frame_f * mask_3d + bg * (1.0 - mask_3d)
		return np.clip(blended, 0, 255).astype(np.uint8)


class BrightnessAdjustment:
	"""Adjust brightness and optionally contrast of the video frame.
	
	Can be applied globally or selectively to the face region using a mask.
	"""
	def apply(self, frame: np.ndarray, mask: np.ndarray | None = None, brightness: int = 0, contrast: float = 1.0, face_only: bool = False) -> np.ndarray:
		"""
		Args:
			frame: Input frame (BGR format)
			mask: Optional segmentation mask (for face-only adjustment)
			brightness: Brightness adjustment (-100 to 100, 0 = no change)
			contrast: Contrast multiplier (0.5 to 2.0, 1.0 = no change)
			face_only: If True and mask provided, apply only to face region
		"""
		# Clamp values
		brightness = np.clip(brightness, -100, 100)
		contrast = np.clip(contrast, 0.5, 2.0)
		
		if face_only and mask is not None:
			# Apply to face region only
			mask_f = np.clip(mask.astype(np.float32), 0.0, 1.0)
			mask_3d = np.stack((mask_f,) * 3, axis=-1)
			
			# Adjust face region
			face_region = frame.astype(np.float32)
			face_adjusted = cv2.convertScaleAbs(face_region, alpha=contrast, beta=brightness)
			
			# Keep background unchanged
			background = frame.astype(np.float32)
			
			# Blend
			result = face_adjusted.astype(np.float32) * mask_3d + background * (1.0 - mask_3d)
			return np.clip(result, 0, 255).astype(np.uint8)
		else:
			# Apply globally
			frame_f = frame.astype(np.float32)
			return cv2.convertScaleAbs(frame_f, alpha=contrast, beta=brightness)


class FaceBeautification:
	"""Apply skin smoothing and beautification effects to the face.
	
	Uses MediaPipe Face Mesh landmarks to identify face region and applies
	bilateral filtering for natural-looking skin smoothing.
	"""
	def __init__(self):
		import mediapipe as mp
		self.face_mesh = mp.solutions.face_mesh.FaceMesh(
			max_num_faces=1,
			refine_landmarks=True,
			min_detection_confidence=0.5,
			min_tracking_confidence=0.5
		)
	
	def apply(self, frame: np.ndarray, mask: np.ndarray | None = None, smoothness: int = 5) -> np.ndarray:
		"""
		Args:
			frame: Input frame (BGR format)
			mask: Optional segmentation mask (unused, kept for API compatibility)
			smoothness: Skin smoothing strength (1-15, higher = more smoothing)
		"""
		# Clamp smoothness
		smoothness = max(1, min(15, smoothness))
		# Ensure odd number for bilateral filter
		if smoothness % 2 == 0:
			smoothness += 1
		
		# Convert to RGB for MediaPipe
		frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
		results = self.face_mesh.process(frame_rgb)
		
		if results.multi_face_landmarks:
			# Get face landmarks
			face_landmarks = results.multi_face_landmarks[0]
			h, w = frame.shape[:2]
			
			# Extract face region using landmarks
			# Get face contour points (approximate face oval)
			face_points = []
			for landmark in face_landmarks.landmark:
				x = int(landmark.x * w)
				y = int(landmark.y * h)
				face_points.append([x, y])
			
			face_points = np.array(face_points, dtype=np.int32)
			
			# Create mask for face region
			face_mask = np.zeros((h, w), dtype=np.uint8)
			# Use convex hull for face region
			hull = cv2.convexHull(face_points)
			cv2.fillPoly(face_mask, [hull], 255)
			
			# Smooth the mask edges
			face_mask = cv2.GaussianBlur(face_mask, (21, 21), 0)
			face_mask = face_mask.astype(np.float32) / 255.0
			face_mask_3d = np.stack((face_mask,) * 3, axis=-1)
			
			# Apply bilateral filter for skin smoothing (preserves edges)
			smoothed = cv2.bilateralFilter(frame, smoothness, 75, 75)
			
			# Blend smoothed face with original
			result = frame.astype(np.float32) * (1.0 - face_mask_3d) + smoothed.astype(np.float32) * face_mask_3d
			return np.clip(result, 0, 255).astype(np.uint8)
		else:
			# No face detected, return original
			return frame


class AutoFraming:
	"""Automatically crop and center the frame on the detected face.
	
	Maintains original frame dimensions by cropping and scaling.
	"""
	def __init__(self):
		self.face_detector = FaceDetector()
	
	def apply(self, frame: np.ndarray, mask: np.ndarray | None = None, padding: float = 0.3, min_zoom: float = 1.0, max_zoom: float = 2.0) -> np.ndarray:
		"""
		Args:
			frame: Input frame (BGR format)
			mask: Optional segmentation mask (unused, kept for API compatibility)
			padding: Padding around face as fraction of face size (0.0-1.0)
			min_zoom: Minimum zoom level (1.0 = no zoom, >1.0 = zoom in)
			max_zoom: Maximum zoom level
		"""
		h, w = frame.shape[:2]
		bbox = self.face_detector.get_face_bbox(frame, smooth=True)
		
		if bbox is None:
			# No face detected, return original
			return frame
		
		x, y, face_w, face_h = bbox
		
		# Calculate desired crop region with padding
		padding_pixels_w = int(face_w * padding)
		padding_pixels_h = int(face_h * padding)
		
		# Crop region
		crop_x = max(0, x - padding_pixels_w)
		crop_y = max(0, y - padding_pixels_h)
		crop_w = min(w - crop_x, face_w + 2 * padding_pixels_w)
		crop_h = min(h - crop_y, face_h + 2 * padding_pixels_h)
		
		# Calculate zoom to fit frame
		zoom_w = w / crop_w
		zoom_h = h / crop_h
		zoom = min(zoom_w, zoom_h)
		
		# Clamp zoom
		zoom = max(min_zoom, min(max_zoom, zoom))
		
		# Adjust crop to account for zoom
		# We want to crop a larger region and scale it down
		actual_crop_w = int(w / zoom)
		actual_crop_h = int(h / zoom)
		
		# Center the crop on the face
		face_center_x = x + face_w // 2
		face_center_y = y + face_h // 2
		
		crop_x = max(0, face_center_x - actual_crop_w // 2)
		crop_y = max(0, face_center_y - actual_crop_h // 2)
		
		# Ensure crop doesn't go out of bounds
		if crop_x + actual_crop_w > w:
			crop_x = w - actual_crop_w
		if crop_y + actual_crop_h > h:
			crop_y = h - actual_crop_h
		crop_x = max(0, crop_x)
		crop_y = max(0, crop_y)
		
		# Crop and resize
		cropped = frame[crop_y:crop_y + actual_crop_h, crop_x:crop_x + actual_crop_w]
		
		# Resize to original dimensions
		if cropped.size > 0:
			result = cv2.resize(cropped, (w, h), interpolation=cv2.INTER_LINEAR)
			return result
		else:
			# Fallback if crop is invalid
			return frame


