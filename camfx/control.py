"""Effect chain and controller for managing effects at runtime."""

import threading
from typing import Optional, List, Dict, Any
import numpy as np

from .effects import (
	BackgroundBlur, BackgroundReplace, BrightnessAdjustment,
	FaceBeautification, AutoFraming, EyeGazeCorrection
)


class EffectChain:
	"""Manages a chain of effects to apply in sequence."""
	
	def __init__(self):
		self.effects: List[tuple] = []  # List of (effect_instance, config_dict)
	
	def add_effect(self, effect_type: str, config: Dict[str, Any]) -> bool:
		"""Add an effect to the chain, or update if same type already exists.
		
		Args:
			effect_type: Type of effect ('blur', 'replace', 'brightness', etc.)
			config: Effect configuration dictionary
		
		Returns:
			True if effect was added or updated successfully
		"""
		# Map effect class names to effect types for comparison
		class_to_type = {
			'BackgroundBlur': 'blur',
			'BackgroundReplace': 'replace',
			'BrightnessAdjustment': 'brightness',
			'FaceBeautification': 'beautify',
			'AutoFraming': 'autoframe',
			'EyeGazeCorrection': 'gaze-correct',
		}
		
		# Check if effect of this type already exists
		for i, (existing_effect, existing_config) in enumerate(self.effects):
			existing_class_name = existing_effect.__class__.__name__
			existing_type = class_to_type.get(existing_class_name, 'unknown')
			
			# If same effect type exists, update it (replace effect and config)
			if existing_type == effect_type:
				effect = self._create_effect(effect_type)
				self.effects[i] = (effect, config)
				return True
		
		# No effect of this type exists, add it
		effect = self._create_effect(effect_type)
		self.effects.append((effect, config))
		return True
	
	def remove_effect(self, index: int):
		"""Remove an effect from the chain.
		
		Args:
			index: Index of effect to remove (0-based)
		"""
		if 0 <= index < len(self.effects):
			del self.effects[index]
	
	def remove_effect_by_type(self, effect_type: str) -> bool:
		"""Remove an effect from the chain by type.
		
		Args:
			effect_type: Type of effect to remove ('blur', 'replace', 'brightness', etc.)
		
		Returns:
			True if effect was found and removed, False otherwise
		"""
		# Map effect class names to effect types for comparison
		class_to_type = {
			'BackgroundBlur': 'blur',
			'BackgroundReplace': 'replace',
			'BrightnessAdjustment': 'brightness',
			'FaceBeautification': 'beautify',
			'AutoFraming': 'autoframe',
			'EyeGazeCorrection': 'gaze-correct',
		}
		
		for i, (effect, _) in enumerate(self.effects):
			effect_class_name = effect.__class__.__name__
			existing_type = class_to_type.get(effect_class_name, 'unknown')
			
			if existing_type == effect_type:
				del self.effects[i]
				return True
		
		return False
	
	def clear(self):
		"""Clear all effects."""
		self.effects = []
	
	def _create_effect(self, effect_type: str):
		"""Create an effect instance based on type."""
		if effect_type == 'blur':
			return BackgroundBlur()
		elif effect_type == 'replace':
			return BackgroundReplace()
		elif effect_type == 'brightness':
			return BrightnessAdjustment()
		elif effect_type == 'beautify':
			return FaceBeautification()
		elif effect_type == 'autoframe':
			return AutoFraming()
		elif effect_type == 'gaze-correct':
			return EyeGazeCorrection()
		else:
			raise ValueError(f"Unknown effect_type: {effect_type}")
	
	def apply(self, frame: np.ndarray, mask: Optional[np.ndarray], **kwargs) -> np.ndarray:
		"""Apply all effects in sequence.
		
		Args:
			frame: Input frame (BGR format)
			mask: Optional segmentation mask
			**kwargs: Additional parameters to pass to effects
		
		Returns:
			Processed frame
		"""
		result = frame
		current_mask = mask
		
		for effect, config in self.effects:
			# Determine if this effect needs a mask
			needs_mask = effect.__class__.__name__ in ['BackgroundBlur', 'BackgroundReplace']
			
			# Merge config with kwargs (kwargs take precedence)
			effect_kwargs = {**config, **kwargs}
			
			# Apply effect
			if needs_mask and current_mask is not None:
				result = effect.apply(result, current_mask, **effect_kwargs)
			else:
				# For effects that don't need mask, pass None
				# Some effects like BrightnessAdjustment may use mask if face_only=True
				if effect.__class__.__name__ == 'BrightnessAdjustment' and effect_kwargs.get('face_only', False):
					# Brightness with face_only needs mask
					result = effect.apply(result, current_mask, **effect_kwargs)
				else:
					result = effect.apply(result, None, **effect_kwargs)
			
			# Note: Some effects might modify the mask in the future
			# For now, mask stays the same through the chain
		
		return result
	
	def __len__(self):
		"""Return number of effects in chain."""
		return len(self.effects)
	
	def __iter__(self):
		"""Iterate over (effect_type, config) tuples."""
		# We need to track effect types - store them in config or infer from instance
		# For now, return (effect_instance, config)
		return iter(self.effects)


