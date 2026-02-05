import json
import os
import re
import ast
from typing import Any, Optional

from pydantic import BaseModel, Field

from sygra.core.base_task_executor import DefaultTaskExecutor
from sygra.core.graph.functions.node_processor import NodePostProcessorWithState, NodePreProcessor
from sygra.core.graph.graph_postprocessor import GraphPostProcessor
from sygra.core.graph.sygra_message import SygraMessage
from sygra.core.graph.sygra_state import SygraState
from sygra.utils import utils


class FlightBookingScenario(BaseModel):
    scenario_id: str = Field(..., description="Unique scenario identifier (snake_case)")
    name: str = Field(..., description="Short scenario name")
    description: str = Field(..., description="Scenario description to guide conversation generation")
    goal: str = Field(..., description="What the assistant should accomplish")
    outcome: str = Field(..., description="success or failure")
    failure_reason: str = Field("", description="Failure reason when outcome is failure")
    policy: list[str] = Field(..., description="Knowledge-article style policy as a list of strings")
    coverage_tags: list[str] = Field(..., description="Tags describing scenario variations")
    category: str = Field("Travel", description="High-level category")
    subcategory: str = Field("Flight booking", description="Subcategory")
    weight: int = Field(5, description="Sampling weight (1-10)")
    dedup_text: str = Field(..., description="Text summary used for semantic deduplication")

def _parse_json_obj(text: str) -> dict[str, Any]:
    if isinstance(text, dict):
        return text

    try:
        val = json.loads(text)
        if isinstance(val, str):
            try:
                val2 = json.loads(val)
                val = val2
            except Exception:
                pass
        return val if isinstance(val, dict) else {}
    except Exception:
        pass

    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```[a-zA-Z0-9_-]*\n?", "", cleaned)
        cleaned = re.sub(r"\n?```$", "", cleaned)
        cleaned = cleaned.strip()

    # Fallback: extract the first JSON object using a simple brace-balance scan.
    start = cleaned.find("{")
    if start == -1:
        return {}

    in_string = False
    escape = False
    depth = 0
    end: Optional[int] = None
    for i in range(start, len(cleaned)):
        ch = cleaned[i]
        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
            continue

        if ch == '"':
            in_string = True
            continue

        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                end = i + 1
                break

    if end is None:
        return {}

    try:
        val = json.loads(cleaned[start:end])
        return val if isinstance(val, dict) else {}
    except Exception:
        try:
            val = ast.literal_eval(cleaned[start:end])
            return val if isinstance(val, dict) else {}
        except Exception:
            return {}


class ScenarioPreProcessor(NodePreProcessor):
    def apply(self, state: SygraState) -> SygraState:
        if "id" not in state or not state.get("id"):
            state["id"] = "scenario_record"
        return state


class ScenarioPostProcessor(NodePostProcessorWithState):
    def apply(self, resp: SygraMessage, state: SygraState) -> SygraState:
        raw = "" if resp is None or resp.message is None else str(resp.message.content or "")
        obj = _parse_json_obj(raw)

        state["scenario_id"] = str(obj.get("scenario_id") or "")
        state["name"] = str(obj.get("name") or "")
        state["description"] = str(obj.get("description") or "")
        state["goal"] = str(obj.get("goal") or "")
        state["outcome"] = str(obj.get("outcome") or "")
        state["failure_reason"] = str(obj.get("failure_reason") or "")
        state["category"] = str(obj.get("category") or "Travel")
        state["subcategory"] = str(obj.get("subcategory") or "Flight booking")

        weight = obj.get("weight")
        try:
            state["weight"] = int(weight) if weight is not None else 5
        except Exception:
            state["weight"] = 5

        policy = obj.get("policy")
        if isinstance(policy, list):
            state["policy"] = [str(x) for x in policy if x is not None]
        elif isinstance(policy, str) and policy.strip():
            state["policy"] = [policy.strip()]
        else:
            state["policy"] = []

        coverage_tags = obj.get("coverage_tags")
        if isinstance(coverage_tags, list):
            state["coverage_tags"] = [str(x) for x in coverage_tags if x is not None]
        elif isinstance(coverage_tags, str) and coverage_tags.strip():
            state["coverage_tags"] = [coverage_tags.strip()]
        else:
            state["coverage_tags"] = []

        state["dedup_text"] = str(obj.get("dedup_text") or "")
        return state


