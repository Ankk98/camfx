import cv2
import mediapipe as mp
import numpy as np


class PersonSegmenter:
	def __init__(self) -> None:
		self.segmenter = mp.solutions.selfie_segmentation.SelfieSegmentation(model_selection=1)

	def get_mask(self, frame: np.ndarray) -> np.ndarray:
		results = self.segmenter.process(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
		mask = getattr(results, "segmentation_mask", None)
		if mask is None:
			h, w = frame.shape[:2]
			return np.zeros((h, w), dtype=np.float32)
		# Ensure float32 in [0,1] and smooth edges
		mask_f32 = np.clip(mask.astype(np.float32), 0.0, 1.0)
		smoothed = cv2.GaussianBlur(mask_f32, (21, 21), 0)
		return smoothed


class FaceDetector:
	"""Detects faces using MediaPipe Face Detection for auto-framing."""
	def __init__(self) -> None:
		self.detector = mp.solutions.face_detection.FaceDetection(
			model_selection=0,  # Short-range model (faster, good for close-up)
			min_detection_confidence=0.5
		)
		self.last_bbox = None  # For smoothing
	
	def get_face_bbox(self, frame: np.ndarray, smooth: bool = True) -> tuple[int, int, int, int] | None:
		"""
		Returns face bounding box as (x, y, width, height) in pixel coordinates.
		Returns None if no face detected.
		
		Args:
			frame: Input frame (BGR format)
			smooth: If True, smooth transitions using exponential moving average
		"""
		frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
		results = self.detector.process(frame_rgb)
		
		h, w = frame.shape[:2]
		
		if results.detections:
			detection = results.detections[0]  # Use first detected face
			bbox = detection.location_data.relative_bounding_box
			
			# Convert normalized coordinates to pixel coordinates
			x = int(bbox.xmin * w)
			y = int(bbox.ymin * h)
			width = int(bbox.width * w)
			height = int(bbox.height * h)
			
			# Clamp to frame bounds
			x = max(0, min(x, w - 1))
			y = max(0, min(y, h - 1))
			width = min(width, w - x)
			height = min(height, h - y)
			
			current_bbox = (x, y, width, height)
			
			if smooth and self.last_bbox is not None:
				# Exponential moving average for smooth transitions
				alpha = 0.3  # Smoothing factor (lower = more smoothing)
				x = int(alpha * x + (1 - alpha) * self.last_bbox[0])
				y = int(alpha * y + (1 - alpha) * self.last_bbox[1])
				width = int(alpha * width + (1 - alpha) * self.last_bbox[2])
				height = int(alpha * height + (1 - alpha) * self.last_bbox[3])
				current_bbox = (x, y, width, height)
			
			self.last_bbox = current_bbox
			return current_bbox
		else:
			# No face detected - return last known position or None
			if smooth and self.last_bbox is not None:
				return self.last_bbox
			return None


