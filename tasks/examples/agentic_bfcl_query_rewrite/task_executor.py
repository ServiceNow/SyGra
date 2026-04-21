"""
Post-processor for BFCL query rewriting pipeline.

The LLM returns a JSON object with:
  {
    "query_medium": "...",
    "query_hard":   "..."
  }

We parse it, validate it is grounded (non-empty, not identical to original),
and write both variants into state.
"""

import json
import re

from sygra.core.graph.functions.node_processor import NodePostProcessorWithState, NodePreProcessor
from sygra.core.graph.sygra_message import SygraMessage
from sygra.core.graph.sygra_state import SygraState

# Truncation limits to stay within context
TOOLS_TRUNCATE = 4000   # chars of available_tools sent to model
CALLS_TRUNCATE = 2000   # chars of expected_tool_calls sent to model


class BuildRewritePromptPreProcessor(NodePreProcessor):
    """Formats available_tools and expected_tool_calls for the prompt."""

    def apply(self, state: SygraState) -> SygraState:
        tools_raw = (state.get("available_tools") or "")
        calls_raw = (state.get("expected_tool_calls") or "")

        # Pretty-print for readability in prompt, then truncate
        try:
            tools_pretty = json.dumps(json.loads(tools_raw), indent=2)
        except Exception:
            tools_pretty = tools_raw
        try:
            calls_pretty = json.dumps(json.loads(calls_raw), indent=2)
        except Exception:
            calls_pretty = calls_raw

        state["tools_section"] = tools_pretty[:TOOLS_TRUNCATE]
        state["calls_section"] = calls_pretty[:CALLS_TRUNCATE]
        return state


class ExtractRewrittenQueriesPostProcessor(NodePostProcessorWithState):
    """Parses the LLM JSON output into query_medium and query_hard."""

    def apply(self, response: SygraMessage, state: SygraState) -> SygraState:
        raw = response.message.content.strip()
        state["llm_raw_output"] = raw

        # Strip markdown fences if present
        if raw.startswith("```"):
            lines = raw.split("\n")
            inner = lines[1:-1] if lines[-1].strip() in ("```", "") else lines[1:]
            raw = "\n".join(inner).strip()

        query_medium = ""
        query_hard = ""

        try:
            parsed = json.loads(raw)
            query_medium = str(parsed.get("query_medium", "")).strip()
            query_hard   = str(parsed.get("query_hard",   "")).strip()
        except (json.JSONDecodeError, AttributeError):
            # Fallback: regex extraction
            m_med  = re.search(r'"query_medium"\s*:\s*"((?:[^"\\]|\\.)*)"', raw, re.DOTALL)
            m_hard = re.search(r'"query_hard"\s*:\s*"((?:[^"\\]|\\.)*)"',   raw, re.DOTALL)
            if m_med:
                query_medium = m_med.group(1).replace('\\"', '"').strip()
            if m_hard:
                query_hard = m_hard.group(1).replace('\\"', '"').strip()

        original = state.get("user_message", "")

        # Sanity checks — fall back to original if rewrite is empty or unchanged
        if not query_medium or query_medium == original:
            query_medium = original
            state["rewrite_medium_status"] = "FAILED"
        else:
            state["rewrite_medium_status"] = "OK"

        if not query_hard or query_hard == original:
            query_hard = original
            state["rewrite_hard_status"] = "FAILED"
        else:
            state["rewrite_hard_status"] = "OK"

        state["query_medium"] = query_medium
        state["query_hard"]   = query_hard
        return state
