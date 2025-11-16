"""D-Bus client wrapper for camfx service."""

import dbus
import dbus.exceptions
from typing import List, Dict, Any, Optional, Callable
import gi
gi.require_version('GLib', '2.0')
from gi.repository import GLib


class CamfxDBusClient:
	"""Wrapper for D-Bus communication with camfx service."""
	
	SERVICE_NAME = 'org.camfx.Control1'
	OBJECT_PATH = '/org/camfx/Control1'
	INTERFACE_NAME = 'org.camfx.Control1'
	
	def __init__(self):
		"""Initialize D-Bus client."""
		self.bus = dbus.SessionBus()
		self.service = None
		self.control = None
		self.signal_handlers = []
		self._connect()
		self._setup_signals()
	
	def _connect(self):
		"""Connect to camfx D-Bus service."""
		try:
			self.service = self.bus.get_object(
				self.SERVICE_NAME,
				self.OBJECT_PATH
			)
			self.control = dbus.Interface(
				self.service,
				self.INTERFACE_NAME
			)
		except dbus.exceptions.DBusException as e:
			raise ConnectionError(f"camfx service not running: {e}")
	
	def is_connected(self) -> bool:
		"""Check if connected to service."""
		return self.service is not None and self.control is not None
	
	def _setup_signals(self):
		"""Set up signal handlers for effect changes."""
		try:
			self.service.connect_to_signal(
				'EffectChanged',
				self._on_effect_changed,
				dbus_interface=self.INTERFACE_NAME
			)
			self.service.connect_to_signal(
				'CameraStateChanged',
				self._on_camera_state_changed,
				dbus_interface=self.INTERFACE_NAME
			)
		except Exception as e:
			# Signals may not be available if service is not running
			pass
	
	def _on_effect_changed(self, action: str, effect_type: str, config: Dict[str, Any]):
		"""Internal callback for effect change signals."""
		# This will be overridden by signal handlers set via connect_signals
		pass
	
	def _on_camera_state_changed(self, is_active: bool):
		"""Internal callback for camera state change signals."""
		# This will be overridden by signal handlers set via connect_signals
		pass
	
	def connect_signals(self, on_effect_changed: Optional[Callable] = None,
	                   on_camera_state_changed: Optional[Callable] = None):
		"""Connect signal handlers.
		
		Args:
			on_effect_changed: Callback(action, effect_type, config)
			on_camera_state_changed: Callback(is_active)
		"""
		if on_effect_changed:
			self._on_effect_changed = on_effect_changed
		if on_camera_state_changed:
			self._on_camera_state_changed = on_camera_state_changed
	
	def get_current_effects(self) -> List[tuple]:
		"""Get current effect chain.
		
		Returns:
			List of tuples: (effect_type, class_name, config_dict)
		"""
		try:
			return self.control.GetCurrentEffects()
		except dbus.exceptions.DBusException as e:
			raise ConnectionError(f"D-Bus error: {e}")
	
	def add_effect(self, effect_type: str, config: Dict[str, Any]) -> bool:
		"""Add effect to chain.
		
		Args:
			effect_type: Type of effect to add
			config: Effect configuration dictionary
		
		Returns:
			True if successful, False otherwise
		"""
		try:
			# Filter out None values - D-Bus can't encode NoneType
			dbus_config = {k: v for k, v in config.items() if v is not None}
			# Convert to dbus-compatible format
			dbus_config = dbus.Dictionary(dbus_config, signature='sv')
			return self.control.AddEffect(effect_type, dbus_config)
		except dbus.exceptions.DBusException as e:
			raise ConnectionError(f"D-Bus error: {e}")
	
	def set_effect(self, effect_type: str, config: Dict[str, Any]) -> bool:
		"""Replace all effects with a single effect.
		
		Args:
			effect_type: Type of effect
			config: Effect configuration dictionary
		
		Returns:
			True if successful, False otherwise
		"""
		try:
			# Filter out None values - D-Bus can't encode NoneType
			dbus_config = {k: v for k, v in config.items() if v is not None}
			# Convert to dbus-compatible format
			dbus_config = dbus.Dictionary(dbus_config, signature='sv')
			return self.control.SetEffect(effect_type, dbus_config)
		except dbus.exceptions.DBusException as e:
			raise ConnectionError(f"D-Bus error: {e}")
	
	def remove_effect(self, index: int) -> bool:
		"""Remove effect from chain by index.
		
		Args:
			index: Index of effect to remove (0-based)
		
		Returns:
			True if successful, False otherwise
		"""
		try:
			return self.control.RemoveEffect(index)
		except dbus.exceptions.DBusException as e:
			raise ConnectionError(f"D-Bus error: {e}")
	
	def remove_effect_by_type(self, effect_type: str) -> bool:
		"""Remove effect from chain by type.
		
		Args:
			effect_type: Type of effect to remove
		
		Returns:
			True if successful, False otherwise
		"""
		try:
			return self.control.RemoveEffectByType(effect_type)
		except dbus.exceptions.DBusException as e:
			raise ConnectionError(f"D-Bus error: {e}")
	
	def clear_chain(self) -> bool:
		"""Clear all effects from chain.
		
		Returns:
			True if successful, False otherwise
		"""
		try:
			return self.control.ClearChain()
		except dbus.exceptions.DBusException as e:
			raise ConnectionError(f"D-Bus error: {e}")
	
	def update_effect_parameter(self, effect_type: str, parameter: str, value: Any) -> bool:
		"""Update a parameter of an effect in the chain.
		
		Args:
			effect_type: Type of effect to update
			parameter: Parameter name
			value: New parameter value
		
		Returns:
			True if successful, False otherwise
		"""
		try:
			# Convert value to dbus-compatible type
			if isinstance(value, (int, float, str, bool)):
				dbus_value = value
			else:
				dbus_value = str(value)
			return self.control.UpdateEffectParameter(effect_type, parameter, dbus_value)
		except dbus.exceptions.DBusException as e:
			raise ConnectionError(f"D-Bus error: {e}")
	
	def start_camera(self) -> bool:
		"""Start the camera.
		
		Returns:
			True if successful, False otherwise
		"""
		try:
			return self.control.StartCamera()
		except dbus.exceptions.DBusException as e:
			raise ConnectionError(f"D-Bus error: {e}")
	
	def stop_camera(self) -> bool:
		"""Stop the camera.
		
		Returns:
			True if successful, False otherwise
		"""
		try:
			return self.control.StopCamera()
		except dbus.exceptions.DBusException as e:
			raise ConnectionError(f"D-Bus error: {e}")
	
	def get_camera_state(self) -> bool:
		"""Get current camera state.
		
		Returns:
			True if camera is active, False otherwise
		"""
		try:
			return self.control.GetCameraState()
		except dbus.exceptions.DBusException as e:
			raise ConnectionError(f"D-Bus error: {e}")

