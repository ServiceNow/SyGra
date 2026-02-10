import json
import re
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


def safe_list_extract(text: str, key: str) -> list:
    """Extract a list from JSON response."""
    parsed = safe_json_extract(text)
    if parsed and key in parsed:
        value = parsed[key]
        if isinstance(value, list):
            return value
        elif isinstance(value, str):
            # Try to parse as JSON list
            try:
                return json.loads(value)
            except:
                return [value]
    return []


class UserScenarioPostProcessor(NodePostProcessorWithState):
    """Extracts user_goal and first_utterance from LLM response."""

    def apply(self, response: SygraMessage, state: SygraState) -> SygraState:
        content = response.message.content
        parsed = safe_json_extract(content)

        if parsed:
            state["user_goal"] = parsed.get("user_goal", "")
            first_utterance = parsed.get("first_utterance", "")
            # Clean up quotes if present
            if first_utterance.startswith('"') and first_utterance.endswith('"'):
                first_utterance = first_utterance[1:-1]
            state["first_utterance"] = first_utterance
        else:
            # Fallback: use raw content
            state["user_goal"] = content
            state["first_utterance"] = ""

        return state


class RequirementsPostProcessor(NodePostProcessorWithState):
    """Extracts and validates selected_agents and selected_tools from LLM response.

    Ensures selected values are subsets of available options from seed data.
    """

    def apply(self, response: SygraMessage, state: SygraState) -> SygraState:
        content = response.message.content
        parsed = safe_json_extract(content)

        # Get available options from seed data
        available_agents = state.get("required_agents", [])
        available_tools = state.get("required_tools", [])

        if parsed:
            selected_agents = parsed.get("selected_agents", [])
            selected_tools = parsed.get("selected_tools", [])

            # Ensure they are lists
            if isinstance(selected_agents, str):
                selected_agents = [selected_agents]
            if isinstance(selected_tools, str):
                selected_tools = [selected_tools]

            # Validate: only keep values that exist in available options
            validated_agents = [a for a in selected_agents if a in available_agents]
            validated_tools = [t for t in selected_tools if t in available_tools]

            # Ensure at least one of each if available
            if not validated_agents and available_agents:
                validated_agents = [available_agents[0]]
            if not validated_tools and available_tools:
                validated_tools = [available_tools[0]]

            state["selected_agents"] = validated_agents
            state["selected_tools"] = validated_tools
        else:
            # Fallback to all available options
            state["selected_agents"] = available_agents
            state["selected_tools"] = available_tools

        return state


class UserScenarioScriptPostProcessor(NodePostProcessorWithState):
    """Extracts the detailed user_scenario script from LLM response."""

    def apply(self, response: SygraMessage, state: SygraState) -> SygraState:
        content = response.message.content.strip()
        # The user_scenario is typically raw text/markdown, not JSON
        state["user_scenario"] = content
        return state


class ExpectedOutcomePostProcessor(NodePostProcessorWithState):
    """Extracts the expected_outcome from LLM response."""

    def apply(self, response: SygraMessage, state: SygraState) -> SygraState:
        content = response.message.content.strip()
        parsed = safe_json_extract(content)

        if parsed and "expected_outcome" in parsed:
            state["expected_outcome"] = parsed["expected_outcome"]
        else:
            # Fallback: use raw content
            state["expected_outcome"] = content

        return state


class ConversationPostProcessor(NodePostProcessorWithState):
    """Extracts raw_conversation from LLM response."""

    def apply(self, response: SygraMessage, state: SygraState) -> SygraState:
        content = response.message.content
        parsed = safe_json_extract(content)

        conversation = []
        if parsed and "conversation_example" in parsed:
            conv = parsed["conversation_example"]
            if isinstance(conv, list):
                conversation = conv
        else:
            # Try to parse the entire response as a list
            try:
                match = re.search(r"\[.*\]", content, re.DOTALL)
                if match:
                    conversation = json.loads(match.group(0))
            except:
                pass

        state["raw_conversation"] = conversation
        return state


class ConversationClosurePostProcessor(NodePostProcessorWithState):
    """Processes LLM-generated conversation closure to ensure proper ending."""

    def apply(self, response: SygraMessage, state: SygraState) -> SygraState:
        content = response.message.content
        parsed = safe_json_extract(content)

        conversation = None
        if parsed and "conversation_example" in parsed:
            conv = parsed["conversation_example"]
            if isinstance(conv, list):
                conversation = conv

        if conversation is None:
            # Try to parse as a list directly
            try:
                match = re.search(r"\[.*\]", content, re.DOTALL)
                if match:
                    conversation = json.loads(match.group(0))
            except:
                pass

        if conversation is not None:
            state["conversation_example"] = conversation
        else:
            # Fall back to raw_conversation if parsing fails
            raw_conv = state.get("raw_conversation", [])
            if raw_conv:
                state["conversation_example"] = raw_conv

        return state


class VoiceAgentOutputGenerator(BaseOutputGenerator):
    """Generates output in voice_agents.jsonl format."""

    # Counter for generating unique IDs
    _counter = 0

    @staticmethod
    def generate_unique_id(data: Any, state: SygraState) -> str:
        """Generate a unique ID for each scenario."""
        VoiceAgentOutputGenerator._counter += 1
        category = state.get("category", "unknown")
        usecase = state.get("usecase", "unknown")
        # Create a short prefix from category and usecase
        cat_prefix = category[:2].upper()
        uc_words = usecase.strip().split()
        uc_prefix = "".join(w[0].upper() for w in uc_words[:2]) if uc_words else "XX"
        return f"{cat_prefix}_{uc_prefix}_{VoiceAgentOutputGenerator._counter:03d}"

    @staticmethod
    def parse_boolean(data: Any, state: SygraState) -> bool:
        """Parse human_escalation_required to boolean."""
        value = state.get("human_escalation_required", False)
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.lower() == "true"
        return bool(value)
