import cv2
import numpy as np


class BackgroundBlur:
	def apply(self, frame: np.ndarray, mask: np.ndarray, strength: int = 25) -> np.ndarray:
		if strength <= 0 or strength % 2 == 0:
			raise ValueError("--strength must be a positive odd integer, e.g., 3,5,7,...")
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


