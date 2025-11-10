"""Patches browsergym tasks at import time.

This module MUST be imported before any browsergym code is executed
to ensure our custom task classes are registered properly.
"""

import os

from sygra.logger.logger_config import logger


def patch_openended_task():
    """Patch OpenEndedTask with our custom completion-aware version."""
    try:
        # Import and patch BEFORE browsergym uses it
        import browsergym.core.task as task_module

        from sygra.integrations.agentlab.custom_openended_task import (
            OpenEndedTaskWithCompletion,
            configure_goal_evaluation,
        )

        # Store original for reference
        original_class = task_module.OpenEndedTask

        # Replace the class
        task_module.OpenEndedTask = OpenEndedTaskWithCompletion

        # Configure goal evaluation from environment variables if set
        enable = os.environ.get("SYGRA_ENABLE_GOAL_EVAL", "false").lower() == "true"
        frequency = int(os.environ.get("SYGRA_EVAL_FREQUENCY", "2"))
        start_step = int(os.environ.get("SYGRA_EVAL_START_STEP", "3"))

        configure_goal_evaluation(enable=enable, frequency=frequency, start_step=start_step)

        # CRITICAL: Re-register the task with gymnasium so it uses our patched class!
        import gymnasium
        from browsergym.core.registration import register_task

        # Unregister the old task
        if "browsergym/openended" in gymnasium.envs.registry:
            del gymnasium.envs.registry["browsergym/openended"]
            logger.debug("Unregistered old openended task from gymnasium registry")

        # Re-register with our patched class
        register_task(
            id="openended",
            task_class=OpenEndedTaskWithCompletion,
        )
        logger.debug("Re-registered openended task with OpenEndedTaskWithCompletion")

        logger.info(
            f"Patched OpenEndedTask - Goal eval: enable={enable}, freq={frequency}, start={start_step}"
        )
        logger.debug(
            f"Patched OpenEndedTask: {original_class.__name__} -> {OpenEndedTaskWithCompletion.__name__}"
        )
        return True

    except Exception as e:
        logger.error(f"Failed to patch OpenEndedTask: {e}")
        return False


# Auto-patch on import
_patched = patch_openended_task()
