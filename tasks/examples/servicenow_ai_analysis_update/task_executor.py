from sygra.core.graph.functions.node_processor import NodePostProcessor
from sygra.core.graph.sygra_state import SygraState


class ParaphrasePostProcessor(NodePostProcessor):

    def apply(self, response) -> SygraState:
        if hasattr(response, 'message'):
            response = response.message

        if hasattr(response, 'content'):
            content = response.content
        else:
            content = str(response)

        return {
            "paraphrase": content
        }
