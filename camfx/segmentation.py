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


