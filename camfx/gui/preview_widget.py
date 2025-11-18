"""Preview widget for displaying live camera feed."""

import logging
import sys
import threading
import time
import numpy as np
import cv2
from typing import Optional
import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Gdk', '4.0')
gi.require_version('GdkPixbuf', '2.0')
gi.require_version('GLib', '2.0')
from gi.repository import Gtk, Gdk, GdkPixbuf, GLib

logger = logging.getLogger('camfx.gui.preview')

try:
	from ..input_pipewire import PipeWireInput
	PIPEWIRE_AVAILABLE = True
	logger.debug("PipeWireInput available")
except ImportError as e:
	PIPEWIRE_AVAILABLE = False
	logger.warning(f"PipeWireInput not available: {e}")


class PreviewWidget(Gtk.Box):
	"""Widget showing live preview from camfx virtual camera."""
	
	def __init__(self, source_name: str = "camfx"):
		"""Initialize preview widget.
		
		Args:
			source_name: Name of PipeWire source to preview
		"""
		super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=10)
		self.source_name = source_name
		self.pipewire_input: Optional[PipeWireInput] = None
		self.preview_thread: Optional[threading.Thread] = None
		self.running = False
		self.current_frame: Optional[np.ndarray] = None
		self._frame_log_interval = 1.0
		self._last_frame_log = 0.0
		self._ui_log_interval = 1.0
		self._last_ui_log = 0.0
		self._placeholder_displayed = False
		self._last_placeholder_reason: Optional[str] = None
		
		# Create picture widget for displaying frames
		self.picture = Gtk.Picture()
		self.picture.set_content_fit(Gtk.ContentFit.CONTAIN)
		self.picture.set_hexpand(True)
		self.picture.set_vexpand(True)
		# Set minimum size so preview area is visible
		self.picture.set_size_request(640, 480)
		# Set a background color so we can see the widget area
		self.picture.set_css_classes(["preview-picture"])
		self.append(self.picture)
		
		# Preview status label
		self.status_label = Gtk.Label(label="Preview: Not connected")
		self.status_label.set_margin_top(5)
		self.append(self.status_label)
		
		# Fullscreen button
		self.fullscreen_button = Gtk.Button(label="Fullscreen")
		self.fullscreen_button.connect("clicked", self._on_fullscreen_clicked)
		self.append(self.fullscreen_button)
		
		# Fullscreen window
		self.fullscreen_window: Optional[Gtk.Window] = None
	
	def start_preview(self):
		"""Start preview thread."""
		if self.running:
			logger.warning("Preview already running, ignoring start request")
			return
		
		logger.info(f"Starting preview for source '{self.source_name}'")
		self.running = True
		self.preview_thread = threading.Thread(target=self._preview_loop, daemon=True)
		self.preview_thread.start()
		logger.debug("Preview thread started")
		self._placeholder_displayed = False
		self._update_status("Preview: Connecting…")
	
	def stop_preview(self, reason: str | None = None):
		"""Stop preview thread."""
		if reason and self._last_placeholder_reason == reason and not self.running:
			self._show_placeholder(reason)
			return
		
		if self.running:
			if reason:
				logger.info("Stopping preview (%s)", reason)
			else:
				logger.info("Stopping preview")
		else:
			logger.info("Stopping preview (%s)", reason or "already stopped")
		
		self.running = False
		self._release_pipewire_input()
		if self.preview_thread:
			self.preview_thread.join(timeout=2.0)
			if self.preview_thread.is_alive():
				logger.warning("Preview thread did not stop within timeout")
				# Give thread a bit more time before detaching
				self.preview_thread.join(timeout=1.0)
				if self.preview_thread.is_alive():
					logger.error("Preview thread stuck; continuing shutdown")
			else:
				logger.debug("Preview thread stopped")
			self.preview_thread = None
		message = reason or "Preview: Not connected"
		self._show_placeholder(message)
		self._placeholder_displayed = True
		self._last_placeholder_reason = reason
	
	def restart_preview(self):
		"""Restart preview with current source."""
		logger.info("Restarting preview")
		self.stop_preview()
		self.start_preview()
	
	def is_running(self) -> bool:
		"""Return True if preview thread is active."""
		return self.running
	
	def show_camera_inactive_message(self):
		"""Display placeholder when camera is off."""
		self.stop_preview(reason="Camera is OFF")
	
	def show_preview_disabled_message(self):
		"""Display placeholder when preview toggle is off."""
		self.stop_preview(reason="Preview disabled")
	
	def _show_placeholder(self, message: str):
		"""Update UI with placeholder message and blank frame."""
		self._update_status(message)
		self.picture.set_pixbuf(None)
		self.current_frame = None
		self._placeholder_displayed = True
	
	def _preview_loop(self):
		"""Preview loop running in separate thread."""
		logger.debug("Preview loop thread started")
		
		# Try to connect to PipeWire source
		if PIPEWIRE_AVAILABLE:
			while self.running and self.pipewire_input is None:
				try:
					logger.info(f"Connecting to PipeWire source '{self.source_name}'")
					self.pipewire_input = PipeWireInput(source_name=self.source_name)
					logger.info("Successfully connected to PipeWire source")
					GLib.idle_add(self._update_status, "Preview: Connected")
				except RuntimeError as e:
					if not self.running:
						return
					logger.warning("Virtual camera busy: %s", e)
					GLib.idle_add(self._update_status, "Preview: Virtual camera busy, retrying…")
					self._release_pipewire_input()
					time.sleep(0.5)
				except Exception as e:
					logger.error(f"Exception connecting to PipeWire source: {e}", exc_info=True)
					error_msg = f"Preview: Error - {str(e)}"
					GLib.idle_add(self._update_status, error_msg)
					self.running = False
					return
				if not self.running:
					return
		else:
			logger.error("PipeWire not available")
			GLib.idle_add(self._update_status, "Preview: PipeWire not available")
			self.running = False
			return
		
		# Main preview loop
		frame_count = 0
		last_fps_time = time.time()
		no_frame_count = 0
		last_log_time = time.time()
		
		logger.info("Entering main preview loop")
		
		while self.running:
			if self.pipewire_input:
				try:
					ret, frame = self.pipewire_input.read()
					if ret and frame is not None:
						if self._should_log_debug('_last_frame_log', self._frame_log_interval):
							logger.debug("Frame received: shape=%s, dtype=%s", frame.shape, frame.dtype)
						self.current_frame = frame
						GLib.idle_add(self._update_frame, frame)
						
						# Update FPS counter (rough estimate)
						frame_count += 1
						no_frame_count = 0
						current_time = time.time()
						if current_time - last_fps_time >= 1.0:
							elapsed = current_time - last_fps_time
							fps = frame_count / elapsed if elapsed > 0 else 0.0
							frame_count = 0
							last_fps_time = current_time
							logger.debug(f"Preview FPS: {fps:.2f}")
							GLib.idle_add(self._update_status, f"Status: Connected ({fps:.2f} FPS)")
						
						# Log summary every 10 seconds
						if current_time - last_log_time >= 10.0:
							logger.info(f"Preview running: {fps} FPS, total frames processed")
							last_log_time = current_time
					else:
						no_frame_count += 1
						if no_frame_count == 1:
							logger.debug("No frame available from PipeWireInput")
						if no_frame_count > 100:  # ~1 second at 10ms intervals
							logger.warning("No frames received for ~1 second")
							no_frame_count = 0
						time.sleep(0.01)  # Small delay if no frame available
				except Exception as e:
					logger.error(f"Exception in preview loop: {e}", exc_info=True)
					time.sleep(0.1)
			else:
				logger.warning("pipewire_input is None, breaking loop")
				break
		
		# Cleanup
		logger.info("Exiting preview loop, cleaning up")
		self._release_pipewire_input()

	def _release_pipewire_input(self):
		if self.pipewire_input:
			try:
				self.pipewire_input.release()
				logger.debug("PipeWireInput released")
			except Exception as e:
				logger.error(f"Error releasing PipeWireInput: {e}", exc_info=True)
		self.pipewire_input = None
	
	def _update_frame(self, frame: np.ndarray):
		"""Update picture widget with new frame (called from main thread)."""
		if not self.running:
			return
		
		try:
			# Convert numpy array to GdkPixbuf
			height, width = frame.shape[:2]
			if self._should_log_debug('_last_ui_log', self._ui_log_interval):
				logger.debug("Updating frame: %sx%s", width, height)
			self._placeholder_displayed = False
			
			# Validate frame dimensions
			if width <= 0 or height <= 0:
				logger.error(f"Invalid frame dimensions: {width}x{height}")
				return
			
			# Convert BGR to RGB
			frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
			
			# Ensure frame is contiguous in memory
			if not frame_rgb.flags['C_CONTIGUOUS']:
				frame_rgb = np.ascontiguousarray(frame_rgb)
			
			# Create pixbuf
			pixbuf = GdkPixbuf.Pixbuf.new_from_data(
				frame_rgb.tobytes(),
				GdkPixbuf.Colorspace.RGB,
				False,
				8,
				width,
				height,
				width * 3
			)
			
			# Update picture widget
			self.picture.set_pixbuf(pixbuf)
			
			# Update fullscreen window if open
			if self.fullscreen_window:
				fullscreen_picture = self.fullscreen_window.get_child()
				if fullscreen_picture and isinstance(fullscreen_picture, Gtk.Picture):
					fullscreen_picture.set_pixbuf(pixbuf)
		
		except Exception as e:
			logger.error(f"Error updating frame: {e}", exc_info=True)
	
	def _update_status(self, status: str):
		"""Update status label (called from main thread)."""
		self.status_label.set_text(status)
	
	def _on_fullscreen_clicked(self, button: Gtk.Button):
		"""Handle fullscreen button click."""
		if self.fullscreen_window:
			# Close fullscreen window
			self.fullscreen_window.destroy()
			self.fullscreen_window = None
		else:
			# Open fullscreen window
			self.fullscreen_window = Gtk.Window()
			self.fullscreen_window.set_title("camfx Preview - Fullscreen")
			self.fullscreen_window.set_default_size(1280, 720)
			self.fullscreen_window.fullscreen()
			
			# Create picture widget for fullscreen
			fullscreen_picture = Gtk.Picture()
			fullscreen_picture.set_content_fit(Gtk.ContentFit.CONTAIN)
			self.fullscreen_window.set_child(fullscreen_picture)
			
			# Update with current frame if available
			if self.current_frame is not None:
				self._update_frame(self.current_frame)
			
			# Handle window close
			self.fullscreen_window.connect("close-request", self._on_fullscreen_close)
			self.fullscreen_window.present()
	
	def _on_fullscreen_close(self, window: Gtk.Window) -> bool:
		"""Handle fullscreen window close."""
		self.fullscreen_window = None
		return False
	
	def do_destroy(self):
		"""Cleanup on widget destruction."""
		self.stop_preview()
		if self.fullscreen_window:
			self.fullscreen_window.destroy()
			self.fullscreen_window = None

	def _should_log_debug(self, attr_name: str, interval: float) -> bool:
		"""Return True if a debug log should be emitted for the given attribute."""
		now = time.time()
		last = getattr(self, attr_name, 0.0)
		if now - last >= interval:
			setattr(self, attr_name, now)
			return True
		return False

