from typing import Any
from core.graph.nodes.base_node import NodeType, BaseNode
from core.graph.nodes.lambda_node import LambdaNode
from core.graph.nodes.llm_node import LLMNode
from core.graph.nodes.multi_llm_node import MultiLLMNode
from core.graph.nodes.special_node import SpecialNode
from core.graph.nodes.connector_node import ConnectorNode
from core.graph.nodes.weighted_sampler_node import WeightedSamplerNode
from core.graph.nodes.agent_node import AgentNode


def get_node(node_name: str, node_config: dict[str, Any]) -> BaseNode:
    """
    Converts the node configuration into a Node object.

    Args:
        node_name: Name of the node.
        node_config: Node configuration dictionary.

    Returns:
        BaseNode object.

    Raises:
        NotImplementedError: If the node type is not recognized.
    """
    assert "node_type" in node_config, (
        f"node_type is required in node configuration for {node_name}"
    )

    node_type = node_config["node_type"]

    node_mapping = {
        NodeType.LLM: LLMNode,
        NodeType.AGENT: AgentNode,
        NodeType.MULTI_LLM: MultiLLMNode,
        NodeType.WEIGHTED_SAMPLER: WeightedSamplerNode,
        NodeType.LAMBDA: LambdaNode,
        NodeType.SPECIAL: SpecialNode,
        NodeType.CONNECTOR: ConnectorNode,
    }

    if node_type == NodeType.SPECIAL or node_type == NodeType.CONNECTOR:
        return node_mapping[node_type](node_name)

    if node_type not in node_mapping:
        raise NotImplementedError(f"Node type '{node_type}' is not implemented.")

    return node_mapping[node_type](node_name, node_config)


def get_node_config(node_name: str, graph_config: dict[str, Any]) -> dict[str, Any]:
    """
    Get the node configuration from graph configuration.

    Args:
        node_name: Node name.
        graph_config: Graph configuration.
    Returns:
        Node configuration dictionary.
    """
    nodes = graph_config.get("nodes", {})
    assert node_name in nodes, f"Node {node_name} not found in graph configuration"
    return nodes[node_name]
