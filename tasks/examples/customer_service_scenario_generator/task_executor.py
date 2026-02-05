"""
Customer Service Scenario Generator - Task Executor

Generates input.json files for customer_service_agent_audio tasks.
Takes seed scenario types and uses LLMs to create diverse, realistic scenarios.
"""

import json
import re
import uuid
from typing import Any

from sygra.core.graph.functions.node_processor import NodePostProcessorWithState
from sygra.core.graph.sygra_message import SygraMessage
from sygra.core.graph.sygra_state import SygraState
from sygra.processors.output_record_generator import BaseOutputGenerator


def safe_json_extract(text: str) -> dict:
    """Safely extract JSON from LLM response text."""
    # Try to find JSON block
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass
    # Try direct parse
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    return {}


class InitialQueryPostProcessor(NodePostProcessorWithState):
    """Extracts the generated initial query."""

    def apply(self, response: SygraMessage, state: SygraState) -> SygraState:
        content = response.message.content.strip()
        # Remove quotes if present
        if content.startswith('"') and content.endswith('"'):
            content = content[1:-1]
        if content.startswith("'") and content.endswith("'"):
            content = content[1:-1]
        state["initial_query"] = content
        return state


class ScenarioDetailsPostProcessor(NodePostProcessorWithState):
    """Extracts scenario_context and ground_truth from LLM response."""

    def apply(self, response: SygraMessage, state: SygraState) -> SygraState:
        content = response.message.content
        parsed = safe_json_extract(content)

        if parsed:
            state["scenario_context"] = parsed.get("scenario_context", "")
            state["ground_truth"] = parsed.get("ground_truth", "")
        else:
            # Fallback: try to extract from text
            state["scenario_context"] = content
            state["ground_truth"] = ""

        return state


class ScenarioOutputGenerator(BaseOutputGenerator):
    """Generates output in the format expected by customer_service_agent_audio tasks."""

    # Counter for generating unique IDs
    _counter = 0

    @staticmethod
    def generate_unique_id(data: Any, state: SygraState) -> str:
        """Generate a unique ID for each scenario."""
        ScenarioOutputGenerator._counter += 1
        scenario_type = state.get("scenario_type", "unknown")
        # Create a short type prefix
        type_prefix = "".join(word[0] for word in scenario_type.split("_"))[:3].upper()
        return f"cs_{type_prefix}_{ScenarioOutputGenerator._counter:03d}"
