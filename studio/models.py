"""
Data models for SyGra Studio.

These Pydantic models define the structure for workflow visualization
and execution tracking, compatible with the Studio frontend format.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, ConfigDict, Field


class NodeType(str, Enum):
    """Types of nodes supported in SyGra workflows."""

    DATA = "data"
    LLM = "llm"
    LAMBDA = "lambda"
    SUBGRAPH = "subgraph"
    WEIGHTED_SAMPLER = "weighted_sampler"
    TOOL = "tool"
    START = "start"
    END = "end"
    OUTPUT = "output"
    BRANCH = "branch"
    LOOP = "loop"


class ExecutionStatus(str, Enum):
    """Status of workflow or node execution."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    WAITING = "waiting"


class NodePosition(BaseModel):
    """Position of a node in the graph visualization."""

    x: float = 0
    y: float = 0


class NodeSize(BaseModel):
    """Size of a node in the graph visualization."""

    width: float = 200
    height: float = 80


class ModelConfig(BaseModel):
    """LLM model configuration."""

    name: str
    parameters: Dict[str, Any] = Field(default_factory=dict)


class PromptMessage(BaseModel):
    """A single prompt message with role and content."""

    role: str  # system, user, assistant
    content: str


class WorkflowNode(BaseModel):
    """
    Represents a single node in the SyGra workflow graph.

    Compatible with Studio's FlowModule structure for visualization.
    """

    id: str
    node_type: NodeType
    summary: Optional[str] = None
    description: Optional[str] = None

    # Position for visualization
    position: NodePosition = Field(default_factory=NodePosition)
    size: NodeSize = Field(default_factory=NodeSize)

    # Node-specific configuration
    model: Optional[ModelConfig] = None
    prompt: Optional[List[PromptMessage]] = None
    pre_process: Optional[str] = None
    post_process: Optional[str] = None

    # For subgraph nodes
    subgraph_path: Optional[str] = None
    inner_graph: Optional["InnerGraph"] = None  # Expanded subgraph contents

    # For lambda nodes
    function_path: Optional[str] = None

    # For data nodes
    data_config: Optional[Dict[str, Any]] = None

    # For output nodes
    output_config: Optional[Dict[str, Any]] = None

    # For weighted sampler nodes
    sampler_config: Optional[Dict[str, Any]] = None

    # Execution state (updated during workflow run)
    execution_status: ExecutionStatus = ExecutionStatus.PENDING
    execution_result: Optional[Any] = None
    execution_error: Optional[str] = None
    execution_duration_ms: Optional[int] = None

    # Additional metadata
    metadata: Dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(use_enum_values=True)


class EdgeCondition(BaseModel):
    """Condition for conditional edges."""

    condition_path: str  # Path to the condition function
    path_map: Dict[str, str]  # Maps condition results to target nodes


class WorkflowEdge(BaseModel):
    """
    Represents an edge between nodes in the workflow graph.

    Supports both simple edges and conditional edges with path_map.
    """

    id: str
    source: str  # Source node ID
    target: str  # Target node ID (for simple edges)

    # For conditional edges
    is_conditional: bool = False
    condition: Optional[EdgeCondition] = None

    # Edge styling
    edge_type: str = "default"  # default, conditional, loop
    label: Optional[str] = None
    animated: bool = False

    model_config = ConfigDict(use_enum_values=True)


class InnerGraph(BaseModel):
    """
    Represents the inner graph of a subgraph node.

    Contains the expanded nodes and edges from a subgraph definition,
    enabling recursive visualization of nested workflows.
    """

    name: str
    nodes: List[WorkflowNode] = Field(default_factory=list)
    edges: List[WorkflowEdge] = Field(default_factory=list)

    model_config = ConfigDict(use_enum_values=True)


# Update forward references for recursive types
WorkflowNode.model_rebuild()


class WorkflowGraph(BaseModel):
    """
    Complete workflow graph structure for visualization.

    This is the main structure sent to the frontend for rendering.
    """

    id: str
    name: str
    description: Optional[str] = None

    # Graph structure
    nodes: List[WorkflowNode]
    edges: List[WorkflowEdge]

    # Configuration metadata
    data_config: Optional[Dict[str, Any]] = None
    output_config: Optional[Dict[str, Any]] = None
    schema_config: Optional[Dict[str, Any]] = None

    # Graph properties
    state_variables: List[str] = Field(default_factory=list)

    # Source file info
    source_path: Optional[str] = None
    last_modified: Optional[datetime] = None

    model_config = ConfigDict(use_enum_values=True)


