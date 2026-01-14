import json

import regex
from sygra.logger.logger_config import logger
from sygra.core.graph.functions.node_processor import NodePostProcessorWithState, NodePreProcessor
from sygra.core.graph.sygra_message import SygraMessage
from sygra.core.graph.sygra_state import SygraState

import uuid


def parse_response_as_json(s):
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


class GenerateIncidentDataPostProcessor(NodePostProcessorWithState):
    def apply(self, resp: SygraMessage, state: SygraState) -> SygraState:
        incident = parse_response_as_json(resp.message.content)
        state["short_description"] = incident.get("short_description", "")
        state["description"] = incident.get("description", "")
        return state


class GenerateIncidentDataPreProcessor(NodePreProcessor):
    def apply(self, state: SygraState) -> SygraState:
        state["unique_id"] = str(uuid.uuid4())
        return state
