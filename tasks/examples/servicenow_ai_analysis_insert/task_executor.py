from langchain_core.messages import AIMessage

from sygra.core.graph.functions.node_processor import NodePostProcessor
from sygra.core.graph.sygra_state import SygraState


class AnalyzerPostProcessor(NodePostProcessor):
    def apply(self, response: AIMessage) -> SygraState:
        # Extract the content string from AIMessage
        content = response.content if hasattr(response, 'content') else str(response)

        return {
            "ai_analysis": content
        }
