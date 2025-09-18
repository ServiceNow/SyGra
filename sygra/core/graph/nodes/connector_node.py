from typing import Any

from sygra.core.graph.nodes.base_node import BaseNode, NodeState, NodeType
from sygra.utils import utils


class ConnectorNode(BaseNode):
    """
    A connector node for handling end of subgraphs
    """

    def __init__(self, node_name: str):
        """
        Create a connector node with just node name.

        Args:
            node_name: Node name
        """

        super().__init__(node_name, None)
        self.node_state = NodeState.ACTIVE.value
        self.node_type = NodeType.CONNECTOR.value

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
        return utils.backend_factory.create_connector_runnable()
