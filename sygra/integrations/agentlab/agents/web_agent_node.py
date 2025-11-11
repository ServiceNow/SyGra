"""Web agent node for vision-enabled browser automation.

A SyGra node that integrates AgentLab's web automation capabilities,
executing browser tasks with vision models (GPT-4o, GPT-4o-mini).

Example:
    workflow = sygra.Workflow("demo")
    workflow.source([{"goal": "Search Python", "url": "https://google.com"}])
    workflow.add_node("agent", {
        "node_type": "web_agent",
        "model": "gpt-4o",
        "max_steps": 10,
    })
    workflow.run()
"""

import json
from pathlib import Path
from typing import Any

from agentlab.agents.agent_args import AgentArgs  # type: ignore[import-untyped]

from sygra.core.graph.nodes.base_node import BaseNode, NodeState
from sygra.core.graph.sygra_state import SygraState
from sygra.logger.logger_config import logger

from .config import AgentConfigBuilder

__all__ = ["WebAgentNode", "create_web_agent_node"]


class WebAgentNode(BaseNode):
    """Vision-enabled web automation agent node for SyGra workflows.

    Provides browser automation using vision-capable language models.
    Supports headless/visual modes, screenshot capture, and Set-of-Mark
    overlays for precise element interaction.

    Attributes:
        agent_args: AgentLab agent configuration
        max_steps: Maximum steps per task execution
        headless: Run browser without GUI
        slow_mo: Slow motion delay in milliseconds
        viewport_width: Browser viewport width in pixels
        viewport_height: Browser viewport height in pixels
    """

    def __init__(
        self,
        node_name: str,
        model: str = "gpt-4o",
        max_steps: int = 15,
        headless: bool = True,
        slow_mo: int = 0,
        use_screenshot: bool = True,
        use_som: bool = True,
        use_html: bool = False,
        temperature: float = 0.1,
        viewport_width: int = 1280,
        viewport_height: int = 720,
        task_name_from_state: str = "task_name",
        agent_args: AgentArgs | None = None,
        enable_chat: bool = True,
        enable_goal_eval: bool = False,
        eval_frequency: int = 2,
        eval_start_step: int = 3,
        eval_use_vision: bool = False,
        **kwargs,
    ):
        """Initialize web agent node.

        Args:
            node_name: Unique node identifier
            model: Model name ("gpt-4o", "gpt-4o-mini")
            max_steps: Maximum steps per task
            headless: Run browser without GUI
            slow_mo: Milliseconds to slow down actions
            use_screenshot: Enable screenshot observations
            use_som: Enable Set-of-Mark overlays
            use_html: Enable HTML observations
            temperature: Model sampling temperature [0.0, 1.0]
            viewport_width: Browser width in pixels
            viewport_height: Browser height in pixels
            task_name_from_state: State key for task name
            agent_args: Optional pre-configured AgentArgs
            enable_chat: Enable chat actions (send_msg_to_user) for task completion
            enable_goal_eval: Enable automatic LLM-based goal evaluation
            eval_frequency: Evaluate goal every N steps (only if enable_goal_eval=True)
            eval_start_step: Start evaluating after N steps (only if enable_goal_eval=True)
            eval_use_vision: Use screenshots for goal evaluation (more accurate, higher cost)
            **kwargs: Additional keyword arguments
        """
        super().__init__(name=node_name, config=kwargs.get("node_config"))
        self.node_state = NodeState.ACTIVE.value

        # Register state variables for LangGraph
        # Default state variables (always included)
        self.state_variables = [
            "agent_result",
            "trajectory",
            "screenshots",
            "exp_dir",
            "current_url",
        ]

        # If output_keys are specified in config, add them as additional state variables
        if self.node_config and "output_keys" in self.node_config:
            output_keys = self.node_config["output_keys"]
            if isinstance(output_keys, str):
                extra_keys = [output_keys]
            elif isinstance(output_keys, list):
                extra_keys = output_keys
            else:
                raise ValueError(f"output_keys must be a string or list, got {type(output_keys)}")

            # Add extra keys without duplicates
            for key in extra_keys:
                if key not in self.state_variables:
                    self.state_variables.append(key)

        if agent_args is not None:
            self.agent_args = agent_args
        else:
            self.agent_args = AgentConfigBuilder.build(
                model=model,
                temperature=temperature,
                use_screenshot=use_screenshot,
                use_som=use_som,
                use_html=use_html,
                enable_chat=enable_chat,
            )

        self.max_steps = max_steps
        self.headless = headless
        self.slow_mo = slow_mo
        self.viewport_width = viewport_width
        self.viewport_height = viewport_height
        self.task_name_from_state = task_name_from_state
        self.enable_goal_eval = enable_goal_eval
        self.eval_frequency = eval_frequency
        self.eval_start_step = eval_start_step
        self.eval_use_vision = eval_use_vision

        logger.info(
            f"Initialized WebAgentNode: {node_name}"
            + (f" (goal_eval every {eval_frequency} steps)" if enable_goal_eval else "")
        )

    def to_backend(self) -> Any:
        """Convert to LangGraph-compatible runnable."""
        from sygra.utils import utils

        return utils.backend_factory.create_llm_runnable(self._async_forward)

    async def _async_forward(self, state: SygraState) -> dict[str, Any]:
        """Async wrapper for LangGraph compatibility."""
        import asyncio

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.forward, state)

    def forward(self, state: SygraState) -> dict[str, Any]:
        """Execute web agent task.

        Orchestrates experiment execution:
        1. Extract task info from state
        2. Run experiment in subprocess
        3. Load results from disk
        4. Update state with outcomes

        Args:
            state: Current workflow state

        Returns:
            Updated state with agent results
        """
        try:
            # Lazy import to avoid early browsergym loading
            from ..evaluation.result_loader import ResultLoader
            from ..experiments.runner import ExperimentConfig, ExperimentRunner

            task_info = self._extract_task_info(state)
            self._log_task_info(task_info)

            exp_dir = self._prepare_exp_dir(state)

            exp_config = ExperimentConfig(
                agent_args=self.agent_args,
                task_name=task_info["task_name"],
                task_type=task_info["task_type"],
                url=task_info["url"],
                goal=task_info["goal"],
                max_steps=self.max_steps,
                headless=self.headless,
                slow_mo=self.slow_mo,
                viewport_width=self.viewport_width,
                viewport_height=self.viewport_height,
                exp_dir=exp_dir,
                model_name=self.agent_args.chat_model_args.model_name,
                enable_goal_eval=self.enable_goal_eval,
                eval_frequency=self.eval_frequency,
                eval_start_step=self.eval_start_step,
                eval_use_vision=self.eval_use_vision,
            )

            logger.info(f"[{task_info['task_name']}] Running experiment in subprocess...")
            result = ExperimentRunner.run(exp_config)

            if not result.get("completed", False):
                return self._handle_failure(state, result, task_info["task_name"])

            actual_exp_dir = result["exp_dir"]
            logger.info(f"[{task_info['task_name']}] Loading results from: {actual_exp_dir}")

            agent_result = ResultLoader.load(actual_exp_dir, task_info["task_name"])

            # Log experiment summary
            self._log_experiment_summary(agent_result, task_info["task_name"])

            complete_output = self._build_complete_output(
                state, task_info, agent_result, actual_exp_dir
            )
            self._save_complete_output(complete_output, actual_exp_dir, task_info["task_name"])

            return self._update_state(state, agent_result, actual_exp_dir, task_info["task_name"])

        except Exception as e:
            logger.error(f"Error running agent: {e}", exc_info=True)
            return self._handle_exception(state, e)

    def _extract_task_info(self, state: SygraState) -> dict[str, str]:
        """Extract task information from state."""
        return {
            "task_name": str(state.get(self.task_name_from_state, "custom.openended")),
            "task_type": str(state.get("task_type", "custom")),
            "url": str(state.get("url", "https://www.google.com")),
            "goal": str(state.get("goal", "Complete the task")),
        }

    def _log_task_info(self, task_info: dict[str, str]):
        """Log task information."""
        logger.info(f"[{task_info['task_name']}] Starting web agent task")
        logger.info(f"  URL: {task_info['url']}")
        logger.info(f"  Goal: {task_info['goal']}")
        logger.info(f"  Headless: {self.headless}")

    def _log_experiment_summary(self, agent_result: dict, task_name: str):
        """Log experiment summary including completion details."""
        logger.info(
            f"Experiment summary - Steps: {agent_result.get('num_steps', 0)}, "
            f"Cost: ${agent_result.get('total_cost', 0.0):.4f}, "
            f"Success: {agent_result.get('success', False)}"
        )

        # Completion details
        completion_reason = agent_result.get("completion_reason", "unknown")
        if completion_reason == "agent_signal":
            logger.info("Completion: Agent signaled (send_msg_to_user)")
        elif completion_reason == "auto_eval":
            confidence = agent_result.get("eval_confidence")
            conf_str = f"{confidence:.2f}" if confidence is not None else "N/A"
            logger.info(f"Completion: Goal evaluator (confidence: {conf_str})")
        elif completion_reason == "user_exit":
            logger.info("Completion: User exit")
        elif completion_reason == "unknown":
            logger.info("Completion: Reached max_steps without completion signal")

    def _prepare_exp_dir(self, state: SygraState) -> str:
        """Prepare experiment directory using SyGra's infrastructure.

        Uses utils.current_task (set by BaseTaskExecutor and Workflow) to determine
        the correct output location. Experiments are stored in an 'agent_experiments' subdirectory
        to keep them organized separately from other task outputs.

        Returns:
            Path to experiment base directory where artifacts will be stored
        """
        from sygra.utils import utils

        # 1. Check for explicit override in node config
        if self.node_config and "output_dir" in self.node_config:
            exp_base = Path(self.node_config["output_dir"]) / "web_agents"
            logger.debug(f"Using explicit output_dir from config: {exp_base}")

        # 2. Use utils.current_task (set by BaseTaskExecutor/Workflow)
        elif hasattr(utils, "current_task") and utils.current_task:
            # Convert task name to path using SyGra's convention
            task_path = utils._normalize_task_path(utils.current_task)
            exp_base = Path(task_path) / "web_agents"
            logger.debug(f"Using task directory: {exp_base}")

        # 3. Fallback to output directory
        else:
            exp_base = Path("output") / "web_agents"
            logger.debug(f"Using fallback directory: {exp_base}")

        exp_base.mkdir(parents=True, exist_ok=True)
        return str(exp_base)

    def _handle_failure(
        self, state: SygraState, result: dict[str, Any], task_name: str
    ) -> dict[str, Any]:
        """Handle experiment failure."""
        error_msg = result.get("error", "Unknown error")
        exp_dir = result.get("exp_dir", "")

        logger.error(f"[{task_name}] Experiment failed: {error_msg}")

        # Return partial state updates
        return {
            "agent_result": {
                "error": error_msg,
                "num_steps": 0,
                "success": False,
                "total_cost": 0.0,
                "truncated": False,
                "final_reward": 0.0,
            },
            "trajectory": [],
            "screenshots": [],
            "exp_dir": exp_dir,
        }

    def _build_complete_output(
        self,
        state: SygraState,
        task_info: dict[str, str],
        agent_result: dict[str, Any],
        exp_dir: str,
    ) -> dict[str, Any]:
        """Build complete output structure."""
        screenshots = agent_result.get("screenshots", [])
        for screenshot in screenshots:
            if "path" in screenshot and isinstance(screenshot["path"], Path):
                screenshot["path"] = str(screenshot["path"])

        return {
            "id": state.get("id", task_info["task_name"].replace("custom.", "")),
            "goal": task_info["goal"],
            "url": task_info["url"],
            "current_url": agent_result.get("current_url", ""),
            "task_name": task_info["task_name"],
            "task_type": task_info["task_type"],
            "num_steps": agent_result.get("num_steps", 0),
            "success": agent_result.get("success", False),
            "agent_result": {
                "num_steps": agent_result.get("num_steps", 0),
                "total_cost": agent_result.get("total_cost", 0.0),
                "success": agent_result.get("success", False),
                "truncated": agent_result.get("truncated", False),
                "final_reward": agent_result.get("final_reward", 0.0),
                "completion_reason": agent_result.get("completion_reason", "unknown"),
                "agent_message": agent_result.get("agent_message"),
                "eval_confidence": agent_result.get("eval_confidence"),
                "eval_reasoning": agent_result.get("eval_reasoning"),
            },
            "trajectory": agent_result.get("trajectory", []),
            "screenshots": screenshots,
            "exp_dir": str(exp_dir),
        }

    def _save_complete_output(self, complete_output: dict[str, Any], exp_dir: str, task_name: str):
        """Save complete output to JSON file."""
        exp_dir_path = Path(exp_dir)
        exp_dir_path.mkdir(parents=True, exist_ok=True)
        output_file = exp_dir_path / "complete_output.json"

        with open(output_file, "w") as f:
            json.dump(complete_output, f, indent=2)

        logger.debug(f"[{task_name}] Complete output saved to: {output_file}")

    def _update_state(
        self, state: SygraState, agent_result: dict[str, Any], exp_dir: str, task_name: str
    ) -> dict[str, Any]:
        """Update state with results.

        Returns a dict of updates that will be merged into the state by LangGraph.
        """
        updates = {
            "agent_result": agent_result,
            "exp_dir": exp_dir,
        }

        if "trajectory" in agent_result:
            updates["trajectory"] = agent_result["trajectory"]
        if "screenshots" in agent_result:
            updates["screenshots"] = agent_result["screenshots"]
        if "current_url" in agent_result:
            updates["current_url"] = agent_result["current_url"]

        logger.info(
            f"[{task_name}] Completed: {agent_result.get('num_steps', 0)} steps, "
            f"success={agent_result.get('success', False)}"
        )
        logger.info(f"[{task_name}] Results: {exp_dir}")
        return updates

    def _handle_exception(self, state: SygraState, error: Exception) -> dict[str, Any]:
        """Handle unexpected exceptions."""
        logger.error(f"Unexpected error in WebAgentNode: {error}", exc_info=True)

        # Return partial state updates
        return {
            "agent_result": {
                "error": str(error),
                "num_steps": 0,
                "success": False,
                "total_cost": 0.0,
                "truncated": False,
                "final_reward": 0.0,
            },
            "trajectory": [],
            "screenshots": [],
            "exp_dir": "",
        }


