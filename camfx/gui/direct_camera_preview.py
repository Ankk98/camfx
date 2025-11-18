"""Direct camera preview widget (physical camera feed)."""

import threading
import time
from typing import Optional

import cv2
import gi
from gi.repository import Gtk, GdkPixbuf, GLib

import numpy as np

from ..camera_devices import list_camera_devices

import logging

logger = logging.getLogger('camfx.gui.direct_preview')


class DirectCameraPreview(Gtk.Box):
	"""Widget to preview the physical camera directly."""
	
	def __init__(self):
		super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=6)
		self.picture = Gtk.Picture()
		self.picture.set_content_fit(Gtk.ContentFit.CONTAIN)
		self.picture.set_hexpand(True)
		self.picture.set_vexpand(True)
		self.append(self.picture)
		
		self.status_label = Gtk.Label(label="Preview: Camera is OFF")
		self.status_label.set_xalign(0)
		self.append(self.status_label)
		
		self._thread: Optional[threading.Thread] = None
		self._running = False
		self._lock = threading.Lock()
		self._capture: Optional[cv2.VideoCapture] = None
		self._current_config: Optional[dict] = None
	
	def set_camera_config(self, config: dict):
		"""Update camera configuration used for preview."""
		self._current_config = config
		if not config:
			self._update_status("Preview: No camera selected")
			if self._running:
				self.stop_preview()
			return
		if self._running:
			self.restart_preview()
	
	def is_running(self) -> bool:
		return self._running
	
	def start_preview(self):
		if self._running:
			logger.debug("Direct preview already running")
			return
		if not self._current_config:
			self._update_status("Preview: No camera selected")
			return
		
		self._running = True
		self._thread = threading.Thread(target=self._preview_loop, daemon=True)
		self._thread.start()
	
	def stop_preview(self):
		if not self._running:
			return
		logger.info("Stopping direct preview")
		self._running = False
		if self._thread:
			self._thread.join(timeout=2.0)
		self._thread = None
		self._release_capture()
		self._update_status("Preview: Camera is OFF")
		self.picture.set_pixbuf(None)
	
	def restart_preview(self):
		self.stop_preview()
		self.start_preview()
	
	def _open_capture(self) -> Optional[cv2.VideoCapture]:
		config = self._current_config or {}
		source = config.get('source_id')
		if not source:
			return None
		
		cap = None
		# Try numeric index first
		if source.startswith('/dev/video'):
			try:
				index = int(source.replace('/dev/video', ''))
			except ValueError:
				index = None
		elif source.isdigit():
			index = int(source)
		else:
			index = None
		
		if index is not None:
			cap = cv2.VideoCapture(index)
			if cap and not cap.isOpened():
				cap.release()
				cap = None
		
		if cap is None:
			cap = cv2.VideoCapture(source)
		
		if not cap or not cap.isOpened():
			if cap:
				cap.release()
			return None
		
		width = config.get('width')
		height = config.get('height')
		fps = config.get('fps')
		if width:
			cap.set(cv2.CAP_PROP_FRAME_WIDTH, int(width))
		if height:
			cap.set(cv2.CAP_PROP_FRAME_HEIGHT, int(height))
		if fps:
			cap.set(cv2.CAP_PROP_FPS, int(fps))
		return cap
	
	def _preview_loop(self):
		self._update_status("Preview: Connecting…")
		cap = self._open_capture()
		if cap is None:
			self._update_status("Preview: Unable to open camera")
			self._running = False
			return
		
		with self._lock:
			self._capture = cap
		
		self._update_status("Preview: Running")
		
		while self._running:
			ret, frame = cap.read()
			if not ret or frame is None:
				time.sleep(0.05)
				continue
			
			GLib.idle_add(self._update_frame, frame.copy())
		
		self._release_capture()
	
	def _release_capture(self):
		with self._lock:
			if self._capture:
				self._capture.release()
			self._capture = None
	
	def _update_frame(self, frame: np.ndarray):
		if frame is None:
			return
		try:
			frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
			if not frame_rgb.flags['C_CONTIGUOUS']:
				frame_rgb = np.ascontiguousarray(frame_rgb)
			height, width = frame_rgb.shape[:2]
			pixbuf = GdkPixbuf.Pixbuf.new_from_data(
				frame_rgb.tobytes(),
				GdkPixbuf.Colorspace.RGB,
				False,
				8,
				width,
				height,
				width * 3
			)
			self.picture.set_pixbuf(pixbuf)
		except Exception as exc:
			logger.error("Error updating direct preview frame: %s", exc, exc_info=True)
	
	def _update_status(self, message: str):
		GLib.idle_add(self.status_label.set_text, message)

