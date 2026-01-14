from __future__ import annotations

from typing import Any, Dict

from sygra.core.graph.functions.edge_condition import EdgeCondition
from sygra.core.graph.functions.lambda_function import LambdaFunction
from sygra.core.graph.sygra_message import SygraMessage
from sygra.core.graph.sygra_state import SygraState
from sygra.logger.logger_config import logger
from sygra.utils import utils


class InitSelfRefinementState(LambdaFunction):
    @staticmethod
    def apply(lambda_node_dict: dict, state: SygraState):
        params = lambda_node_dict.get("params", {}) if isinstance(lambda_node_dict, dict) else {}
        max_iterations = int(params.get("max_iterations", 2))
        score_threshold = int(params.get("score_threshold", 4))

        # Internal keys are prefixed to reduce collision risk in host graphs
        state["_self_refine_iteration"] = 0
        state["_self_refine_max_iterations"] = max_iterations
        state["_self_refine_score_threshold"] = score_threshold

        if "reflection_trajectory" not in state or not isinstance(
            state.get("reflection_trajectory"), list
        ):
            state["reflection_trajectory"] = []

        return state


class SelfRefinementJudgePostProcessor:
    def __init__(self, node_config: dict | None = None):
        self.node_config = node_config or {}

    def apply(self, resp: SygraMessage, state: SygraState) -> SygraState:
        content = ""
        try:
            content = resp.message.content  # type: ignore[attr-defined]
        except Exception:
            content = ""

        parsed = utils.extract_and_load_json(str(content))
        if not isinstance(parsed, dict):
            parsed = {"raw": content}

        # Normalize outputs
        score = parsed.get("score")
        is_good = parsed.get("is_good")
        critique = parsed.get("critique")

        # Allow alternative key names
        if score is None:
            score = parsed.get("QUALITY_SCORE")
        if is_good is None:
            is_good = parsed.get("pass")
        if critique is None:
            critique = parsed.get("QUALITY_EXPLANATION")

        try:
            score_int = int(score) if score is not None else None
        except Exception:
            score_int = None

        max_score_threshold = state.get("_self_refine_score_threshold", 4)

        is_good_bool = False
        if isinstance(is_good, bool):
            is_good_bool = is_good
        elif isinstance(is_good, str):
            is_good_bool = is_good.strip().lower() in {"true", "yes", "y", "pass", "good"}
        elif score_int is not None:
            is_good_bool = score_int >= int(max_score_threshold)

        state["self_refine_judge"] = {
            "score": score_int,
            "is_good": is_good_bool,
            "critique": critique,
            "raw": parsed,
        }
        state["self_refine_is_good"] = is_good_bool
        state["self_refine_critique"] = critique or ""
        return state


class UpdateSelfRefinementTrajectory(LambdaFunction):
    @staticmethod
    def apply(lambda_node_dict: dict, state: SygraState):
        iteration = int(state.get("_self_refine_iteration", 0))
        candidate_key = "candidate"
        judge_key = "self_refine_judge"

        params = lambda_node_dict.get("params", {}) if isinstance(lambda_node_dict, dict) else {}
        if isinstance(params, dict):
            candidate_key = params.get("candidate_key", candidate_key)
            judge_key = params.get("judge_key", judge_key)

        candidate_val = state.get(candidate_key)
        judge_val = state.get(judge_key)

        entry: Dict[str, Any] = {
            "iteration": iteration,
            "candidate_key": candidate_key,
            "candidate": candidate_val,
            "judge": judge_val,
        }

        trajectory = state.get("reflection_trajectory")
        if not isinstance(trajectory, list):
            trajectory = []

        trajectory.append(entry)
        state["reflection_trajectory"] = trajectory

        state["_self_refine_iteration"] = iteration + 1
        return state


class SelfRefinementLoopCondition(EdgeCondition):
    @staticmethod
    def apply(state: SygraState) -> str:
        is_good = state.get("self_refine_is_good", False)
        iteration = int(state.get("_self_refine_iteration", 0))
        max_iterations = int(state.get("_self_refine_max_iterations", 2))

        if is_good:
            logger.debug("Self refinement accepted by judge.")
            return "accept"

        if iteration >= max_iterations:
            logger.debug(
                "Self refinement reached max iterations (%s). Accepting last candidate.",
                max_iterations,
            )
            return "accept"

        return "refine"
