from abc import abstractmethod, ABC

from grasp.core.graph.grasp_message import GraspMessage
from grasp.core.graph.grasp_state import GraspState


class NodePreProcessor(ABC):
    """
    This is a function class represent a node pre processor method, which will be performing on the state object
    state is the memory store for the variables.
    For common preprocessor: for langgraph flow, implement under langgraph/langgraph_node_processor.py
    """

    @abstractmethod
    def apply(self, state: GraspState) -> GraspState:
        """
        Implement the preprocessing of the node using state.
        The actual implementation might be langgraph specific.
        Args:
            state: the state object which store the variable values
        Returns:
            GraspState: the state object
        """
        pass


class NodePostProcessor(ABC):
    """
    Implement this function class for node post-processing.
    For common postprocessor: for langgraph flow, implement under langgraph/langgraph_node_processor.py
    """

    @abstractmethod
    def apply(self, resp: GraspMessage) -> GraspState:
        """
        Implement the postprocessing of the node using the response or result out of the node.
        The actual implementation might be langgraph specific.
        Args:
            resp: response of the node, wrapped in class GraspMessage
        Returns:
            GraspState: the updated state object
        """
        pass


class NodePostProcessorWithState(ABC):
    """
    Implement this function class for node post-processing.
    For common postprocessor: for langgraph flow, implement under langgraph/langgraph_node_processor.py
    """

    @abstractmethod
    def apply(self, resp: GraspMessage, state: GraspState) -> GraspState:
        """
        Implement the postprocessing of the node using the response or result out of the node.
        The actual implementation might be langgraph specific.
        Args:
            resp: response of the node, wrapped in class GraspMessage
            state: the state object which store the variable values
        Returns:
            GraspState: the updated state object
        """
        pass
