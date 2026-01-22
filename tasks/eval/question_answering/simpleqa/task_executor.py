"""Post-processors for SimpleQA question answering evaluation tasks."""

from sygra.core.graph.functions.node_processor import NodePostProcessorWithState
from sygra.core.graph.sygra_message import SygraMessage
from sygra.core.graph.sygra_state import SygraState
from tasks.eval.utils import parse_response_as_json


class GenerateAnswerPostProcessor(NodePostProcessorWithState):
    """Extract `predicted_answer` from a model response and store it in the state."""

    def apply(self, response: SygraMessage, state: SygraState) -> SygraState:
        """Parse `response` as JSON and update `state` with `predicted_answer`."""
        content = response.message.content
        json_data = parse_response_as_json(content)
        if json_data:
            output_dict = {
                "predicted_answer": json_data.get("predicted_answer", ""),
            }
            state.update(output_dict)
            return state

        else:
            state.update({"predicted_answer": ""})
            return state
