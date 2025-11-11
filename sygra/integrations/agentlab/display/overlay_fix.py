"""
Production SOM overlay coordinate fix for high-DPI display compatibility.

This module patches the browsergym overlay_som function to handle coordinate
scaling issues that occur on high-DPI displays (such as Retina displays) where
browser coordinates are reported at 2x scale while screenshots are captured at 1x.
"""

import sys
from typing import Any, Callable, Optional

import numpy as np

from sygra.logger.logger_config import logger

# Store reference to original function to avoid recursion
_original_overlay_som: Optional[Callable[..., np.ndarray]] = None


def corrected_overlay_som(screenshot: np.ndarray, extra_properties: dict[str, Any]) -> np.ndarray:
    """
    SOM overlay function with coordinate scaling fix for high-DPI displays.

    This function detects when browser coordinates are reported at 2x scale
    (common on Retina displays) and applies 0.5x scaling to normalize them
    before calling the original overlay_som function.

    Args:
        screenshot: Screenshot image as numpy array
        extra_properties: Dictionary mapping element IDs to properties containing bbox coordinates

    Returns:
        Screenshot with properly positioned SOM markers overlaid

    Note:
        Uses the same coordinate scaling approach as AgentLab's overlay_action function
        to ensure consistent behavior across the codebase.
    """
    global _original_overlay_som

    try:

        # Create corrected properties following AgentLab's exact approach
        corrected_properties = {}

        # Detect if we need coordinate scaling
        needs_scaling = False
        if isinstance(screenshot, np.ndarray):
            screenshot_height, screenshot_width = screenshot.shape[:2]
        else:
            screenshot_width, screenshot_height = (
                screenshot.size if hasattr(screenshot, "size") else (1366, 768)
            )

        # Check if coordinates are roughly 2x screen size (indicating need for scaling)
        for properties in extra_properties.values():
            if (
                isinstance(properties, dict)
                and "bbox" in properties
                and properties["bbox"] is not None
            ):
                bbox = properties["bbox"]
                if len(bbox) == 4:
                    x, y, w, h = bbox
                    if w > screenshot_width * 1.5 or h > screenshot_height * 1.5:
                        needs_scaling = True
                        break

        # Apply coordinate scaling if needed (following AgentLab's approach)
        for bid, properties in extra_properties.items():
            corrected_properties[bid] = (
                properties.copy() if isinstance(properties, dict) else properties
            )

            if (
                needs_scaling
                and isinstance(properties, dict)
                and "bbox" in properties
                and properties["bbox"] is not None
            ):
                try:
                    # Divide coordinates by 2 - exactly like AgentLab's overlay_action
                    corrected_properties[bid]["bbox"] = [elem / 2 for elem in properties["bbox"]]
                except Exception as e:
                    logger.warning("Failed to scale coordinates for element %s: %s" % (bid, e))

        if needs_scaling:
            logger.debug("Applied coordinate scaling (0.5x) for high-DPI display compatibility")

        # Call original function with corrected coordinates
        if _original_overlay_som is not None:
            try:
                # Try with keyword argument first (AgentLab style)
                return _original_overlay_som(screenshot, extra_properties=corrected_properties)
            except TypeError:
                # Fallback to positional argument
                return _original_overlay_som(screenshot, corrected_properties)
        else:
            return screenshot

    except Exception as e:
        logger.warning("SOM coordinate scaling failed: %s" % e)

        # Fallback to original function with original properties
        if _original_overlay_som is not None:
            try:
                return _original_overlay_som(screenshot, extra_properties=extra_properties)
            except (TypeError, Exception):
                try:
                    return _original_overlay_som(screenshot, extra_properties)
                except Exception:
                    pass

        return screenshot


def patch_som_overlay() -> bool:
    """
    Apply the SOM overlay coordinate fix across all relevant modules.

    This function patches the overlay_som function in browsergym and all
    AgentLab modules that import it, ensuring consistent coordinate handling.

    Returns:
        True if patching was successful, False otherwise
    """
    global _original_overlay_som

    try:
        # Store reference to original function (first time only)
        if _original_overlay_som is None:
            try:
                import browsergym.utils.obs as obs_module  # type: ignore[import-untyped]

                _original_overlay_som = getattr(obs_module, "overlay_som", None)
            except ImportError:
                # browsergym not available - this is not necessarily an error
                return False

        # Patch browsergym.utils.obs module
        try:
            import browsergym.utils.obs as obs_module  # type: ignore[import-untyped]

            obs_module.overlay_som = corrected_overlay_som  # type: ignore[attr-defined]
        except ImportError:
            pass

        # Patch browsergym in sys.modules if already loaded
        if "browsergym.utils.obs" in sys.modules:
            sys.modules["browsergym.utils.obs"].overlay_som = corrected_overlay_som  # type: ignore[attr-defined]

        # Patch AgentLab modules that import overlay_som
        agentlab_modules = [
            "agentlab.agents.dynamic_prompting",
            "agentlab.agents.debug_agent",
            "agentlab.agents.tool_use_agent.tool_use_agent",
            "agentlab.agents.visualwebarena.agent",
        ]

        for module_name in agentlab_modules:
            try:
                if module_name in sys.modules:
                    module = sys.modules[module_name]
                    if hasattr(module, "overlay_som"):
                        module.overlay_som = corrected_overlay_som  # type: ignore[attr-defined]
                else:
                    # Try to import and patch
                    try:
                        import importlib

                        module = importlib.import_module(module_name)
                        if hasattr(module, "overlay_som"):
                            module.overlay_som = corrected_overlay_som  # type: ignore[attr-defined]
                    except ImportError:
                        # Module not available - this is expected in some configurations
                        continue
            except Exception as e:
                logger.error("Failed to patch %s: %s" % (module_name, e))
                # Continue with other modules if one fails
                continue

        return True

    except Exception as e:
        logger.error("Failed to patch overlay_som: %s" % e)
        return False
