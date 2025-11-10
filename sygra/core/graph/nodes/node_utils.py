from typing import Any, Callable, Optional, Type, cast

from sygra.core.graph.nodes.agent_node import AgentNode
from sygra.core.graph.nodes.base_node import BaseNode, NodeType
from sygra.core.graph.nodes.connector_node import ConnectorNode
from sygra.core.graph.nodes.lambda_node import LambdaNode
from sygra.core.graph.nodes.llm_node import LLMNode
from sygra.core.graph.nodes.multi_llm_node import MultiLLMNode
from sygra.core.graph.nodes.special_node import SpecialNode
from sygra.core.graph.nodes.weighted_sampler_node import WeightedSamplerNode

# Import AgentLab integration if available
create_web_agent_node: Optional[Callable[[str, dict[Any, Any]], Any]] = None

try:
    from sygra.integrations.agentlab import AGENTLAB_AVAILABLE

    if AGENTLAB_AVAILABLE:
        from sygra.integrations.agentlab import create_web_agent_node  # type: ignore[assignment]
except ImportError:
    AGENTLAB_AVAILABLE = False


def get_node(node_name: str, node_config: dict[str, Any]) -> BaseNode:
    """
    Converts the node configuration into a Node object.
    """
    assert (
        "node_type" in node_config
    ), f"node_type is required in node configuration for {node_name}"

    node_type = node_config["node_type"]

    # Dict of string → subclass of BaseNode
    node_mapping: dict[str, Type[BaseNode]] = {
        NodeType.LLM.value: LLMNode,
        NodeType.AGENT.value: AgentNode,
        NodeType.MULTI_LLM.value: MultiLLMNode,
        NodeType.WEIGHTED_SAMPLER.value: WeightedSamplerNode,
        NodeType.LAMBDA.value: LambdaNode,
        NodeType.SPECIAL.value: SpecialNode,
        NodeType.CONNECTOR.value: ConnectorNode,
    }

    # Handle AgentLab agent node types
    if node_type in ("web_agent"):
        if AGENTLAB_AVAILABLE and create_web_agent_node is not None:
            return cast(BaseNode, create_web_agent_node(node_name, node_config))
        else:
            raise NotImplementedError(
                "AgentLab integration not available. Install with: poetry install --with agentlab"
            )

    if node_type not in node_mapping:
        raise NotImplementedError(f"Node type '{node_type}' is not implemented.")

    if node_type in (NodeType.SPECIAL.value, NodeType.CONNECTOR.value):
        return node_mapping[node_type](node_name)  # type: ignore[call-arg]

    return node_mapping[node_type](node_name, node_config)  # type: ignore[call-arg]


def get_node_config(node_name: str, graph_config: dict[str, Any]) -> dict[str, Any]:
    """
    Get the node configuration from graph configuration.

    Args:
        node_name: Node name.
        graph_config: Graph configuration.
    Returns:
        Node configuration dictionary.
    """
    nodes = cast(dict[str, Any], graph_config.get("nodes", {}))
    assert node_name in nodes, f"Node {node_name} not found in graph configuration"
    return cast(dict[str, Any], nodes[node_name])
