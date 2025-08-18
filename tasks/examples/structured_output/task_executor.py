import json

from regex import regex

from core.graph.functions.node_processor import NodePostProcessorWithState
from core.graph.grasp_message import GraspMessage
from core.graph.grasp_state import GraspState
from logger.logger_config import logger


def parse_response_as_json(s):
    JSON_REGEX_PATTERN = regex.compile(r'\{(?:[^{}]|(?R))*\}')
    try:
        return json.loads(s)
    except json.decoder.JSONDecodeError as e:
        p = JSON_REGEX_PATTERN.search(s)
        if not p:
            logger.error("No json string found: " + e.msg)
            logger.error(s)
        try:
            return json.loads(p[0])
        except json.decoder.JSONDecodeError as e:
            logger.error("Unable to parse json string: " + e.msg)
            logger.error(s)


class GenerateTaxonomyPostProcessor(NodePostProcessorWithState):
    def apply(self, response: GraspMessage, state: GraspState) -> GraspState:
        content = response.message.content
        json_data = parse_response_as_json(content)
        if json_data:
            output_dict = {
                "category": json_data.get("category", ""),
                "sub_category": json_data.get("sub_category", "")
            }
            state.update(output_dict)
            return state

        else:
            state.update({
                "category": "",
                "sub_category": ""
            })
            return state
