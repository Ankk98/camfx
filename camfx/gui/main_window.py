"""Main window for camfx control panel."""

from typing import Optional, Dict, Any
import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Gdk', '4.0')
gi.require_version('GLib', '2.0')
from gi.repository import Gtk, Gdk, GLib
from .dbus_client import CamfxDBusClient
from .preview_widget import PreviewWidget
from .effect_chain_widget import EffectChainWidget
from .effect_controls import EffectControlsWidget


class CamfxMainWindow(Gtk.ApplicationWindow):
	"""Main window for camfx control panel."""
	
	def __init__(self, app: Gtk.Application):
		"""Initialize main window.
		
		Args:
			app: GTK Application instance
		"""
		super().__init__(application=app, title="camfx Control Panel")
		self.set_default_size(1200, 800)
		
		# Initialize connection state
		self.dbus_client = None
		self.connected = False
		
		# Try to connect to D-Bus service (non-blocking, don't fail if unavailable)
		try:
			self.dbus_client = CamfxDBusClient()
			self.dbus_client.connect_signals(
				on_effect_changed=self._on_effect_changed,
				on_camera_state_changed=self._on_camera_state_changed
			)
			self.connected = True
		except Exception as e:
			# Don't fail if D-Bus is not available - show warning in UI
			self.dbus_client = None
			self.connected = False
			print(f"Warning: Could not connect to camfx service: {e}")
			print("The GUI will still open, but you'll need to start camfx with --dbus to use it.")
		
		# Current selected effect
		self.selected_effect_type: Optional[str] = None
		self.selected_effect_config: Optional[Dict[str, Any]] = None
		
		# Build UI
		try:
			self._build_ui()
		except Exception as e:
			import traceback
			traceback.print_exc()
			raise
		
		# Start preview (non-blocking, don't fail if preview unavailable)
		if hasattr(self, 'preview_widget'):
			try:
				self.preview_widget.start_preview()
			except Exception as e:
				print(f"Warning: Could not start preview: {e}")
	
	def _build_ui(self):
		"""Build the user interface."""
		# Main container
		main_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
		main_box.set_margin_start(10)
		main_box.set_margin_end(10)
		main_box.set_margin_top(10)
		main_box.set_margin_bottom(10)
		self.set_child(main_box)
		
		# Left pane: Preview
		preview_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
		preview_box.set_size_request(640, 480)
		
		preview_label = Gtk.Label()
		preview_label.set_markup("<b>Live Preview</b>")
		preview_label.set_xalign(0)
		preview_box.append(preview_label)
		
		# Create a frame/border for the preview
		preview_frame = Gtk.Frame()
		preview_frame.set_margin_start(5)
		preview_frame.set_margin_end(5)
		preview_frame.set_margin_top(5)
		preview_frame.set_margin_bottom(5)
		
		self.preview_widget = PreviewWidget(source_name="camfx")
		preview_frame.set_child(self.preview_widget)
		preview_box.append(preview_frame)
		
		# Camera control buttons
		camera_control_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
		
		self.camera_toggle = Gtk.ToggleButton(label="Camera: OFF")
		self.camera_toggle.connect('toggled', self._on_camera_toggled)
		camera_control_box.append(self.camera_toggle)
		
		self.preview_toggle = Gtk.ToggleButton(label="Preview: ON")
		self.preview_toggle.set_active(True)
		self.preview_toggle.connect('toggled', self._on_preview_toggled)
		camera_control_box.append(self.preview_toggle)
		
		preview_box.append(camera_control_box)
		
		# Connection status
		if self.connected:
			self.status_label = Gtk.Label(label="Status: Connected")
			self.status_label.add_css_class("success")
			# Get initial camera state
			try:
				camera_active = self.dbus_client.get_camera_state()
				self.camera_toggle.set_active(camera_active)
				self.camera_toggle.set_label("Camera: ON" if camera_active else "Camera: OFF")
			except Exception:
				pass
		else:
			self.status_label = Gtk.Label(label="Status: Not connected - Start camfx with --dbus")
			self.status_label.add_css_class("error")
			self.camera_toggle.set_sensitive(False)
		self.status_label.set_xalign(0)
		preview_box.append(self.status_label)
		
		main_box.append(preview_box)
		
		# Right pane: Controls
		control_pane = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
		control_pane.set_hexpand(True)
		
		# Effect chain widget
		if self.connected:
			self.effect_chain = EffectChainWidget(
				self.dbus_client,
				on_effect_selected=self._on_effect_selected
			)
		else:
			# Show error message if not connected
			self.effect_chain = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
			error_label = Gtk.Label(label="Cannot connect to camfx service.\nPlease start camfx with --dbus flag.")
			error_label.set_wrap(True)
			error_label.add_css_class("error")
			self.effect_chain.append(error_label)
		
		control_pane.append(self.effect_chain)
		
		# Separator
		separator = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
		control_pane.append(separator)
		
		# Effect parameter controls
		self.effect_controls = EffectControlsWidget(
			on_update=self._on_parameter_update,
			on_apply=self._on_apply_changes,
			application=self.get_application()
		)
		control_pane.append(self.effect_controls)
		
		main_box.append(control_pane)
	
	def _on_effect_selected(self, effect_type: str, config: Dict[str, Any]):
		"""Handle effect selection from chain widget.
		
		Args:
			effect_type: Selected effect type
			config: Effect configuration
		"""
		self.selected_effect_type = effect_type
		self.selected_effect_config = config
		self.effect_controls.update_effect(effect_type, config)
	
	def _on_parameter_update(self, effect_type: str, parameter: str, value: Any):
		"""Handle parameter update from controls.
		
		Args:
			effect_type: Effect type
			parameter: Parameter name
			value: New parameter value
		"""
		if not self.connected or not self.dbus_client:
			return
		
		try:
			# Update parameter via D-Bus
			success = self.dbus_client.update_effect_parameter(effect_type, parameter, value)
			if success:
				# Update local config
				if self.selected_effect_config is not None:
					self.selected_effect_config[parameter] = value
			else:
				self._show_error("Failed to update parameter")
		except Exception as e:
			self._show_error(f"Error updating parameter: {e}")
	
	def _on_apply_changes(self):
		"""Handle Apply Changes button click - refresh effect chain display."""
		if hasattr(self, 'effect_chain') and isinstance(self.effect_chain, EffectChainWidget):
			# Refresh the effect chain to show updated parameter values
			self.effect_chain.refresh()
	
	def _on_effect_changed(self, action: str, effect_type: str, config: Dict[str, Any]):
		"""Handle effect change signal from D-Bus.
		
		Args:
			action: Action taken ('set', 'add', 'remove', 'clear', 'update')
			effect_type: Effect type
			config: Effect configuration
		"""
		# Refresh effect chain display
		if hasattr(self, 'effect_chain') and isinstance(self.effect_chain, EffectChainWidget):
			GLib.idle_add(self.effect_chain.refresh)
		
		# If this is the selected effect, update controls
		if self.selected_effect_type == effect_type:
			GLib.idle_add(self.effect_controls.update_effect, effect_type, config)
	
	def _on_camera_state_changed(self, is_active: bool):
		"""Handle camera state change signal from D-Bus.
		
		Args:
			is_active: True if camera is active
		"""
		# Update toggle button state (without triggering the callback)
		GLib.idle_add(self._update_camera_toggle, is_active)
	
	def _update_camera_toggle(self, is_active: bool):
		"""Update camera toggle button state without triggering callback."""
		self.camera_toggle.handler_block_by_func(self._on_camera_toggled)
		self.camera_toggle.set_active(is_active)
		self.camera_toggle.set_label("Camera: ON" if is_active else "Camera: OFF")
		self.camera_toggle.handler_unblock_by_func(self._on_camera_toggled)
	
	def _on_camera_toggled(self, button: Gtk.ToggleButton):
		"""Handle camera toggle button click.
		
		Args:
			button: The toggle button
		"""
		if not self.connected or not self.dbus_client:
			return
		
		is_active = button.get_active()
		try:
			if is_active:
				success = self.dbus_client.start_camera()
				if success:
					button.set_label("Camera: ON")
				else:
					button.set_active(False)
					self._show_error("Failed to start camera")
			else:
				success = self.dbus_client.stop_camera()
				if success:
					button.set_label("Camera: OFF")
				else:
					button.set_active(True)
					self._show_error("Failed to stop camera")
		except Exception as e:
			# Revert toggle state on error
			button.set_active(not button.get_active())
			button.set_label("Camera: ON" if button.get_active() else "Camera: OFF")
			self._show_error(f"Error controlling camera: {e}")
	
	def _on_preview_toggled(self, button: Gtk.ToggleButton):
		"""Handle preview toggle button click.
		
		Args:
			button: The toggle button
		"""
		is_active = button.get_active()
		try:
			if is_active:
				if hasattr(self, 'preview_widget'):
					self.preview_widget.start_preview()
				button.set_label("Preview: ON")
			else:
				if hasattr(self, 'preview_widget'):
					self.preview_widget.stop_preview()
				button.set_label("Preview: OFF")
		except Exception as e:
			# Revert toggle state on error
			button.set_active(not is_active)
			button.set_label("Preview: ON" if button.get_active() else "Preview: OFF")
			self._show_error(f"Error toggling preview: {e}")
	
	def _show_error(self, message: str):
		"""Show error message dialog."""
		dialog = Gtk.MessageDialog(
			transient_for=self,
			message_type=Gtk.MessageType.ERROR,
			buttons=Gtk.ButtonsType.OK,
			text="Error"
		)
		# In GTK4, use get_message_area() to add secondary text
		message_area = dialog.get_message_area()
		secondary_label = Gtk.Label(label=message)
		secondary_label.set_wrap(True)
		message_area.append(secondary_label)
		dialog.connect("response", lambda d, r: d.destroy())
		dialog.show()
	
	def do_close_request(self):
		"""Handle window close request."""
		# Stop preview
		if hasattr(self, 'preview_widget'):
			self.preview_widget.stop_preview()
		# Quit the application
		app = self.get_application()
		if app:
			app.quit()
		return False  # Allow window to close


