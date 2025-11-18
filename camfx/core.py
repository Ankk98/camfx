import logging
import os
import threading
import cv2
import numpy as np
import time
from typing import Dict, List, Optional

from .camera_devices import list_camera_devices, probe_camera_modes
from .segmentation import PersonSegmenter
from .output_pipewire import PipeWireOutput
from .control import EffectController

logger = logging.getLogger('camfx.core')


class VideoEnhancer:
	def __init__(self, input_device: int = 0, effect_type: str = 'blur', config: dict | None = None) -> None:
		self.input_device = input_device
		self.config = config or {}
		self.camera_lock = threading.RLock()
		self.camera_source_id = self._normalize_source_id(input_device)
		self.camera_source_index = self._source_id_to_index(self.camera_source_id)
		self._capability_cache: Dict[str, List[Dict[str, object]]] = {}
		self._last_camera_state_log = 0.0
		self._last_inactive_log = 0.0
		self._last_frame_failure_log = 0.0
		self._last_black_frame_log = 0.0
		self._last_virtual_send_log = 0.0
		self._virtual_frames_sent = 0
		self._black_frames_sent = 0
		self._last_effect_chain_signature: Optional[str] = None
		self._virtual_warning_logged = False
		
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
		self.camera_name = self.config.get('camera_name', 'camfx')
		
		# Use config dimensions or defaults
		target_width = self.config.get('width')
		target_height = self.config.get('height')
		self.width = target_width or 640
		self.height = target_height or 480
		print("Camera is off by default. Use D-Bus or CLI to start it.")
		self._log_checkpoint(
			'init',
			source=self.camera_source_id,
			source_index=self.camera_source_index,
			width=self.width,
			height=self.height,
			target_fps=self.target_fps,
			enable_virtual=self.enable_virtual,
			camera_name=self.camera_name,
		)
		
		# Virtual camera output via PipeWire (always initialize, even if camera not active)
		self.virtual_cam = None
		self._create_virtual_output()
		
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
	
	def _log_checkpoint(self, stage: str, level: int = logging.INFO, **details) -> None:
		"""Emit structured log lines that act as debugging checkpoints."""
		if not logger.isEnabledFor(level):
			return
		payload = " ".join(f"{key}={value!r}" for key, value in details.items())
		if payload:
			logger.log(level, "[checkpoint:%s] %s", stage, payload)
		else:
			logger.log(level, "[checkpoint:%s]", stage)
	
	def _start_camera(self):
		"""Start camera capture."""
		with self.camera_lock:
			if self.cap is not None:
				logger.debug("Camera start requested but capture is already active")
				return  # Already started
			
			self._log_checkpoint(
				'camera.start.request',
				source_id=self.camera_source_id,
				source_index=self.camera_source_index,
				requested_width=self.config.get('width'),
				requested_height=self.config.get('height'),
			)
			self.cap = self._open_capture_for_source()
			if self.cap is None or not self.cap.isOpened():
				if self.cap:
					self.cap.release()
				self.cap = None
				self.camera_active = False
				logger.error("Failed to open camera source %s", self.camera_source_id)
				self._log_checkpoint(
					'camera.start.failed',
					level=logging.ERROR,
					source_id=self.camera_source_id,
				)
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
			self._last_camera_state_log = time.time()
			self._log_checkpoint(
				'camera.start.success',
				actual_width=self.width,
				actual_height=self.height,
				fps=self.target_fps,
			)
	
	def _stop_camera(self):
		"""Stop camera capture."""
		with self.camera_lock:
			if self.cap is None:
				self.camera_active = False
				logger.debug("Camera stop requested but capture already released")
				return
			
			self._log_checkpoint('camera.stop.request')
			self.cap.release()
			self.cap = None
			self.camera_active = False
			self._last_camera_state_log = time.time()
			self._log_checkpoint('camera.stop.success')
	
	def _open_capture_for_source(self) -> Optional[cv2.VideoCapture]:
		"""Create a VideoCapture for the current source."""
		if self.camera_source_index is not None:
			logger.debug("Attempting to open camera index %s", self.camera_source_index)
			cap = cv2.VideoCapture(self.camera_source_index)
			if cap and cap.isOpened():
				logger.debug("Successfully opened camera index %s", self.camera_source_index)
				return cap
			if cap:
				logger.debug("Failed to open camera index %s", self.camera_source_index)
				cap.release()
		
		logger.debug("Attempting to open camera source %s", self.camera_source_id)
		cap = cv2.VideoCapture(self.camera_source_id)
		if cap and cap.isOpened():
			logger.debug("Successfully opened camera source %s", self.camera_source_id)
			return cap
		if cap:
			logger.debug("Failed to open camera source %s", self.camera_source_id)
			cap.release()
		return None
	
	def _create_virtual_output(self):
		"""Initialize virtual camera output with current dimensions."""
		if not self.enable_virtual:
			logger.info("Virtual camera output disabled via configuration")
			return
		
		try:
			self._log_checkpoint(
				'virtual.create.attempt',
				width=self.width,
				height=self.height,
				fps=self.target_fps,
				name=self.camera_name,
			)
			print(f"Initializing PipeWire virtual camera ({self.width}x{self.height} @ {self.target_fps}fps)...")
			self.virtual_cam = PipeWireOutput(
				width=self.width,
				height=self.height,
				fps=self.target_fps,
				name=self.camera_name,
			)
			print("PipeWire virtual camera ready")
			self._log_checkpoint('virtual.create.success', name=self.camera_name)
			self._virtual_warning_logged = False
		except Exception as exc:
			print(f"Warning: Failed to initialize PipeWire virtual camera: {exc}")
			print("Continuing with preview only. To enable virtual camera:")
			print("  1. Ensure PipeWire is running: systemctl --user status pipewire")
			print("  2. Ensure wireplumber is running: systemctl --user start wireplumber")
			print("  3. Or use --no-virtual to skip virtual camera initialization")
			self.virtual_cam = None
			self._log_checkpoint(
				'virtual.create.failed',
				level=logging.ERROR,
				error=str(exc),
			)
			logger.error("Failed to initialize virtual camera", exc_info=True)
	
	def _cleanup_virtual_output(self):
		"""Release existing virtual camera pipeline."""
		if self.virtual_cam is None:
			return
		try:
			self._log_checkpoint('virtual.cleanup')
			self.virtual_cam.cleanup()
		except Exception as exc:
			logger.error(f"Error cleaning up virtual camera: {exc}", exc_info=True)
		finally:
			self.virtual_cam = None
	
	def _recreate_virtual_output(self):
		"""Recreate virtual camera pipeline with new dimensions."""
		if not self.enable_virtual:
			return
		self._log_checkpoint('virtual.recreate')
		old_virtual = self.virtual_cam
		self.virtual_cam = None
		if old_virtual:
			try:
				old_virtual.cleanup()
			except Exception as exc:
				logger.error(f"Error cleaning up virtual camera: {exc}", exc_info=True)
		self._create_virtual_output()
	
	def list_camera_sources(self) -> List[Dict[str, str]]:
		"""Return available camera sources for selection."""
		devices = list_camera_devices()
		return [{'id': device.id, 'label': device.label} for device in devices]
	
	def get_camera_modes(self, source_id: str) -> List[Dict[str, object]]:
		"""Return cached or probed modes for a camera source."""
		if source_id in self._capability_cache:
			return self._capability_cache[source_id]
		modes = probe_camera_modes(source_id)
		self._capability_cache[source_id] = modes
		return modes
	
	def get_camera_config(self) -> Dict[str, int | str]:
		"""Return current camera configuration."""
		return {
			'source_id': self.camera_source_id,
			'width': int(self.width),
			'height': int(self.height),
			'fps': int(self.target_fps),
		}
	
	def apply_camera_config(self, source_id: str, width: int, height: int, fps: int) -> bool:
		"""Apply a new camera configuration."""
		with self.camera_lock:
			self._log_checkpoint(
				'camera.config.apply',
				source_id=source_id,
				width=width,
				height=height,
				fps=fps,
			)
			restart_camera = self.camera_active
			self._stop_camera()
			self.camera_source_id = self._normalize_source_id(source_id)
			self.camera_source_index = self._source_id_to_index(self.camera_source_id)
			self.config['width'] = width
			self.config['height'] = height
			self.config['fps'] = fps
			self.width = width
			self.height = height
			self.target_fps = fps
			self._recreate_virtual_output()
			if restart_camera:
				self._start_camera()
			self._log_checkpoint(
				'camera.config.applied',
				restarted=restart_camera,
				source_id=self.camera_source_id,
				width=self.width,
				height=self.height,
				fps=self.target_fps,
			)
		return True
	
	def _normalize_source_id(self, source: int | str) -> str:
		"""Convert different source declarations into a canonical /dev path."""
		if isinstance(source, str):
			if source.startswith('/dev/'):
				return source
			if source.isdigit():
				return f"/dev/video{source}"
			return source
		return f"/dev/video{source}"
	
	def _source_id_to_index(self, source_id: str) -> Optional[int]:
		"""Extract numeric index from /dev/video style identifiers."""
		basename = os.path.basename(str(source_id))
		if basename.startswith('video'):
			try:
				return int(basename.replace('video', ''))
			except ValueError:
				return None
		if basename.isdigit():
			return int(basename)
		try:
			return int(source_id)
		except ValueError:
			return None
	
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
			self._log_checkpoint('loop.start', preview=preview)
			frame_count = 0
			frames_since_log = 0
			last_log_time = time.time()
			
			while True:
				if self.virtual_cam is None and self.enable_virtual and not self._virtual_warning_logged:
					logger.warning("Virtual camera enabled but not initialized; frames will not be sent")
					self._log_checkpoint('virtual.unavailable', level=logging.WARNING)
					self._virtual_warning_logged = True
				elif self.virtual_cam is not None and self._virtual_warning_logged:
					self._virtual_warning_logged = False
					self._log_checkpoint('virtual.available')
				
				# Check if camera is active
				if not self.camera_active:
					now = time.time()
					if now - self._last_inactive_log >= 5.0:
						self._log_checkpoint(
							'camera.inactive',
							virtual_ready=bool(self.virtual_cam),
							reason='camera_off',
						)
						self._last_inactive_log = now
					# Send a black frame when camera is off
					if self.virtual_cam is not None:
						black_frame = np.zeros((self.height, self.width, 3), dtype=np.uint8)
						frame_rgb = cv2.cvtColor(black_frame, cv2.COLOR_BGR2RGB)
						try:
							self.virtual_cam.send(frame_rgb.tobytes())
							self.virtual_cam.sleep_until_next_frame()
							self._black_frames_sent += 1
							if self._black_frames_sent == 1 or now - self._last_black_frame_log >= 5.0:
								self._log_checkpoint(
									'virtual.black_frame',
									total=self._black_frames_sent,
									resolution=f"{self.width}x{self.height}",
								)
								self._last_black_frame_log = now
						except Exception as e:
							logger.error(f"Error sending black frame to virtual camera: {e}", exc_info=True)
							self._log_checkpoint(
								'virtual.black_frame.error',
								level=logging.ERROR,
								error=str(e),
							)
					
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
					logger.warning("Camera marked active but VideoCapture handle is None; restarting soon")
					time.sleep(0.1)
					continue
				
				ret, frame = self.cap.read()
				if not ret or frame is None:
					now = time.time()
					if now - self._last_frame_failure_log >= 2.0:
						logger.warning("Camera read returned no frame (ret=%s); backing off briefly", ret)
						self._log_checkpoint(
							'camera.frame.empty',
							level=logging.WARNING,
							ret=ret,
						)
						self._last_frame_failure_log = now
					time.sleep(0.1)
					continue
				
				# Get effect chain
				chain = self.effect_controller.get_chain()
				chain_signature = ",".join(effect.__class__.__name__ for effect, _ in chain.effects) or "none"
				if chain_signature != self._last_effect_chain_signature:
					self._log_checkpoint(
						'effects.chain',
						chain=chain_signature,
						length=len(chain.effects),
					)
					self._last_effect_chain_signature = chain_signature
				
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
					self._log_checkpoint('segmenter.init', reason='mask_required')
					self.segmenter = PersonSegmenter()
				
				# Get mask if needed
				mask = self.segmenter.get_mask(frame) if needs_mask else None
				
				# Apply effect chain
				try:
					processed = chain.apply(frame, mask, **kwargs)
				except Exception as effect_error:
					logger.error("Effect chain processing failed: %s", effect_error, exc_info=True)
					self._log_checkpoint(
						'effects.apply.failed',
						level=logging.ERROR,
						error=str(effect_error),
					)
					processed = frame
				
				# Send to virtual camera
				if self.virtual_cam is not None:
					try:
						frame_rgb = cv2.cvtColor(processed, cv2.COLOR_BGR2RGB)
						self.virtual_cam.send(frame_rgb.tobytes())
						self.virtual_cam.sleep_until_next_frame()
						self._virtual_frames_sent += 1
						now = time.time()
						if self._virtual_frames_sent == 1 or now - self._last_virtual_send_log >= 5.0:
							self._log_checkpoint(
								'virtual.send',
								total=self._virtual_frames_sent,
								resolution=f"{self.width}x{self.height}",
								camera_active=self.camera_active,
							)
							self._last_virtual_send_log = now
					except Exception as e:
						logger.error(f"Error sending frame to virtual camera: {e}", exc_info=True)
						self._log_checkpoint(
							'virtual.send.failed',
							level=logging.ERROR,
							error=str(e),
						)
				
				# Show preview
				if preview:
					cv2.imshow('camfx preview', processed)
					key = cv2.waitKey(1) & 0xFF
					if key == ord('q'):
						break
				
				frame_count += 1
				frames_since_log += 1
				if frame_count == 1:
					print(f"Processing frames... (Press 'q' in preview window to quit)")
					self._log_checkpoint('loop.first_frame')
				
				now = time.time()
				if now - last_log_time >= 10.0:
					elapsed = now - last_log_time
					fps = frames_since_log / (elapsed if elapsed > 0 else 1)
					self._log_checkpoint(
						'loop.fps',
						fps=f"{fps:.2f}",
						virtual_frames=self._virtual_frames_sent,
						camera_active=self.camera_active,
					)
					frames_since_log = 0
					last_log_time = now
		
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


