import cv2
import numpy as np

from .mediapipe_tasks import face_landmarks_from_bgr, person_mask_from_bgr


class PersonSegmenter:
	def __init__(self) -> None:
		# Tasks backend is initialized lazily inside camfx.mediapipe_tasks.
		pass

	def get_mask(self, frame: np.ndarray, timestamp_ms: int) -> np.ndarray:
		return person_mask_from_bgr(frame, timestamp_ms)


class FaceDetector:
	"""Detects faces using MediaPipe Face Detection for auto-framing."""
	def __init__(self) -> None:
		self.last_bbox = None  # For smoothing
	
	def get_face_bbox(self, frame: np.ndarray, timestamp_ms: int, smooth: bool = True) -> tuple[int, int, int, int] | None:
		"""
		Returns face bounding box as (x, y, width, height) in pixel coordinates.
		Returns None if no face detected.
		
		Args:
			frame: Input frame (BGR format)
			smooth: If True, smooth transitions using exponential moving average
		"""
		h, w = frame.shape[:2]
		landmarks = face_landmarks_from_bgr(frame, timestamp_ms)
		if landmarks is None:
			return self.last_bbox if (smooth and self.last_bbox is not None) else None

		xs = [lm.x for lm in landmarks]
		ys = [lm.y for lm in landmarks]
		x_min = int(max(0.0, min(xs)) * w)
		y_min = int(max(0.0, min(ys)) * h)
		x_max = int(min(1.0, max(xs)) * w)
		y_max = int(min(1.0, max(ys)) * h)
		fw = max(1, x_max - x_min)
		fh = max(1, y_max - y_min)
		current_bbox = (x_min, y_min, fw, fh)
		if smooth and self.last_bbox is not None:
			alpha = 0.3
			x = int(alpha * current_bbox[0] + (1 - alpha) * self.last_bbox[0])
			y = int(alpha * current_bbox[1] + (1 - alpha) * self.last_bbox[1])
			fw = int(alpha * current_bbox[2] + (1 - alpha) * self.last_bbox[2])
			fh = int(alpha * current_bbox[3] + (1 - alpha) * self.last_bbox[3])
			current_bbox = (x, y, fw, fh)
		self.last_bbox = current_bbox
		return current_bbox


