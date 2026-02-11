import json

import regex
import uuid

from sygra import DefaultTaskExecutor
from sygra.core.graph.functions.node_processor import NodePostProcessorWithState, NodePreProcessor
from sygra.core.graph.sygra_message import SygraMessage
from sygra.core.graph.sygra_state import SygraState
from sygra.logger.logger_config import logger


def parse_response_as_json(s: str) -> dict:
    JSON_REGEX_PATTERN = regex.compile(r"\{(?:[^{}]|(?R))*\}")
    try:
        return json.loads(s)
    except json.decoder.JSONDecodeError as e:
        p = JSON_REGEX_PATTERN.search(s)
        if not p:
            logger.error("No json string found: " + e.msg)
            logger.error(s)
            return {}
        try:
            return json.loads(p[0])
        except json.decoder.JSONDecodeError as e:
            logger.error("Unable to parse json string: " + e.msg)
            logger.error(s)
            return {}


class SeedPreProcessor(NodePreProcessor):
    def apply(self, state: SygraState) -> SygraState:
        if not state.get("unique_id"):
            state["unique_id"] = str(uuid.uuid4())
        return state


class GenerateUserScenarioPostProcessor(NodePostProcessorWithState):
    def apply(self, resp: SygraMessage, state: SygraState) -> SygraState:
        result = parse_response_as_json(resp.message.content)
        state["user_scenario"] = result.get("user_scenario", "")
        return state


class GenerateScenarioSeedPostProcessor(NodePostProcessorWithState):
    def apply(self, resp: SygraMessage, state: SygraState) -> SygraState:
        seed = parse_response_as_json(resp.message.content)
        state["user_goal"] = seed.get("user_goal", "")
        state["first_utterance"] = seed.get("first_utterance", "")
        state["expected_outcome"] = seed.get("expected_outcome", "")
        return state

# class TaskExecutor(DefaultTaskExecutor):
#     def init_dataset(self):
#         num_records = int(getattr(self.args, "num_records", 10) or 10)
#         return [{"id": f"voice_eval_{i}"} for i in range(num_records)]