class ExportFlightBookingScenariosJsonPostProcessor(GraphPostProcessor):
    def __init__(
        self,
        target_task: str = "tasks.examples.flight_booking_conversations",
        target_filename: str = "scenarios_generated.json",
        dedup_processor_name: str = "SemanticDedupPostProcessor",
        overwrite: bool = True,
    ):
        self.target_task = target_task
        self.target_filename = target_filename
        self.dedup_processor_name = dedup_processor_name
        self.overwrite = bool(overwrite)

    @staticmethod
    def _coerce_str_list(v: Any) -> list[str]:
        if v is None:
            return []
        if isinstance(v, list):
            return [str(x) for x in v if x is not None and str(x).strip()]
        if isinstance(v, str) and v.strip():
            return [v.strip()]
        return []

    @staticmethod
    def _coerce_policy(v: Any) -> list[str]:
        return ExportFlightBookingScenariosJsonPostProcessor._coerce_str_list(v)

    def _deduped_output_path(self, output_file: str) -> str:
        base = os.path.basename(output_file)
        if base.startswith("output"):
            new_base = base.replace("output", self.dedup_processor_name, 1)
            return os.path.join(os.path.dirname(output_file), new_base)
        return os.path.join(os.path.dirname(output_file), f"{self.dedup_processor_name}_{base}")

    def process(self, data: list, metadata: dict) -> list:
        output_file = str(metadata.get("output_file", ""))
        source_data: list

        dedup_path = self._deduped_output_path(output_file) if output_file else ""
        if dedup_path and os.path.exists(dedup_path):
            try:
                with open(dedup_path, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                source_data = loaded if isinstance(loaded, list) else data
            except Exception:
                source_data = data
        else:
            source_data = data

        scenarios: list[dict[str, Any]] = []
        seen_ids: set[str] = set()

        for i, item in enumerate(source_data):
            if not isinstance(item, dict):
                continue

            scenario_id = str(item.get("scenario_id") or "").strip()
            if not scenario_id:
                scenario_id = f"scenario_{i}"

            if scenario_id in seen_ids:
                suffix = 2
                while f"{scenario_id}_{suffix}" in seen_ids:
                    suffix += 1
                scenario_id = f"{scenario_id}_{suffix}"
            seen_ids.add(scenario_id)

            weight_raw = item.get("weight")
            try:
                weight = int(weight_raw) if weight_raw is not None else 5
            except Exception:
                weight = 5
            weight = max(1, min(10, weight))

            scenario: dict[str, Any] = {
                "category": str(item.get("category") or "Travel"),
                "coverage_tags": self._coerce_str_list(item.get("coverage_tags")),
                "description": str(item.get("description") or ""),
                "goal": str(item.get("goal") or ""),
                "name": str(item.get("name") or ""),
                "outcome": str(item.get("outcome") or "success"),
                "policy": self._coerce_policy(item.get("policy")),
                "scenario_id": scenario_id,
                "subcategory": str(item.get("subcategory") or "Flight booking"),
                "weight": weight,
            }

            failure_reason = str(item.get("failure_reason") or "").strip()
            if failure_reason:
                scenario["failure_reason"] = failure_reason

            scenarios.append(scenario)

        target_path = utils.get_file_in_task_dir(self.target_task, self.target_filename)
        if os.path.exists(target_path) and not self.overwrite:
            return source_data

        os.makedirs(os.path.dirname(target_path), exist_ok=True)
        with open(target_path, "w", encoding="utf-8") as f:
            json.dump(scenarios, f, indent=2, ensure_ascii=False)

        return source_data


class TaskExecutor(DefaultTaskExecutor):
    def init_dataset(self):
        num_records = int(getattr(self.args, "num_records", 100) or 100)
        return [{"id": f"flight_booking_scenario_{i}"} for i in range(num_records)]