class CamfxApplication(Gtk.Application):
	"""GTK Application for camfx control panel."""
	
	def __init__(self):
		"""Initialize application."""
		# Use FLAGS_NONE to avoid file handling issues
		# We don't need HANDLES_OPEN since we're not opening files from command line
		# Use a fixed application ID
		# Note: If you want to allow multiple instances, use a unique ID
		super().__init__(application_id="org.camfx.ControlPanel", flags=0)
		self.window: Optional[CamfxMainWindow] = None
	
	def do_activate(self):
		"""Activate application."""
		if self.window is None:
			try:
				self.window = CamfxMainWindow(self)
				self.window.present()
			except Exception as e:
				import traceback
				traceback.print_exc()
				# Show error dialog
				try:
					dialog = Gtk.MessageDialog(
						transient_for=None,
						message_type=Gtk.MessageType.ERROR,
						buttons=Gtk.ButtonsType.OK,
						text="Failed to start camfx GUI"
					)
					# In GTK4, use get_message_area() to add secondary text
					message_area = dialog.get_message_area()
					secondary_label = Gtk.Label(label=str(e))
					secondary_label.set_wrap(True)
					message_area.append(secondary_label)
					dialog.connect("response", lambda d, r: (d.destroy(), self.quit()))
					dialog.show()
				except Exception:
					self.quit()
		else:
			self.window.present()


