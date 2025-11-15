import cv2

from .segmentation import PersonSegmenter
from .effects import BackgroundBlur, BackgroundReplace, BrightnessAdjustment, FaceBeautification, AutoFraming, EyeGazeCorrection
from .output_pipewire import PipeWireOutput


class VideoEnhancer:
	def __init__(self, input_device: int = 0, effect_type: str = 'blur', config: dict | None = None) -> None:
		print(f"Opening camera device {input_device}...")
		self.cap = cv2.VideoCapture(input_device)
		if not self.cap.isOpened():
			raise RuntimeError(
				f"Unable to open input camera device index {input_device}. Use 'camfx list-devices' to discover working indexes."
			)
		print("Camera opened successfully")
		# Only initialize segmentation for effects that need it
		# Note: brightness may need it if face_only=True, but we'll handle that in run()
		effects_needing_mask = {'blur', 'replace'}
		if effect_type in effects_needing_mask:
			print("Initializing segmentation model...")
			self.segmenter = PersonSegmenter()
			print("Segmentation model ready")
		else:
			self.segmenter = None
		self.effect = self._create_effect(effect_type)
		print(f"Effect '{effect_type}' created")
		self.target_fps = int((config or {}).get('fps', 30))
		self.enable_virtual = bool((config or {}).get('enable_virtual', True))
		camera_name = (config or {}).get('camera_name', 'camfx')

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

		# Virtual camera output via PipeWire
		self.virtual_cam = None
		if self.enable_virtual:
			try:
				print(f"Initializing PipeWire virtual camera ({self.width}x{self.height} @ {self.target_fps}fps)...")
				self.virtual_cam = PipeWireOutput(
					width=self.width,
					height=self.height,
					fps=self.target_fps,
					name=camera_name,
				)
				print("PipeWire virtual camera ready")
			except Exception as exc:
				print(f"Warning: Failed to initialize PipeWire virtual camera: {exc}")
				print("Continuing with preview only. To enable virtual camera:")
				print("  1. Ensure PipeWire is running: systemctl --user status pipewire")
				print("  2. Ensure wireplumber is running: systemctl --user start wireplumber")
				print("  3. Or use --no-virtual to skip virtual camera initialization")
				self.virtual_cam = None

	def _create_effect(self, effect_type: str):
		if effect_type == 'blur':
			return BackgroundBlur()
		elif effect_type == 'replace':
			return BackgroundReplace()
		elif effect_type == 'brightness':
			return BrightnessAdjustment()
		elif effect_type == 'beautify':
			return FaceBeautification()
		elif effect_type == 'autoframe':
			return AutoFraming()
		elif effect_type == 'gaze-correct':
			return EyeGazeCorrection()
		raise ValueError(f"Unknown effect_type: {effect_type}")

	def run(self, preview: bool = False, **kwargs) -> None:
		try:
			if preview:
				# Create window early to ensure it's ready
				cv2.namedWindow('camfx preview', cv2.WINDOW_NORMAL)
				print("Preview window created. Press 'q' to quit.")
			
			frame_count = 0
			while True:
				ret, frame = self.cap.read()
				if not ret:
					print("Failed to read frame from camera")
					break

				# Get mask only if needed
				# For brightness with face_only, we need segmentation
				needs_mask = (self.segmenter is not None) or (
					self.effect.__class__.__name__ == 'BrightnessAdjustment' and kwargs.get('face_only', False)
				)
				if needs_mask and self.segmenter is None:
					# Lazy initialization for brightness with face_only
					print("Initializing segmentation model for face-only brightness...")
					self.segmenter = PersonSegmenter()
					print("Segmentation model ready")
				mask = self.segmenter.get_mask(frame) if needs_mask else None
				processed = self.effect.apply(frame, mask, **kwargs)

				if self.virtual_cam is not None:
					# Convert BGR to RGB and send to PipeWire
					frame_rgb = cv2.cvtColor(processed, cv2.COLOR_BGR2RGB)
					self.virtual_cam.send(frame_rgb.tobytes())
					self.virtual_cam.sleep_until_next_frame()
				
				if preview:
					cv2.imshow('camfx preview', processed)
					# Use waitKey with a timeout to prevent hanging
					key = cv2.waitKey(1) & 0xFF
					if key == ord('q'):
						print("Quit requested")
						break
				
				frame_count += 1
				if frame_count == 1:
					print(f"Processing frames... (Press 'q' in preview window to quit)")
		finally:
			self.cap.release()
			if self.virtual_cam is not None:
				self.virtual_cam.cleanup()
			try:
				cv2.destroyAllWindows()
			except Exception:
				pass


