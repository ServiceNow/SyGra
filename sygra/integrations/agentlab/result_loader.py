"""Result loader for AgentLab experiments.

Loads and processes experiment results from AgentLab's ExpArgs output,
including trajectory reconstruction, screenshot encoding, metric aggregation,
and action coordinate extraction.
"""

import base64
import gzip
import json
import pickle
import re
from pathlib import Path
from typing import Any, Optional, Tuple

from sygra.logger.logger_config import logger

__all__ = ["ResultLoader"]


class ResultLoader:
    """Loads and processes results from AgentLab experiment directories."""

    @staticmethod
    def load(exp_dir: str, task_name: str) -> dict[str, object]:
        """Load complete experiment results including trajectory and screenshots.

        Args:
            exp_dir: Path to experiment directory
            task_name: Task identifier for logging

        Returns:
            Dictionary containing trajectory, screenshots, and performance metrics
        """
        summary_file = Path(exp_dir) / "summary_info.json"

        if not summary_file.exists():
            logger.warning(f"Summary file not found: {summary_file}")
            return ResultLoader._empty_result("No summary file found")

        try:
            with open(summary_file) as f:
                summary = json.load(f)

            n_steps = summary.get("n_steps", 0)
            exp_path = Path(exp_dir)

            actions, reasoning = ResultLoader._parse_experiment_log(exp_path)
            trajectory, screenshots = ResultLoader._build_trajectory(
                exp_path, n_steps, actions, reasoning
            )

            logger.info(
                f"Loaded {len(trajectory)} trajectory entries with {len(screenshots)} screenshots"
            )

            # Extract completion information - check multiple sources
            completion_info = ResultLoader._extract_completion_info(exp_path, summary)
            completion_reason = completion_info["completion_reason"]
            eval_confidence = completion_info.get("eval_confidence")
            eval_reasoning = completion_info.get("eval_reasoning")
            agent_message = completion_info.get("agent_message")

            # Log completion details
            if completion_reason == "agent_signal":
                logger.info("Task completion: Agent signaled")
                logger.debug(f"Agent message: {agent_message[:100] if agent_message else 'N/A'}")
            elif completion_reason == "auto_eval":
                conf_str = f"{eval_confidence:.2f}" if eval_confidence is not None else "N/A"
                logger.info(f"Task completion: Goal evaluation (confidence: {conf_str})")
                logger.debug(f"Reasoning: {eval_reasoning[:100] if eval_reasoning else 'N/A'}")
            elif completion_reason != "unknown":
                logger.info(f"Task completion: {completion_reason}")

            return {
                "trajectory": trajectory,
                "screenshots": screenshots,
                "num_steps": len(trajectory),
                "success": summary.get("cum_reward", 0.0) > 0
                or completion_reason in ("agent_signal", "auto_eval"),
                "final_reward": summary.get("cum_reward", 0.0),
                "done": n_steps >= summary.get("n_steps", 0),
                "truncated": n_steps >= summary.get("n_steps", 0),
                "total_cost": summary.get("stats.cum_cost", 0.0),
                "exp_dir": str(exp_dir),
                "completion_reason": completion_reason,
                "agent_message": agent_message,
                "eval_confidence": eval_confidence,
                "eval_reasoning": eval_reasoning,
            }

        except Exception as e:
            logger.error(f"Error loading results: {e}", exc_info=True)
            return ResultLoader._empty_result(str(e))

    @staticmethod
    def _empty_result(error_msg: str) -> dict[str, object]:
        """Create empty result dictionary with error message."""
        return {
            "error": error_msg,
            "num_steps": 0,
            "success": False,
            "trajectory": [],
            "screenshots": [],
        }

    @staticmethod
    def _extract_completion_info(exp_path: Path, summary: dict) -> dict:
        """Extract task completion information from various sources.

        Checks:
        1. completion_info.json file (saved by custom task)
        2. Experiment log for send_msg_to_user or evaluation messages
        3. Task info in summary

        Returns:
            Dict with completion_reason, agent_message, eval_confidence, eval_reasoning
        """
        completion_info: dict[str, Any] = {
            "completion_reason": "unknown",
            "agent_message": None,
            "eval_confidence": None,
            "eval_reasoning": None,
        }

        # 1. Check for completion_info.json file
        completion_file = exp_path / "completion_info.json"
        if completion_file.exists():
            try:
                with open(completion_file) as f:
                    file_info = json.load(f)
                    completion_info.update(file_info)
                    return completion_info
            except Exception as e:
                logger.debug(f"Could not read completion_info.json: {e}")

        # 2. Parse experiment log for completion signals
        log_file = exp_path / "experiment.log"
        if log_file.exists():
            try:
                with open(log_file) as f:
                    log_content = f.read()

                    # Check for send_msg_to_user (agent signal)
                    if "send_msg_to_user(" in log_content:
                        # Extract the message
                        import re

                        match = re.search(r"send_msg_to_user\(['\"](.+?)['\"]\)", log_content)
                        if match:
                            completion_info["completion_reason"] = "agent_signal"
                            completion_info["agent_message"] = match.group(1)
                            return completion_info

                    # Check for goal evaluation completion
                    if "Task terminated by goal evaluation" in log_content:
                        completion_info["completion_reason"] = "auto_eval"
                        # Try to extract confidence and reasoning
                        conf_match = re.search(r"confidence: ([\d.]+)", log_content)
                        if conf_match:
                            completion_info["eval_confidence"] = float(conf_match.group(1))
                        return completion_info

            except Exception as e:
                logger.debug(f"Could not parse experiment log for completion: {e}")

        # 3. Check summary task_info (if it exists)
        task_info = summary.get("task_info", {})
        if task_info.get("completion_reason"):
            completion_info.update(task_info)

        return completion_info

    @staticmethod
    def _parse_experiment_log(exp_path: Path) -> tuple[dict[int, str], dict[int, str]]:
        """Parse experiment log to extract actions and reasoning per step.

        Args:
            exp_path: Path to experiment directory

        Returns:
            Tuple of (actions_by_step, reasoning_by_step) dictionaries
        """
        log_file = exp_path / "experiment.log"
        actions_by_step: dict[int, str] = {}
        reasoning_by_step: dict[int, str] = {}

        if not log_file.exists():
            return actions_by_step, reasoning_by_step

        try:
            with open(log_file, "r") as f:
                lines = f.readlines()

            for i, line in enumerate(lines):
                if line.strip() == "action:" and i + 1 < len(lines):
                    action = lines[i + 1].strip()

                    if action and not action.startswith("2025-"):
                        step_num = len(actions_by_step)
                        actions_by_step[step_num] = action

                        for j in range(i - 1, max(0, i - 5), -1):
                            prev_line = lines[j]
                            if "- INFO -" in prev_line:
                                parts = prev_line.split("- INFO -")
                                if len(parts) > 1:
                                    reasoning_by_step[step_num] = parts[1].strip()
                                break

        except Exception as e:
            logger.warning(f"Failed to parse log: {e}")

        return actions_by_step, reasoning_by_step

    @staticmethod
    def _build_trajectory(
        exp_path: Path, n_steps: int, actions: dict[int, str], reasoning: dict[int, str]
    ) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
        """Build trajectory from screenshots, actions, and reasoning.

        Args:
            exp_path: Path to experiment directory
            n_steps: Number of steps completed
            actions: Actions indexed by step number
            reasoning: Reasoning indexed by step number

        Returns:
            Tuple of (trajectory, screenshots) lists
        """
        trajectory = []
        screenshots = []

        logger.info(f"Loading {n_steps + 1} steps with screenshots...")

        for step_num in range(n_steps + 1):
            screenshot_file = exp_path / f"screenshot_step_{step_num}.png"
            som_file = exp_path / f"screenshot_som_step_{step_num}.png"

            screenshot_data = ResultLoader._load_image_as_base64(screenshot_file)
            som_data = ResultLoader._load_image_as_base64(som_file)

            # Extract coordinates from action
            action_str = actions.get(step_num, "")
            coordinates = ResultLoader._extract_action_coordinates(exp_path, step_num, action_str)

            if screenshot_data:
                screenshots.append(
                    {"step": step_num, "type": "screenshot", "path": str(screenshot_file)}
                )

                trajectory_entry = {
                    "step": step_num,
                    "reasoning": reasoning.get(step_num, ""),
                    "action": action_str,
                    "screenshot": screenshot_data,
                    "som": som_data,
                }

                # Add coordinates if available
                if coordinates:
                    trajectory_entry["coordinates"] = coordinates

                trajectory.append(trajectory_entry)

            if som_data:
                screenshots.append({"step": step_num, "type": "som", "path": str(som_file)})

        return trajectory, screenshots

    @staticmethod
    def _load_image_as_base64(image_path: Path) -> str:
        """Load image file and encode as base64 string.

        Args:
            image_path: Path to image file

        Returns:
            Base64-encoded image data, or empty string if file doesn't exist
        """
        if not image_path.exists():
            return ""

        try:
            with open(image_path, "rb") as f:
                return base64.b64encode(f.read()).decode("utf-8")
        except Exception as e:
            logger.warning(f"Failed to load image {image_path}: {e}")
            return ""

    @staticmethod
    def _extract_bid_from_action(action: str) -> Optional[str]:
        """Extract BID (browser element ID) from action string.

        Actions are in formats like:
        - click('285')
        - fill('42', 'search text')
        - hover('100')

        Args:
            action: Action string

        Returns:
            BID string or None if not found
        """
        if not action:
            return None

        # Match patterns like click('285'), fill('42', ...), etc.
        # BID is the first quoted argument
        match = re.search(r"[a-z_]+\(['\"](\d+)['\"]", action)
        if match:
            return match.group(1)
        return None

    @staticmethod
    def _load_step_element_properties(exp_path: Path, step_num: int) -> Optional[dict]:
        """Load element properties from step pickle file.

        Args:
            exp_path: Path to experiment directory
            step_num: Step number

        Returns:
            Dictionary of element properties by BID, or None if unavailable
        """
        step_file = exp_path / f"step_{step_num}.pkl.gz"
        if not step_file.exists():
            return None

        try:
            with gzip.open(step_file, "rb") as f:
                step_data = pickle.load(f)  # type: ignore

            if hasattr(step_data, "obs") and isinstance(step_data.obs, dict):
                return step_data.obs.get("extra_element_properties", {})  # type: ignore
        except Exception as e:
            logger.debug(f"Could not load element properties from {step_file}: {e}")

        return None

    @staticmethod
    def _calculate_center_from_bbox(bbox: list) -> Tuple[float, float]:
        """Calculate center coordinates from bounding box.

        Args:
            bbox: Bounding box as [x, y, width, height]

        Returns:
            Tuple of (center_x, center_y)
        """
        if bbox and len(bbox) >= 4:
            x, y, width, height = bbox[:4]
            center_x = x + width / 2
            center_y = y + height / 2
            return (center_x, center_y)
        return (0.0, 0.0)

    @staticmethod
    def _extract_action_coordinates(exp_path: Path, step_num: int, action: str) -> Optional[dict]:
        """Extract coordinates from action by looking up element properties.

        Args:
            exp_path: Path to experiment directory
            step_num: Step number
            action: Action string

        Returns:
            Dictionary with coordinate information or None
        """
        # Extract BID from action
        bid = ResultLoader._extract_bid_from_action(action)
        if not bid:
            return None

        # Load element properties for this step
        elem_props = ResultLoader._load_step_element_properties(exp_path, step_num)
        if not elem_props or bid not in elem_props:
            return None

        # Get bounding box
        element = elem_props[bid]
        if not isinstance(element, dict) or "bbox" not in element:
            return None

        bbox = element.get("bbox")
        if not bbox:
            return None

        center_x, center_y = ResultLoader._calculate_center_from_bbox(bbox)

        return {
            "bid": bid,
            "bbox": bbox,
            "center_x": round(center_x, 2),
            "center_y": round(center_y, 2),
            "clickable": element.get("clickable", False),
            "visibility": element.get("visibility", 0.0),
        }
