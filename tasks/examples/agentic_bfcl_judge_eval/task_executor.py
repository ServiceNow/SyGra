from typing import Any
import json
import re

from langchain_core.messages import AIMessage, HumanMessage

from sygra.core.graph.functions.edge_condition import EdgeCondition
from sygra.core.graph.functions.node_processor import (
    NodePostProcessor,
    NodePreProcessor,
    NodePostProcessorWithState,
)
from sygra.core.graph.sygra_state import SygraState
from sygra.core.graph.sygra_message import SygraMessage
from sygra.processors.output_record_generator import BaseOutputGenerator
from sygra.utils import constants, utils
from sygra.core.graph.functions.lambda_function import LambdaFunction
from sygra.core.graph.sygra_state import SygraState

class SerializeFieldsPreProcessor(NodePreProcessor):
    """Ensures list/dict fields in state are serialized to JSON strings for prompt templates."""

    def apply(self, state: SygraState) -> SygraState:
        for key in ["generated_tool_calls", "available_tools", "expected_responses"]:
            val = state.get(key)
            if val is not None and not isinstance(val, str):
                state[key] = json.dumps(val, indent=2)
        return state


def safe_parse_json(raw):
    """Parse a JSON value from a string, list, or dict. Strips markdown fences and think tags."""
    if not isinstance(raw, str):
        return raw
    text = raw.strip()
    # Strip think tags
    if "</think>" in text:
        text = text.split("</think>")[-1].strip()
    # Strip markdown fences
    text = re.sub(r"^```(?:json)?\s*\n?", "", text)
    text = re.sub(r"\n?```\s*$", "", text)
    text = text.strip()
    return json.loads(text)


def extract_tool_calls(generated_tool_calls, expected_responses):
    """
    Normalize tool calls into:
    [
      {
        "tool_name": str,
        "arguments": dict
      }
    ]

    Supports:
    - generated_tool_calls (list of {function: {...}})
    - expected_responses (assistant messages with tool_calls)
    """

    generated = safe_parse_json(generated_tool_calls)
    expected_responses = safe_parse_json(expected_responses)

    expected = []

    for msg in expected_responses:
        if not isinstance(msg, dict):
            continue

        if msg.get("role") == "assistant" and msg.get("tool_calls"):
            tool_calls = msg["tool_calls"]

            # tool_calls may be a JSON string
            try:
                tool_calls = safe_parse_json(tool_calls)
            except Exception:
                continue

            # flatten
            if isinstance(tool_calls, list):
                for tc in tool_calls:
                    if isinstance(tc, dict):
                        expected.append(tc)

    return generated, expected

class ProgrammaticJudge(LambdaFunction):
    def apply(lambda_node_dict: dict, state: SygraState) -> SygraState:
        """
        Programmatic judge for agentic tool-calling behavior.

        Metrics:
        1. Tool selection accuracy:
           Penalizes missing and extra tools (exact tool identity required).

        2. Parameter structure accuracy:
           Enforces exact parameter-key matching for expected tools.
           Unknown tools score 0. Extra or missing parameters are penalized.

        3. Sequence accuracy:
           Measures positional correctness of tool calls (order matters).

        4. Query coverage accuracy:
           Measures how much of the expected tool intent space is covered,
           independent of correctness.

        This judge is strictly symbolic and deterministic:
        - No semantic reasoning
        - No value correctness checks
        - No natural language analysis
        """

        # ----------------------------
        # Normalize inputs
        # ----------------------------
        generated, expected = extract_tool_calls(state["generated_tool_calls"], state["expected_responses"])

        gen_tools = [g["function"]["name"] for g in generated]
        exp_tools = [e["function"]["name"] for e in expected]

        gen_set, exp_set = set(gen_tools), set(exp_tools)
        intersection = gen_set & exp_set

        # ----------------------------
        # 1. TOOL SELECTION ACCURACY
        # ----------------------------
        extra_tools = gen_set - exp_set
        missing_tools = exp_set - gen_set

        if not gen_set and not exp_set:
            tool_selection_accuracy = 1.0
        else:
            tool_selection_accuracy = max(
                0.0,
                1.0 - (len(extra_tools) + len(missing_tools)) / max(len(exp_set), 1)
            )

        # --------------------------------
        # 2. PARAMETER STRUCTURE ACCURACY
        # --------------------------------
        exp_arg_map = {
            e["function"]["name"]: set(e["function"]["arguments"].keys())
            for e in expected
        }

        param_scores = []

        for g in generated:
            tool = g["function"]["name"]
            provided = set(g["function"]["arguments"].keys())
            expected_args = exp_arg_map.get(tool)

            # Unknown tool → hard fail
            if expected_args is None:
                param_scores.append(0.0)
                continue

            missing = expected_args - provided
            extra = provided - expected_args

            if not missing and not extra:
                param_scores.append(1.0)
            elif not missing:
                param_scores.append(0.5)  # extra args only
            else:
                param_scores.append(0.0)

        parameter_structure_accuracy = (
            sum(param_scores) / len(param_scores)
            if param_scores else 1.0
        )

        # ----------------------------
        # 3. SEQUENCE ACCURACY
        # ----------------------------
        matched_positions = sum(
            1
            for i, tool in enumerate(gen_tools)
            if i < len(exp_tools) and tool == exp_tools[i]
        )

        sequence_accuracy = (
            matched_positions / max(len(exp_tools), 1)
            if exp_tools else 1.0
        )

        # ----------------------------
        # 4. QUERY COVERAGE ACCURACY
        # ----------------------------
        if not exp_set:
            query_coverage_accuracy = 1.0
        elif not intersection:
            query_coverage_accuracy = 0.0
        else:
            query_coverage_accuracy = len(intersection) / len(exp_set)

        # ----------------------------
        # Final Output (STRICT)
        # ----------------------------
        state["programmatic_judge_response"] = {
            "tool_selection_accuracy": {
                "accuracy": round(tool_selection_accuracy, 4)
            },
            "parameter_structure_accuracy": {
                "accuracy": round(parameter_structure_accuracy, 4)
            },
            "sequence_accuracy": {
                "accuracy": round(sequence_accuracy, 4)
            },
            "query_coverage_accuracy": {
                "accuracy": round(query_coverage_accuracy, 4)
            }
        }

        return state

