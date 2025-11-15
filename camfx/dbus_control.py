"""D-Bus service for controlling camfx effects at runtime."""

import threading
from typing import Dict, Any, List, Optional

try:
	import dbus
	import dbus.service
	import dbus.mainloop.glib
	from gi.repository import GLib
	DBUS_AVAILABLE = True
except ImportError as e:
	DBUS_AVAILABLE = False
	_dbus_import_error = e

# D-Bus service details
SERVICE_NAME = 'org.camfx.Control1'
OBJECT_PATH = '/org/camfx/Control1'
INTERFACE_NAME = 'org.camfx.Control1'


if DBUS_AVAILABLE:
	class CamfxControlServiceObject(dbus.service.Object):
		"""D-Bus service object implementation."""
		
		def __init__(self, bus_name, object_path, service):
			"""Initialize service object.
			
			Args:
				bus_name: D-Bus bus name
				object_path: Object path
				service: CamfxControlService instance
			"""
			dbus.service.Object.__init__(self, bus_name, object_path)
			self.service = service
			self.effect_controller = service.effect_controller
		
		@dbus.service.method(INTERFACE_NAME, in_signature='sa{sv}', out_signature='b')
		def SetEffect(self, effect_type: str, config: Dict[str, Any]) -> bool:
			"""Replace all effects with a single effect.
			
			Args:
				effect_type: Type of effect ('blur', 'replace', 'brightness', etc.)
				config: Effect configuration dictionary
			
			Returns:
				True if successful, False otherwise
			"""
			try:
				self.effect_controller.set_effect(effect_type, config)
				self.EffectChanged('set', effect_type, config)
				return True
			except Exception as e:
				print(f"Error setting effect: {e}")
				return False
		
		@dbus.service.method(INTERFACE_NAME, in_signature='sa{sv}', out_signature='b')
		def AddEffect(self, effect_type: str, config: Dict[str, Any]) -> bool:
			"""Add an effect to the chain, or update if same type already exists.
			
			Args:
				effect_type: Type of effect to add
				config: Effect configuration dictionary
			
			Returns:
				True if successful, False if error occurred
			"""
			try:
				# Check if effect of this type already exists
				chain = self.effect_controller.get_chain()
				class_to_type = {
					'BackgroundBlur': 'blur',
					'BackgroundReplace': 'replace',
					'BrightnessAdjustment': 'brightness',
					'FaceBeautification': 'beautify',
					'AutoFraming': 'autoframe',
					'EyeGazeCorrection': 'gaze-correct',
				}
				action = 'update'
				for effect, _ in chain.effects:
					effect_class_name = effect.__class__.__name__
					existing_type = class_to_type.get(effect_class_name, 'unknown')
					if existing_type == effect_type:
						action = 'update'
						break
				else:
					action = 'add'
				
				success = self.effect_controller.add_effect(effect_type, config)
				if success:
					self.EffectChanged(action, effect_type, config)
				return success
			except Exception as e:
				print(f"Error adding effect: {e}")
				return False
		
		@dbus.service.method(INTERFACE_NAME, in_signature='i', out_signature='b')
		def RemoveEffect(self, index: int) -> bool:
			"""Remove an effect from the chain by index.
			
			Args:
				index: Index of effect to remove (0-based)
			
			Returns:
				True if successful, False otherwise
			"""
			try:
				self.effect_controller.remove_effect(index)
				self.EffectChanged('remove', str(index), {})
				return True
			except Exception as e:
				print(f"Error removing effect: {e}")
				return False
		
		@dbus.service.method(INTERFACE_NAME, in_signature='s', out_signature='b')
		def RemoveEffectByType(self, effect_type: str) -> bool:
			"""Remove an effect from the chain by type.
			
			Args:
				effect_type: Type of effect to remove ('blur', 'replace', 'brightness', etc.)
			
			Returns:
				True if successful, False if effect not found
			"""
			try:
				success = self.effect_controller.remove_effect_by_type(effect_type)
				if success:
					self.EffectChanged('remove', effect_type, {})
				return success
			except Exception as e:
				print(f"Error removing effect: {e}")
				return False
		
		@dbus.service.method(INTERFACE_NAME, out_signature='b')
		def ClearChain(self) -> bool:
			"""Clear all effects from the chain.
			
			Returns:
				True if successful, False otherwise
			"""
			try:
				self.effect_controller.clear_chain()
				self.EffectChanged('clear', '', {})
				return True
			except Exception as e:
				print(f"Error clearing chain: {e}")
				return False
		
		@dbus.service.method(INTERFACE_NAME, out_signature='a(ssa{sv})')
		def GetCurrentEffects(self) -> List[tuple]:
			"""Get current effect chain.
			
			Returns:
				List of tuples: (effect_type, config_dict) for each effect in chain
				Note: effect_type is inferred from effect class name
			"""
			try:
				chain = self.effect_controller.get_chain()
				result = []
				
				# Map effect class names to effect types
				class_to_type = {
					'BackgroundBlur': 'blur',
					'BackgroundReplace': 'replace',
					'BrightnessAdjustment': 'brightness',
					'FaceBeautification': 'beautify',
					'AutoFraming': 'autoframe',
					'EyeGazeCorrection': 'gaze-correct',
				}
				
				for effect, config in chain.effects:
					effect_class_name = effect.__class__.__name__
					effect_type = class_to_type.get(effect_class_name, 'unknown')
					# Convert config dict to dbus-compatible format
					dbus_config = dbus.Dictionary(config, signature='sv')
					result.append((effect_type, effect_class_name, dbus_config))
				
				return result
			except Exception as e:
				print(f"Error getting effects: {e}")
				return []
		
		@dbus.service.method(INTERFACE_NAME, in_signature='ssv', out_signature='b')
		def UpdateEffectParameter(self, effect_type: str, parameter: str, value: Any) -> bool:
			"""Update a parameter of an effect in the chain.
			
			Args:
				effect_type: Type of effect to update
				parameter: Parameter name (e.g., 'strength', 'brightness')
				value: New parameter value
			
			Returns:
				True if successful, False otherwise
			"""
			try:
				self.effect_controller.update_effect_parameter(effect_type, parameter, value)
				self.EffectChanged('update', effect_type, {parameter: value})
				return True
			except Exception as e:
				print(f"Error updating parameter: {e}")
				return False
		
		@dbus.service.signal(INTERFACE_NAME, signature='ssa{sv}')
		def EffectChanged(self, action: str, effect_type: str, config: Dict[str, Any]):
			"""Signal emitted when effect chain changes.
			
			Args:
				action: Action taken ('set', 'add', 'remove', 'clear', 'update')
				effect_type: Type of effect affected
				config: Configuration dictionary
			"""
			pass
		
		@dbus.service.signal(INTERFACE_NAME, signature='b')
		def CameraStateChanged(self, is_active: bool):
			"""Signal emitted when camera state changes.
			
			Args:
				is_active: True if camera is now active, False if inactive
			"""
			pass


