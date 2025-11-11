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

        from sygra.integrations.agentlab.tasks.openended_task import configure_goal_evaluation

        # Store original for reference
        original_class = task_module.OpenEndedTask

        # Import the complete implementation from our openended_task module
        from sygra.integrations.agentlab.tasks.openended_task import (
            OpenEndedTaskWithCompletion as OpenEndedTaskImpl,
        )

        # Create a new class that combines both base class and our implementation
        class OpenEndedTaskWithCompletion(original_class):
            """OpenEnded task that detects agent completion signals."""

            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                # Initialize completion detection attributes from our implementation
                self._step_count = 0
                self._goal_evaluator = None
                self._completion_detected = False
                self._config_logged = False

            def validate(self, page, chat_messages):
                """Use our custom validation logic for completion detection."""
                # Import the implementation temporarily to access its validate method
                temp_impl = OpenEndedTaskImpl.__new__(OpenEndedTaskImpl)
                temp_impl._step_count = self._step_count
                temp_impl._goal_evaluator = getattr(self, "_goal_evaluator", None)
                temp_impl._completion_detected = self._completion_detected
                temp_impl._config_logged = self._config_logged
                temp_impl.goal = getattr(self, "goal", "")

                # Call the implementation's validate method
                result = OpenEndedTaskImpl.validate(temp_impl, page, chat_messages)

                # Copy back the state
                self._step_count = temp_impl._step_count
                self._goal_evaluator = temp_impl._goal_evaluator
                self._completion_detected = temp_impl._completion_detected
                self._config_logged = temp_impl._config_logged

                return result

        # Replace the class
        task_module.OpenEndedTask = OpenEndedTaskWithCompletion

        # Configure goal evaluation from environment variables if set
        # Only override if environment variables are explicitly set
        from sygra.integrations.agentlab.tasks.openended_task import _GOAL_EVAL_CONFIG

        # Only override with env vars if they are explicitly set
        if "SYGRA_ENABLE_GOAL_EVAL" in os.environ:
            enable = os.environ.get("SYGRA_ENABLE_GOAL_EVAL", "false").lower() == "true"
            frequency = int(os.environ.get("SYGRA_EVAL_FREQUENCY", "2"))
            start_step = int(os.environ.get("SYGRA_EVAL_START_STEP", "3"))
            use_vision = os.environ.get("SYGRA_EVAL_USE_VISION", "false").lower() == "true"

            configure_goal_evaluation(
                enable=enable, frequency=frequency, start_step=start_step, use_vision=use_vision
            )
        else:
            # Use current config (don't override what was set by ExperimentRunner)
            enable = _GOAL_EVAL_CONFIG["enable"]
            frequency = _GOAL_EVAL_CONFIG["frequency"]
            start_step = _GOAL_EVAL_CONFIG["start_step"]

        # Re-register the task with gymnasium so it uses our patched class!
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


# Main function for external use
def patch_tasks():
    """Patch all browsergym tasks. Alias for patch_openended_task for compatibility."""
    return patch_openended_task()


# Auto-patch on import to ensure it happens
_patched = patch_openended_task()
