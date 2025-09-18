from abc import ABC, abstractmethod

from sygra.core.graph.sygra_state import SygraState


class LambdaFunction(ABC):
    """
    This is a function class represent a Lambda Function class.
    Implement apply() method for lambda function to be called by graph node.
    """

    @staticmethod
    @abstractmethod
    def apply(lambda_node_dict: dict, state: SygraState):
        """
        Implement this method to apply lambda function
        Args:
            lambda_node_dict: configuration dictionary
            state: current state of the graph
        Returns:
            SygraState: the updated state object
        """
        pass
