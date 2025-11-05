import cv2
import pyvirtualcam

from .segmentation import PersonSegmenter
from .effects import BackgroundBlur, BackgroundReplace



class VideoEnhancer:
	def __init__(self, input_device: int = 0, effect_type: str = 'blur', config: dict | None = None) -> None:
		self.cap = cv2.VideoCapture(input_device)
		if not self.cap.isOpened():
			raise RuntimeError(
				f"Unable to open input camera device index {input_device}. Use 'camfx list-devices' to discover working indexes."
			)
		self.segmenter = PersonSegmenter()
		self.effect = self._create_effect(effect_type)
		self.output_device = (config or {}).get('vdevice', '/dev/video10')
		self.target_fps = int((config or {}).get('fps', 30))
		self.enable_virtual = bool((config or {}).get('enable_virtual', True))

		# Optional input dimensions
		target_width = (config or {}).get('width')
		target_height = (config or {}).get('height')
		if target_width:
			self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, int(target_width))
		if target_height:
			self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, int(target_height))

		# Get input dimensions (after any requested sets)
		self.width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
		self.height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

		# Virtual camera output
		self.virtual_cam = None
		if self.enable_virtual:
			try:
				self.virtual_cam = pyvirtualcam.Camera(
					width=self.width,
					height=self.height,
					fps=self.target_fps,
					device=self.output_device,
					pixel_format=pyvirtualcam.PixelFormat.RGB,
				)
			except Exception as exc:
				self.cap.release()
				raise RuntimeError(
					f"Failed to open virtual camera at {self.output_device}. Ensure v4l2loopback is loaded and the device is writable. Original error: {exc}"
				)

	def _create_effect(self, effect_type: str):
		if effect_type == 'blur':
			return BackgroundBlur()
		elif effect_type == 'replace':
			return BackgroundReplace()
		raise ValueError(f"Unknown effect_type: {effect_type}")

	def run(self, preview: bool = False, **kwargs) -> None:
		while True:
			ret, frame = self.cap.read()
			if not ret:
				break

			mask = self.segmenter.get_mask(frame)
			processed = self.effect.apply(frame, mask, **kwargs)

			if self.virtual_cam is not None:
				# pyvirtualcam configured for RGB above; convert BGR -> RGB
				self.virtual_cam.send(cv2.cvtColor(processed, cv2.COLOR_BGR2RGB))
				self.virtual_cam.sleep_until_next_frame()
			if preview:
				cv2.imshow('camfx preview', processed)
				if cv2.waitKey(1) & 0xFF == ord('q'):
					break
		self.cap.release()
		try:
			cv2.destroyAllWindows()
		except Exception:
			pass


