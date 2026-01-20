"""
SyGra Studio Integration

This module provides seamless integration between SyGra workflows and Studio
UI visualization. It enables:
- Converting SyGra YAML configs to visualization-friendly graph format
- Running SyGra workflows from a web UI
- Real-time workflow execution monitoring

Usage:
    # Start the UI server
    from studio import run_server
    run_server(tasks_dir="./tasks/examples", port=8000)

    # Or use the CLI
    python -m studio.server --tasks-dir ./tasks/examples

    # Build graph from YAML
    from studio import build_graph_from_yaml
    graph = build_graph_from_yaml("./tasks/examples/glaive_code_assistant/graph_config.yaml")

    # Convert to OpenFlow format
    from studio import convert_sygra_to_openflow
    openflow = convert_sygra_to_openflow("./tasks/examples/glaive_code_assistant/graph_config.yaml")
"""

from studio.converter import (
    SygraToStudioConverter,
    convert_sygra_to_openflow,
)
from studio.graph_builder import (
    SygraGraphBuilder,
    build_graph_from_yaml,
    build_graph_from_config,
)
from studio.models import (
    WorkflowNode,
    WorkflowEdge,
    WorkflowGraph,
    WorkflowExecution,
    ExecutionStatus,
    NodeType,
    NodePosition,
    NodeSize,
    ModelConfig,
    PromptMessage,
    EdgeCondition,
    NodeExecutionState,
    WorkflowListItem,
    ExecutionRequest,
    ExecutionResponse,
)
from studio.execution_manager import (
    ExecutionManager,
    ExecutionCallback,
    SygraExecutionRunner,
    get_execution_manager,
)

# Server components are lazily imported to avoid circular import warnings
# when running `python -m studio.server`

def create_server(*args, **kwargs):
    """Create and return the Studio server instance (lazy import)."""
    from studio.server import create_server as _create_server
    return _create_server(*args, **kwargs)


def run_server(*args, **kwargs):
    """Run the Studio server (lazy import)."""
    from studio.server import run_server as _run_server
    return _run_server(*args, **kwargs)

def create_app(*args, **kwargs):
    """Create the FastAPI application (lazy import)."""
    from studio.api import create_app as _create_app
    return _create_app(*args, **kwargs)


def __getattr__(name):
    """Lazy import for server components."""
    if name == "create_server":
        from studio.server import create_server
        return create_server
    elif name == "run_server":
        from studio.server import run_server
        return run_server
    elif name == "create_app":
        from studio.api import create_app
        return create_app
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

__all__ = [
    # Converter
    "SygraToStudioConverter",
    "convert_sygra_to_openflow",
    # Graph Builder
    "SygraGraphBuilder",
    "build_graph_from_yaml",
    "build_graph_from_config",
    # Models
    "WorkflowNode",
    "WorkflowEdge",
    "WorkflowGraph",
    "WorkflowExecution",
    "ExecutionStatus",
    "NodeType",
    "NodePosition",
    "NodeSize",
    "ModelConfig",
    "PromptMessage",
    "EdgeCondition",
    "NodeExecutionState",
    "WorkflowListItem",
    "ExecutionRequest",
    "ExecutionResponse",
    # Execution
    "ExecutionManager",
    "ExecutionCallback",
    "SygraExecutionRunner",
    "get_execution_manager",
    # Server
    "create_server",
    "run_server",
    "create_app",
]
