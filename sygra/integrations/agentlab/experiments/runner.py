"""Experiment runner for AgentLab integration.

Executes AgentLab experiments in isolated subprocesses to avoid
async/sync conflicts with LangGraph and ensure clean state.
"""

import json
import multiprocessing
from pathlib import Path
from typing import Any

from agentlab.agents.agent_args import AgentArgs  # type: ignore[import-untyped]

from sygra.logger.logger_config import logger

# IMPORTANT: Patch tasks BEFORE any other browsergym imports
# from ..tasks import patch_tasks  # noqa: F401 - Must be first
from .env_setup import EnvironmentMapper

# NOTE: browsergym.experiments is imported INSIDE functions to allow
# goal evaluation configuration to happen first in subprocesses

__all__ = ["ExperimentConfig", "ExperimentRunner"]


class ExperimentConfig:
    """Encapsulates all parameters needed to run an AgentLab experiment."""

    def __init__(
        self,
        agent_args: AgentArgs,
        task_name: str,
        task_type: str,
        url: str,
        goal: str,
        max_steps: int,
        headless: bool,
        slow_mo: int,
        viewport_width: int,
        viewport_height: int,
        exp_dir: str,
        model_name: str,
        enable_goal_eval: bool = False,
        eval_frequency: int = 2,
        eval_start_step: int = 3,
        eval_use_vision: bool = False,
    ):
        self.agent_args = agent_args
        self.task_name = task_name
        self.task_type = task_type
        self.url = url
        self.goal = goal
        self.max_steps = max_steps
        self.headless = headless
        self.slow_mo = slow_mo
        self.viewport_width = viewport_width
        self.viewport_height = viewport_height
        self.exp_dir = exp_dir
        self.model_name = model_name
        self.enable_goal_eval = enable_goal_eval
        self.eval_frequency = eval_frequency
        self.eval_start_step = eval_start_step
        self.eval_use_vision = eval_use_vision

    def to_dict(self) -> dict[str, Any]:
        """Convert configuration to dictionary for subprocess serialization."""
        return {
            "agent_args": self.agent_args,
            "task_name": self.task_name,
            "task_type": self.task_type,
            "url": self.url,
            "goal": self.goal,
            "max_steps": self.max_steps,
            "headless": self.headless,
            "slow_mo": self.slow_mo,
            "viewport_width": self.viewport_width,
            "viewport_height": self.viewport_height,
            "exp_dir": self.exp_dir,
            "model_name": self.model_name,
            "enable_goal_eval": self.enable_goal_eval,
            "eval_frequency": self.eval_frequency,
            "eval_start_step": self.eval_start_step,
            "eval_use_vision": self.eval_use_vision,
        }


