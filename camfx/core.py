import logging
import cv2
import numpy as np
import time
from typing import Optional

from .segmentation import PersonSegmenter
from .output_pipewire import PipeWireOutput
from .control import EffectController

logger = logging.getLogger('camfx.core')


class VideoEnhancer:
	def __init__(self, input_device: int = 0, effect_type: str = 'blur', config: dict | None = None) -> None:
		self.input_device = input_device
		self.config = config or {}
		
		# Camera is not opened immediately - requires explicit start via D-Bus or CLI
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
		
		# Use config dimensions or defaults
		target_width = self.config.get('width')
		target_height = self.config.get('height')
		self.width = target_width or 640
		self.height = target_height or 480
		print("Camera is off by default. Use D-Bus or CLI to start it.")
		
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
		
		# Initialize D-Bus service if enabled
		self.dbus_service = None
		if self.config.get('enable_dbus', False):
			try:
				from .dbus_control import CamfxControlService
				self.dbus_service = CamfxControlService(self.effect_controller, self)
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
	
	def _start_camera(self):
		"""Start camera capture."""
		if self.cap is not None:
			return  # Already started
		
		self.cap = cv2.VideoCapture(self.input_device)
		if not self.cap.isOpened():
			self.cap = None
			self.camera_active = False
			return
		
		# Set resolution if specified
		if 'width' in self.config and self.config['width'] is not None:
			self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, int(self.config['width']))
		if 'height' in self.config and self.config['height'] is not None:
			self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, int(self.config['height']))
		
		# Update dimensions from actual camera
		self.width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
		self.height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
		
		self.camera_active = True
	
	def _stop_camera(self):
		"""Stop camera capture."""
		if self.cap is None:
			self.camera_active = False
			return
		
		self.cap.release()
		self.cap = None
		self.camera_active = False
	
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
		"""Main processing loop."""
		try:
			if preview:
				cv2.namedWindow('camfx preview', cv2.WINDOW_NORMAL)
				print("Preview window created. Press 'q' to quit.")
			
			# Camera is not auto-started - must be started explicitly via D-Bus or CLI
			frame_count = 0
			last_log_time = time.time()
			
			while True:
				# Check if camera is active
				if not self.camera_active:
					# Send a black frame when camera is off
					if self.virtual_cam is not None:
						black_frame = np.zeros((self.height, self.width, 3), dtype=np.uint8)
						frame_rgb = cv2.cvtColor(black_frame, cv2.COLOR_BGR2RGB)
						try:
							self.virtual_cam.send(frame_rgb.tobytes())
							self.virtual_cam.sleep_until_next_frame()
						except Exception as e:
							logger.error(f"Error sending black frame to virtual camera: {e}", exc_info=True)
					
					if preview:
						display_frame = np.zeros((480, 640, 3), dtype=np.uint8)
						cv2.putText(display_frame, "Camera inactive (explicitly off)", 
						           (10, 240), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
						cv2.imshow('camfx preview', display_frame)
						key = cv2.waitKey(1) & 0xFF
						if key == ord('q'):
							break
					
					time.sleep(0.1)  # Small delay when inactive
					continue
				
				# Camera is active, process frames
				if self.cap is None:
					self.camera_active = False
					time.sleep(0.1)
					continue
				
				ret, frame = self.cap.read()
				if not ret or frame is None:
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
						if kwargs.get('face_only', False):
							needs_mask = True
							break
				
				# Initialize segmenter if needed
				if needs_mask and self.segmenter is None:
					self.segmenter = PersonSegmenter()
				
				# Get mask if needed
				mask = self.segmenter.get_mask(frame) if needs_mask else None
				
				# Apply effect chain
				processed = chain.apply(frame, mask, **kwargs)
				
				# Send to virtual camera
				if self.virtual_cam is not None:
					try:
						frame_rgb = cv2.cvtColor(processed, cv2.COLOR_BGR2RGB)
						self.virtual_cam.send(frame_rgb.tobytes())
						self.virtual_cam.sleep_until_next_frame()
					except Exception as e:
						logger.error(f"Error sending frame to virtual camera: {e}", exc_info=True)
				
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
			if self.dbus_service:
				self.dbus_service.stop()
			if self.virtual_cam is not None:
				self.virtual_cam.cleanup()
			try:
				cv2.destroyAllWindows()
			except Exception:
				pass


