"""Main window for camfx control panel."""

from typing import Optional, Dict, Any, List
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
				on_camera_state_changed=self._on_camera_state_changed,
				on_camera_config_changed=self._on_camera_config_changed
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
		
		# Camera configuration state
		self.camera_sources: List[Dict[str, Any]] = []
		self.camera_modes_cache: Dict[str, List[Dict[str, Any]]] = {}
		self.current_camera_config: Optional[Dict[str, Any]] = None
		self._camera_controls_busy = False
		
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
		
		# D-Bus connection status
		if self.connected:
			self.status_label = Gtk.Label(label="D-Bus: Connected")
			self.status_label.add_css_class("success")
			# Get initial camera state
			try:
				camera_active = self.dbus_client.get_camera_state()
				self.camera_toggle.set_active(camera_active)
				self.camera_toggle.set_label("Camera: ON" if camera_active else "Camera: OFF")
			except Exception:
				pass
		else:
			self.status_label = Gtk.Label(label="D-Bus: Not connected - Start camfx with --dbus")
			self.status_label.add_css_class("error")
			self.camera_toggle.set_sensitive(False)
		self.status_label.set_xalign(0)
		preview_box.append(self.status_label)
		
		self._build_camera_settings(preview_box)
		
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
		
		if self.connected:
			GLib.idle_add(self._load_initial_camera_data)
	
	def _build_camera_settings(self, parent: Gtk.Box):
		"""Create camera source/resolution/fps selectors."""
		settings_frame = Gtk.Frame()
		settings_frame.set_label("Camera Settings")
		settings_frame.set_margin_start(5)
		settings_frame.set_margin_end(5)
		parent.append(settings_frame)
		
		settings_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
		settings_box.set_margin_start(10)
		settings_box.set_margin_end(10)
		settings_box.set_margin_top(10)
		settings_box.set_margin_bottom(10)
		settings_frame.set_child(settings_box)
		
		def build_row(title: str) -> Gtk.Box:
			row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
			label = Gtk.Label(label=title)
			label.set_xalign(0)
			label.set_hexpand(True)
			row.append(label)
			return row
		
		# Camera source dropdown
		source_row = build_row("Source")
		self.camera_source_store = Gtk.StringList()
		self.camera_source_dropdown = Gtk.DropDown(model=self.camera_source_store)
		self.camera_source_dropdown.set_hexpand(True)
		self.camera_source_dropdown.set_sensitive(False)
		self.camera_source_dropdown.connect("notify::selected", self._on_camera_source_changed)
		source_row.append(self.camera_source_dropdown)
		settings_box.append(source_row)
		
		# Resolution dropdown
		res_row = build_row("Resolution")
		self.camera_resolution_store = Gtk.StringList()
		self.camera_resolution_dropdown = Gtk.DropDown(model=self.camera_resolution_store)
		self.camera_resolution_dropdown.set_hexpand(True)
		self.camera_resolution_dropdown.set_sensitive(False)
		self.camera_resolution_dropdown.connect("notify::selected", self._on_resolution_changed)
		res_row.append(self.camera_resolution_dropdown)
		settings_box.append(res_row)
		
		# FPS dropdown
		fps_row = build_row("Frame rate")
		self.camera_fps_store = Gtk.StringList()
		self.camera_fps_dropdown = Gtk.DropDown(model=self.camera_fps_store)
		self.camera_fps_dropdown.set_hexpand(True)
		self.camera_fps_dropdown.set_sensitive(False)
		self.camera_fps_dropdown.connect("notify::selected", self._on_fps_changed)
		fps_row.append(self.camera_fps_dropdown)
		settings_box.append(fps_row)
		
		# Apply button
		self.camera_apply_button = Gtk.Button(label="Apply Settings")
		self.camera_apply_button.set_sensitive(False)
		self.camera_apply_button.connect("clicked", self._on_apply_camera_settings)
		settings_box.append(self.camera_apply_button)
		
		# Status label
		self.camera_settings_status = Gtk.Label(label="Camera controls require camfx service")
		self.camera_settings_status.set_xalign(0)
		settings_box.append(self.camera_settings_status)
	
	def _refresh_string_list(self, dropdown: Gtk.DropDown, items: List[str]) -> Gtk.StringList:
		store = Gtk.StringList()
		for item in items:
			store.append(item)
		dropdown.set_model(store)
		if items:
			dropdown.set_selected(0)
		else:
			dropdown.set_selected(Gtk.INVALID_LIST_POSITION)
		return store
	
	def _load_initial_camera_data(self):
		"""Fetch initial camera configuration and available sources."""
		if not self.connected or not self.dbus_client:
			self._clear_camera_dropdowns("camfx service not connected")
			return False
		try:
			self.current_camera_config = self.dbus_client.get_camera_config()
		except Exception as e:
			self.current_camera_config = None
			self._update_camera_settings_status(f"Failed to fetch camera config: {e}")
		self._refresh_camera_sources()
		return False
	
	def _refresh_camera_sources(self):
		"""Refresh camera source list from D-Bus."""
		if not self.dbus_client:
			self._clear_camera_dropdowns("camfx service unavailable")
			return
		try:
			sources = self.dbus_client.list_camera_sources()
		except Exception as e:
			self._clear_camera_dropdowns(f"Failed to load cameras: {e}")
			return
		
		self.camera_sources = sources
		self.camera_source_store = self._refresh_string_list(
			self.camera_source_dropdown,
			[source['label'] for source in sources]
		)
		
		if not sources:
			self.camera_source_dropdown.set_sensitive(False)
			self.camera_resolution_dropdown.set_sensitive(False)
			self.camera_fps_dropdown.set_sensitive(False)
			self.camera_apply_button.set_sensitive(False)
			self._update_camera_settings_status("No camera sources detected")
			return
		
		self.camera_source_dropdown.set_sensitive(True)
		target_id = self.current_camera_config.get('source_id') if self.current_camera_config else None
		selected_index = 0
		if target_id:
			for idx, source in enumerate(sources):
				if source['id'] == target_id:
					selected_index = idx
					break
		self._set_dropdown_selection(self.camera_source_dropdown, selected_index)
		self._load_modes_for_source(sources[selected_index]['id'])
	
	def _load_modes_for_source(self, source_id: str):
		"""Load and display resolution/fps combos for a source."""
		modes = self.camera_modes_cache.get(source_id)
		if modes is None:
			if not self.dbus_client:
				return
			try:
				modes = self.dbus_client.get_camera_modes(source_id)
			except Exception as e:
				self._update_camera_settings_status(f"Failed to load modes: {e}")
				self._clear_resolution_and_fps()
				return
			self.camera_modes_cache[source_id] = modes
		self._populate_resolution_dropdown(source_id, modes)
	
	def _clear_resolution_and_fps(self):
		self.camera_resolution_store = self._refresh_string_list(self.camera_resolution_dropdown, [])
		self.camera_fps_store = self._refresh_string_list(self.camera_fps_dropdown, [])
		self.camera_resolution_dropdown.set_sensitive(False)
		self.camera_fps_dropdown.set_sensitive(False)
		self.camera_apply_button.set_sensitive(False)
	
	def _populate_resolution_dropdown(self, source_id: str, modes: List[Dict[str, Any]]):
		labels = [f"{mode.get('width', 0)} x {mode.get('height', 0)}" for mode in modes]
		self.camera_resolution_store = self._refresh_string_list(self.camera_resolution_dropdown, labels)
		if not labels:
			self._clear_resolution_and_fps()
			self._update_camera_settings_status("No supported modes for selected camera")
			return
		
		self.camera_resolution_dropdown.set_sensitive(True)
		target = None
		if self.current_camera_config and self.current_camera_config.get('source_id') == source_id:
			target = (
				self.current_camera_config.get('width'),
				self.current_camera_config.get('height')
			)
		
		selected_index = 0
		if target:
			for idx, mode in enumerate(modes):
				if int(mode.get('width', 0)) == int(target[0]) and int(mode.get('height', 0)) == int(target[1]):
					selected_index = idx
					break
		self._set_dropdown_selection(self.camera_resolution_dropdown, selected_index)
		self._populate_fps_dropdown(source_id, modes, selected_index)
	
	def _populate_fps_dropdown(self, source_id: str, modes: List[Dict[str, Any]], mode_index: int):
		if mode_index < 0 or mode_index >= len(modes):
			self._clear_resolution_and_fps()
			return
		
		mode = modes[mode_index]
		fps_values = [int(fps) for fps in mode.get('fps', [])]
		fps_labels = [f"{fps} fps" for fps in fps_values]
		self.camera_fps_store = self._refresh_string_list(self.camera_fps_dropdown, fps_labels)
		
		if not fps_values:
			self.camera_fps_dropdown.set_sensitive(False)
			self.camera_apply_button.set_sensitive(False)
			self._update_camera_settings_status("No frame rates available for selected resolution")
			return
		
		self.camera_fps_dropdown.set_sensitive(True)
		target_fps = None
		if (self.current_camera_config and
		    self.current_camera_config.get('source_id') == source_id and
		    int(self.current_camera_config.get('width', 0)) == int(mode.get('width', 0)) and
		    int(self.current_camera_config.get('height', 0)) == int(mode.get('height', 0))):
			target_fps = int(self.current_camera_config.get('fps', 0))
		
		selected_index = 0
		if target_fps:
			for idx, fps in enumerate(fps_values):
				if fps == target_fps:
					selected_index = idx
					break
		self._set_dropdown_selection(self.camera_fps_dropdown, selected_index)
		self._update_camera_apply_button_state()
	
	def _on_camera_source_changed(self, dropdown: Gtk.DropDown, _param):
		if self._camera_controls_busy:
			return
		index = dropdown.get_selected()
		if index is None or index < 0 or index >= len(self.camera_sources):
			self._clear_resolution_and_fps()
			return
		source_id = self.camera_sources[index]['id']
		self._load_modes_for_source(source_id)
		self._update_camera_apply_button_state()
	
	def _on_resolution_changed(self, dropdown: Gtk.DropDown, _param):
		if self._camera_controls_busy:
			return
		source_index = self.camera_source_dropdown.get_selected()
		if source_index is None or source_index < 0 or source_index >= len(self.camera_sources):
			self._clear_resolution_and_fps()
			return
		mode_index = dropdown.get_selected()
		source_id = self.camera_sources[source_index]['id']
		modes = self.camera_modes_cache.get(source_id, [])
		if mode_index is None or mode_index < 0 or mode_index >= len(modes):
			self._clear_resolution_and_fps()
			return
		self._populate_fps_dropdown(source_id, modes, mode_index)
	
	def _on_fps_changed(self, dropdown: Gtk.DropDown, _param):
		if self._camera_controls_busy:
			return
		if dropdown.get_selected() is None or dropdown.get_selected() < 0:
			self.camera_apply_button.set_sensitive(False)
			return
		self._update_camera_apply_button_state()
	
	def _get_selected_camera_config(self) -> Optional[Dict[str, Any]]:
		source_index = self.camera_source_dropdown.get_selected()
		if source_index is None or source_index < 0 or source_index >= len(self.camera_sources):
			return None
		source = self.camera_sources[source_index]
		modes = self.camera_modes_cache.get(source['id'])
		if not modes:
			return None
		res_index = self.camera_resolution_dropdown.get_selected()
		if res_index is None or res_index < 0 or res_index >= len(modes):
			return None
		mode = modes[res_index]
		fps_values = [int(fps) for fps in mode.get('fps', [])]
		fps_index = self.camera_fps_dropdown.get_selected()
		if fps_index is None or fps_index < 0 or fps_index >= len(fps_values):
			return None
		return {
			'source_id': source['id'],
			'width': int(mode.get('width', 0)),
			'height': int(mode.get('height', 0)),
			'fps': int(fps_values[fps_index]),
		}
	
	def _update_camera_apply_button_state(self):
		if not hasattr(self, 'camera_apply_button'):
			return
		if not self.connected or not self.dbus_client:
			self.camera_apply_button.set_sensitive(False)
			return
		selected = self._get_selected_camera_config()
		if not selected:
			self.camera_apply_button.set_sensitive(False)
			return
		if not self.current_camera_config:
			self.camera_apply_button.set_sensitive(True)
			return
		is_same = (
			self.current_camera_config.get('source_id') == selected['source_id'] and
			int(self.current_camera_config.get('width', 0)) == selected['width'] and
			int(self.current_camera_config.get('height', 0)) == selected['height'] and
			int(self.current_camera_config.get('fps', 0)) == selected['fps']
		)
		self.camera_apply_button.set_sensitive(not is_same)
	
	def _on_apply_camera_settings(self, _button):
		if not self.connected or not self.dbus_client:
			self._update_camera_settings_status("camfx service not connected")
			return
		config = self._get_selected_camera_config()
		if not config:
			self._update_camera_settings_status("Select source, resolution, and fps before applying")
			return
		try:
			success = self.dbus_client.apply_camera_config(
				config['source_id'],
				config['width'],
				config['height'],
				config['fps']
			)
			if success:
				self.current_camera_config = config
				self._update_camera_settings_status("Camera settings applied")
				self._update_camera_apply_button_state()
				if self.preview_toggle.get_active() and hasattr(self, 'preview_widget'):
					self.preview_widget.restart_preview()
			else:
				self._update_camera_settings_status("Failed to apply camera settings")
		except Exception as e:
			self._update_camera_settings_status(f"Error applying camera settings: {e}")
			self._show_error(f"Error applying camera settings: {e}")
	
	def _update_camera_settings_status(self, message: str):
		if hasattr(self, 'camera_settings_status') and self.camera_settings_status:
			self.camera_settings_status.set_text(message)
	
	def _clear_camera_dropdowns(self, message: str):
		self.camera_sources = []
		self.camera_modes_cache.clear()
		self.camera_source_store = self._refresh_string_list(self.camera_source_dropdown, [])
		self._clear_resolution_and_fps()
		self.camera_source_dropdown.set_sensitive(False)
		self._update_camera_settings_status(message)
	
	def _set_dropdown_selection(self, dropdown: Gtk.DropDown, index: int):
		self._camera_controls_busy = True
		try:
			if index >= 0:
				dropdown.set_selected(index)
			else:
				dropdown.set_selected(Gtk.INVALID_LIST_POSITION)
		finally:
			self._camera_controls_busy = False
	
	def _sync_camera_controls(self):
		if not self.camera_sources or not self.current_camera_config:
			return
		target_id = self.current_camera_config.get('source_id')
		if not target_id:
			return
		for idx, source in enumerate(self.camera_sources):
			if source['id'] == target_id:
				self._set_dropdown_selection(self.camera_source_dropdown, idx)
				self._load_modes_for_source(target_id)
				break
		self._update_camera_apply_button_state()
	
	def _handle_camera_config_changed(self, source_id: str, width: int, height: int, fps: int):
		self.current_camera_config = {
			'source_id': str(source_id),
			'width': int(width),
			'height': int(height),
			'fps': int(fps),
		}
		self._sync_camera_controls()
		if self.preview_toggle.get_active() and hasattr(self, 'preview_widget'):
			self.preview_widget.restart_preview()
		return False
	
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
	
	def _on_camera_config_changed(self, source_id: str, width: int, height: int, fps: int):
		"""Handle camera configuration changes from D-Bus."""
		GLib.idle_add(self._handle_camera_config_changed, source_id, width, height, fps)
	
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

