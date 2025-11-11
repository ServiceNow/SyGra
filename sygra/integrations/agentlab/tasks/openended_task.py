"""Custom OpenEnded Task with agent completion detection.

This module provides an enhanced OpenEndedTask that allows the agent to signal
task completion by sending messages, similar to how WebArena/VisualWebArena work.

It also supports automatic LLM-based goal evaluation to check if the goal has been
achieved, even if the agent doesn't explicitly signal completion.
"""

from typing import Any, Optional, Tuple

import playwright.sync_api

from sygra.logger.logger_config import logger

# Global configuration (can be set via environment variables)
_GOAL_EVAL_CONFIG = {
    "enable": False,
    "frequency": 2,
    "start_step": 3,
    "use_vision": False,
}


def configure_goal_evaluation(
    enable: bool = False, frequency: int = 2, start_step: int = 3, use_vision: bool = False
):
    """Configure goal evaluation globally."""
    global _GOAL_EVAL_CONFIG
    # Update dict in-place (don't reassign!) so all references see the change
    _GOAL_EVAL_CONFIG["enable"] = enable
    _GOAL_EVAL_CONFIG["frequency"] = frequency
    _GOAL_EVAL_CONFIG["start_step"] = start_step
    _GOAL_EVAL_CONFIG["use_vision"] = use_vision
    logger.info(
        f"Goal evaluation configured: enable={enable}, frequency={frequency}, start_step={start_step}, use_vision={use_vision}"
    )


