"""Effect chain list widget."""

from typing import List, Dict, Any, Optional, Callable
import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk
from .utils import format_effect_name, get_effect_defaults
from .dbus_client import CamfxDBusClient


class EffectChainWidget(Gtk.Box):
	"""Widget showing and managing effect chain."""
	
	def __init__(self, dbus_client: CamfxDBusClient, on_effect_selected: Optional[Callable] = None):
		"""Initialize effect chain widget.
		
		Args:
			dbus_client: D-Bus client instance
			on_effect_selected: Callback(effect_type, config) when effect is selected
		"""
		super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=10)
		self.dbus_client = dbus_client
		self.on_effect_selected = on_effect_selected
		self.effect_rows = []
		self._last_selected_row = None  # Track last selected row for deselection
		
		self.set_margin_start(10)
		self.set_margin_end(10)
		self.set_margin_top(10)
		self.set_margin_bottom(10)
		
		# Title
		title_label = Gtk.Label()
		title_label.set_markup("<b>Effect Chain</b>")
		title_label.set_xalign(0)
		self.append(title_label)
		
		# Scrolled window for effect list
		self.scrolled = Gtk.ScrolledWindow()
		self.scrolled.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
		self.scrolled.set_min_content_height(200)
		self.scrolled.set_max_content_height(400)
		
		# List box for effects
		self.list_box = Gtk.ListBox()
		self.list_box.set_selection_mode(Gtk.SelectionMode.SINGLE)
		self.list_box.connect("row-selected", self._on_row_selected)
		# Allow deselection by clicking selected row again
		self.list_box.set_activate_on_single_click(False)
		self.scrolled.set_child(self.list_box)
		self.append(self.scrolled)
		
		# Add effect button
		self.add_button = Gtk.Button(label="Add Effect")
		self.add_button.connect("clicked", self._on_add_clicked)
		self.append(self.add_button)
		
		# Clear button
		self.clear_button = Gtk.Button(label="Clear All")
		self.clear_button.connect("clicked", self._on_clear_clicked)
		self.append(self.clear_button)
		
		# Refresh chain
		self._refresh_chain()
	
	def _refresh_chain(self):
		"""Refresh effect chain from D-Bus service."""
		# Clear ALL existing rows from list_box (including empty/error rows)
		# Get all children first, then remove them
		children = []
		child = self.list_box.get_first_child()
		while child is not None:
			children.append(child)
			child = child.get_next_sibling()
		
		for row in children:
			self.list_box.remove(row)
		
		# Clear effect_rows list and reset selection tracking
		self.effect_rows.clear()
		self._last_selected_row = None
		
		# Get current effects
		try:
			effects = self.dbus_client.get_current_effects()
		except Exception as e:
			# Service not available or error
			error_row = Gtk.ListBoxRow()
			error_label = Gtk.Label(label=f"Error: {e}")
			error_label.set_margin_start(10)
			error_label.set_margin_top(10)
			error_label.set_margin_bottom(10)
			error_row.set_child(error_label)
			self.list_box.append(error_row)
			return
		
		if not effects:
			# Empty state
			empty_row = Gtk.ListBoxRow()
			empty_label = Gtk.Label(label="No effects in chain")
			empty_label.set_margin_start(10)
			empty_label.set_margin_top(10)
			empty_label.set_margin_bottom(10)
			empty_row.set_child(empty_label)
			self.list_box.append(empty_row)
			return
		
		# Add effect rows
		for i, (effect_type, class_name, config) in enumerate(effects):
			row = self._create_effect_row(i, effect_type, config)
			self.list_box.append(row)
			self.effect_rows.append(row)
	
	def _create_effect_row(self, index: int, effect_type: str, config: Dict[str, Any]) -> Gtk.ListBoxRow:
		"""Create a row widget for an effect.
		
		Args:
			index: Effect index
			effect_type: Effect type
			config: Effect configuration
		
		Returns:
			ListBoxRow widget
		"""
		row = Gtk.ListBoxRow()
		
		# Main box
		box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
		box.set_margin_start(10)
		box.set_margin_end(10)
		box.set_margin_top(5)
		box.set_margin_bottom(5)
		
		# Index label (use a fixed-width box for alignment)
		index_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
		index_box.set_size_request(30, -1)
		index_label = Gtk.Label(label=f"{index + 1}.")
		index_box.append(index_label)
		box.append(index_box)
		
		# Effect name and config
		info_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
		info_box.set_hexpand(True)
		
		name_label = Gtk.Label(label=format_effect_name(effect_type))
		name_label.set_xalign(0)
		info_box.append(name_label)
		
		# Config summary
		config_parts = []
		for key, value in config.items():
			if key in ['background', 'image'] and isinstance(value, str):
				# Show filename only for image paths
				import os
				config_parts.append(f"{key}={os.path.basename(value)}")
			else:
				config_parts.append(f"{key}={value}")
		
		config_text = ", ".join(config_parts) if config_parts else "default"
		config_label = Gtk.Label(label=config_text)
		config_label.set_xalign(0)
		config_label.add_css_class("dim-label")
		info_box.append(config_label)
		
		box.append(info_box)
		
		# Remove button
		remove_button = Gtk.Button(icon_name="window-close-symbolic")
		remove_button.set_tooltip_text("Remove effect")
		remove_button.add_css_class("circular")
		remove_button.connect("clicked", self._on_remove_clicked, index, effect_type)
		box.append(remove_button)
		
		row.set_child(box)
		
		# Store effect data in row
		row.effect_type = effect_type
		row.effect_config = config
		row.effect_index = index
		
		return row
	
	def _on_row_selected(self, list_box: Gtk.ListBox, row: Optional[Gtk.ListBoxRow]):
		"""Handle effect row selection or deselection."""
		if row and hasattr(row, 'effect_type'):
			# If clicking the same row again, deselect it
			if self._last_selected_row == row:
				self.list_box.unselect_row(row)
				self._last_selected_row = None
				if self.on_effect_selected:
					self.on_effect_selected(None, None)
			else:
				# New selection
				self._last_selected_row = row
				if self.on_effect_selected:
					self.on_effect_selected(row.effect_type, row.effect_config)
		else:
			# Row deselected (None passed)
			self._last_selected_row = None
			if self.on_effect_selected:
				self.on_effect_selected(None, None)
	
	def _on_add_clicked(self, button: Gtk.Button):
		"""Handle add effect button click."""
		dialog = EffectSelectionDialog(button.get_root(), on_effect_selected=self._on_effect_added)
		dialog.show()
	
	def _on_effect_added(self, effect_type: str, config: Dict[str, Any]):
		"""Handle effect selection from dialog."""
		try:
			success = self.dbus_client.add_effect(effect_type, config)
			if success:
				self._refresh_chain()
			else:
				self._show_error("Failed to add effect")
		except Exception as e:
			self._show_error(f"Error adding effect: {e}")
	
	def _on_remove_clicked(self, button: Gtk.Button, index: int, effect_type: str):
		"""Handle remove effect button click."""
		try:
			success = self.dbus_client.remove_effect(index)
			if success:
				# Clear selection before refreshing (will be handled by _on_effect_changed)
				# but we also clear it here to ensure UI updates immediately
				if self.on_effect_selected:
					self.on_effect_selected(None, None)
				self._refresh_chain()
			else:
				self._show_error("Failed to remove effect")
		except Exception as e:
			self._show_error(f"Error removing effect: {e}")
	
	def _on_clear_clicked(self, button: Gtk.Button):
		"""Handle clear all button click."""
		# Show confirmation dialog
		dialog = Gtk.MessageDialog(
			transient_for=button.get_root(),
			message_type=Gtk.MessageType.QUESTION,
			buttons=Gtk.ButtonsType.YES_NO,
			text="Clear all effects?"
		)
		# In GTK4, use get_message_area() to add secondary text
		message_area = dialog.get_message_area()
		secondary_label = Gtk.Label(label="This will remove all effects from the chain.")
		secondary_label.set_wrap(True)
		message_area.append(secondary_label)
		
		def on_response(dialog, response):
			if response == Gtk.ResponseType.YES:
				try:
					success = self.dbus_client.clear_chain()
					if success:
						# Clear selection when clearing all effects
						if self.on_effect_selected:
							self.on_effect_selected(None, None)
						self._refresh_chain()
					else:
						self._show_error("Failed to clear effects")
				except Exception as e:
					self._show_error(f"Error clearing effects: {e}")
			dialog.destroy()
		
		dialog.connect("response", on_response)
		dialog.show()
	
	def _show_error(self, message: str):
		"""Show error message."""
		# Simple error dialog - try to get parent window
		parent = None
		if hasattr(self, 'get_root') and self.get_root():
			parent = self.get_root()
		
		dialog = Gtk.MessageDialog(
			transient_for=parent,
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
	
	def refresh(self):
		"""Public method to refresh the chain."""
		self._refresh_chain()


class EffectSelectionDialog(Gtk.Dialog):
	"""Dialog for selecting an effect to add."""
	
	def __init__(self, parent: Optional[Gtk.Window] = None, on_effect_selected: Optional[Callable] = None):
		"""Initialize effect selection dialog.
		
		Args:
			parent: Parent window
			on_effect_selected: Callback(effect_type, config) when effect is selected
		"""
		super().__init__(
			title="Add Effect",
			transient_for=parent,
			modal=True
		)
		
		self.on_effect_selected = on_effect_selected
		
		self.add_buttons(
			"_Cancel", Gtk.ResponseType.CANCEL,
			"_Add", Gtk.ResponseType.ACCEPT
		)
		
		# Content area
		content = self.get_content_area()
		content.set_spacing(10)
		content.set_margin_start(20)
		content.set_margin_end(20)
		content.set_margin_top(20)
		content.set_margin_bottom(20)
		
		# Effect type selection
		label = Gtk.Label(label="Select effect type:")
		label.set_xalign(0)
		content.append(label)
		
		# Dropdown for effect types
		self.effect_store = Gtk.StringList()
		effect_types = ['blur', 'replace', 'brightness', 'beautify', 'autoframe', 'gaze-correct']
		for effect_type in effect_types:
			self.effect_store.append(format_effect_name(effect_type))
		
		self.effect_dropdown = Gtk.DropDown(model=self.effect_store)
		self.effect_dropdown.set_selected(0)
		content.append(self.effect_dropdown)
		
		# Store effect types mapping
		self.effect_types = effect_types
		
		# Connect accept button
		self.connect("response", self._on_response)
	
	def _on_response(self, dialog: Gtk.Dialog, response: int):
		"""Handle dialog response."""
		if response == Gtk.ResponseType.ACCEPT:
			selected = self.effect_dropdown.get_selected()
			if selected is not None:
				effect_type = self.effect_types[selected]
				# Get default config
				config = get_effect_defaults(effect_type)
				if self.on_effect_selected:
					self.on_effect_selected(effect_type, config)
		
		self.destroy()

