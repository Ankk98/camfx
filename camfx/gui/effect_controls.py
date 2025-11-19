"""Effect parameter controls widget."""

from typing import Dict, Any, Optional, Callable
import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Gio', '2.0')
from gi.repository import Gtk, Gio
from .utils import format_parameter_name, get_effect_defaults


class EffectControlsWidget(Gtk.Box):
	"""Widget for adjusting effect parameters."""
	
	def __init__(self, effect_type: Optional[str] = None, 
	             config: Optional[Dict[str, Any]] = None,
	             on_update: Optional[Callable] = None,
	             on_apply: Optional[Callable] = None,
	             application: Optional[Gtk.Application] = None):
		"""Initialize effect controls widget.
		
		Args:
			effect_type: Type of effect (None to show empty state)
			config: Current effect configuration
			on_update: Callback(effect_type, parameter, value) when parameter changes
			on_apply: Callback() to refresh effect chain display
			application: GTK Application instance (for file chooser)
		"""
		super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=10)
		self.effect_type = effect_type
		self.config = config or {}
		self.on_update = on_update
		self.on_apply = on_apply
		self.application = application
		self.controls = {}  # Store control widgets
		self.pending_updates = {}  # Track pending parameter updates
		
		self.set_margin_start(10)
		self.set_margin_end(10)
		self.set_margin_top(10)
		self.set_margin_bottom(10)
		
		if effect_type:
			self._build_controls()
		else:
			self._show_empty_state()
	
	def _show_empty_state(self):
		"""Show empty state when no effect is selected."""
		label = Gtk.Label(label="Select an effect to adjust parameters")
		label.set_margin_top(20)
		label.set_margin_bottom(20)
		self.append(label)
	
	def _build_controls(self):
		"""Build parameter controls based on effect type."""
		# Clear existing controls - remove all children
		# Use list() to create a copy since we're modifying during iteration
		children = list(self)
		for child in children:
			self.remove(child)
		self.controls.clear()
		
		if not self.effect_type:
			self._show_empty_state()
			return
		
		# Title
		title_label = Gtk.Label()
		title_label.set_markup(f"<b>Effect Parameters</b>")
		title_label.set_margin_bottom(10)
		self.append(title_label)
		
		# Store reference to apply button (will be added at the end)
		self.apply_button = None
		
		# Build controls based on effect type
		if self.effect_type == 'blur':
			self._add_strength_control(3, 51, 2)  # Odd numbers only
		elif self.effect_type == 'replace':
			self._add_image_picker()
		elif self.effect_type == 'brightness':
			self._add_brightness_control()
			self._add_contrast_control()
			self._add_face_only_checkbox()
		elif self.effect_type == 'beautify':
			self._add_smoothness_control()
		elif self.effect_type == 'autoframe':
			self._add_padding_control()
			self._add_min_zoom_control()
			self._add_max_zoom_control()
		elif self.effect_type == 'gaze-correct':
			self._add_strength_control(0.0, 1.0, 0.01, is_float=True)
		
		# Add Apply button at the end
		if self.effect_type:
			self._add_apply_button()
	
	def _add_strength_control(self, min_val: float, max_val: float, step: float = 1.0, is_float: bool = False):
		"""Add strength slider control."""
		box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
		
		label = Gtk.Label(label="Strength:")
		label.set_xalign(0)
		box.append(label)
		
		# Value label
		value_label = Gtk.Label()
		value_label.set_xalign(0)
		box.append(value_label)
		
		# Slider
		adjustment = Gtk.Adjustment(
			value=self.config.get('strength', get_effect_defaults(self.effect_type).get('strength', min_val)),
			lower=min_val,
			upper=max_val,
			step_increment=step,
			page_increment=step * 5
		)
		
		scale = Gtk.Scale(orientation=Gtk.Orientation.HORIZONTAL, adjustment=adjustment)
		scale.set_draw_value(False)
		
		def on_value_changed(scale):
			value = scale.get_value()
			if not is_float and self.effect_type == 'blur':
				# Ensure odd number for blur
				value = int(value)
				if value % 2 == 0:
					value = max(min_val, value - 1)
				adjustment.set_value(value)
			else:
				value = int(value) if not is_float else round(value, 2) if is_float else value
			
			value_label.set_text(str(value))
			# Store pending update instead of applying immediately
			self.pending_updates['strength'] = value
			# Update apply button state
			if self.apply_button:
				self.apply_button.set_sensitive(True)
		
		scale.connect("value-changed", on_value_changed)
		
		# Set initial value label
		initial_value = adjustment.get_value()
		if not is_float and self.effect_type == 'blur':
			initial_value = int(initial_value)
			if initial_value % 2 == 0:
				initial_value = max(min_val, initial_value - 1)
		value_label.set_text(str(initial_value))
		
		box.append(scale)
		self.append(box)
		self.controls['strength'] = (scale, value_label)
	
	def _add_brightness_control(self):
		"""Add brightness slider control."""
		box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
		
		label = Gtk.Label(label="Brightness:")
		label.set_xalign(0)
		box.append(label)
		
		value_label = Gtk.Label()
		value_label.set_xalign(0)
		box.append(value_label)
		
		adjustment = Gtk.Adjustment(
			value=self.config.get('brightness', 0),
			lower=-100,
			upper=100,
			step_increment=1,
			page_increment=10
		)
		
		scale = Gtk.Scale(orientation=Gtk.Orientation.HORIZONTAL, adjustment=adjustment)
		scale.set_draw_value(False)
		
		def on_value_changed(scale):
			value = int(scale.get_value())
			value_label.set_text(str(value))
			self.pending_updates['brightness'] = value
			if self.apply_button:
				self.apply_button.set_sensitive(True)
		
		scale.connect("value-changed", on_value_changed)
		value_label.set_text(str(int(adjustment.get_value())))
		
		box.append(scale)
		self.append(box)
		self.controls['brightness'] = (scale, value_label)
	
	def _add_contrast_control(self):
		"""Add contrast slider control."""
		box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
		
		label = Gtk.Label(label="Contrast:")
		label.set_xalign(0)
		box.append(label)
		
		value_label = Gtk.Label()
		value_label.set_xalign(0)
		box.append(value_label)
		
		adjustment = Gtk.Adjustment(
			value=self.config.get('contrast', 1.0),
			lower=0.5,
			upper=2.0,
			step_increment=0.1,
			page_increment=0.5
		)
		
		scale = Gtk.Scale(orientation=Gtk.Orientation.HORIZONTAL, adjustment=adjustment)
		scale.set_draw_value(False)
		
		def on_value_changed(scale):
			value = round(scale.get_value(), 2)
			value_label.set_text(str(value))
			self.pending_updates['contrast'] = value
			if self.apply_button:
				self.apply_button.set_sensitive(True)
		
		scale.connect("value-changed", on_value_changed)
		value_label.set_text(str(round(adjustment.get_value(), 2)))
		
		box.append(scale)
		self.append(box)
		self.controls['contrast'] = (scale, value_label)
	
	def _add_face_only_checkbox(self):
		"""Add face-only checkbox."""
		checkbox = Gtk.CheckButton(label="Face Only")
		checkbox.set_active(self.config.get('face_only', False))
		
		def on_toggled(checkbox):
			value = checkbox.get_active()
			self.pending_updates['face_only'] = value
			if self.apply_button:
				self.apply_button.set_sensitive(True)
		
		checkbox.connect("toggled", on_toggled)
		self.append(checkbox)
		self.controls['face_only'] = checkbox
	
	def _add_smoothness_control(self):
		"""Add smoothness slider control."""
		box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
		
		label = Gtk.Label(label="Smoothness:")
		label.set_xalign(0)
		box.append(label)
		
		value_label = Gtk.Label()
		value_label.set_xalign(0)
		box.append(value_label)
		
		adjustment = Gtk.Adjustment(
			value=self.config.get('smoothness', 5),
			lower=1,
			upper=15,
			step_increment=1,
			page_increment=2
		)
		
		scale = Gtk.Scale(orientation=Gtk.Orientation.HORIZONTAL, adjustment=adjustment)
		scale.set_draw_value(False)
		
		def on_value_changed(scale):
			value = int(scale.get_value())
			value_label.set_text(str(value))
			self.pending_updates['smoothness'] = value
			if self.apply_button:
				self.apply_button.set_sensitive(True)
		
		scale.connect("value-changed", on_value_changed)
		value_label.set_text(str(int(adjustment.get_value())))
		
		box.append(scale)
		self.append(box)
		self.controls['smoothness'] = (scale, value_label)
	
	def _add_padding_control(self):
		"""Add padding slider control."""
		box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
		
		label = Gtk.Label(label="Padding:")
		label.set_xalign(0)
		box.append(label)
		
		value_label = Gtk.Label()
		value_label.set_xalign(0)
		box.append(value_label)
		
		adjustment = Gtk.Adjustment(
			value=self.config.get('padding', 0.3),
			lower=0.0,
			upper=1.0,
			step_increment=0.05,
			page_increment=0.2
		)
		
		scale = Gtk.Scale(orientation=Gtk.Orientation.HORIZONTAL, adjustment=adjustment)
		scale.set_draw_value(False)
		
		def on_value_changed(scale):
			value = round(scale.get_value(), 2)
			value_label.set_text(str(value))
			self.pending_updates['padding'] = value
			if self.apply_button:
				self.apply_button.set_sensitive(True)
		
		scale.connect("value-changed", on_value_changed)
		value_label.set_text(str(round(adjustment.get_value(), 2)))
		
		box.append(scale)
		self.append(box)
		self.controls['padding'] = (scale, value_label)
	
	def _add_min_zoom_control(self):
		"""Add min zoom slider control."""
		box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
		
		label = Gtk.Label(label="Min Zoom:")
		label.set_xalign(0)
		box.append(label)
		
		value_label = Gtk.Label()
		value_label.set_xalign(0)
		box.append(value_label)
		
		adjustment = Gtk.Adjustment(
			value=self.config.get('min_zoom', 1.0),
			lower=1.0,
			upper=3.0,
			step_increment=0.1,
			page_increment=0.5
		)
		
		scale = Gtk.Scale(orientation=Gtk.Orientation.HORIZONTAL, adjustment=adjustment)
		scale.set_draw_value(False)
		
		def on_value_changed(scale):
			value = round(scale.get_value(), 2)
			value_label.set_text(str(value))
			self.pending_updates['min_zoom'] = value
			if self.apply_button:
				self.apply_button.set_sensitive(True)
		
		scale.connect("value-changed", on_value_changed)
		value_label.set_text(str(round(adjustment.get_value(), 2)))
		
		box.append(scale)
		self.append(box)
		self.controls['min_zoom'] = (scale, value_label)
	
	def _add_max_zoom_control(self):
		"""Add max zoom slider control."""
		box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
		
		label = Gtk.Label(label="Max Zoom:")
		label.set_xalign(0)
		box.append(label)
		
		value_label = Gtk.Label()
		value_label.set_xalign(0)
		box.append(value_label)
		
		adjustment = Gtk.Adjustment(
			value=self.config.get('max_zoom', 2.0),
			lower=1.0,
			upper=5.0,
			step_increment=0.1,
			page_increment=0.5
		)
		
		scale = Gtk.Scale(orientation=Gtk.Orientation.HORIZONTAL, adjustment=adjustment)
		scale.set_draw_value(False)
		
		def on_value_changed(scale):
			value = round(scale.get_value(), 2)
			value_label.set_text(str(value))
			self.pending_updates['max_zoom'] = value
			if self.apply_button:
				self.apply_button.set_sensitive(True)
		
		scale.connect("value-changed", on_value_changed)
		value_label.set_text(str(round(adjustment.get_value(), 2)))
		
		box.append(scale)
		self.append(box)
		self.controls['max_zoom'] = (scale, value_label)
	
	def _add_image_picker(self):
		"""Add background image picker button."""
		box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
		
		label = Gtk.Label(label="Background Image:")
		label.set_xalign(0)
		box.append(label)
		
		# Check if image path is already in config
		image_path = self.config.get('image') or self.config.get('background')
		if isinstance(image_path, str):
			import os
			button_label = f"Selected: {os.path.basename(image_path)}"
		else:
			button_label = "Select Image..."
		
		button = Gtk.Button(label=button_label)
		
		def on_clicked(button):
			# Create file chooser dialog
			dialog = Gtk.FileChooserDialog(
				title="Select Background Image",
				transient_for=button.get_root(),
				action=Gtk.FileChooserAction.OPEN
			)
			
			# Set application if available (required for file access)
			if self.application:
				dialog.set_application(self.application)
			
			dialog.add_buttons(
				"_Cancel", Gtk.ResponseType.CANCEL,
				"_Open", Gtk.ResponseType.ACCEPT
			)
			
			# Add image filters
			filter_image = Gtk.FileFilter()
			filter_image.set_name("Image files")
			filter_image.add_mime_type("image/png")
			filter_image.add_mime_type("image/jpeg")
			filter_image.add_mime_type("image/jpg")
			dialog.add_filter(filter_image)
			
			# Show dialog and handle response
			def on_response(dialog, response):
				if response == Gtk.ResponseType.ACCEPT:
					file = dialog.get_file()
					if file:
						file_path = file.get_path()
						# Use 'image' parameter for file path (as per core.py)
						self.pending_updates['image'] = file_path
						button.set_label(f"Selected: {file.get_basename()}")
						if self.apply_button:
							self.apply_button.set_sensitive(True)
				dialog.destroy()
			
			dialog.connect("response", on_response)
			dialog.show()
		
		button.connect("clicked", on_clicked)
		box.append(button)
		self.append(box)
		self.controls['image'] = button
	
	def _add_apply_button(self):
		"""Add Apply Changes button."""
		# Separator
		separator = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
		separator.set_margin_top(10)
		separator.set_margin_bottom(10)
		self.append(separator)
		
		# Apply button
		self.apply_button = Gtk.Button(label="Apply Changes")
		self.apply_button.set_sensitive(False)  # Disabled until changes are made
		self.apply_button.add_css_class("suggested-action")
		self.apply_button.connect("clicked", self._on_apply_clicked)
		self.append(self.apply_button)
	
	def _on_apply_clicked(self, button: Gtk.Button):
		"""Handle Apply Changes button click."""
		if not self.effect_type or not self.pending_updates:
			return
		
		# Apply all pending updates
		for parameter, value in self.pending_updates.items():
			if self.on_update:
				self.on_update(self.effect_type, parameter, value)
		
		# Clear pending updates
		self.pending_updates.clear()
		
		# Disable button
		button.set_sensitive(False)
		
		# Refresh effect chain display if callback provided
		if self.on_apply:
			self.on_apply()
	
	def update_effect(self, effect_type: Optional[str], config: Optional[Dict[str, Any]]):
		"""Update displayed effect and parameters.
		
		Args:
			effect_type: New effect type (None to clear)
			config: New effect configuration
		"""
		self.effect_type = effect_type
		self.config = config or {}
		self.pending_updates.clear()  # Clear pending updates when switching effects
		self._build_controls()

