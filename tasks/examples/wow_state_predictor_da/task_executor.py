"""SyGra node processors for the WoW state predictor task.

InitState:          Lambda node — validates and normalises incoming state keys.
DiscoveryPostProcessor: Agent post-processor — extracts {"audits": [...]} from
                        the ReAct agent's final AIMessage.
"""

import json
import logging
import re
from typing import Any, Optional

from sygra.core.graph.functions.node_processor import NodePostProcessorWithState
from sygra.core.graph.sygra_message import SygraMessage
from sygra.core.graph.sygra_state import SygraState

_log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# InitState — Lambda node
# ---------------------------------------------------------------------------


class InitState:
    """Validate and normalise state keys before the discovery agent runs.

    Ensures that all keys the agent prompt references are present and
    serialised to JSON strings (never raw dicts), so the prompt template
    can safely interpolate them.
    """

    @staticmethod
    def apply(config: dict, state: SygraState) -> SygraState:
        required = ("action_json", "previous_states_json", "table_schemas_json", "tool_specs_json")
        for key in required:
            if key not in state:
                raise ValueError(
                    f"InitState: required key '{key}' missing from state. "
                    "runner.py must populate it before invoking the graph."
                )

        # Normalise any key that might have arrived as a Python dict/list
        # (e.g. if the runner passes dicts directly instead of JSON strings).
        for key in required:
            val = state[key]
            if not isinstance(val, str):
                state[key] = json.dumps(val)

        # Default step_index
        state.setdefault("step_index", 0)

        return state


# ---------------------------------------------------------------------------
# DiscoveryPostProcessor — Agent post-processor
# ---------------------------------------------------------------------------


class DiscoveryPostProcessor(NodePostProcessorWithState):
    """Extract {"audits": [...]} from the discovery agent's final response.

    Extraction priority:
      1. JSON inside a ```json ... ``` code fence
      2. Greedy {.*} regex (re.DOTALL) — same as WoW's agent.py
      3. Empty audits fallback — never raises, always writes something

    Also handles WoW's backward-compat key rename: sysauditrecord → audits.
    """

    # ------------------------------------------------------------------
    # Parsing helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_json_from_fences(text: str) -> Optional[dict]:
        """Try to extract the first valid JSON object from a code fence."""
        for fence_match in re.finditer(r"```(?:json)?\s*(\{)", text):
            start_pos = fence_match.start(1)
            fence_end = text.find("```", fence_match.end())
            if fence_end == -1:
                fence_end = len(text)

            brace_depth = 0
            end_pos = -1
            for i, ch in enumerate(text[start_pos:fence_end]):
                if ch == "{":
                    brace_depth += 1
                elif ch == "}":
                    brace_depth -= 1
                    if brace_depth == 0:
                        end_pos = start_pos + i + 1
                        break

            if end_pos > 0:
                try:
                    obj = json.loads(text[start_pos:end_pos])
                    if isinstance(obj, dict):
                        return obj
                except json.JSONDecodeError:
                    pass
        return None

    @staticmethod
    def _extract_json_greedy(text: str) -> Optional[dict]:
        """Greedy {.*} extraction — mirrors WoW's agent.py regex approach."""
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            try:
                obj = json.loads(match.group())
                if isinstance(obj, dict):
                    return obj
            except json.JSONDecodeError:
                pass
        return None

    @classmethod
    def _parse_prediction(cls, text: str) -> dict:
        """Parse agent output to extract the state prediction dict.

        Returns a dict guaranteed to have an 'audits' key (possibly empty list).
        """
        if not text or not text.strip():
            _log.warning("DiscoveryPostProcessor: empty agent response")
            return {"audits": []}

        # 1. Code-fence extraction
        obj = cls._extract_json_from_fences(text)

        # 2. Greedy regex fallback
        if obj is None:
            obj = cls._extract_json_greedy(text)

        if obj is None:
            _log.warning(
                "DiscoveryPostProcessor: could not parse JSON from agent output "
                "(first 300 chars): %s",
                text[:300],
            )
            return {"audits": []}

        # Backward compat: WoW used 'sysauditrecord' in early trajectories
        if "sysauditrecord" in obj and "audits" not in obj:
            obj["audits"] = obj.pop("sysauditrecord")

        if "audits" not in obj:
            _log.warning(
                "DiscoveryPostProcessor: parsed JSON has no 'audits' key. Keys: %s",
                list(obj.keys()),
            )
            # The model may have returned just an array — wrap it
            if isinstance(obj, list):
                return {"audits": obj}
            return {"audits": []}

        # Ensure each audit record has the required fields; fill missing optional fields
        audits = obj.get("audits", [])
        normalised = []
        for audit in audits:
            if not isinstance(audit, dict):
                continue
            normalised.append(
                {
                    "fieldname": audit.get("fieldname", ""),
                    "newvalue": str(audit.get("newvalue", "")),
                    "tablename": audit.get("tablename", ""),
                    "oldvalue": str(audit.get("oldvalue", "")),
                    "documentkey": audit.get("documentkey", None),
                    "newvalue_display_value": audit.get("newvalue_display_value", None),
                    "oldvalue_display_value": audit.get("oldvalue_display_value", None),
                }
            )
        return {"audits": normalised}

    # ------------------------------------------------------------------
    # Main apply
    # ------------------------------------------------------------------

    def apply(self, response: SygraMessage, state: SygraState) -> SygraState:
        content: str = ""
        if response.message is not None:
            content = response.message.content or ""
            if not isinstance(content, str):
                content = str(content)

        _log.info(
            "DiscoveryPostProcessor: agent output length=%d chars, step=%s",
            len(content),
            state.get("step_index", "?"),
        )

        prediction = self._parse_prediction(content)
        n_audits = len(prediction.get("audits", []))
        _log.info("DiscoveryPostProcessor: extracted %d audit records", n_audits)

        state["predicted_state_json"] = json.dumps(prediction)
        return state
