import cv2
import numpy as np
import time
from typing import Optional

from .segmentation import PersonSegmenter
from .output_pipewire import PipeWireOutput
from .control import EffectController


class VideoEnhancer:
	def __init__(self, input_device: int = 0, effect_type: str = 'blur', config: dict | None = None, 
	             enable_lazy_camera: bool = False) -> None:
		self.input_device = input_device
		self.config = config or {}
		self.enable_lazy_camera = enable_lazy_camera
		
		# Camera is not opened immediately if lazy mode is enabled
		self.cap: Optional[cv2.VideoCapture] = None
		self.camera_active = False
		
		# Initialize effect controller
		self.effect_controller = EffectController()
		
		# Set initial effect
		if effect_type:
			initial_config = self._get_effect_config(effect_type, config)
			self.effect_controller.set_effect(effect_type, initial_config)
			print(f"Effect '{effect_type}' configured")
		
		# Segmentation will be initialized lazily when needed
		self.segmenter: Optional[PersonSegmenter] = None
		
		# Get target dimensions and FPS from config
		self.target_fps = int(self.config.get('fps', 30))
		self.enable_virtual = bool(self.config.get('enable_virtual', True))
		camera_name = self.config.get('camera_name', 'camfx')
		
		# For lazy camera, we need to know dimensions before opening camera
		# Use config values or defaults
		target_width = self.config.get('width')
		target_height = self.config.get('height')
		
		# If lazy camera is disabled, open camera immediately to get dimensions
		if not enable_lazy_camera:
			print(f"Opening camera device {input_device}...")
			self.cap = cv2.VideoCapture(input_device)
			if not self.cap.isOpened():
				# Check if camera is in use by another process
				import subprocess
				try:
					result = subprocess.run(
						['lsof', f'/dev/video{input_device}'],
						capture_output=True,
						text=True,
						timeout=1
					)
					if result.returncode == 0 and result.stdout.strip():
						# Camera is in use
						lines = result.stdout.strip().split('\n')
						if len(lines) > 1:  # Header + at least one process
							processes = []
							for line in lines[1:]:
								parts = line.split()
								if len(parts) >= 2:
									processes.append(f"{parts[0]} (PID {parts[1]})")
							process_list = ", ".join(processes)
							raise RuntimeError(
								f"Unable to open camera device {input_device}. "
								f"Camera is already in use by: {process_list}. "
								f"Close the other process or use a different camera index."
							)
				except (subprocess.TimeoutExpired, FileNotFoundError, subprocess.SubprocessError):
					pass  # lsof not available or failed, use generic message
				
				raise RuntimeError(
					f"Unable to open input camera device index {input_device}. "
					f"Use 'camfx list-devices' to discover working indexes. "
					f"If the camera is in use by another process, close it first."
				)
			print("Camera opened successfully")
			
			# Set dimensions if specified
			if target_width:
				self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, int(target_width))
			if target_height:
				self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, int(target_height))
			
			# Get actual dimensions
			self.width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
			self.height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
			self.camera_active = True
		else:
			# For lazy camera, use config dimensions or defaults
			self.width = target_width or 640
			self.height = target_height or 480
			print(f"Lazy camera mode enabled. Camera will start when source is in use.")
		
		# Virtual camera output via PipeWire (always initialize, even if camera not active)
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
		
		# Initialize source monitor for lazy camera
		self.source_monitor = None
		if enable_lazy_camera:
			from .pipewire_monitor import PipeWireSourceMonitor
			self.source_monitor = PipeWireSourceMonitor(camera_name)
			self.source_monitor.start_monitoring(self._on_source_usage_changed)
		
		# Initialize D-Bus service if enabled
		self.dbus_service = None
		if self.config.get('enable_dbus', False):
			try:
				from .dbus_control import CamfxControlService
				self.dbus_service = CamfxControlService(self.effect_controller)
				self.dbus_service.start()
			except Exception as exc:
				print(f"Warning: Failed to start D-Bus service: {exc}")
				print("Runtime effect control via D-Bus will not be available")
				self.dbus_service = None
	
	def _get_effect_config(self, effect_type: str, config: dict | None) -> dict:
		"""Extract effect-specific config from general config."""
		if not config:
			return {}
		
		# Effect-specific parameters
		effect_params = {
			'blur': ['strength'],
			'replace': ['background', 'image'],  # image is for file path, background is numpy array
			'brightness': ['brightness', 'contrast', 'face_only'],
			'beautify': ['smoothness'],
			'autoframe': ['padding', 'min_zoom', 'max_zoom'],
			'gaze-correct': ['strength'],
		}
		
		# Extract relevant parameters for this effect type
		effect_config = {}
		params = effect_params.get(effect_type, [])
		for param in params:
			if param in config:
				effect_config[param] = config[param]
		
		# Also copy any other config that might be effect-specific
		# (for future extensibility)
		return effect_config
	
	def _on_source_usage_changed(self, is_used: bool):
		"""Callback when source usage changes."""
		if is_used and not self.camera_active:
			self._start_camera()
		elif not is_used and self.camera_active:
			self._stop_camera()
	
	def _start_camera(self):
		"""Start camera capture."""
		if self.cap is not None:
			return  # Already started
		
		print(f"Starting camera (source is in use)...")
		self.cap = cv2.VideoCapture(self.input_device)
		if not self.cap.isOpened():
			print(f"Warning: Failed to open camera {self.input_device}")
			return
		
		# Set resolution if specified
		if 'width' in self.config:
			self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, int(self.config['width']))
		if 'height' in self.config:
			self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, int(self.config['height']))
		
		# Update dimensions from actual camera
		self.width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
		self.height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
		
		self.camera_active = True
		print("Camera started")
	
	def _stop_camera(self):
		"""Stop camera capture."""
		if self.cap is None:
			return
		
		print("Stopping camera (source not in use)...")
		self.cap.release()
		self.cap = None
		self.camera_active = False
		print("Camera stopped")
	
	def set_effect(self, effect_type: str, config: dict):
		"""Change effect at runtime."""
		effect_config = self._get_effect_config(effect_type, config)
		self.effect_controller.set_effect(effect_type, effect_config)
		print(f"Effect changed to: {effect_type}")
	
	def add_effect(self, effect_type: str, config: dict):
		"""Add effect to chain at runtime."""
		effect_config = self._get_effect_config(effect_type, config)
		self.effect_controller.add_effect(effect_type, effect_config)
		print(f"Effect added to chain: {effect_type}")

	def run(self, preview: bool = False, **kwargs) -> None:
		"""Main processing loop with lazy camera support."""
		try:
			if preview:
				cv2.namedWindow('camfx preview', cv2.WINDOW_NORMAL)
				print("Preview window created. Press 'q' to quit.")
			
			# If lazy camera is disabled, camera should already be started
			if not self.enable_lazy_camera and not self.camera_active:
				self._start_camera()
			
			frame_count = 0
			while True:
				# Check if camera should be active (for lazy camera mode)
				if self.enable_lazy_camera and not self.camera_active:
					# Send a black frame or last frame when camera is off
					if self.virtual_cam is not None:
						# Send black frame
						black_frame = np.zeros((self.height, self.width, 3), dtype=np.uint8)
						frame_rgb = cv2.cvtColor(black_frame, cv2.COLOR_BGR2RGB)
						self.virtual_cam.send(frame_rgb.tobytes())
						self.virtual_cam.sleep_until_next_frame()
					
					if preview:
						# Show message in preview
						display_frame = np.zeros((480, 640, 3), dtype=np.uint8)
						cv2.putText(display_frame, "Camera inactive (source not in use)", 
						           (10, 240), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
						cv2.imshow('camfx preview', display_frame)
						key = cv2.waitKey(1) & 0xFF
						if key == ord('q'):
							break
					
					time.sleep(0.1)  # Small delay when inactive
					continue
				
				# Camera is active, process frames
				if self.cap is None:
					time.sleep(0.1)
					continue
				
				ret, frame = self.cap.read()
				if not ret:
					print("Failed to read frame from camera")
					time.sleep(0.1)
					continue
				
				# Get effect chain
				chain = self.effect_controller.get_chain()
				
				# Determine if any effect in chain needs a mask
				needs_mask = False
				for effect, _ in chain.effects:
					effect_class_name = effect.__class__.__name__
					if effect_class_name in ['BackgroundBlur', 'BackgroundReplace']:
						needs_mask = True
						break
					elif effect_class_name == 'BrightnessAdjustment':
						# Check if brightness effect needs mask (face_only mode)
						# We'll check this in the effect chain apply method
						if kwargs.get('face_only', False):
							needs_mask = True
							break
				
				# Initialize segmenter if needed
				if needs_mask and self.segmenter is None:
					print("Initializing segmentation model...")
					self.segmenter = PersonSegmenter()
					print("Segmentation model ready")
				
				# Get mask if needed
				mask = self.segmenter.get_mask(frame) if needs_mask else None
				
				# Apply effect chain
				processed = chain.apply(frame, mask, **kwargs)
				
				# Send to virtual camera
				if self.virtual_cam is not None:
					frame_rgb = cv2.cvtColor(processed, cv2.COLOR_BGR2RGB)
					self.virtual_cam.send(frame_rgb.tobytes())
					self.virtual_cam.sleep_until_next_frame()
				
				# Show preview
				if preview:
					cv2.imshow('camfx preview', processed)
					key = cv2.waitKey(1) & 0xFF
					if key == ord('q'):
						break
				
				frame_count += 1
				if frame_count == 1:
					print(f"Processing frames... (Press 'q' in preview window to quit)")
		
		finally:
			self._stop_camera()
			if self.source_monitor:
				self.source_monitor.stop_monitoring()
			if self.dbus_service:
				self.dbus_service.stop()
			if self.virtual_cam is not None:
				self.virtual_cam.cleanup()
			try:
				cv2.destroyAllWindows()
			except Exception:
				pass