class ExperimentRunner:
    """Executes AgentLab experiments in isolated subprocesses."""

    @staticmethod
    def run(config: ExperimentConfig) -> dict[str, Any]:
        """Run experiment in a subprocess to avoid async conflicts.

        Args:
            config: Complete experiment configuration

        Returns:
            Dictionary with exp_dir and completion status
        """
        # Note: Goal evaluation config is passed via config.to_dict() and configured
        # directly in the subprocess (see _execute method)
        try:
            result_queue: multiprocessing.Queue[dict[str, Any]] = multiprocessing.Queue()

            # Create subprocess with explicit environment
            # Note: On macOS, multiprocessing uses 'spawn' which creates a fresh interpreter
            # Need to ensure environment variables are available in the subprocess
            ctx = multiprocessing.get_context("spawn")
            process = ctx.Process(
                target=ExperimentRunner._subprocess_target, args=(config.to_dict(), result_queue)
            )

            process.start()
            process.join()

            if not result_queue.empty():
                return result_queue.get()  # type: ignore[no-any-return]

            return {
                "exp_dir": config.exp_dir,
                "completed": False,
                "error": "Process failed to return results",
            }
        except Exception as e:
            logger.error(f"Error spawning subprocess: {e}", exc_info=True)
            return {"exp_dir": config.exp_dir, "completed": False, "error": str(e)}

    @staticmethod
    def _subprocess_target(config_dict: dict[str, Any], result_queue: multiprocessing.Queue):
        """Subprocess entry point for experiment execution.

        IMPORTANT: Configure goal evaluation FIRST, before any browsergym imports!
        """
        try:
            # Configure goal evaluation BEFORE any browsergym code runs
            # This ensures the task class reads the correct configuration
            from sygra.integrations.agentlab.tasks.openended_task import configure_goal_evaluation

            configure_goal_evaluation(
                enable=config_dict.get("enable_goal_eval", False),
                frequency=config_dict.get("eval_frequency", 2),
                start_step=config_dict.get("eval_start_step", 3),
                use_vision=config_dict.get("eval_use_vision", False),
            )

            result = ExperimentRunner._execute(config_dict)
            result_queue.put(result)
        except Exception as e:
            logger.error(f"Subprocess error: {e}", exc_info=True)
            result_queue.put(
                {"exp_dir": config_dict.get("exp_dir", ""), "completed": False, "error": str(e)}
            )

    @staticmethod
    def _execute(config: dict[str, Any]) -> dict[str, Any]:
        """Execute experiment using AgentLab's ExpArgs.run().

        Args:
            config: Experiment configuration dictionary

        Returns:
            Dictionary with exp_dir and completion status
        """
        EnvironmentMapper.setup(config["model_name"])

        # Apply task patches FIRST before any browsergym operations
        from ..tasks import patch_tasks

        patch_tasks()

        # Import browsergym AFTER patching is done
        # Set exp_dir env var so task can save completion info
        import os

        from browsergym.experiments import EnvArgs, ExpArgs  # type: ignore[import-untyped]

        exp_dir_parent = Path(config["exp_dir"])
        # Browse gym will create a timestamped subdirectory, but we'll update this later
        # For now, pass the parent so task knows where to write
        os.environ["BROWSERGYM_EXP_DIR_PARENT"] = str(exp_dir_parent)

        # Apply SOM overlay retina fix to ensure consistent coordinate scaling
        # This gives SOM overlays the same coordinate scaling as action overlays
        from ..display.overlay_fix import patch_som_overlay

        patch_som_overlay()

        # Use AgentLab's native retina display handling (but don't disable our SOM patches)
        ExperimentRunner._setup_retina_handling(disable_som_patches=False)

        env_args = ExperimentRunner._create_env_args(config, EnvArgs)

        # DON'T set exp_dir in ExpArgs - let browsergym create timestamped subdirectories
        exp_args = ExpArgs(
            agent_args=config["agent_args"],
            env_args=env_args,
            exp_dir=None,  # Let browsergym manage directory creation
            exp_name=config["task_name"],
            enable_debug=False,
            save_screenshot=True,
            save_som=True,
        )

        # Pass the base directory - browsergym will create timestamped subdirs automatically
        # Format: {base_dir}/{timestamp}_{exp_name}
        exp_root = Path(config["exp_dir"])
        exp_root.mkdir(parents=True, exist_ok=True)

        exp_args.prepare(exp_root)
        exp_args.run()

        actual_exp_dir = str(exp_args.exp_dir)
        logger.info(f"Experiment completed: {actual_exp_dir}")

        ExperimentRunner._log_summary(actual_exp_dir)

        return {"exp_dir": actual_exp_dir, "completed": True}

    @staticmethod
    def _create_env_args(config: dict[str, Any], EnvArgs):
        """Create BrowserGym EnvArgs from experiment configuration."""
        task_type = config["task_type"]
        is_custom = task_type in ("custom", "openended")

        # Build task kwargs for custom/openended tasks
        task_kwargs = {}
        if is_custom:
            task_kwargs = {
                "start_url": config["url"],
                "goal": config["goal"],
                # Note: Goal evaluation is configured via configure_goal_evaluation()
                # in _subprocess_target before browsergym is imported
            }

        return EnvArgs(
            task_name="openended" if is_custom else task_type,
            task_kwargs=task_kwargs,
            max_steps=config["max_steps"],
            headless=config["headless"],
            slow_mo=config["slow_mo"],
            viewport={"width": config["viewport_width"], "height": config["viewport_height"]},
            record_video=not config["headless"],
        )

    @staticmethod
    def _log_summary(exp_dir: str):
        """Log experiment summary statistics if available."""
        summary_file = Path(exp_dir) / "summary_info.json"

        if summary_file.exists():
            try:
                with open(summary_file) as f:
                    summary = json.load(f)
                logger.info(f"Steps completed: {summary.get('n_steps', 0)}")
            except Exception:
                pass

    @staticmethod
    def _setup_retina_handling(disable_som_patches: bool = True):
        """Setup AgentLab's native retina display handling.

        Uses AGENTLAB_USE_RETINA environment variable which AgentLab uses
        internally to scale coordinates for high-DPI displays.

        Args:
            disable_som_patches: Whether to disable custom SOM patches. Set to False
                               when using our new AgentLab-compatible SOM overlay fix.
        """
        import os
        import platform

        # Check if already set by user
        if "AGENTLAB_USE_RETINA" in os.environ:
            # User has manually set this, conditionally disable old patches
            if disable_som_patches:
                ExperimentRunner._disable_custom_som_patches()
            return

        # Auto-detect retina displays on macOS
        if platform.system() == "Darwin":
            try:
                # Try to detect retina display using system_profiler
                import subprocess

                result = subprocess.run(
                    ["system_profiler", "SPDisplaysDataType"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                if "Retina" in result.stdout or "5K" in result.stdout or "4K" in result.stdout:
                    os.environ["AGENTLAB_USE_RETINA"] = "1"
                    from sygra.logger.logger_config import logger

                    logger.info("🖥️  Detected Retina display, enabling AGENTLAB_USE_RETINA")
                    # Only disable custom patches if requested (for compatibility)
                    if disable_som_patches:
                        ExperimentRunner._disable_custom_som_patches()
            except Exception:
                # Fallback: enable for all macOS since most have high-DPI displays
                os.environ["AGENTLAB_USE_RETINA"] = "1"
                from sygra.logger.logger_config import logger

                logger.info("🖥️  Enabling AGENTLAB_USE_RETINA for macOS (fallback)")
                # Only disable custom patches if requested (for compatibility)
                if disable_som_patches:
                    ExperimentRunner._disable_custom_som_patches()

        # For other platforms, user can manually set AGENTLAB_USE_RETINA=1 if needed

    @staticmethod
    def _disable_custom_som_patches():
        """Disable our custom SOM overlay patches to prevent double scaling.

        This method restores the original overlay_som function in all modules
        that may have been patched by our custom implementation.
        """
        try:
            from sygra.logger.logger_config import logger

            logger.info("🛑 _disable_custom_som_patches called - disabling SOM patches")

            # Set a flag to prevent our overlay patches from applying coordinate scaling
            import os

            os.environ["SYGRA_DISABLE_SOM_PATCHES"] = "1"

            # Try to restore original overlay_som function if it was patched
            try:
                from ..display.overlay_fix import _original_overlay_som

                if _original_overlay_som is not None:
                    # Restore original function in browsergym.utils.obs
                    try:
                        import browsergym.utils.obs as obs_module  # type: ignore[import-untyped]

                        obs_module.overlay_som = _original_overlay_som  # type: ignore[attr-defined]
                    except ImportError:
                        pass

                    # Restore in sys.modules
                    import sys

                    if "browsergym.utils.obs" in sys.modules:
                        sys.modules["browsergym.utils.obs"].overlay_som = _original_overlay_som  # type: ignore[attr-defined]

                    logger.info(
                        "Disabled custom SOM overlay patches to prevent double scaling with AGENTLAB_USE_RETINA"
                    )

            except ImportError:
                # overlay_fix module not available, nothing to disable
                pass

        except Exception as e:
            from sygra.logger.logger_config import logger

            logger.warning(f"Failed to disable custom SOM patches: {e}")
