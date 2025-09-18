from abc import ABC, abstractmethod

from sygra.core.graph.sygra_state import SygraState


class EdgeCondition(ABC):
    """
    This function class can be used to define the condition to flow form one node to many.

    For common edge conditions: for langgraph flow, implement under langgraph/langgraph_edge_condition.py
    """

    @staticmethod
    @abstractmethod
    def apply(state: SygraState) -> str:
        """
        This function defines the condition to flow form one node to many.
        Args:
            state: State containing memory
        Returns:
            str: condition string, used to switch case the path
        """
        pass