class OpenEndedTaskWithCompletion:
    """OpenEnded task that detects agent completion signals.

    This task extends the base OpenEndedTask to allow the agent to signal
    completion by sending a message via send_msg_to_user(). When the agent
    sends a message, the task is marked as done.

    Additionally supports automatic LLM-based goal evaluation to check if
    the goal has been achieved, even without explicit agent signaling.

    This behavior is similar to WebArena/VisualWebArena benchmarks where
    the agent can signal completion with its answer.

    Example:
        In the agent's response:
        ```
        <thinking>
        I have successfully added the running shoes to the cart. The goal is complete.
        </thinking>

        <action>
        send_msg_to_user("Task completed: Added 1 pair of running shoes to cart.")
        </action>
        ```

    Args:
        seed: Random seed
        start_url: Starting URL for the task
        goal: Task goal description

    Note:
        Goal evaluation is configured globally via configure_goal_evaluation()
        or environment variables, not through constructor parameters.
    """

    def __init__(
        self,
        seed: int,
        start_url: str,
        goal: Optional[str] = None,
    ) -> None:
        super().__init__(seed, start_url, goal)

        # Don't read config here - read it dynamically in validate()
        # This allows the config to be set after task instantiation
        self._step_count = 0
        self._goal_evaluator: Optional[Any] = None
        self._completion_detected = False  # Track if we've already detected completion
        self._config_logged = False  # Track if we've logged config once

    def validate(
        self, page: playwright.sync_api.Page, chat_messages: list[dict[str, Any]]  # type: ignore[override]
    ) -> Tuple[float, bool, str, dict]:
        """Validate task completion.

        Checks for:
        1. User sending "exit" command (original behavior)
        2. Agent sending completion message via send_msg_to_user()
        3. Automatic LLM-based goal evaluation (if enabled)

        Args:
            page: Playwright page instance
            chat_messages: List of chat messages exchanged

        Returns:
            Tuple of (reward, done, message, info)
            - reward: Always 0 (no automatic reward for openended tasks)
            - done: True if user exits, agent signals, or goal is evaluated as complete
            - message: Status message
            - info: Additional information dictionary
        """
        reward, done, msg = 0, False, ""
        info: dict[str, Any] = {}
        self._step_count += 1

        # Read config dynamically from global (allows setting after task creation)
        global _GOAL_EVAL_CONFIG
        enable_goal_eval = bool(_GOAL_EVAL_CONFIG["enable"])
        eval_frequency = int(_GOAL_EVAL_CONFIG["frequency"])
        eval_start_step = int(_GOAL_EVAL_CONFIG["start_step"])
        use_vision = bool(_GOAL_EVAL_CONFIG["use_vision"])

        # Log config once on first validation
        if not self._config_logged:
            logger.info(
                f"Task validate() reading config: enable={enable_goal_eval}, freq={eval_frequency}, start={eval_start_step}, use_vision={use_vision}"
            )
            self._config_logged = True

        # If we've already detected completion, keep returning done=True
        if self._completion_detected:
            return 0, True, "Task already completed", {"completion_reason": "agent_signal"}

        # Check if user requested exit (original behavior)
        for message in chat_messages:
            if message["role"] == "user" and message["message"] == "exit":
                done = True
                msg = "User requested exit"
                info["completion_reason"] = "user_exit"
                self._completion_detected = True
                break

        # Check if agent signaled completion via send_msg_to_user
        # Only messages that start with "Goal completed:" or contain completion signals
        if not done and chat_messages:
            last_message = chat_messages[-1]
            if (
                last_message["role"] == "assistant"
                and last_message["message"]
                and (
                    "Goal completed:" in last_message["message"]
                    or "Task completed:" in last_message["message"]
                    or "send_msg_to_user" in str(last_message.get("action", ""))
                )
            ):
                done = True
                msg = f"Agent signaled completion: {last_message['message']}"
                info["agent_message"] = last_message["message"]
                info["completion_reason"] = "agent_signal"
                self._completion_detected = True
                logger.info(f"Agent signaled completion: {last_message['message'][:80]}")

        # Automatic goal evaluation (if enabled and not already done)
        if not done and enable_goal_eval:
            should_evaluate = (
                self._step_count >= eval_start_step
                and (self._step_count - eval_start_step) % eval_frequency == 0
            )

            if should_evaluate:
                logger.info(f"Running goal evaluation at step {self._step_count}")

                # Wait for page to stabilize before evaluation
                import time

                try:
                    # Wait for page load state to be 'networkidle' (no network activity for 500ms)
                    page.wait_for_load_state("networkidle", timeout=5000)
                    logger.debug("Page reached networkidle state")
                except Exception as e:
                    # If timeout or error, fall back to fixed wait
                    logger.debug(f"Page load wait timeout or error: {e}, using fixed delay")
                    time.sleep(1.5)

                try:
                    is_complete, reasoning, confidence = self._evaluate_goal(page, chat_messages)

                    logger.info(
                        f"Evaluation result: complete={is_complete}, confidence={confidence:.2f}"
                    )
                    logger.debug(f"Evaluation reasoning: {reasoning[:150]}")

                    if is_complete and confidence > 0.9:
                        done = True
                        msg = f"Goal evaluation: {reasoning}"
                        info["completion_reason"] = "auto_eval"
                        info["eval_confidence"] = float(confidence)
                        info["eval_reasoning"] = str(reasoning)
                        self._completion_detected = True
                        logger.info(
                            f"Task terminated by goal evaluation (confidence: {confidence:.2f})"
                        )
                    else:
                        if not is_complete:
                            logger.debug("Goal not yet complete, continuing")
                        else:
                            logger.info(
                                f"Goal complete but confidence too low: {confidence:.2f} <= 0.7"
                            )

                except Exception as e:
                    logger.error(f"Goal evaluation error at step {self._step_count}: {e}")
                    logger.debug("Evaluation traceback:", exc_info=True)

        # Save completion info to file for result loader
        if done and info.get("completion_reason"):
            self._save_completion_info(info)

        return reward, done, msg, info

    def _save_completion_info(self, info: dict):
        """Save completion information to a file for the result loader to read."""
        try:
            import json

            # Get the experiment directory from the environment
            # (set by browsergym when running experiments)
            import os
            from pathlib import Path

            exp_dir = os.environ.get("BROWSERGYM_EXP_DIR")

            if exp_dir:
                completion_file = Path(exp_dir) / "completion_info.json"
                with open(completion_file, "w") as f:
                    json.dump(
                        {
                            "completion_reason": info.get("completion_reason"),
                            "agent_message": info.get("agent_message"),
                            "eval_confidence": info.get("eval_confidence"),
                            "eval_reasoning": info.get("eval_reasoning"),
                        },
                        f,
                        indent=2,
                    )
                logger.debug(f"Saved completion info to {completion_file}")
        except Exception as e:
            logger.warning(f"Could not save completion info: {e}")

    def _evaluate_goal(
        self, page: playwright.sync_api.Page, chat_messages: list[dict[str, Any]]
    ) -> Tuple[bool, str, float]:
        """Evaluate if goal has been achieved using LLM.

        Returns:
            Tuple of (is_complete, reasoning, confidence)
        """
        # Get current config
        global _GOAL_EVAL_CONFIG
        use_vision = bool(_GOAL_EVAL_CONFIG["use_vision"])

        # Lazy import and initialization
        if self._goal_evaluator is None:
            from ..evaluation.goal_evaluator import GoalEvaluator

            self._goal_evaluator = GoalEvaluator(use_vision=use_vision)
            logger.debug(f"Initialized goal evaluator (vision={use_vision})")

        # Extract current observation from page
        current_observation = self._extract_page_observation(page, use_vision)

        # Build simple trajectory from chat messages
        trajectory = [{"message": msg} for msg in chat_messages[-5:]]  # Last 5 messages

        # Run evaluation
        return self._goal_evaluator.evaluate_goal_completion(
            goal=self.goal, trajectory=trajectory, current_observation=current_observation
        )

    def _extract_page_observation(
        self, page: playwright.sync_api.Page, use_vision: bool = False
    ) -> dict:
        """Extract relevant page information for evaluation."""
        try:
            observation = {
                "url": page.url,
                "title": page.title(),
                "content": page.content()[:5000],  # Truncate for LLM context
            }

            # Add screenshot if vision is enabled
            if use_vision:
                try:
                    screenshot_bytes = page.screenshot()
                    observation["screenshot"] = screenshot_bytes  # type: ignore[assignment]
                    logger.debug(
                        f"Captured screenshot for evaluation ({len(screenshot_bytes)} bytes)"
                    )
                except Exception as e:
                    logger.warning(f"Could not capture screenshot: {e}")

            return observation
        except Exception as e:
            logger.warning(f"Could not extract page observation: {e}")
            return {"url": "unknown", "title": "unknown", "content": ""}


def get_task_class_for_type(task_type: str) -> type:
    """Get the appropriate task class for a given task type.

    For openended/custom tasks, returns our enhanced version with completion detection.
    For other task types, looks them up from browsergym's task registry.

    Args:
        task_type: Task type identifier (e.g., "openended", "webarena.1")

    Returns:
        Task class to use for this task type
    """
    # Use our custom task for openended/custom tasks
    if task_type in ("openended", "custom"):
        return OpenEndedTaskWithCompletion

    # For benchmark tasks, use browsergym's lookup
    try:
        import gymnasium as gym  # type: ignore

        env = gym.make(f"browsergym/{task_type}")
        return env.unwrapped.task.__class__  # type: ignore[no-any-return, attr-defined]
    except Exception:
        # Fallback to default OpenEndedTaskWithCompletion
        return OpenEndedTaskWithCompletion  # type: ignore[no-any-return]
