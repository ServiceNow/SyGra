"""SOM display coordination and overlay fixes for cross-platform compatibility."""

from .coordinator import detect_coordinate_scaling, setup_display_environment
from .overlay_fix import patch_som_overlay

__all__ = ["detect_coordinate_scaling", "setup_display_environment", "patch_som_overlay"]
