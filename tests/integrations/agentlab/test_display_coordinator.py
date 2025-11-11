"""
Tests for Display Coordinator

Tests coordinate scaling detection and display environment setup.
"""

from unittest.mock import patch

import numpy as np
import pytest

try:
    from sygra.integrations.agentlab.display.coordinator import (
        detect_coordinate_scaling,
        setup_display_environment,
    )

    AGENTLAB_AVAILABLE = True
except ImportError:
    AGENTLAB_AVAILABLE = False


@pytest.mark.skipif(not AGENTLAB_AVAILABLE, reason="AgentLab not installed")
class TestCoordinateDetection:
    """Test coordinate scaling detection"""

    def test_detect_coordinate_scaling_2x_detected(self):
        """Test detection of 2x coordinate scaling"""
        # Mock a screenshot at 400x300
        screenshot = np.zeros((300, 400, 3), dtype=np.uint8)

        # Mock properties with coordinates that are 2x the screenshot size
        # The function expects extra_properties.values() to contain dicts with "bbox"
        extra_properties = {
            "element1": {
                "bbox": [0, 0, 800, 600]
            },  # 2x screenshot size: 800 > 400*1.5, 600 > 300*1.5
            "element2": {"bbox": [100, 100, 700, 500]},  # Also larger than 1.5x
        }

        result = detect_coordinate_scaling(screenshot, extra_properties)

        assert result is True

    def test_detect_coordinate_scaling_no_scaling_needed(self):
        """Test detection when no scaling is needed"""
        # Mock a screenshot at 400x300
        screenshot = np.zeros((300, 400, 3), dtype=np.uint8)

        # Mock properties with coordinates that are within normal range
        extra_properties = {
            "element1": {"bbox": [0, 0, 400, 300]},  # Same as screenshot size
            "element2": {"bbox": [50, 50, 350, 250]},  # Smaller than screenshot
        }

        result = detect_coordinate_scaling(screenshot, extra_properties)

        assert result is False

    def test_detect_coordinate_scaling_empty_properties(self):
        """Test detection with empty properties"""
        screenshot = np.zeros((300, 400, 3), dtype=np.uint8)
        extra_properties = {}

        result = detect_coordinate_scaling(screenshot, extra_properties)

        assert result is False

    def test_detect_coordinate_scaling_no_elements(self):
        """Test detection with no elements in properties"""
        screenshot = np.zeros((300, 400, 3), dtype=np.uint8)
        extra_properties = {}  # Empty properties

        result = detect_coordinate_scaling(screenshot, extra_properties)

        assert result is False

    def test_detect_coordinate_scaling_invalid_screenshot(self):
        """Test detection with invalid screenshot"""
        screenshot = None
        extra_properties = {"element1": {"bbox": [0, 0, 400, 300]}}

        result = detect_coordinate_scaling(screenshot, extra_properties)

        assert result is False


@pytest.mark.skipif(not AGENTLAB_AVAILABLE, reason="AgentLab not installed")
class TestDisplayEnvironmentSetup:
    """Test display environment setup"""

    @patch("os.environ")
    @patch("platform.system")
    def test_setup_display_environment_macos(self, mock_system, mock_environ):
        """Test setup on macOS"""
        mock_system.return_value = "Darwin"

        setup_display_environment()

        # Should complete without error
        assert True

    @patch("os.environ")
    @patch("platform.system")
    def test_setup_display_environment_linux(self, mock_system, mock_environ):
        """Test setup on Linux"""
        mock_system.return_value = "Linux"

        setup_display_environment()

        # Should complete without error
        assert True

    @patch("os.environ")
    @patch("platform.system")
    def test_setup_display_environment_windows(self, mock_system, mock_environ):
        """Test setup on Windows"""
        mock_system.return_value = "Windows"

        setup_display_environment()

        # Should complete without error
        assert True

    def test_setup_completes_successfully(self):
        """Test that setup completes successfully"""
        # Should complete without error
        try:
            setup_display_environment()
            success = True
        except Exception:
            success = False

        assert success is True
