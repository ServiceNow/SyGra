from abc import ABC, abstractmethod

from sygra.core.graph.sygra_message import SygraMessage
from sygra.core.graph.sygra_state import SygraState


class NodePreProcessor(ABC):
    """
    This is a function class represent a node pre processor method, which will be performing on the state object
    state is the memory store for the variables.
    For common preprocessor: for langgraph flow, implement under langgraph/langgraph_node_processor.py
    """

    @abstractmethod
    def apply(self, state: SygraState) -> SygraState:
        """
        Implement the preprocessing of the node using state.
        The actual implementation might be langgraph specific.
        Args:
            state: the state object which store the variable values
        Returns:
            SygraState: the state object
        """
        pass


class NodePostProcessor(ABC):
    """
    Implement this function class for node post-processing.
    For common postprocessor: for langgraph flow, implement under langgraph/langgraph_node_processor.py
    """

    @abstractmethod
    def apply(self, resp: SygraMessage) -> SygraState:
        """
        Implement the postprocessing of the node using the response or result out of the node.
        The actual implementation might be langgraph specific.
        Args:
            resp: response of the node, wrapped in class SygraMessage
        Returns:
            SygraState: the updated state object
        """
        pass


class NodePostProcessorWithState(ABC):
    """
    Implement this function class for node post-processing.
    For common postprocessor: for langgraph flow, implement under langgraph/langgraph_node_processor.py
    """

    @abstractmethod
    def apply(self, resp: SygraMessage, state: SygraState) -> SygraState:
        """
        Implement the postprocessing of the node using the response or result out of the node.
        The actual implementation might be langgraph specific.
        Args:
            resp: response of the node, wrapped in class SygraMessage
            state: the state object which store the variable values
        Returns:
            SygraState: the updated state object
        """
        pass
