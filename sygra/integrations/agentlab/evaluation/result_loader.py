"""This module provides a clean, maintainable interface for loading and processing
experiment results from AgentLab's ExpArgs output, including trajectory reconstruction,
screenshot encoding, metric aggregation, and action coordinate extraction.
"""

import base64
import gzip
import json
import pickle
import re
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Optional

from sygra.logger.logger_config import logger

__all__ = ["ResultLoader", "CompletionInfo", "CompletionReason"]


class CompletionReason(Enum):
    """Enumeration of possible task completion reasons."""

    UNKNOWN = "unknown"
    AGENT_SIGNAL = "agent_signal"
    AUTO_EVAL = "auto_eval"
    USER_EXIT = "user_exit"
    TIMEOUT = "timeout"
    ERROR = "error"


@dataclass(frozen=True)
class CompletionInfo:
    """Data class for task completion information."""

    reason: CompletionReason
    agent_message: Optional[str] = None
    eval_confidence: Optional[float] = None
    eval_reasoning: Optional[str] = None


# Constants for file patterns and regex patterns
class _Constants:
    """Internal constants for file processing."""

    # File patterns
    SUMMARY_FILE = "summary_info.json"
    COMPLETION_FILE = "completion_info.json"
    EXPERIMENT_LOG = "experiment.log"
    SCREENSHOT_PATTERN = "screenshot_step_{step}.png"
    SOM_PATTERN = "screenshot_som_step_{step}.png"
    STEP_DATA_PATTERN = "step_{step}.pkl.gz"

    # Regex patterns
    AGENT_MESSAGE_PATTERN = r"send_msg_to_user\(['\"](.+?)['\"]\)"
    CONFIDENCE_PATTERN = r"confidence[=:]\s*([\d.]+)"
    REASONING_PATTERN = r"reason(?:ing)?[=:]\s*(.+?)(?:\n|$)"
    ACTION_BID_PATTERN = r"[a-z_]+\(['\"](\d+)['\"]"

    # Log markers
    AGENT_SIGNAL_MARKER = "send_msg_to_user("
    GOAL_EVAL_TERMINATION = "Task terminated by goal evaluation"
    ACTION_MARKER = "action:"
    LOG_INFO_MARKER = "- INFO -"

    # URL extraction keys
    URL_KEYS = ["url", "page_url", "current_url"]


