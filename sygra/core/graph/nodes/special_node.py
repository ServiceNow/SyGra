from typing import Any

from sygra.core.graph.nodes.base_node import BaseNode, NodeState, NodeType


class SpecialNode(BaseNode):
    """
    A dummy node to handle START and END
    """

    # list of special nodes
    SPECIAL_NODES = ["START", "END"]

    def __init__(self, node_name: str):
        """
        Create a special node with just node name.

        Args:
            node_name: Node name
        """
        if node_name not in self.SPECIAL_NODES:
            raise RuntimeError(f"Special node name '{node_name}' is not supported")

        super().__init__(node_name, None)
        self.node_state = NodeState.ACTIVE.value
        self.node_type = NodeType.SPECIAL.value

    def is_valid(self) -> bool:
        return True

    def is_active(self) -> bool:
        return True

    def to_backend(self) -> Any:
        """
        Convert the Node object to backend platform specific Runnable object.

        Returns:
             Any: platform specific runnable object like Runnable in LangGraph.
        """
        pass