def create_web_agent_node(node_name: str, node_config: dict) -> WebAgentNode:
    """Factory function to create WebAgentNode from configuration.

    Args:
        node_name: Unique node identifier
        node_config: Configuration dictionary

    Returns:
        Configured WebAgentNode instance

    Example:
        config = {
            "node_type": "web_agent",
            "model": "gpt-4o",
            "max_steps": 15,
            "headless": True,
            "output_keys": ["custom_metric"]
        }
        node = create_web_agent_node("agent", config)
        # Default state variables (agent_result, trajectory, screenshots, exp_dir) are always included
    """
    return WebAgentNode(
        node_name=node_name,
        model=node_config.get("model", "gpt-4o"),
        max_steps=node_config.get("max_steps", 15),
        headless=node_config.get("headless", True),
        slow_mo=node_config.get("slow_mo", 0),
        use_screenshot=node_config.get("use_screenshot", True),
        use_som=node_config.get("use_som", True),
        use_html=node_config.get("use_html", False),
        temperature=node_config.get("temperature", 0.1),
        viewport_width=node_config.get("viewport_width", 1280),
        viewport_height=node_config.get("viewport_height", 720),
        task_name_from_state=node_config.get("task_from_state", "task_name"),
        agent_args=node_config.get("agent_args"),
        enable_chat=node_config.get("enable_chat", True),
        enable_goal_eval=node_config.get("enable_goal_eval", False),
        eval_frequency=node_config.get("eval_frequency", 2),
        eval_start_step=node_config.get("eval_start_step", 3),
        eval_use_vision=node_config.get("eval_use_vision", False),
        node_config=node_config,  # Pass full config for output_keys extraction
    )
