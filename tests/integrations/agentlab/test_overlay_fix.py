"""
Tests for SOM Overlay Fix

Tests the Set-of-Mark overlay coordinate fixing functionality.
"""

import numpy as np
import pytest

try:
    from sygra.integrations.agentlab.display.overlay_fix import (
        corrected_overlay_som,
        patch_som_overlay,
    )

    AGENTLAB_AVAILABLE = True
except ImportError:
    AGENTLAB_AVAILABLE = False


@pytest.mark.skipif(not AGENTLAB_AVAILABLE, reason="AgentLab not installed")
class TestSOMOverlayFix:
    """Test SOM overlay coordinate fixing"""

    def test_corrected_overlay_som_basic(self):
        """Test basic corrected overlay SOM functionality"""
        screenshot = np.zeros((300, 400, 3), dtype=np.uint8)
        extra_properties = {}

        result = corrected_overlay_som(screenshot, extra_properties)

        # Should return a valid numpy array
        assert isinstance(result, np.ndarray)

    def test_corrected_overlay_som_with_elements(self):
        """Test corrected overlay SOM with element properties"""
        screenshot = np.zeros((300, 400, 3), dtype=np.uint8)
        extra_properties = {
            "element1": {"bbox": [100, 100, 200, 200]},
            "element2": {"bbox": [50, 50, 150, 150]},
        }

        result = corrected_overlay_som(screenshot, extra_properties)

        assert isinstance(result, np.ndarray)

    def test_patch_som_overlay_callable(self):
        """Test that patch_som_overlay function exists and is callable"""
        assert callable(patch_som_overlay)

    def test_patch_som_overlay_basic(self):
        """Test basic patch_som_overlay functionality"""
        # Should not raise exception
        result = patch_som_overlay()

        # Should return a boolean indicating success/failure
        assert isinstance(result, bool)

    def test_corrected_overlay_som_error_handling(self):
        """Test error handling in corrected overlay SOM"""
        screenshot = np.zeros((100, 100, 3), dtype=np.uint8)

        # Test with various input types
        try:
            result1 = corrected_overlay_som(screenshot, {})
            result2 = corrected_overlay_som(screenshot, {"test": {"bbox": [0, 0, 50, 50]}})

            # Should handle all cases gracefully
            assert isinstance(result1, np.ndarray) or result1 is screenshot
            assert isinstance(result2, np.ndarray) or result2 is screenshot

        except Exception as e:
            # Should not raise unexpected exceptions
            pytest.fail(f"Unexpected exception: {e}")

    def test_module_imports(self):
        """Test that required functions can be imported"""
        from sygra.integrations.agentlab.display.overlay_fix import (
            corrected_overlay_som,
            patch_som_overlay,
        )

        assert corrected_overlay_som is not None
        assert patch_som_overlay is not None

    def test_patch_som_overlay_idempotent(self):
        """Test that patching can be called multiple times"""
        try:
            result1 = patch_som_overlay()
            result2 = patch_som_overlay()
            result3 = patch_som_overlay()

            # All should complete without error
            assert isinstance(result1, bool)
            assert isinstance(result2, bool)
            assert isinstance(result3, bool)

        except Exception as e:
            pytest.fail(f"Multiple patch calls should be safe: {e}")

    def test_corrected_overlay_som_preserves_screenshot_shape(self):
        """Test that overlay function preserves screenshot properties"""
        original_screenshot = np.random.randint(0, 255, (200, 300, 3), dtype=np.uint8)
        extra_properties = {"elem": {"bbox": [10, 10, 50, 50]}}

        result = corrected_overlay_som(original_screenshot, extra_properties)

        # Should return array with reasonable dimensions
        assert isinstance(result, np.ndarray)
        assert len(result.shape) >= 2  # At least 2D

    def test_overlay_fix_integration(self):
        """Test integration between patch and overlay functions"""
        # Test that both main functions exist and work together
        patch_result = patch_som_overlay()

        screenshot = np.zeros((100, 100, 3), dtype=np.uint8)
        overlay_result = corrected_overlay_som(screenshot, {})

        assert isinstance(patch_result, bool)
        assert isinstance(overlay_result, np.ndarray)

    def test_different_screenshot_sizes(self):
        """Test overlay function with different screenshot sizes"""
        sizes = [(100, 100, 3), (400, 600, 3), (768, 1024, 3)]

        for size in sizes:
            screenshot = np.zeros(size, dtype=np.uint8)
            result = corrected_overlay_som(screenshot, {})

            assert isinstance(result, np.ndarray)
            # Result should have reasonable dimensions
            assert len(result.shape) >= 2
