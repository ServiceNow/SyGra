"""Post-processors for SimpleQA classification evaluation tasks."""

from sygra.core.graph.functions.node_processor import NodePostProcessorWithState
from sygra.core.graph.sygra_message import SygraMessage
from sygra.core.graph.sygra_state import SygraState
from tasks.eval.utils import parse_response_as_json


class GenerateTopicPostProcessor(NodePostProcessorWithState):
    """Extract `predicted_topic` from a model response and store it in the state."""

    def apply(self, response: SygraMessage, state: SygraState) -> SygraState:
        """Parse `response` as JSON and update `state` with `predicted_topic`."""
        content = response.message.content
        json_data = parse_response_as_json(content)
        if json_data:
            output_dict = {
                "predicted_topic": json_data.get("predicted_topic", ""),
            }
            state.update(output_dict)
            return state

        else:
            state.update({"predicted_topic": ""})
            return state
