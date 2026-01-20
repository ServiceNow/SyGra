from typing import Any, Dict, List, Optional

from studio.models import (
    NodeType,
    WorkflowGraph,
)
from sygra.utils import utils


class SygraToStudioConverter:
    """
    Converts SyGra workflow configurations to OpenFlow format.

    This enables SyGra workflows to be visualized and potentially execute.
    """

    # Map SyGra node types to Studio module types
    MODULE_TYPE_MAP = {
        NodeType.LLM: "rawscript",
        NodeType.MULTI_LLM: "rawscript",
        NodeType.AGENT: "rawscript",
        NodeType.WEB_AGENT: "rawscript",
        NodeType.LAMBDA: "rawscript",
        NodeType.SUBGRAPH: "flow",
        NodeType.WEIGHTED_SAMPLER: "rawscript",
        NodeType.TOOL: "rawscript",
        NodeType.START: "identity",
        NodeType.END: "identity",
        NodeType.BRANCH: "branchone",
        NodeType.LOOP: "forloopflow",
    }

    def convert_workflow(self, workflow: WorkflowGraph) -> Dict[str, Any]:
        """
        Convert a SyGra WorkflowGraph to OpenFlow format.

        Args:
            workflow: SyGra WorkflowGraph object.

        Returns:
            Dictionary in OpenFlow format.
        """
        modules = self._convert_nodes_to_modules(workflow)

        openflow = {
            "summary": workflow.name,
            "description": workflow.description or "",
            "value": {
                "modules": modules,
                "failure_module": None,
                "preprocessor_module": None,
                "same_worker": False,
            },
            "schema": self._build_input_schema(workflow),
        }

        return openflow

    def convert_from_yaml(self, yaml_path: str) -> Dict[str, Any]:
        """
        Convert a SyGra YAML config directly to OpenFlow format.

        Args:
            yaml_path: Path to the graph_config.yaml file.

        Returns:
            Dictionary in OpenFlow format.
        """
        from studio.graph_builder import build_graph_from_yaml

        workflow = build_graph_from_yaml(yaml_path)
        return self.convert_workflow(workflow)

    def convert_from_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Convert a SyGra config dictionary to OpenFlow format.

        Args:
            config: SyGra configuration dictionary.

        Returns:
            Dictionary in OpenFlow format.
        """
        from studio.graph_builder import build_graph_from_config

        workflow = build_graph_from_config(config)
        return self.convert_workflow(workflow)

    def _convert_nodes_to_modules(self, workflow: WorkflowGraph) -> List[Dict[str, Any]]:
        """Convert SyGra nodes to flow modules."""
        modules = []

        # Build edge map for determining flow structure
        edge_map = self._build_edge_map(workflow)

        # Find the execution order using topological sort
        execution_order = self._topological_sort(workflow)

        for node_id in execution_order:
            # Skip START and END - they're implicit in Studio
            if node_id in ("START", "END"):
                continue

            node = next((n for n in workflow.nodes if n.id == node_id), None)
            if node is None:
                continue

            module = self._convert_node_to_module(node, edge_map, workflow)
            if module:
                modules.append(module)

        return modules

    def _convert_node_to_module(
        self,
        node: Any,  # WorkflowNode
        edge_map: Dict[str, List[Dict[str, Any]]],
        workflow: WorkflowGraph
    ) -> Optional[Dict[str, Any]]:
        """Convert a single SyGra node to a Studio module."""

        # Check if this node has conditional edges (branching)
        outgoing_edges = edge_map.get(node.id, [])
        has_conditional = any(e.get("is_conditional") for e in outgoing_edges)

        if has_conditional:
            return self._create_branch_module(node, outgoing_edges, workflow)

        # Standard module based on node type
        if node.node_type == NodeType.LLM:
            return self._create_llm_module(node)
        elif node.node_type == NodeType.LAMBDA:
            return self._create_lambda_module(node)
        elif node.node_type == NodeType.SUBGRAPH:
            return self._create_subflow_module(node)
        elif node.node_type == NodeType.WEIGHTED_SAMPLER:
            return self._create_sampler_module(node)
        else:
            return self._create_identity_module(node)

    def _create_llm_module(self, node: Any) -> Dict[str, Any]:
        """Create a Studio module for an LLM node."""
        # Build the Python script for LLM call
        script_content = self._generate_llm_script(node)

        return {
            "id": node.id,
            "summary": node.summary or node.id,
            "value": {
                "type": "rawscript",
                "content": script_content,
                "language": "python3",
                "input_transforms": self._build_input_transforms(node),
            },
        }

    def _create_lambda_module(self, node: Any) -> Dict[str, Any]:
        """Create a Studio module for a Lambda node."""
        function_path = node.function_path or ""

        script_content = f'''
# Lambda Node: {node.id}
# Function: {function_path}

def main(**kwargs):
    """Execute the lambda function."""
    from sygra.utils import utils

    func = utils.import_class_or_function("{function_path}")
    return func(**kwargs)
'''

        return {
            "id": node.id,
            "summary": node.summary or node.id,
            "value": {
                "type": "rawscript",
                "content": script_content,
                "language": "python3",
                "input_transforms": {},
            },
        }

    def _create_subflow_module(self, node: Any) -> Dict[str, Any]:
        """Create a Studio module for a Subgraph node."""
        return {
            "id": node.id,
            "summary": node.summary or node.id,
            "value": {
                "type": "flow",
                "path": node.subgraph_path or "",
                "input_transforms": {},
            },
        }

    def _create_identity_module(self, node: Any) -> Dict[str, Any]:
        """Create a Studio identity (pass-through) module."""
        return {
            "id": node.id,
            "summary": node.summary or node.id,
            "value": {
                "type": "identity",
            },
        }

    def _create_sampler_module(self, node: Any) -> Dict[str, Any]:
        """Create a Studio module for a Weighted Sampler node."""
        # Build attributes info for the script
        attributes_str = "{}"
        if hasattr(node, 'sampler_config') and node.sampler_config:
            import json
            attributes_str = json.dumps(node.sampler_config.get('attributes', {}))

        script_content = f'''
# Weighted Sampler Node: {node.id}
# Randomly samples attribute values for workflow variables

import random
from typing import Dict, Any

def main(**kwargs) -> Dict[str, Any]:
    """Sample random values from configured attributes."""
    attributes = {attributes_str}

    result = {{}}
    for attr_name, attr_config in attributes.items():
        values = attr_config.get('values', [])
        weights = attr_config.get('weights')

        if values:
            if weights and len(weights) == len(values):
                result[attr_name] = random.choices(values, weights=weights, k=1)[0]
            else:
                result[attr_name] = random.choice(values)

    return result
'''

        return {
            "id": node.id,
            "summary": node.summary or node.id,
            "value": {
                "type": "rawscript",
                "content": script_content,
                "language": "python3",
                "input_transforms": {},
            },
        }

    def _create_branch_module(
        self,
        node: Any,
        outgoing_edges: List[Dict[str, Any]],
        workflow: WorkflowGraph
    ) -> Dict[str, Any]:
        """Create a Studio branching module."""
        branches = []
        default_modules = []

        for edge in outgoing_edges:
            if edge.get("is_conditional"):
                condition = edge.get("condition", {})
                path_map = condition.get("path_map", {})

                for result_key, target_node in path_map.items():
                    if target_node == "END":
                        continue

                    branch = {
                        "summary": f"Branch: {result_key}",
                        "expr": f"result == '{result_key}'",
                        "modules": [],  # Would contain nested modules
                    }
                    branches.append(branch)

        return {
            "id": node.id,
            "summary": node.summary or node.id,
            "value": {
                "type": "branchone",
                "branches": branches,
                "default": default_modules,
            },
        }

    def _generate_llm_script(self, node: Any) -> str:
        """Generate Python script for LLM execution."""
        model_name = node.model.name if node.model else "gpt-4o"
        model_params = node.model.parameters if node.model else {}

        # Build prompt template
        prompts = []
        if node.prompt:
            for msg in node.prompt:
                # Handle both simple string and multi-modal content
                if isinstance(msg.content, str):
                    prompts.append(f'{{"role": "{msg.role}", "content": """{msg.content}"""}}')
                elif isinstance(msg.content, list):
                    # Multi-modal content - serialize as JSON
                    import json
                    content_json = json.dumps(msg.content)
                    prompts.append(f'{{"role": "{msg.role}", "content": {content_json}}}')

        prompt_list = ",\n        ".join(prompts)

        script = f'''
# LLM Node: {node.id}
# Model: {model_name}

def main(**state):
    """Execute the LLM node."""
    from langchain_openai import ChatOpenAI
    from langchain_core.messages import HumanMessage, SystemMessage

    # Initialize model
    model = ChatOpenAI(
        model="{model_name}",
        temperature={model_params.get("temperature", 0.7)},
    )

    # Build messages from prompts
    messages = [
        {prompt_list}
    ]

    # Format messages with state variables
    formatted_messages = []
    for msg in messages:
        content = msg["content"].format(**state)
        if msg["role"] == "system":
            formatted_messages.append(SystemMessage(content=content))
        else:
            formatted_messages.append(HumanMessage(content=content))

    # Execute LLM call
    response = model.invoke(formatted_messages)

    return response.content
'''
        return script.strip()

    def _build_input_transforms(self, node: Any) -> Dict[str, Any]:
        """Build input transforms for a node."""
        transforms = {}

        # Extract variable references from prompts
        if node.prompt:
            import re
            pattern = r"(?<!\{)\{([^{}]+)\}(?!\})"

            for msg in node.prompt:
                # Handle both simple string and multi-modal content
                if isinstance(msg.content, str):
                    matches = re.findall(pattern, msg.content)
                    for var in matches:
                        transforms[var] = {
                            "type": "javascript",
                            "expr": f"flow_input.{var}",
                        }
                elif isinstance(msg.content, list):
                    # Multi-modal content - extract variables from each part
                    for part in msg.content:
                        if isinstance(part, dict):
                            for key, value in part.items():
                                if isinstance(value, str):
                                    matches = re.findall(pattern, value)
                                    for var in matches:
                                        transforms[var] = {
                                            "type": "javascript",
                                            "expr": f"flow_input.{var}",
                                        }

        return transforms

    def _build_input_schema(self, workflow: WorkflowGraph) -> Dict[str, Any]:
        """Build JSON schema for workflow inputs."""
        properties = {}

        for var in workflow.state_variables:
            properties[var] = {
                "type": "string",
                "description": f"Input variable: {var}",
            }

        return {
            "type": "object",
            "properties": properties,
            "required": workflow.state_variables,
        }

    def _build_edge_map(self, workflow: WorkflowGraph) -> Dict[str, List[Dict[str, Any]]]:
        """Build a map of node ID to outgoing edges."""
        edge_map: Dict[str, List[Dict[str, Any]]] = {}

        for edge in workflow.edges:
            if edge.source not in edge_map:
                edge_map[edge.source] = []

            edge_map[edge.source].append({
                "target": edge.target,
                "is_conditional": edge.is_conditional,
                "condition": edge.condition.model_dump() if edge.condition else None,
                "label": edge.label,
            })

        return edge_map

    def _topological_sort(self, workflow: WorkflowGraph) -> List[str]:
        """Perform topological sort on workflow nodes."""
        # Build adjacency list
        adjacency: Dict[str, List[str]] = {node.id: [] for node in workflow.nodes}
        in_degree: Dict[str, int] = {node.id: 0 for node in workflow.nodes}

        for edge in workflow.edges:
            if edge.source in adjacency:
                adjacency[edge.source].append(edge.target)
            if edge.target in in_degree:
                in_degree[edge.target] += 1

        # Kahn's algorithm
        result = []
        queue = [node_id for node_id, degree in in_degree.items() if degree == 0]

        while queue:
            current = queue.pop(0)
            result.append(current)

            for neighbor in adjacency.get(current, []):
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        return result


def convert_sygra_to_openflow(yaml_path: str) -> Dict[str, Any]:
    """
    Convenience function to convert SyGra YAML to OpenFlow format.

    Args:
        yaml_path: Path to the graph_config.yaml file.

    Returns:
        Dictionary in Studio OpenFlow format.
    """
    converter = SygraToStudioConverter()
    return converter.convert_from_yaml(yaml_path)
