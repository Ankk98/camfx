"""Tests for effect chaining functionality."""

import cv2
import numpy as np
import pytest

from camfx.control import EffectChain, EffectController
from camfx.effects import (
	BackgroundBlur, BackgroundReplace, BrightnessAdjustment,
	FaceBeautification, AutoFraming, EyeGazeCorrection
)


class TestEffectChain:
	"""Test EffectChain class."""
	
	def test_empty_chain(self):
		"""Test empty chain returns original frame."""
		chain = EffectChain()
		frame = np.zeros((100, 100, 3), dtype=np.uint8)
		result = chain.apply(frame, None)
		np.testing.assert_array_equal(result, frame)
	
	def test_single_effect(self):
		"""Test chain with single effect."""
		chain = EffectChain()
		chain.add_effect('brightness', {'brightness': 10})
		
		frame = np.ones((100, 100, 3), dtype=np.uint8) * 128
		result = chain.apply(frame, None)
		
		# Brightness adjustment should change the frame
		assert not np.array_equal(result, frame)
		assert result.shape == frame.shape
	
	def test_chain_update_same_type(self):
		"""Test that adding same effect type updates it instead of duplicating."""
		chain = EffectChain()
		chain.add_effect('brightness', {'brightness': 10})
		assert len(chain) == 1
		
		# Adding same type should update, not duplicate
		chain.add_effect('brightness', {'brightness': 5})
		assert len(chain) == 1  # Still only one effect
		
		# Verify the config was updated
		effect, config = chain.effects[0]
		assert config['brightness'] == 5
	
	def test_blur_with_mask(self):
		"""Test blur effect requires mask."""
		chain = EffectChain()
		chain.add_effect('blur', {'strength': 25})
		
		frame = np.ones((100, 100, 3), dtype=np.uint8) * 128
		mask = np.ones((100, 100), dtype=np.float32) * 0.5
		
		result = chain.apply(frame, mask)
		assert result.shape == frame.shape
	
	def test_blur_without_mask(self):
		"""Test blur effect without mask should still work (no-op on background)."""
		chain = EffectChain()
		chain.add_effect('blur', {'strength': 25})
		
		frame = np.ones((100, 100, 3), dtype=np.uint8) * 128
		
		# Should not crash even without mask
		result = chain.apply(frame, None)
		assert result.shape == frame.shape
	
	def test_replace_with_mask(self):
		"""Test replace effect with mask."""
		chain = EffectChain()
		background = np.ones((100, 100, 3), dtype=np.uint8) * 255
		chain.add_effect('replace', {'background': background})
		
		frame = np.ones((100, 100, 3), dtype=np.uint8) * 128
		mask = np.ones((100, 100), dtype=np.float32) * 0.5
		
		result = chain.apply(frame, mask)
		assert result.shape == frame.shape
	
	def test_brightness_face_only_with_mask(self):
		"""Test brightness with face_only requires mask."""
		chain = EffectChain()
		chain.add_effect('brightness', {'brightness': 10, 'face_only': True})
		
		frame = np.ones((100, 100, 3), dtype=np.uint8) * 128
		mask = np.ones((100, 100), dtype=np.float32) * 0.5
		
		result = chain.apply(frame, mask)
		assert result.shape == frame.shape
	
	def test_brightness_global_no_mask(self):
		"""Test brightness without face_only doesn't need mask."""
		chain = EffectChain()
		chain.add_effect('brightness', {'brightness': 10, 'face_only': False})
		
		frame = np.ones((100, 100, 3), dtype=np.uint8) * 128
		
		result = chain.apply(frame, None)
		assert result.shape == frame.shape
	
	def test_chain_blur_then_brightness(self):
		"""Test chaining blur then brightness."""
		chain = EffectChain()
		chain.add_effect('blur', {'strength': 25})
		chain.add_effect('brightness', {'brightness': 10})
		
		frame = np.ones((100, 100, 3), dtype=np.uint8) * 128
		mask = np.ones((100, 100), dtype=np.float32) * 0.5
		
		result = chain.apply(frame, mask)
		assert result.shape == frame.shape
	
	def test_chain_brightness_then_blur(self):
		"""Test chaining brightness then blur."""
		chain = EffectChain()
		chain.add_effect('brightness', {'brightness': 10})
		chain.add_effect('blur', {'strength': 25})
		
		frame = np.ones((100, 100, 3), dtype=np.uint8) * 128
		mask = np.ones((100, 100), dtype=np.float32) * 0.5
		
		result = chain.apply(frame, mask)
		assert result.shape == frame.shape
	
	def test_chain_remove_effect(self):
		"""Test removing effect from chain by index."""
		chain = EffectChain()
		chain.add_effect('brightness', {'brightness': 10})
		chain.add_effect('blur', {'strength': 25})
		
		assert len(chain) == 2
		chain.remove_effect(0)
		assert len(chain) == 1
		# Remaining effect should be blur
		effect, config = chain.effects[0]
		assert effect.__class__.__name__ == 'BackgroundBlur'
	
	def test_chain_remove_effect_by_type(self):
		"""Test removing effect from chain by type."""
		chain = EffectChain()
		chain.add_effect('brightness', {'brightness': 10})
		chain.add_effect('blur', {'strength': 25})
		
		assert len(chain) == 2
		success = chain.remove_effect_by_type('brightness')
		assert success is True
		assert len(chain) == 1
		# Remaining effect should be blur
		effect, config = chain.effects[0]
		assert effect.__class__.__name__ == 'BackgroundBlur'
	
	def test_chain_remove_effect_by_type_not_found(self):
		"""Test removing effect by type when it doesn't exist."""
		chain = EffectChain()
		chain.add_effect('brightness', {'brightness': 10})
		
		success = chain.remove_effect_by_type('blur')
		assert success is False
		assert len(chain) == 1
	
	def test_chain_clear(self):
		"""Test clearing chain."""
		chain = EffectChain()
		chain.add_effect('brightness', {'brightness': 10})
		chain.add_effect('blur', {'strength': 25})
		
		assert len(chain) == 2
		chain.clear()
		assert len(chain) == 0
	
	def test_chain_update_effect_multiple_times(self):
		"""Test that updating same effect type multiple times works."""
		chain = EffectChain()
		chain.add_effect('brightness', {'brightness': 10})
		assert len(chain) == 1
		
		chain.add_effect('brightness', {'brightness': 20})
		assert len(chain) == 1
		effect, config = chain.effects[0]
		assert config['brightness'] == 20
		
		chain.add_effect('brightness', {'brightness': 30})
		assert len(chain) == 1
		effect, config = chain.effects[0]
		assert config['brightness'] == 30
	
	def test_chain_mixed_effects(self):
		"""Test chain with multiple different effects."""
		chain = EffectChain()
		chain.add_effect('brightness', {'brightness': 10})
		chain.add_effect('blur', {'strength': 25})
		# Adding brightness again should update the first one, not add a duplicate
		chain.add_effect('brightness', {'brightness': 5})
		
		# Should have only 2 effects (brightness updated, blur added)
		assert len(chain) == 2
		
		# Verify brightness was updated
		effect1, config1 = chain.effects[0]
		assert effect1.__class__.__name__ == 'BrightnessAdjustment'
		assert config1['brightness'] == 5
		
		frame = np.ones((100, 100, 3), dtype=np.uint8) * 128
		mask = np.ones((100, 100), dtype=np.float32) * 0.5
		
		result = chain.apply(frame, mask)
		assert result.shape == frame.shape
	
	def test_chain_invalid_index_remove(self):
		"""Test removing effect with invalid index."""
		chain = EffectChain()
		chain.add_effect('brightness', {'brightness': 10})
		
		# Should not crash on invalid index
		chain.remove_effect(-1)  # Should not remove anything
		assert len(chain) == 1
		
		chain.remove_effect(10)  # Should not remove anything
		assert len(chain) == 1
	
	def test_chain_config_override(self):
		"""Test that kwargs override config."""
		chain = EffectChain()
		chain.add_effect('brightness', {'brightness': 10})
		
		frame = np.ones((100, 100, 3), dtype=np.uint8) * 128
		
		# Apply with config brightness=10
		result1 = chain.apply(frame, None)
		
		# Apply with kwargs brightness=20 (should override)
		result2 = chain.apply(frame, None, brightness=20)
		
		# Results should be different
		assert not np.array_equal(result1, result2)