class NodeExecutionState(BaseModel):
    """Execution state for a single node."""

    node_id: str
    status: ExecutionStatus
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration_ms: Optional[int] = None
    result: Optional[Any] = None
    error: Optional[str] = None
    logs: List[str] = Field(default_factory=list)

    model_config = ConfigDict(use_enum_values=True)


class WorkflowExecution(BaseModel):
    """
    Represents an execution instance of a workflow.

    Tracks execution progress and results for UI updates.
    """

    id: str
    workflow_id: str
    workflow_name: str

    # Execution status
    status: ExecutionStatus
    current_node: Optional[str] = None

    # Timing
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration_ms: Optional[int] = None

    # Input/Output
    input_data: Dict[str, Any] = Field(default_factory=dict)
    output_data: Optional[Any] = None
    output_file: Optional[str] = None
    metadata_file: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None  # Loaded metadata content

    # Node execution states
    node_states: Dict[str, NodeExecutionState] = Field(default_factory=dict)

    # Error handling
    error: Optional[str] = None
    error_node: Optional[str] = None

    # Logs
    logs: List[str] = Field(default_factory=list)

    model_config = ConfigDict(use_enum_values=True)


class WorkflowListItem(BaseModel):
    """Summary item for listing workflows."""

    id: str
    name: str
    description: Optional[str] = None
    source_path: str
    node_count: int
    edge_count: int
    last_modified: Optional[datetime] = None
    last_run: Optional[datetime] = None


class ExecutionRequest(BaseModel):
    """Request to execute a workflow.

    Options align with main.py CLI arguments for consistency.
    """

    workflow_id: Optional[str] = None  # Optional since it's in the URL path
    input_data: Union[Dict[str, Any], List[Dict[str, Any]]] = Field(default_factory=dict)

    # Core execution parameters (from main.py)
    start_index: int = Field(default=0, description="Start index of the input dataset")
    num_records: int = Field(default=10, description="Number of records to process")
    batch_size: int = Field(default=25, description="Records to process in a batch")
    checkpoint_interval: int = Field(default=100, description="Records between checkpoints")

    # Output options
    run_name: str = Field(default="", description="Name for this run (used in output file)")
    output_with_ts: bool = Field(default=True, description="Add timestamp to output filename")
    output_dir: Optional[str] = Field(default=None, description="Custom output directory")

    # Execution options
    debug: bool = Field(default=False, description="Enable debug mode")
    resume: Optional[bool] = Field(default=None, description="Override resume behavior")
    quality: bool = Field(default=False, description="Enable quality metrics")
    disable_metadata: bool = Field(default=False, description="Disable metadata collection")

    # Custom arguments
    run_args: Dict[str, Any] = Field(default_factory=dict, description="Custom run arguments")

    # Legacy fields for backward compatibility
    streaming: bool = False
    max_samples: int = 1  # Deprecated: use num_records instead


class ExecutionResponse(BaseModel):
    """Response from workflow execution."""

    execution_id: str
    status: ExecutionStatus
    message: str

    model_config = ConfigDict(use_enum_values=True)


class WorkflowCreateRequest(BaseModel):
    """Request to create or update a workflow."""

    id: Optional[str] = None  # Will be generated from name if not provided
    name: str
    description: Optional[str] = None
    nodes: List[WorkflowNode]
    edges: List[WorkflowEdge]
    data_config: Optional[Dict[str, Any]] = None
    output_config: Optional[Dict[str, Any]] = None
    schema_config: Optional[Dict[str, Any]] = None
    state_variables: List[str] = Field(default_factory=list)
    source_path: Optional[str] = None  # Will be set by server

    model_config = ConfigDict(use_enum_values=True)


class WorkflowSaveResponse(BaseModel):
    """Response from workflow save operation."""

    success: bool
    workflow_id: str
    source_path: str
    message: str
    files_created: List[str] = Field(default_factory=list)
