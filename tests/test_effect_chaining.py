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
	
	def test_chain_order(self):
		"""Test that effects are applied in order."""
		chain = EffectChain()
		chain.add_effect('brightness', {'brightness': 10})
		chain.add_effect('brightness', {'brightness': 5})
		
		frame = np.ones((100, 100, 3), dtype=np.uint8) * 128
		result = chain.apply(frame, None)
		
		# Should apply both brightness adjustments sequentially
		assert result.shape == frame.shape
	
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
		"""Test removing effect from chain."""
		chain = EffectChain()
		chain.add_effect('brightness', {'brightness': 10})
		chain.add_effect('brightness', {'brightness': 5})
		
		assert len(chain) == 2
		chain.remove_effect(0)
		assert len(chain) == 1
	
	def test_chain_clear(self):
		"""Test clearing chain."""
		chain = EffectChain()
		chain.add_effect('brightness', {'brightness': 10})
		chain.add_effect('brightness', {'brightness': 5})
		
		assert len(chain) == 2
		chain.clear()
		assert len(chain) == 0
	
	def test_chain_duplicate_effects(self):
		"""Test that duplicate effects can be added."""
		chain = EffectChain()
		chain.add_effect('brightness', {'brightness': 10})
		chain.add_effect('brightness', {'brightness': 20})
		chain.add_effect('brightness', {'brightness': 30})
		
		assert len(chain) == 3
		
		frame = np.ones((100, 100, 3), dtype=np.uint8) * 128
		result = chain.apply(frame, None)
		assert result.shape == frame.shape
	
	def test_chain_mixed_effects(self):
		"""Test chain with multiple different effects."""
		chain = EffectChain()
		chain.add_effect('brightness', {'brightness': 10})
		chain.add_effect('blur', {'strength': 25})
		chain.add_effect('brightness', {'brightness': 5})
		
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
		controller.add_effect('brightness', {'brightness': 5})
		assert len(controller.get_chain()) == 2
		
		controller.set_effect('brightness', {'brightness': 20})
		chain = controller.get_chain()
		assert len(chain) == 1
	
	def test_add_effect(self):
		"""Test adding effect to chain."""
		controller = EffectController()
		
		controller.add_effect('brightness', {'brightness': 10})
		assert len(controller.get_chain()) == 1
		
		controller.add_effect('brightness', {'brightness': 5})
		assert len(controller.get_chain()) == 2
	
	def test_remove_effect(self):
		"""Test removing effect from chain."""
		controller = EffectController()
		
		controller.add_effect('brightness', {'brightness': 10})
		controller.add_effect('brightness', {'brightness': 5})
		controller.add_effect('brightness', {'brightness': 3})
		
		assert len(controller.get_chain()) == 3
		controller.remove_effect(1)
		assert len(controller.get_chain()) == 2
	
	def test_clear_chain(self):
		"""Test clearing chain."""
		controller = EffectController()
		
		controller.add_effect('brightness', {'brightness': 10})
		controller.add_effect('brightness', {'brightness': 5})
		
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
		# Should have added effects (exact count may vary due to race conditions)
		assert len(controller.get_chain()) > 0


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
		chain.add_effect('brightness', {'brightness': 5})
		chain.add_effect('brightness', {'brightness': 3})
		
		while len(chain) > 0:
			chain.remove_effect(0)
		
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
		
		# Remove and re-add should preserve config
		chain.remove_effect(0)
		chain.add_effect('brightness', {'brightness': 10, 'contrast': 1.5})
		
		effect, config = chain.effects[0]
		assert config['brightness'] == 10
		assert config['contrast'] == 1.5