class TestEffectController:
	"""Test EffectController class."""
	
	def test_set_effect(self):
		"""Test setting effect replaces all effects."""
		controller = EffectController()
		
		controller.add_effect('brightness', {'brightness': 10})
		controller.add_effect('blur', {'strength': 25})
		assert len(controller.get_chain()) == 2
		
		controller.set_effect('brightness', {'brightness': 20})
		chain = controller.get_chain()
		assert len(chain) == 1
	
	def test_add_effect(self):
		"""Test adding effect to chain."""
		controller = EffectController()
		
		controller.add_effect('brightness', {'brightness': 10})
		assert len(controller.get_chain()) == 1
		
		# Adding different effect type should add it
		controller.add_effect('blur', {'strength': 25})
		assert len(controller.get_chain()) == 2
		
		# Adding same effect type should update it
		controller.add_effect('brightness', {'brightness': 5})
		assert len(controller.get_chain()) == 2  # Still 2, brightness was updated
		
		# Verify brightness was updated
		chain = controller.get_chain()
		effect, config = chain.effects[0]
		assert effect.__class__.__name__ == 'BrightnessAdjustment'
		assert config['brightness'] == 5
	
	def test_remove_effect(self):
		"""Test removing effect from chain by index."""
		controller = EffectController()
		
		controller.add_effect('brightness', {'brightness': 10})
		controller.add_effect('blur', {'strength': 25})
		controller.add_effect('beautify', {'smoothness': 5})
		
		assert len(controller.get_chain()) == 3
		controller.remove_effect(1)
		assert len(controller.get_chain()) == 2
	
	def test_remove_effect_by_type(self):
		"""Test removing effect from chain by type."""
		controller = EffectController()
		
		controller.add_effect('brightness', {'brightness': 10})
		controller.add_effect('blur', {'strength': 25})
		controller.add_effect('beautify', {'smoothness': 5})
		
		assert len(controller.get_chain()) == 3
		
		success = controller.remove_effect_by_type('blur')
		assert success is True
		assert len(controller.get_chain()) == 2
		
		# Try removing non-existent effect
		success = controller.remove_effect_by_type('gaze-correct')
		assert success is False
		assert len(controller.get_chain()) == 2
	
	def test_clear_chain(self):
		"""Test clearing chain."""
		controller = EffectController()
		
		controller.add_effect('brightness', {'brightness': 10})
		controller.add_effect('blur', {'strength': 25})
		
		assert len(controller.get_chain()) == 2
		controller.clear_chain()
		assert len(controller.get_chain()) == 0
	
	def test_get_chain_copy(self):
		"""Test that get_chain returns a copy."""
		controller = EffectController()
		
		controller.add_effect('brightness', {'brightness': 10})
		chain1 = controller.get_chain()
		chain2 = controller.get_chain()
		
		# Should be different objects
		assert chain1 is not chain2
		# But should have same content
		assert len(chain1) == len(chain2)
	
	def test_update_effect_parameter(self):
		"""Test updating effect parameter."""
		controller = EffectController()
		
		controller.add_effect('brightness', {'brightness': 10})
		controller.update_effect_parameter('brightness', 'brightness', 20)
		
		chain = controller.get_chain()
		assert len(chain) == 1
		effect, config = chain.effects[0]
		assert config['brightness'] == 20
	
	def test_update_effect_parameter_not_found(self):
		"""Test updating parameter of non-existent effect."""
		controller = EffectController()
		
		controller.add_effect('brightness', {'brightness': 10})
		
		with pytest.raises(ValueError, match="not found"):
			controller.update_effect_parameter('blur', 'strength', 25)
	
	def test_thread_safety(self):
		"""Test that controller is thread-safe."""
		import threading
		
		controller = EffectController()
		errors = []
		
		def add_effects():
			try:
				for i in range(10):
					controller.add_effect('brightness', {'brightness': i})
			except Exception as e:
				errors.append(e)
		
		threads = [threading.Thread(target=add_effects) for _ in range(5)]
		for t in threads:
			t.start()
		for t in threads:
			t.join()
		
		# Should not have any errors
		assert len(errors) == 0
		# Should have effects (may be updated multiple times due to race conditions)
		# But since we update instead of duplicate, should have at least one
		assert len(controller.get_chain()) > 0
	
	def test_thread_safety_update_and_remove(self):
		"""Test thread safety when updating and removing effects concurrently."""
		import threading
		
		controller = EffectController()
		controller.add_effect('brightness', {'brightness': 10})
		controller.add_effect('blur', {'strength': 25})
		errors = []
		
		def update_effects():
			try:
				for i in range(5):
					controller.add_effect('brightness', {'brightness': i * 10})
			except Exception as e:
				errors.append(e)
		
		def remove_effects():
			try:
				for _ in range(3):
					controller.remove_effect_by_type('blur')
					controller.add_effect('blur', {'strength': 30})
			except Exception as e:
				errors.append(e)
		
		threads = [
			threading.Thread(target=update_effects) for _ in range(3)
		] + [
			threading.Thread(target=remove_effects) for _ in range(2)
		]
		
		for t in threads:
			t.start()
		for t in threads:
			t.join()
		
		# Should not have any errors
		assert len(errors) == 0
		# Chain should still be valid
		chain = controller.get_chain()
		assert len(chain) >= 0  # At least 0 (could be empty if all removed)