class CamfxControlService:
	"""D-Bus service for controlling camfx effects at runtime."""
	
	def __init__(self, effect_controller):
		"""Initialize D-Bus service.
		
		Args:
			effect_controller: EffectController instance to control
		"""
		if not DBUS_AVAILABLE:
			error_msg = "D-Bus Python bindings not available. Install dbus-python or python-dbus."
			if '_dbus_import_error' in globals():
				error_msg += f" Import error: {_dbus_import_error}"
			raise RuntimeError(error_msg)
		
		self.effect_controller = effect_controller
		self.main_loop: Optional[GLib.MainLoop] = None
		self.loop_thread: Optional[threading.Thread] = None
		self.service_object: Optional[object] = None
		
		# Set up D-Bus main loop
		dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
		
		# Get session bus
		self.bus = dbus.SessionBus()
		
		# Request service name
		try:
			bus_name = dbus.service.BusName(SERVICE_NAME, bus=self.bus, do_not_queue=True)
		except dbus.exceptions.NameExistsException:
			# Service already exists, try to connect to existing one
			print(f"Warning: D-Bus service {SERVICE_NAME} already exists")
			bus_name = dbus.service.BusName(SERVICE_NAME, bus=self.bus)
		
		# Create service object
		self.service_object = CamfxControlServiceObject(bus_name, OBJECT_PATH, self)
	
	def start(self):
		"""Start the D-Bus service main loop."""
		self.main_loop = GLib.MainLoop.new(None, False)
		self.loop_thread = threading.Thread(target=self._run_loop, daemon=True)
		self.loop_thread.start()
		print(f"D-Bus service started: {SERVICE_NAME} on {OBJECT_PATH}")
	
	def _run_loop(self):
		"""Run GLib main loop in separate thread."""
		if self.main_loop:
			self.main_loop.run()
	
	def stop(self):
		"""Stop the D-Bus service."""
		if self.main_loop:
			self.main_loop.quit()
		if self.loop_thread:
			self.loop_thread.join(timeout=2.0)

