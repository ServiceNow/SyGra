from core.graph.functions.node_processor import NodePostProcessorWithState
from core.graph.grasp_message import GraspMessage
from core.graph.grasp_state import GraspState


class MathAgentPostProcessor(NodePostProcessorWithState):
    def apply(self, resp: GraspMessage, state: GraspState) -> GraspState:
        answer = resp.message.content
        state["math_result"] = answer
        return state
