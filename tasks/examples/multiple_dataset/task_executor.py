import json

from langchain_core.messages import AIMessage

from sygra.core.graph.functions.node_processor import NodePostProcessor
from sygra.core.graph.sygra_state import SygraState


class AnalyzerPostProcessor(NodePostProcessor):
    def apply(self, response: AIMessage) -> SygraState:
        # Extract the content string from AIMessage
        content = response.message.content if hasattr(response, 'message') else str(response)
        empty_response = {
            "severity_score" : 1,
            "predicted_resolution_time" : 0,
            "recommended_action": "",
            "root_cause_category": "",
            "confidence": 0.0
            }
        try:
            return json.loads(content)
        except Exception as e:
           return empty_response