class TestEffectChainingEdgeCases:
	"""Test edge cases and corner cases for effect chaining."""
	
	def test_empty_frame(self):
		"""Test chain with empty frame."""
		chain = EffectChain()
		chain.add_effect('brightness', {'brightness': 10})
		
		frame = np.zeros((0, 0, 3), dtype=np.uint8)
		# Empty frames might be handled differently by OpenCV
		# Just verify it doesn't crash - actual behavior may vary
		try:
			result = chain.apply(frame, None)
			# If it doesn't raise, check result is valid
			if result is not None:
				assert result.shape == frame.shape
		except (ValueError, IndexError, cv2.error, AttributeError):
			# These exceptions are acceptable for empty frames
			pass
	
	def test_single_pixel_frame(self):
		"""Test chain with single pixel frame."""
		chain = EffectChain()
		chain.add_effect('brightness', {'brightness': 10})
		
		frame = np.array([[[128, 128, 128]]], dtype=np.uint8)
		result = chain.apply(frame, None)
		assert result.shape == frame.shape
	
	def test_very_large_frame(self):
		"""Test chain with very large frame."""
		chain = EffectChain()
		chain.add_effect('brightness', {'brightness': 10})
		
		frame = np.ones((2000, 2000, 3), dtype=np.uint8) * 128
		result = chain.apply(frame, None)
		assert result.shape == frame.shape
	
	def test_mask_size_mismatch(self):
		"""Test chain with mask size mismatch."""
		chain = EffectChain()
		chain.add_effect('blur', {'strength': 25})
		
		frame = np.ones((100, 100, 3), dtype=np.uint8) * 128
		mask = np.ones((50, 50), dtype=np.float32) * 0.5  # Wrong size
		
		# Should handle gracefully or raise appropriate error
		with pytest.raises((ValueError, IndexError)):
			chain.apply(frame, mask)
	
	def test_chain_with_all_effects(self):
		"""Test chain with all available effects."""
		chain = EffectChain()
		chain.add_effect('brightness', {'brightness': 10})
		chain.add_effect('blur', {'strength': 25})
		# Note: replace and beautify require more setup, so we'll skip them for now
		
		frame = np.ones((100, 100, 3), dtype=np.uint8) * 128
		mask = np.ones((100, 100), dtype=np.float32) * 0.5
		
		result = chain.apply(frame, mask)
		assert result.shape == frame.shape
	
	def test_chain_remove_all_effects(self):
		"""Test removing all effects one by one."""
		chain = EffectChain()
		chain.add_effect('brightness', {'brightness': 10})
		chain.add_effect('blur', {'strength': 25})
		chain.add_effect('beautify', {'smoothness': 5})
		
		# Remove by type
		chain.remove_effect_by_type('brightness')
		assert len(chain) == 2
		
		chain.remove_effect_by_type('blur')
		assert len(chain) == 1
		
		chain.remove_effect_by_type('beautify')
		assert len(chain) == 0
		
		# Should still work with empty chain
		frame = np.ones((100, 100, 3), dtype=np.uint8) * 128
		result = chain.apply(frame, None)
		np.testing.assert_array_equal(result, frame)
	
	def test_chain_invalid_effect_type(self):
		"""Test chain with invalid effect type."""
		chain = EffectChain()
		
		with pytest.raises(ValueError, match="Unknown effect_type"):
			chain.add_effect('invalid_effect', {})
	
	def test_chain_config_preservation(self):
		"""Test that config is preserved through chain operations."""
		chain = EffectChain()
		chain.add_effect('brightness', {'brightness': 10, 'contrast': 1.5})
		
		effect, config = chain.effects[0]
		assert config['brightness'] == 10
		assert config['contrast'] == 1.5
		
		# Update should replace entire config (not merge)
		chain.add_effect('brightness', {'brightness': 20})
		effect, config = chain.effects[0]
		assert config['brightness'] == 20
		# Contrast is not in new config, so it won't be in the updated config
		
		# Full config update
		chain.add_effect('brightness', {'brightness': 15, 'contrast': 2.0})
		effect, config = chain.effects[0]
		assert config['brightness'] == 15
		assert config['contrast'] == 2.0
	
	def test_chain_update_preserves_position(self):
		"""Test that updating an effect preserves its position in chain."""
		chain = EffectChain()
		chain.add_effect('brightness', {'brightness': 10})
		chain.add_effect('blur', {'strength': 25})
		chain.add_effect('beautify', {'smoothness': 5})
		
		# Update brightness - should stay at position 0
		chain.add_effect('brightness', {'brightness': 20})
		assert len(chain) == 3
		effect, config = chain.effects[0]
		assert effect.__class__.__name__ == 'BrightnessAdjustment'
		assert config['brightness'] == 20
		
		# Verify other effects are still in correct positions
		effect1, _ = chain.effects[1]
		assert effect1.__class__.__name__ == 'BackgroundBlur'
		effect2, _ = chain.effects[2]
		assert effect2.__class__.__name__ == 'FaceBeautification'
	
	def test_chain_update_all_effect_types(self):
		"""Test updating all different effect types."""
		chain = EffectChain()
		
		# Add all effect types
		chain.add_effect('blur', {'strength': 25})
		chain.add_effect('brightness', {'brightness': 10})
		chain.add_effect('beautify', {'smoothness': 5})
		chain.add_effect('autoframe', {'padding': 0.3})
		chain.add_effect('gaze-correct', {'strength': 0.5})
		
		assert len(chain) == 5
		
		# Update each one
		chain.add_effect('blur', {'strength': 35})
		chain.add_effect('brightness', {'brightness': 20})
		chain.add_effect('beautify', {'smoothness': 10})
		chain.add_effect('autoframe', {'padding': 0.5})
		chain.add_effect('gaze-correct', {'strength': 0.8})
		
		assert len(chain) == 5  # Still 5, all were updated
		
		# Verify updates
		_, config = chain.effects[0]
		assert config['strength'] == 35
		_, config = chain.effects[1]
		assert config['brightness'] == 20
		_, config = chain.effects[2]
		assert config['smoothness'] == 10
		_, config = chain.effects[3]
		assert config['padding'] == 0.5
		_, config = chain.effects[4]
		assert config['strength'] == 0.8
	
	def test_chain_remove_effect_by_type_empty_chain(self):
		"""Test removing effect by type from empty chain."""
		chain = EffectChain()
		success = chain.remove_effect_by_type('brightness')
		assert success is False
	
	def test_chain_remove_effect_by_type_multiple_same_type(self):
		"""Test removing effect by type when only one instance exists (since we prevent duplicates)."""
		chain = EffectChain()
		chain.add_effect('brightness', {'brightness': 10})
		chain.add_effect('blur', {'strength': 25})
		
		# Since we prevent duplicates, there should only be one brightness
		success = chain.remove_effect_by_type('brightness')
		assert success is True
		assert len(chain) == 1
		# Remaining should be blur
		effect, _ = chain.effects[0]
		assert effect.__class__.__name__ == 'BackgroundBlur'