def main():
	"""Main entry point for GUI application."""
	# Check for display
	import os
	display = os.environ.get('DISPLAY') or os.environ.get('WAYLAND_DISPLAY')
	if not display:
		print("Error: No display available. Make sure you're running in a graphical environment.", file=sys.stderr)
		return 1
	
	# Suppress the GLib-GIO-CRITICAL warning (known GTK4 false positive)
	os.environ.setdefault('G_MESSAGES_DEBUG', '')
	
	try:
		app = CamfxApplication()
		
		# Run the application - this will call do_activate automatically
		# Note: app.run() blocks until the application quits
		try:
			# Register the application first
			register_result = app.register()
			
			if not register_result:
				return 1
			
			# Check if app is already running (single-instance)
			is_remote = app.get_is_remote()
			
			if is_remote:
				app.activate()
				return 0
			
			# Activate the application (this will call do_activate)
			app.activate()
			
			# Run the main loop
			from gi.repository import GLib
			main_loop = GLib.MainLoop()
			
			# Connect quit signal to exit main loop
			def on_quit(app):
				main_loop.quit()
			
			app.connect("shutdown", on_quit)
			
			main_loop.run()
			
			return 0
		except Exception as run_error:
			import traceback
			traceback.print_exc()
			return 1
	except KeyboardInterrupt:
		return 0
	except Exception as e:
		import traceback
		traceback.print_exc()
		return 1


if __name__ == '__main__':
	main()

