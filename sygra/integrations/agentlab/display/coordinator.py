"""
SOM (Set of Marks) coordinate system management for cross-platform compatibility.

This module provides utilities for detecting and handling coordinate scaling issues
that occur on high-DPI displays where browser coordinates may be reported at a
different scale than screenshot dimensions.
"""

import os
import platform
from typing import Any

import numpy as np

from sygra.logger.logger_config import logger


def detect_coordinate_scaling(screenshot: np.ndarray, extra_properties: dict[str, Any]) -> bool:
    """
    Detect if coordinate scaling is needed based on screenshot vs coordinate dimensions.

    Args:
        screenshot: Screenshot array
        extra_properties: Element properties containing bounding boxes

    Returns:
        True if 2x coordinate scaling is detected, False otherwise
    """
    if isinstance(screenshot, np.ndarray):
        screenshot_height, screenshot_width = screenshot.shape[:2]
    else:
        screenshot_width, screenshot_height = (
            screenshot.size if hasattr(screenshot, "size") else (1366, 768)
        )

    # Check if any bounding box coordinates are roughly 2x the screenshot dimensions
    for properties in extra_properties.values():
        if isinstance(properties, dict) and "bbox" in properties and properties["bbox"] is not None:
            bbox = properties["bbox"]
            if len(bbox) == 4:
                x, y, w, h = bbox
                # If coordinates are significantly larger than screenshot, scaling is needed
                if w > screenshot_width * 1.5 or h > screenshot_height * 1.5:
                    return True
    return False


def setup_display_environment() -> None:
    """
    Configure display-related environment variables for consistent rendering.

    Sets platform-specific environment variables to prevent display scaling
    that can interfere with coordinate calculations.
    """
    system = platform.system()

    if system == "Darwin":  # macOS
        os.environ.setdefault("QT_SCALE_FACTOR", "1")
        os.environ.setdefault("QT_AUTO_SCREEN_SCALE_FACTOR", "0")
        logger.debug("Configured macOS display environment for SOM compatibility")

    elif system == "Linux":
        os.environ.setdefault("GDK_SCALE", "1")
        os.environ.setdefault("QT_SCALE_FACTOR", "1")
        logger.debug("Configured Linux display environment for SOM compatibility")

    # Windows typically handles DPI scaling at the system level