class ComputeLLMVsProgrammaticAccuracy(LambdaFunction):
    def apply(lambda_node_dict: dict, state: SygraState) -> SygraState:
        """
        Computes alignment accuracy (%) of LLM judge against programmatic judge.

        - Programmatic judge is treated as ground truth
        - Accuracy is based on absolute difference per metric
        - Exact match = 100%
        """

        total_metrics = 0
        cumulative_match = 0.0
        per_metric_results = {}
        programmatic_judge_response = state["programmatic_judge_response"]
        judge_response = state["judge_response"]

        for metric, prog_val in programmatic_judge_response.items():
            prog_acc = prog_val.get("accuracy")
            llm_acc = judge_response.get(metric, {}).get("accuracy")

            total_metrics += 1

            if llm_acc is None:
                match_score = 0.0
                error = 1.0
            else:
                error = abs(llm_acc - prog_acc)
                match_score = 1.0 - error  # exact match → 1.0

            per_metric_results[metric] = {
                "programmatic_accuracy": prog_acc,
                "llm_accuracy": llm_acc,
                "absolute_error": round(error, 4),
                "match_score": round(match_score, 4)
            }

            cumulative_match += match_score

        overall_accuracy_percentage = (
            cumulative_match / total_metrics * 100
            if total_metrics else 100.0
        )

        state["per_metric_comparison"] = per_metric_results
        state["overall_llm_alignment_percentage"] = round(overall_accuracy_percentage, 2)
        return state


class JudgeToolCallsPostProcessor(NodePostProcessorWithState):
    def apply(self, response: SygraMessage, state: SygraState) -> SygraState:
        state["judge_response"] = safe_parse_json(response.message.content)
        return state

class JudgeToolCallsAnswerOnlyPostProcessor(NodePostProcessorWithState):
    def apply(self, response: SygraMessage, state: SygraState) -> SygraState:
        state["judge_response_no_gt"] = safe_parse_json(response.message.content)
        return state

class ComputeLLMVsProgrammaticAccuracyAnswerOnly(LambdaFunction):
    def apply(lambda_node_dict: dict, state: SygraState) -> SygraState:
        """
        Computes alignment accuracy (%) of LLM judge against programmatic judge.

        - Programmatic judge is treated as ground truth
        - Accuracy is based on absolute difference per metric
        - Exact match = 100%
        """

        total_metrics = 0
        cumulative_match = 0.0
        per_metric_results = {}
        programmatic_judge_response = state["programmatic_judge_response"]
        judge_response = state["judge_response_no_gt"]

        for metric, prog_val in programmatic_judge_response.items():
            prog_acc = prog_val.get("accuracy")
            llm_acc = judge_response.get(metric, {}).get("accuracy")

            total_metrics += 1

            if llm_acc is None:
                match_score = 0.0
                error = 1.0
            else:
                error = abs(llm_acc - prog_acc)
                match_score = 1.0 - error  # exact match → 1.0

            per_metric_results[metric] = {
                "programmatic_accuracy": prog_acc,
                "llm_accuracy": llm_acc,
                "absolute_error": round(error, 4),
                "match_score": round(match_score, 4)
            }

            cumulative_match += match_score

        overall_accuracy_percentage = (
            cumulative_match / total_metrics * 100
            if total_metrics else 100.0
        )

        state["per_metric_comparison_no_gt"] = per_metric_results
        state["overall_llm_alignment_percentage_no_gt"] = round(overall_accuracy_percentage, 2)
        return state