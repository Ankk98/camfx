"""Preview widget for displaying live camera feed."""

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

try:
	from ..input_pipewire import PipeWireInput
	PIPEWIRE_AVAILABLE = True
except ImportError:
	PIPEWIRE_AVAILABLE = False


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
		
		# Status label
		self.status_label = Gtk.Label(label="Status: Not connected")
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
			return
		
		self.running = True
		self.preview_thread = threading.Thread(target=self._preview_loop, daemon=True)
		self.preview_thread.start()
	
	def stop_preview(self):
		"""Stop preview thread."""
		self.running = False
		if self.preview_thread:
			self.preview_thread.join(timeout=2.0)
		if self.pipewire_input:
			self.pipewire_input.release()
			self.pipewire_input = None
	
	def _preview_loop(self):
		"""Preview loop running in separate thread."""
		# Try to connect to PipeWire source
		if PIPEWIRE_AVAILABLE:
			try:
				self.pipewire_input = PipeWireInput(source_name=self.source_name)
				GLib.idle_add(self._update_status, "Status: Connected")
			except RuntimeError as e:
				error_msg = f"Status: {str(e)}"
				GLib.idle_add(self._update_status, error_msg)
				self.running = False
				return
			except Exception as e:
				error_msg = f"Status: Error - {str(e)}"
				GLib.idle_add(self._update_status, error_msg)
				self.running = False
				return
		else:
			GLib.idle_add(self._update_status, "Status: PipeWire not available")
			self.running = False
			return
		
		# Main preview loop
		frame_count = 0
		last_fps_time = time.time()
		no_frame_count = 0
		
		while self.running:
			if self.pipewire_input:
				try:
					ret, frame = self.pipewire_input.read()
					if ret and frame is not None:
						self.current_frame = frame
						GLib.idle_add(self._update_frame, frame)
						
						# Update FPS counter (rough estimate)
						frame_count += 1
						no_frame_count = 0
						if time.time() - last_fps_time >= 1.0:
							fps = frame_count
							frame_count = 0
							last_fps_time = time.time()
							GLib.idle_add(self._update_status, f"Status: Connected ({fps} FPS)")
					else:
						no_frame_count += 1
						if no_frame_count > 100:  # ~1 second at 10ms intervals
							no_frame_count = 0
						time.sleep(0.01)  # Small delay if no frame available
				except Exception:
					time.sleep(0.1)
			else:
				break
		
		# Cleanup
		if self.pipewire_input:
			try:
				self.pipewire_input.release()
			except Exception:
				pass
			self.pipewire_input = None
	
	def _update_frame(self, frame: np.ndarray):
		"""Update picture widget with new frame (called from main thread)."""
		if not self.running:
			return
		
		try:
			# Convert numpy array to GdkPixbuf
			height, width = frame.shape[:2]
			
			# Validate frame dimensions
			if width <= 0 or height <= 0:
				print(f"Invalid frame dimensions: {width}x{height}", file=sys.stderr)
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
			print(f"Error updating frame: {e}", file=sys.stderr)
			import traceback
			traceback.print_exc()
	
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