class EffectController:
	"""Thread-safe controller for managing effects."""
	
	def __init__(self):
		self.chain = EffectChain()
		self.lock = threading.Lock()
	
	def set_effect(self, effect_type: str, config: Dict[str, Any]):
		"""Replace all effects with a single effect.
		
		Args:
			effect_type: Type of effect ('blur', 'replace', 'brightness', etc.)
			config: Effect configuration dictionary
		"""
		with self.lock:
			self.chain.clear()
			self.chain.add_effect(effect_type, config)
	
	def add_effect(self, effect_type: str, config: Dict[str, Any]) -> bool:
		"""Add an effect to the chain.
		
		Args:
			effect_type: Type of effect to add
			config: Effect configuration dictionary
		
		Returns:
			True if effect was added, False if duplicate was detected
		"""
		with self.lock:
			return self.chain.add_effect(effect_type, config)
	
	def remove_effect(self, index: int):
		"""Remove an effect from the chain by index.
		
		Args:
			index: Index of effect to remove (0-based)
		"""
		with self.lock:
			self.chain.remove_effect(index)
	
	def remove_effect_by_type(self, effect_type: str) -> bool:
		"""Remove an effect from the chain by type.
		
		Args:
			effect_type: Type of effect to remove ('blur', 'replace', 'brightness', etc.)
		
		Returns:
			True if effect was found and removed, False otherwise
		"""
		with self.lock:
			return self.chain.remove_effect_by_type(effect_type)
	
	def clear_chain(self):
		"""Clear all effects from the chain."""
		with self.lock:
			self.chain.clear()
	
	def get_chain(self) -> EffectChain:
		"""Get current effect chain (thread-safe copy).
		
		Returns:
			A copy of the current effect chain
		"""
		with self.lock:
			# Return a copy to avoid race conditions
			chain_copy = EffectChain()
			# Deep copy effects list
			chain_copy.effects = [(effect, config.copy()) for effect, config in self.chain.effects]
			return chain_copy
	
	def update_effect_parameter(self, effect_type: str, parameter: str, value: Any):
		"""Update a parameter of an effect in the chain.
		
		Args:
			effect_type: Type of effect to update
			parameter: Parameter name (e.g., 'strength', 'brightness')
			value: New parameter value
		"""
		with self.lock:
			# Find first effect of this type and update its config
			for effect, config in self.chain.effects:
				# Check if effect matches type by class name
				effect_class_name = effect.__class__.__name__
				expected_class_names = {
					'blur': 'BackgroundBlur',
					'replace': 'BackgroundReplace',
					'brightness': 'BrightnessAdjustment',
					'beautify': 'FaceBeautification',
					'autoframe': 'AutoFraming',
					'gaze-correct': 'EyeGazeCorrection',
				}
				if effect_class_name == expected_class_names.get(effect_type):
					config[parameter] = value
					return
			raise ValueError(f"Effect type '{effect_type}' not found in chain")

