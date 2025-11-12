"""SOM overlay coordinate fix for retina displays."""

import copy
import os
import sys
from typing import Any, Callable, Optional

from sygra.logger.logger_config import logger

_original_overlay_som: Optional[Callable[..., Any]] = None
_patch_applied = False


def agentlab_compatible_overlay_som(
    screenshot: Any, extra_properties: dict[str, Any], **kwargs: Any
) -> Any:
    """
    SOM overlay that applies the exact same retina coordinate scaling
    that AgentLab uses for action overlays in agent_utils.py
    """
    global _original_overlay_som

    processed_properties = copy.deepcopy(extra_properties)

    if os.getenv("AGENTLAB_USE_RETINA"):
        for key, value in processed_properties.items():
            try:
                processed_properties[key]["bbox"] = [elem / 2 for elem in value["bbox"]]
            except Exception:
                pass
    else:
        logger.info("Env AGENTLAB_USE_RETINA not set - using original coordinates")

    # Call original overlay_som with processed coordinates
    if _original_overlay_som:
        try:
            return _original_overlay_som(
                screenshot, extra_properties=processed_properties, **kwargs
            )
        except TypeError:
            return _original_overlay_som(screenshot, processed_properties)

    return screenshot


def patch_som_overlay() -> bool:
    """Patch browsergym overlay_som and AgentLab modules for retina coordinates."""
    global _original_overlay_som, _patch_applied

    # Don't patch twice in the same process
    if _patch_applied:
        logger.info("SOM overlay patch already applied in this process")
        return True

    logger.info("Patching SOM overlay for retina support")

    try:
        # First patch the base browsergym module
        import browsergym.utils.obs as obs_module  # type: ignore[import-untyped]

        if _original_overlay_som is None:
            _original_overlay_som = getattr(obs_module, "overlay_som", None)
            logger.info(f"Stored original overlay_som: {_original_overlay_som}")

        setattr(obs_module, "overlay_som", agentlab_compatible_overlay_som)

        # Also patch sys.modules if already loaded
        if "browsergym.utils.obs" in sys.modules:
            setattr(
                sys.modules["browsergym.utils.obs"],
                "overlay_som",
                agentlab_compatible_overlay_som,
            )

        # CRITICAL: Patch AgentLab modules that imported overlay_som at import time
        agentlab_modules_to_patch = [
            "agentlab.agents.dynamic_prompting",
            "agentlab.agents.debug_agent",
            "agentlab.agents.tool_use_agent.tool_use_agent",
            "agentlab.agents.visualwebarena.agent",
        ]

        for module_name in agentlab_modules_to_patch:
            try:
                if module_name in sys.modules:
                    module = sys.modules[module_name]
                    # Replace the imported function directly
                    if hasattr(module, "overlay_som"):
                        logger.info(f"Patching {module_name}.overlay_som")
                        setattr(module, "overlay_som", agentlab_compatible_overlay_som)

            except Exception as e:
                logger.warning(f"Failed to patch {module_name}: {e}")
                continue

        _patch_applied = True
        logger.info("SOM overlay patching complete (base + AgentLab modules)")
        return True

    except Exception as e:
        logger.error(f"Failed to patch SOM overlay: {e}")
        return False