class ResultLoader:
    """Loads and processes results from AgentLab experiment directories."""

    @staticmethod
    def load(exp_dir: str, task_name: str) -> dict[str, Any]:
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

            # Extract current page URL from the final step
            current_url = ResultLoader._extract_current_url(exp_path, n_steps)

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
                "current_url": current_url,
            }

        except Exception as e:
            logger.error(f"Error loading results: {e}", exc_info=True)
            return ResultLoader._empty_result(str(e))

    @staticmethod
    def _empty_result(error_msg: str) -> dict[str, Any]:
        """Create empty result dictionary with error message."""
        return {
            "error": error_msg,
            "num_steps": 0,
            "success": False,
            "trajectory": [],
            "screenshots": [],
            "current_url": "",
        }

    @staticmethod
    def _extract_completion_info(exp_path: Path, summary: dict[str, Any]) -> dict[str, Any]:
        """Extract task completion information from multiple sources.

        This method follows a priority order:
        1. Explicit completion_info.json file (highest priority)
        2. Experiment log parsing for completion signals
        3. Summary task_info fallback

        Args:
            exp_path: Path to experiment directory
            summary: Summary dictionary from experiment

        Returns:
            Dictionary with completion information in legacy format for compatibility
        """
        completion_info = CompletionInfo(reason=CompletionReason.UNKNOWN)

        # Priority 1: Check for explicit completion file
        completion_info = ResultLoader._load_completion_file(exp_path) or completion_info
        if completion_info.reason != CompletionReason.UNKNOWN:
            return ResultLoader._completion_info_to_dict(completion_info)

        # Priority 2: Parse experiment log for completion signals
        completion_info = ResultLoader._parse_log_for_completion(exp_path) or completion_info
        if completion_info.reason != CompletionReason.UNKNOWN:
            return ResultLoader._completion_info_to_dict(completion_info)

        # Priority 3: Check summary task_info
        completion_info = ResultLoader._extract_from_summary(summary) or completion_info
        return ResultLoader._completion_info_to_dict(completion_info)

    @staticmethod
    def _load_completion_file(exp_path: Path) -> Optional[CompletionInfo]:
        """Load completion information from completion_info.json file."""
        completion_file = exp_path / _Constants.COMPLETION_FILE
        if not completion_file.exists():
            return None

        try:
            with open(completion_file) as f:
                data = json.load(f)

            reason = CompletionReason(data.get("completion_reason", "unknown"))
            return CompletionInfo(
                reason=reason,
                agent_message=data.get("agent_message"),
                eval_confidence=data.get("eval_confidence"),
                eval_reasoning=data.get("eval_reasoning"),
            )
        except (json.JSONDecodeError, ValueError, OSError) as e:
            logger.debug(f"Could not read {_Constants.COMPLETION_FILE}: {e}")
            return None

    @staticmethod
    def _parse_log_for_completion(exp_path: Path) -> Optional[CompletionInfo]:
        """Parse experiment log for completion signals."""
        log_file = exp_path / _Constants.EXPERIMENT_LOG
        if not log_file.exists():
            return None

        try:
            with open(log_file) as f:
                log_content = f.read()
        except OSError as e:
            logger.debug(f"Could not read {_Constants.EXPERIMENT_LOG}: {e}")
            return None

        # Check for agent signal first (higher priority)
        agent_completion = ResultLoader._extract_agent_signal(log_content)
        if agent_completion:
            return agent_completion

        # Check for goal evaluation completion
        eval_completion = ResultLoader._extract_goal_evaluation(log_content)
        if eval_completion:
            return eval_completion

        return None

    @staticmethod
    def _extract_agent_signal(log_content: str) -> Optional[CompletionInfo]:
        """Extract agent signal completion from log content."""
        if _Constants.AGENT_SIGNAL_MARKER not in log_content:
            return None

        match = re.search(_Constants.AGENT_MESSAGE_PATTERN, log_content)
        if not match:
            return None

        return CompletionInfo(reason=CompletionReason.AGENT_SIGNAL, agent_message=match.group(1))

    @staticmethod
    def _extract_goal_evaluation(log_content: str) -> Optional[CompletionInfo]:
        """Extract goal evaluation completion from log content."""
        if _Constants.GOAL_EVAL_TERMINATION not in log_content:
            return None

        # Extract confidence values (take the last one - final evaluation)
        conf_matches = re.findall(_Constants.CONFIDENCE_PATTERN, log_content)
        confidence = float(conf_matches[-1]) if conf_matches else None

        # Extract reasoning if available
        reason_match = re.search(_Constants.REASONING_PATTERN, log_content, re.IGNORECASE)
        reasoning = reason_match.group(1).strip() if reason_match else None

        logger.debug(f"Extracted goal evaluation: confidence={confidence}, reasoning={reasoning}")

        return CompletionInfo(
            reason=CompletionReason.AUTO_EVAL, eval_confidence=confidence, eval_reasoning=reasoning
        )

    @staticmethod
    def _extract_from_summary(summary: dict[str, Any]) -> Optional[CompletionInfo]:
        """Extract completion info from summary task_info."""
        task_info = summary.get("task_info", {})
        completion_reason = task_info.get("completion_reason")

        if not completion_reason:
            return None

        try:
            reason = CompletionReason(completion_reason)
            return CompletionInfo(
                reason=reason,
                agent_message=task_info.get("agent_message"),
                eval_confidence=task_info.get("eval_confidence"),
                eval_reasoning=task_info.get("eval_reasoning"),
            )
        except ValueError:
            logger.debug(f"Unknown completion reason in summary: {completion_reason}")
            return None

    @staticmethod
    def _completion_info_to_dict(completion_info: CompletionInfo) -> dict[str, Any]:
        """Convert CompletionInfo to legacy dictionary format for compatibility."""
        return {
            "completion_reason": completion_info.reason.value,
            "agent_message": completion_info.agent_message,
            "eval_confidence": completion_info.eval_confidence,
            "eval_reasoning": completion_info.eval_reasoning,
        }

    @staticmethod
    def _parse_experiment_log(exp_path: Path) -> tuple[dict[int, str], dict[int, str]]:
        """Parse experiment log to extract actions and reasoning per step.

        Args:
            exp_path: Path to experiment directory

        Returns:
            tuple of (actions_by_step, reasoning_by_step) dictionaries
        """
        log_file = exp_path / _Constants.EXPERIMENT_LOG
        if not log_file.exists():
            return {}, {}

        try:
            with open(log_file, "r", encoding="utf-8") as f:
                lines = f.readlines()
        except OSError as e:
            logger.warning(f"Failed to read experiment log: {e}")
            return {}, {}

        return ResultLoader._extract_actions_and_reasoning(lines)

    @staticmethod
    def _extract_actions_and_reasoning(lines: list[str]) -> tuple[dict[int, str], dict[int, str]]:
        """Extract actions and reasoning from log lines.

        Args:
            lines: list of log file lines

        Returns:
            tuple of (actions_by_step, reasoning_by_step) dictionaries
        """
        actions_by_step: dict[int, str] = {}
        reasoning_by_step: dict[int, str] = {}

        for i, line in enumerate(lines):
            if ResultLoader._is_action_line(line, i, lines):
                action = lines[i + 1].strip()
                if ResultLoader._is_valid_action(action):
                    step_num = len(actions_by_step)
                    actions_by_step[step_num] = action

                    # Find associated reasoning
                    reasoning = ResultLoader._find_reasoning_for_step(lines, i)
                    if reasoning:
                        reasoning_by_step[step_num] = reasoning

        return actions_by_step, reasoning_by_step

    @staticmethod
    def _is_action_line(line: str, index: int, lines: list[str]) -> bool:
        """Check if a line indicates the start of an action."""
        return line.strip() == _Constants.ACTION_MARKER and index + 1 < len(lines)

    @staticmethod
    def _is_valid_action(action: str) -> bool:
        """Check if an action string is valid (not a timestamp or empty)."""
        return bool(action and not action.startswith("2025-"))

    @staticmethod
    def _find_reasoning_for_step(lines: list[str], action_line_index: int) -> Optional[str]:
        """Find reasoning associated with an action by looking backwards in log lines.

        Args:
            lines: list of log file lines
            action_line_index: Index of the "action:" line

        Returns:
            Reasoning text or None if not found
        """
        # Look backwards up to 5 lines for reasoning
        search_start = max(0, action_line_index - 5)
        for j in range(action_line_index - 1, search_start - 1, -1):
            line = lines[j]
            if _Constants.LOG_INFO_MARKER in line:
                parts = line.split(_Constants.LOG_INFO_MARKER, 1)
                if len(parts) > 1:
                    return parts[1].strip()
        return None

    @staticmethod
    def _build_trajectory(
        exp_path: Path, n_steps: int, actions: dict[int, str], reasoning: dict[int, str]
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """Build trajectory from screenshots, actions, and reasoning.

        Args:
            exp_path: Path to experiment directory
            n_steps: Number of steps completed
            actions: Actions indexed by step number
            reasoning: Reasoning indexed by step number

        Returns:
            tuple of (trajectory, screenshots) lists
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

                # Add current URL for this step
                step_url = ResultLoader._extract_current_url(exp_path, step_num)
                trajectory_entry["current_url"] = step_url

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
    def _calculate_center_from_bbox(bbox: list) -> tuple[float, float]:
        """Calculate center coordinates from bounding box.

        Args:
            bbox: Bounding box as [x, y, width, height]

        Returns:
            tuple of (center_x, center_y)
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

    @staticmethod
    def _extract_current_url(exp_path: Path, n_steps: int) -> str:
        """Extract the current page URL from the final step data.

        Args:
            exp_path: Path to experiment directory
            n_steps: Number of steps completed

        Returns:
            Current page URL, or empty string if not found
        """
        step_file = exp_path / _Constants.STEP_DATA_PATTERN.format(step=n_steps)
        if not step_file.exists():
            return ""

        try:
            with gzip.open(step_file, "rb") as f:
                step_data = pickle.load(f)
        except (OSError, pickle.PickleError):
            # URL extraction is not critical - fail silently
            return ""

        return ResultLoader._extract_url_from_step_data(step_data)

    @staticmethod
    def _extract_url_from_step_data(step_data: Any) -> str:
        """Extract URL from step data object.

        Args:
            step_data: Step data from pickle file

        Returns:
            URL string or empty string if not found
        """
        # Handle browsergym StepInfo object (newer format)
        if hasattr(step_data, "obs"):
            url = ResultLoader._extract_url_from_observation(step_data.obs)
            if url:
                return url

        # Handle tuple format (older format)
        if isinstance(step_data, tuple) and len(step_data) >= 1:
            url = ResultLoader._extract_url_from_observation(step_data[0])
            if url:
                return url

        return ""

    @staticmethod
    def _extract_url_from_observation(obs: Any) -> str:
        """Extract URL from observation object.

        Args:
            obs: Observation object (dict or object with attributes)

        Returns:
            URL string or empty string if not found
        """
        # Handle dictionary observations
        if isinstance(obs, dict):
            # Try direct URL keys
            for url_key in _Constants.URL_KEYS:
                if url_key in obs and obs[url_key]:
                    return str(obs[url_key])

            # Try nested page info
            if "page" in obs and isinstance(obs["page"], dict):
                for url_key in _Constants.URL_KEYS:
                    if url_key in obs["page"] and obs["page"][url_key]:
                        return str(obs["page"][url_key])

        # Handle object observations with attributes
        for url_attr in _Constants.URL_KEYS:
            if hasattr(obs, url_attr):
                url_value = getattr(obs, url_attr)
                if url_value:
                    return str(url_value)

        return ""
