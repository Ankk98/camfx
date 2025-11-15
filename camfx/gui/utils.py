"""Utility functions for GUI."""

from typing import Dict, Any


def format_effect_name(effect_type: str) -> str:
	"""Format effect type name for display.
	
	Args:
		effect_type: Effect type string (e.g., 'blur', 'gaze-correct')
	
	Returns:
		Formatted display name
	"""
	name_map = {
		'blur': 'Background Blur',
		'replace': 'Background Replace',
		'brightness': 'Brightness Adjustment',
		'beautify': 'Face Beautification',
		'autoframe': 'Auto Framing',
		'gaze-correct': 'Eye Gaze Correction',
	}
	return name_map.get(effect_type, effect_type.replace('-', ' ').title())


def format_parameter_name(parameter: str) -> str:
	"""Format parameter name for display.
	
	Args:
		parameter: Parameter name (e.g., 'strength', 'face_only')
	
	Returns:
		Formatted display name
	"""
	name_map = {
		'strength': 'Strength',
		'background': 'Background Image',
		'brightness': 'Brightness',
		'contrast': 'Contrast',
		'face_only': 'Face Only',
		'smoothness': 'Smoothness',
		'padding': 'Padding',
		'min_zoom': 'Min Zoom',
		'max_zoom': 'Max Zoom',
	}
	return name_map.get(parameter, parameter.replace('_', ' ').title())


def get_effect_defaults(effect_type: str) -> Dict[str, Any]:
	"""Get default parameter values for an effect.
	
	Args:
		effect_type: Effect type string
	
	Returns:
		Dictionary of default parameter values
	"""
	defaults = {
		'blur': {'strength': 25},
		'replace': {'background': None},
		'brightness': {'brightness': 0, 'contrast': 1.0, 'face_only': False},
		'beautify': {'smoothness': 5},
		'autoframe': {'padding': 0.3, 'min_zoom': 1.0, 'max_zoom': 2.0},
		'gaze-correct': {'strength': 0.5},
	}
	return defaults.get(effect_type, {})

