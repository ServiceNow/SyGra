"""
SyGra Graph Builder for Studio Visualization.

Converts SyGra YAML workflow configurations into visualization-friendly
graph structures compatible with the Studio frontend.
"""

import hashlib
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from studio.models import (
    EdgeCondition,
    ExecutionStatus,
    InnerGraph,
    ModelConfig,
    NodePosition,
    NodeSize,
    NodeType,
    PromptMessage,
    WorkflowEdge,
    WorkflowGraph,
    WorkflowNode,
)
from sygra.utils import utils
import importlib
import importlib.util


class SygraGraphBuilder:
    """
    Builds visualization-friendly graph from SyGra YAML configuration.

    Performs automatic layout calculation and converts SyGra node types
    to standardized formats for frontend rendering.
    """

    # Node type mapping from SyGra to visualization types
    NODE_TYPE_MAP = {
        "llm": NodeType.LLM,
        "multi_llm": NodeType.MULTI_LLM,
        "agent": NodeType.AGENT,
        "web_agent": NodeType.WEB_AGENT,
        "lambda": NodeType.LAMBDA,
        "subgraph": NodeType.SUBGRAPH,
        "weighted_sampler": NodeType.WEIGHTED_SAMPLER,
        "tool": NodeType.TOOL,
    }

    # Layout constants - optimized for visual clarity
    NODE_WIDTH = 200
    NODE_HEIGHT = 80
    HORIZONTAL_SPACING = 320  # Increased for better horizontal spread
    VERTICAL_SPACING = 140    # Increased for better vertical spread
    START_X = 150
    START_Y = 200             # Start lower for better centering

    def __init__(self):
        """Initialize the graph builder."""
        self._node_levels: Dict[str, int] = {}
        self._node_positions: Dict[str, Tuple[float, float]] = {}

    def build_from_yaml(self, yaml_path: str) -> WorkflowGraph:
        """
        Build a WorkflowGraph from a SyGra YAML configuration file.

        Args:
            yaml_path: Path to the graph_config.yaml file.

        Returns:
            WorkflowGraph ready for visualization.
        """
        config = utils.load_yaml_file(yaml_path)
        return self.build_from_config(config, source_path=yaml_path)

    def build_from_config(
        self,
        config: Dict[str, Any],
        source_path: Optional[str] = None
    ) -> WorkflowGraph:
        """
        Build a WorkflowGraph from a SyGra configuration dictionary.

        Args:
            config: SyGra configuration dictionary.
            source_path: Optional source file path for metadata.

        Returns:
            WorkflowGraph ready for visualization.
        """
        if "graph_config" not in config:
            raise ValueError("Configuration must contain 'graph_config' key")

        graph_config = config["graph_config"]
        nodes_config = graph_config.get("nodes", {})
        edges_config = graph_config.get("edges", [])

        # Generate workflow ID
        workflow_id = self._generate_workflow_id(config, source_path)
        workflow_name = self._extract_workflow_name(config, source_path)

        # Build nodes (including DATA and OUTPUT if configs exist)
        data_config = config.get("data_config")
        output_config = config.get("output_config")
        nodes = self._build_nodes(nodes_config, data_config, output_config)

        # Build edges (including DATA→START and END→OUTPUT connections)
        edges = self._build_edges(edges_config, nodes, data_config, output_config)

        # Calculate layout
        self._calculate_layout(nodes, edges)

        # Extract state variables
        state_variables = self._extract_state_variables(nodes_config)

        # Build the graph
        return WorkflowGraph(
            id=workflow_id,
            name=workflow_name,
            description=config.get("description"),
            nodes=nodes,
            edges=edges,
            data_config=config.get("data_config"),
            output_config=config.get("output_config"),
            schema_config=config.get("schema_config"),
            state_variables=state_variables,
            source_path=source_path,
            last_modified=self._get_file_modified_time(source_path) if source_path else None,
        )

    def _generate_workflow_id(
        self,
        config: Dict[str, Any],
        source_path: Optional[str]
    ) -> str:
        """Generate a unique workflow ID based on config content or path."""
        if source_path:
            # Use path-based ID for consistency
            return hashlib.md5(source_path.encode()).hexdigest()[:12]
        else:
            # Use config content hash
            import json
            config_str = json.dumps(config, sort_keys=True)
            return hashlib.md5(config_str.encode()).hexdigest()[:12]

    def _extract_workflow_name(
        self,
        config: Dict[str, Any],
        source_path: Optional[str]
    ) -> str:
        """Extract a human-readable workflow name."""
        # Check for explicit name in config
        if "name" in config:
            return config["name"]

        # Extract from source path
        if source_path:
            path = Path(source_path)
            # Use parent directory name (task name)
            return path.parent.name

        return "Unnamed Workflow"

    def _build_nodes(
        self,
        nodes_config: Dict[str, Any],
        data_config: Optional[Dict[str, Any]] = None,
        output_config: Optional[Dict[str, Any]] = None
    ) -> List[WorkflowNode]:
        """Build WorkflowNode objects from node configuration."""
        nodes = []

        # Add DATA node if data_config exists
        if data_config:
            source = data_config.get("source", {})
            # Build summary from source config
            if isinstance(source, list) and source:
                source_type = source[0].get("type", "data")
            elif isinstance(source, dict):
                source_type = source.get("type", "data")
            else:
                source_type = "data"

            nodes.append(WorkflowNode(
                id="DATA",
                node_type=NodeType.DATA,
                summary="Data Source",
                description="Data source & sink configuration",
                data_config=data_config,
            ))

        # Add START node
        nodes.append(WorkflowNode(
            id="START",
            node_type=NodeType.START,
            summary="Start",
            description="Workflow entry point",
        ))

        # Add configured nodes
        for node_name, node_config in nodes_config.items():
            node = self._build_node(node_name, node_config)
            nodes.append(node)

        # Add END node
        nodes.append(WorkflowNode(
            id="END",
            node_type=NodeType.END,
            summary="End",
            description="Workflow exit point",
        ))

        # Add OUTPUT node if output_config exists
        if output_config:
            output_map = output_config.get("output_map", {})
            num_mappings = len(output_map)

            nodes.append(WorkflowNode(
                id="OUTPUT",
                node_type=NodeType.OUTPUT,
                summary="Output",
                description=f"Output mapping ({num_mappings} fields)" if num_mappings else "Output configuration",
                output_config=output_config,
            ))

        return nodes

    def _build_node(
        self,
        node_name: str,
        node_config: Dict[str, Any],
        expand_subgraphs: bool = True,
        depth: int = 0,
        max_depth: int = 5
    ) -> WorkflowNode:
        """Build a single WorkflowNode from configuration."""
        node_type_str = node_config.get("node_type", "llm")
        node_type = self.NODE_TYPE_MAP.get(node_type_str, NodeType.LLM)

        # Extract model configuration (for single LLM/Agent nodes)
        model_config = None
        if "model" in node_config:
            model = node_config["model"]
            model_config = ModelConfig(
                name=model.get("name", "unknown"),
                parameters=model.get("parameters", {}),
            )

        # Extract models configuration (for multi_llm nodes)
        models_config = None
        multi_llm_post_process = None
        if node_type == NodeType.MULTI_LLM and "models" in node_config:
            models_config = node_config["models"]
            multi_llm_post_process = node_config.get("multi_llm_post_process")

        # Extract prompt messages
        prompts = None
        if "prompt" in node_config:
            prompts = self._parse_prompts(node_config["prompt"])

        # Build summary from node config (node_name in YAML, with fallback to legacy 'summary')
        summary = node_config.get("node_name") or node_config.get("summary") or node_name.replace("_", " ").title()

        # For subgraph nodes, try to load and expand the inner graph
        inner_graph = None
        subgraph_path = node_config.get("subgraph")
        inline_inner_graph = node_config.get("inner_graph")

        if node_type == NodeType.SUBGRAPH:
            if inline_inner_graph:
                # Load inline inner_graph data (from grouped subgraphs)
                inner_graph = self._parse_inline_inner_graph(inline_inner_graph, depth + 1, max_depth)
            elif subgraph_path and expand_subgraphs and depth < max_depth:
                # Load from external subgraph path
                inner_graph = self._load_subgraph(subgraph_path, depth + 1, max_depth)

        # Extract node_config_map for subgraph nodes (allows overriding inner node configs)
        node_config_map = node_config.get("node_config_map") if node_type == NodeType.SUBGRAPH else None

        # Extract output_keys for LLM/multi_llm nodes
        output_keys = node_config.get("output_keys")

        return WorkflowNode(
            id=node_name,
            node_type=node_type,
            summary=summary,
            description=node_config.get("description"),
            model=model_config,
            models=models_config,
            prompt=prompts,
            pre_process=node_config.get("pre_process"),
            post_process=node_config.get("post_process"),
            multi_llm_post_process=multi_llm_post_process,
            output_keys=output_keys,
            subgraph_path=subgraph_path,
            inner_graph=inner_graph,
            node_config_map=node_config_map,
            function_path=node_config.get("lambda") or node_config.get("function"),
            metadata={
                "original_config": node_config,
            },
        )

    def _load_subgraph(
        self,
        subgraph_path: str,
        depth: int = 0,
        max_depth: int = 5
    ) -> Optional[InnerGraph]:
        """
        Load and expand a subgraph definition.

        Subgraph path can be:
        - Module path: "sygra.recipes.evol_instruct"
        - File path: "path/to/subgraph.yaml"
        """
        try:
            # Try to load as a Python module (recipe)
            if "." in subgraph_path and not subgraph_path.endswith((".yaml", ".yml")):
                return self._load_recipe_subgraph(subgraph_path, depth, max_depth)
            else:
                # Try to load as YAML file
                return self._load_yaml_subgraph(subgraph_path, depth, max_depth)
        except Exception as e:
            print(f"Warning: Could not load subgraph '{subgraph_path}': {e}")
            return None

    def _load_recipe_subgraph(
        self,
        module_path: str,
        depth: int,
        max_depth: int
    ) -> Optional[InnerGraph]:
        """Load a subgraph from a Python recipe module."""
        graph_config = None

        # Method 1: Try to import the module directly
        try:
            module = importlib.import_module(module_path)

            # Look for graph_config or GRAPH_CONFIG
            graph_config = getattr(module, 'graph_config', None)
            if graph_config is None:
                graph_config = getattr(module, 'GRAPH_CONFIG', None)

            # Some recipes have a get_graph_config() function
            if graph_config is None and hasattr(module, 'get_graph_config'):
                graph_config = module.get_graph_config()

            # Try loading from __init__.py pattern with yaml file
            if graph_config is None:
                module_file = getattr(module, '__file__', None)
                if module_file:
                    module_dir = Path(module_file).parent
                    yaml_path = module_dir / "graph_config.yaml"
                    if yaml_path.exists():
                        config = utils.load_yaml_file(str(yaml_path))
                        graph_config = config.get("graph_config", {})
        except ImportError:
            pass

        # Method 2: Try to resolve path and find graph_config.yaml directly
        if graph_config is None:
            try:
                # Convert module path to filesystem path
                # e.g., "sygra.recipes.evol_instruct" -> "sygra/recipes/evol_instruct"
                parts = module_path.split(".")

                # Try to find the base package
                base_module = parts[0]
                try:
                    base = importlib.import_module(base_module)
                    base_path = Path(getattr(base, '__file__', '')).parent

                    # Build the rest of the path
                    sub_path = Path(*parts[1:])
                    full_path = base_path / sub_path

                    # Look for graph_config.yaml
                    yaml_path = full_path / "graph_config.yaml"
                    if yaml_path.exists():
                        config = utils.load_yaml_file(str(yaml_path))
                        graph_config = config.get("graph_config", {})
                except Exception:
                    pass
            except Exception:
                pass

        # Method 3: Try common base paths
        if graph_config is None:
            try:
                # Try from current working directory
                rel_path = module_path.replace(".", "/")
                for base in [Path.cwd(), Path(__file__).parent.parent.parent.parent]:
                    yaml_path = base / rel_path / "graph_config.yaml"
                    if yaml_path.exists():
                        config = utils.load_yaml_file(str(yaml_path))
                        graph_config = config.get("graph_config", {})
                        break
            except Exception:
                pass

        if graph_config is None:
            print(f"Warning: Could not find graph_config for '{module_path}'")
            return None

        try:
            # Extract graph config - could be a dict or have graph_config key
            if isinstance(graph_config, dict):
                if "graph_config" in graph_config:
                    graph_config = graph_config["graph_config"]

            nodes_config = graph_config.get("nodes", {})
            edges_config = graph_config.get("edges", [])

            # Build inner nodes (recursively expand subgraphs)
            inner_nodes = []
            for name, config in nodes_config.items():
                node = self._build_node(name, config, expand_subgraphs=True, depth=depth, max_depth=max_depth)
                inner_nodes.append(node)

            # Build inner edges
            inner_edges = self._build_inner_edges(edges_config, inner_nodes)

            # Calculate layout for inner nodes
            self._calculate_inner_layout(inner_nodes, inner_edges)

            # Extract name from module path
            name = module_path.split(".")[-1].replace("_", " ").title()

            return InnerGraph(
                name=name,
                nodes=inner_nodes,
                edges=inner_edges,
            )

        except Exception as e:
            print(f"Warning: Could not load recipe subgraph '{module_path}': {e}")
            return None

    def _load_yaml_subgraph(
        self,
        yaml_path: str,
        depth: int,
        max_depth: int
    ) -> Optional[InnerGraph]:
        """Load a subgraph from a YAML file."""
        try:
            # Resolve the path
            if not Path(yaml_path).is_absolute():
                # Try relative to current working directory
                yaml_path = str(Path.cwd() / yaml_path)

            if not Path(yaml_path).exists():
                return None

            config = utils.load_yaml_file(yaml_path)
            graph_config = config.get("graph_config", {})

            nodes_config = graph_config.get("nodes", {})
            edges_config = graph_config.get("edges", [])

            # Build inner nodes
            inner_nodes = []
            for name, node_config in nodes_config.items():
                node = self._build_node(name, node_config, expand_subgraphs=True, depth=depth, max_depth=max_depth)
                inner_nodes.append(node)

            # Build inner edges
            inner_edges = self._build_inner_edges(edges_config, inner_nodes)

            # Calculate layout for inner nodes
            self._calculate_inner_layout(inner_nodes, inner_edges)

            # Extract name from file path
            name = Path(yaml_path).stem.replace("_", " ").title()

            return InnerGraph(
                name=name,
                nodes=inner_nodes,
                edges=inner_edges,
            )

        except Exception as e:
            print(f"Warning: Could not load YAML subgraph '{yaml_path}': {e}")
            return None

    def _parse_inline_inner_graph(
        self,
        inner_graph_data: Dict[str, Any],
        depth: int = 0,
        max_depth: int = 5
    ) -> Optional[InnerGraph]:
        """
        Parse inline inner_graph data from YAML config.

        This handles subgraphs that were created by grouping nodes in the builder
        and saved inline in the workflow config.
        """
        try:
            name = inner_graph_data.get("name", "Subgraph")
            nodes_config = inner_graph_data.get("nodes", {})
            edges_config = inner_graph_data.get("edges", [])

            # Build inner nodes
            inner_nodes = []
            for node_id, node_config in nodes_config.items():
                # Parse node type
                node_type_str = node_config.get("node_type", "llm")
                try:
                    node_type = NodeType(node_type_str)
                except ValueError:
                    node_type = NodeType.LLM

                # Parse position
                pos_data = node_config.get("position", {})
                position = NodePosition(
                    x=pos_data.get("x", 0),
                    y=pos_data.get("y", 0)
                )

                # Parse size
                size_data = node_config.get("size", {})
                size = NodeSize(
                    width=size_data.get("width", 150),
                    height=size_data.get("height", 60)
                )

                # Handle nested inner_graph recursively
                nested_inner_graph = None
                if node_config.get("inner_graph") and depth < max_depth:
                    nested_inner_graph = self._parse_inline_inner_graph(
                        node_config["inner_graph"],
                        depth + 1,
                        max_depth
                    )

                inner_node = WorkflowNode(
                    id=node_id,
                    node_type=node_type,
                    summary=node_config.get("node_name") or node_config.get("summary") or node_id.replace("_", " ").title(),
                    position=position,
                    size=size,
                    inner_graph=nested_inner_graph,
                )
                inner_nodes.append(inner_node)

            # Build inner edges
            inner_edges = []
            for idx, edge_config in enumerate(edges_config):
                source = edge_config.get("from", "")
                target = edge_config.get("to", "")
                if source and target:
                    edge_id = f"inner_edge_{source}_{target}_{idx}"
                    inner_edges.append(WorkflowEdge(
                        id=edge_id,
                        source=source,
                        target=target,
                        edge_type="default",
                    ))

            return InnerGraph(
                name=name,
                nodes=inner_nodes,
                edges=inner_edges,
            )

        except Exception as e:
            print(f"Warning: Could not parse inline inner_graph: {e}")
            return None

    def _build_inner_edges(
        self,
        edges_config: List[Dict[str, Any]],
        nodes: List[WorkflowNode]
    ) -> List[WorkflowEdge]:
        """Build edges for inner subgraph (without START/END connections)."""
        edges = []
        node_ids = {node.id for node in nodes}

        for idx, edge_config in enumerate(edges_config):
            source = edge_config.get("from", "")
            target = edge_config.get("to", "")

            # Skip START/END references for inner graphs
            if source == "START" or target == "END":
                continue

            # Only add edges where both nodes exist
            if source in node_ids and target in node_ids:
                edge_id = f"inner_edge_{source}_{target}_{idx}"
                edges.append(WorkflowEdge(
                    id=edge_id,
                    source=source,
                    target=target,
                    edge_type="default",
                ))

        return edges

    def _calculate_inner_layout(
        self,
        nodes: List[WorkflowNode],
        edges: List[WorkflowEdge]
    ) -> Tuple[int, int]:
        """
        Calculate layout for inner subgraph nodes with smaller spacing.

        Returns:
            Tuple of (width, height) - the bounding dimensions of the inner graph
        """
        if not nodes:
            return (200, 60)  # Minimum dimensions

        # Use compact spacing for inner graphs (matching frontend layoutUtils.ts)
        inner_node_width = 140
        inner_node_height = 44
        inner_h_spacing = 30
        inner_v_spacing = 20
        inner_start_x = 0  # No start offset - padding applied separately
        inner_start_y = 0

        # Build adjacency
        adjacency: Dict[str, List[str]] = {node.id: [] for node in nodes}
        reverse_adj: Dict[str, List[str]] = {node.id: [] for node in nodes}
        in_degree: Dict[str, int] = {node.id: 0 for node in nodes}

        for edge in edges:
            if edge.source in adjacency and edge.target in adjacency:
                adjacency[edge.source].append(edge.target)
                reverse_adj[edge.target].append(edge.source)
                in_degree[edge.target] += 1

        # Layer assignment using topological sort
        layers: Dict[int, List[str]] = {}
        node_layer: Dict[str, int] = {}
        queue = [nid for nid, deg in in_degree.items() if deg == 0]

        # If no root nodes, start with first node
        if not queue and nodes:
            queue = [nodes[0].id]

        while queue:
            current = queue.pop(0)
            if current in node_layer:
                continue
            pred_layers = [node_layer.get(p, -1) for p in reverse_adj.get(current, [])]
            layer = max(pred_layers, default=-1) + 1

            node_layer[current] = layer
            if layer not in layers:
                layers[layer] = []
            layers[layer].append(current)

            for successor in adjacency.get(current, []):
                in_degree[successor] -= 1
                if in_degree[successor] <= 0 and successor not in node_layer:
                    queue.append(successor)

        # Handle remaining nodes (cycles or disconnected)
        for node in nodes:
            if node.id not in node_layer:
                max_layer = max(layers.keys()) if layers else 0
                node_layer[node.id] = max_layer + 1
                if max_layer + 1 not in layers:
                    layers[max_layer + 1] = []
                layers[max_layer + 1].append(node.id)

        # Calculate positions with proper vertical centering
        max_layer_size = max(len(l) for l in layers.values()) if layers else 1
        total_layer_height = max_layer_size * (inner_node_height + inner_v_spacing)

        max_x = 0
        max_y = 0

        for layer_idx, layer_nodes in sorted(layers.items()):
            # Center this layer vertically
            layer_height = len(layer_nodes) * (inner_node_height + inner_v_spacing)
            start_y = inner_start_y + (total_layer_height - layer_height) / 2

            for node_idx, node_id in enumerate(layer_nodes):
                x = inner_start_x + (layer_idx * (inner_node_width + inner_h_spacing))
                y = start_y + (node_idx * (inner_node_height + inner_v_spacing))

                for node in nodes:
                    if node.id == node_id:
                        node.position = NodePosition(x=x, y=y)
                        node.size = NodeSize(width=inner_node_width, height=inner_node_height)

                        # Track max dimensions
                        max_x = max(max_x, x + inner_node_width)
                        max_y = max(max_y, y + inner_node_height)
                        break

        # Return content dimensions (padding applied by caller)
        return (max_x, max_y)

    def _parse_prompts(self, prompt_config: List[Dict[str, str]]) -> List[PromptMessage]:
        """Parse prompt configuration into PromptMessage objects."""
        messages = []
        for prompt in prompt_config:
            for role, content in prompt.items():
                if isinstance(content, str):
                    messages.append(PromptMessage(role=role, content=content))
        return messages

    def _build_edges(
        self,
        edges_config: List[Dict[str, Any]],
        nodes: List[WorkflowNode],
        data_config: Optional[Dict[str, Any]] = None,
        output_config: Optional[Dict[str, Any]] = None
    ) -> List[WorkflowEdge]:
        """Build WorkflowEdge objects from edge configuration."""
        edges = []
        node_ids = {node.id for node in nodes}

        # Add DATA → START edge if data_config exists
        if data_config and "DATA" in node_ids:
            edges.append(WorkflowEdge(
                id="edge_DATA_START",
                source="DATA",
                target="START",
                edge_type="default",
            ))

        for idx, edge_config in enumerate(edges_config):
            source = edge_config.get("from", "START")
            target = edge_config.get("to")
            condition = edge_config.get("condition")
            path_map = edge_config.get("path_map")

            if condition and path_map:
                # Conditional edge - create multiple edges
                for result_key, target_node in path_map.items():
                    edge_id = f"edge_{source}_{target_node}_{idx}_{result_key}"
                    edges.append(WorkflowEdge(
                        id=edge_id,
                        source=source,
                        target=target_node,
                        is_conditional=True,
                        condition=EdgeCondition(
                            condition_path=condition,
                            path_map=path_map,
                        ),
                        edge_type="conditional",
                        label=result_key,
                        animated=True,
                    ))
            elif target:
                # Simple edge
                edge_id = f"edge_{source}_{target}_{idx}"
                edges.append(WorkflowEdge(
                    id=edge_id,
                    source=source,
                    target=target,
                    edge_type="default",
                ))

        # Add END → OUTPUT edge if output_config exists
        if output_config and "OUTPUT" in node_ids:
            edges.append(WorkflowEdge(
                id="edge_END_OUTPUT",
                source="END",
                target="OUTPUT",
                edge_type="default",
            ))

        return edges

    def _calculate_layout(
        self,
        nodes: List[WorkflowNode],
        edges: List[WorkflowEdge]
    ) -> None:
        """
        Calculate node positions using an improved Sugiyama-style layered layout.

        This algorithm:
        1. Assigns nodes to layers based on longest path (better for DAGs)
        2. Orders nodes within layers using barycenter heuristic to minimize crossings
        3. Positions nodes with proper centering and spacing
        """
        if not nodes:
            return

        # Build adjacency lists
        adjacency: Dict[str, List[str]] = {node.id: [] for node in nodes}
        reverse_adj: Dict[str, List[str]] = {node.id: [] for node in nodes}
        in_degree: Dict[str, int] = {node.id: 0 for node in nodes}

        for edge in edges:
            if edge.source in adjacency and edge.target in adjacency:
                adjacency[edge.source].append(edge.target)
                reverse_adj[edge.target].append(edge.source)
                in_degree[edge.target] += 1

        # Layer assignment using longest path from roots
        layers: Dict[int, List[str]] = {}
        node_layer: Dict[str, int] = {}

        # Start with nodes that have no incoming edges
        queue = [node_id for node_id, degree in in_degree.items() if degree == 0]

        while queue:
            current = queue.pop(0)

            # Calculate layer based on predecessors (longest path)
            predecessor_layers = [
                node_layer.get(pred, -1)
                for pred in reverse_adj.get(current, [])
            ]
            layer = max(predecessor_layers, default=-1) + 1

            node_layer[current] = layer
            if layer not in layers:
                layers[layer] = []
            layers[layer].append(current)

            # Add successors to queue
            for successor in adjacency.get(current, []):
                in_degree[successor] -= 1
                if in_degree[successor] == 0 and successor not in node_layer:
                    queue.append(successor)

        # Handle any remaining nodes (cycles or disconnected)
        for node in nodes:
            if node.id not in node_layer:
                max_layer = max(layers.keys()) if layers else 0
                node_layer[node.id] = max_layer + 1
                if max_layer + 1 not in layers:
                    layers[max_layer + 1] = []
                layers[max_layer + 1].append(node.id)

        # Order nodes within layers using barycenter method (minimize edge crossings)
        node_order: Dict[str, float] = {}
        sorted_layers = sorted(layers.keys())

        # Initialize order for first layer
        if sorted_layers:
            for idx, node_id in enumerate(layers[sorted_layers[0]]):
                node_order[node_id] = idx

        # Forward pass: order based on predecessors
        for layer_idx in sorted_layers[1:]:
            layer_nodes = layers[layer_idx]
            for node_id in layer_nodes:
                predecessors = reverse_adj.get(node_id, [])
                if predecessors:
                    # Barycenter: average position of predecessors
                    node_order[node_id] = sum(node_order.get(p, 0) for p in predecessors) / len(predecessors)
                else:
                    node_order[node_id] = 0
            # Sort layer by barycenter
            layers[layer_idx] = sorted(layer_nodes, key=lambda n: node_order.get(n, 0))

        # Backward pass: refine based on successors
        for layer_idx in reversed(sorted_layers[:-1]):
            layer_nodes = layers[layer_idx]
            for node_id in layer_nodes:
                successors = adjacency.get(node_id, [])
                if successors:
                    node_order[node_id] = sum(node_order.get(s, 0) for s in successors) / len(successors)
            layers[layer_idx] = sorted(layer_nodes, key=lambda n: node_order.get(n, 0))

        # Calculate total height for centering
        max_layer_size = max(len(layer_nodes) for layer_nodes in layers.values()) if layers else 1
        total_height = max_layer_size * self.VERTICAL_SPACING
        center_y = self.START_Y + total_height / 2

        # Assign positions with proper centering
        for layer_idx, layer_nodes in sorted(layers.items()):
            layer_size = len(layer_nodes)
            layer_height = layer_size * self.VERTICAL_SPACING
            start_y = center_y - layer_height / 2 + self.VERTICAL_SPACING / 2

            for node_idx, node_id in enumerate(layer_nodes):
                x = self.START_X + (layer_idx * self.HORIZONTAL_SPACING)
                y = start_y + (node_idx * self.VERTICAL_SPACING)

                # Find and update the node
                for node in nodes:
                    if node.id == node_id:
                        node.position = NodePosition(x=x, y=y)
                        node.size = NodeSize(width=self.NODE_WIDTH, height=self.NODE_HEIGHT)
                        break

    def _get_predecessors(
        self,
        node_id: str,
        edges: List[WorkflowEdge]
    ) -> List[str]:
        """Get all predecessor nodes for a given node."""
        return [edge.source for edge in edges if edge.target == node_id]

    def _extract_state_variables(self, nodes_config: Dict[str, Any]) -> List[str]:
        """Extract state variables from node configurations."""
        import re

        variables = set()
        pattern = r"(?<!\{)\{([^{}]+)\}(?!\})"

        for node_config in nodes_config.values():
            # Extract from prompts
            if "prompt" in node_config:
                for prompt in node_config["prompt"]:
                    for content in prompt.values():
                        if isinstance(content, str):
                            matches = re.findall(pattern, content)
                            variables.update(matches)

        return sorted(list(variables))

    def _get_file_modified_time(self, file_path: str) -> Optional[datetime]:
        """Get the last modified time of a file."""
        try:
            stat = os.stat(file_path)
            return datetime.fromtimestamp(stat.st_mtime)
        except OSError:
            return None


def build_graph_from_yaml(yaml_path: str) -> WorkflowGraph:
    """
    Convenience function to build a WorkflowGraph from YAML file.

    Args:
        yaml_path: Path to the graph_config.yaml file.

    Returns:
        WorkflowGraph ready for visualization.
    """
    builder = SygraGraphBuilder()
    return builder.build_from_yaml(yaml_path)


def build_graph_from_config(config: Dict[str, Any]) -> WorkflowGraph:
    """
    Convenience function to build a WorkflowGraph from config dict.

    Args:
        config: SyGra configuration dictionary.

    Returns:
        WorkflowGraph ready for visualization.
    """
    builder = SygraGraphBuilder()
    return builder.build_from_config(config)
