import time
from abc import ABC, abstractmethod
from enum import Enum
from typing import Any, List, Optional

from sygra.metadata.metadata_collector import get_metadata_collector
from sygra.utils import utils


class NodeType(Enum):
    """
    Types of Node Supported in SyGra.

    """

    LLM = "llm"
    MULTI_LLM = "multi_llm"
    AGENT = "agent"
    LAMBDA = "lambda"
    WEIGHTED_SAMPLER = "weighted_sampler"
    UNKNOWN = "unknown"
    SPECIAL = "special"
    CONNECTOR = "connector"


class NodeState(Enum):
    """
    by default node is ACTIVE, but it can be disabled with idle key.

    """

    ACTIVE = "active"
    IDLE = "idle"


class BaseNode(ABC):
    """
    Node structure holds the node configuration, SyGra uses this Node in the platform.

    """

    def __init__(self, name, config: Optional[dict[str, Any]] = None):
        """
        Node constructor to build the Node object
        :param name: node name
        :param config: node configuration
        """
        # name of the node defined in yaml file
        self.name: str = name
        self.node_type: str
        self.node_state: str

        if self.name is None:
            raise ValueError("Node name is required")

        if config is not None:
            # node type
            self.node_type = config.get("node_type", NodeType.UNKNOWN.value)
            # node state
            self.node_state = config.get("node_state", NodeState.ACTIVE.value)
            # store the node config from graph yaml file for this specific node
            self.node_config = config
            if self.node_config is None:
                raise ValueError("Node configuration is required.")
        else:
            self.node_type = NodeType.UNKNOWN.value
            self.node_state = NodeState.IDLE.value
            # Ensure node_config is always a dict to simplify downstream typing
            self.node_config = {}
        # stores node specific state variables, this should be passed to langgraph
        self.state_variables: List[str] = []

        # throws ValueError
        self.validate_node()

    def get_node_state(self) -> str:
        """
        Get the node_state.

        Which can be "active" by default or "idle" if not used int the graph.
        User might disable a node during experiment, by setting "node_state" to "idle" in the YAML file.

        Returns:
            NodeState: state of the node
        """
        return self.node_state

    def get_node_type(self) -> str:
        """
        Get the node_type.

        Which can be llm, lambda, multi_llm, special, weighted_sampler, or unknown.
        llm type node talks to single model and response is assigned to output after postprocessing.
        multi_llm type node talks to multiple models.
        weighted_sampler type node is used to select random sample data from the static list of samples.
        special type of node is used to denote START or END node.

        Returns:
            NodeType: type of the node
        """
        return self.node_type

    def is_special_type(self) -> bool:
        """
        Checks if the node is special type.

        Returns:
            bool: True if the node is special type.
        """
        return bool(self.node_type == NodeType.SPECIAL.value)

    def get_node_config(self) -> dict[str, Any]:
        """
        Get the node configuration as dictionary type.

        This is the raw data defined in the YAML file.
        Returns:
             dict: node configuration as defined in the YAML file.
        """
        return self.node_config

    def get_name(self) -> str:
        """
        Get the name of the node, which is the key name given for each node in the nodes definition.

        Returns:
             str: name of the node as defined in the YAML file.
        """
        return self.name

    def get_state_variables(self) -> list[str]:
        """
        If there are variables needs to be injected from node level to graph state, this variable is used.

        Before the graph is built, these variables has to be fed into the GraphConfig object.

        Returns:
            list[str]: list of variable names which will be injected into graph as state variables.
        """
        return self.state_variables

    def is_active(self) -> bool:
        """
        Checks if the node is active.

        Returns:
             bool: True if the node is active.
        """
        return self.get_node_state() != NodeState.IDLE.value

    def is_valid(self) -> bool:
        """
        Checks if the node is valid.
        This method differentiate between a valid node and an active node.
        Like we can have nodes used for other purpose, which are not valid.

        Returns:
             bool: True if the node is valid.
        """
        return self.is_active()

    def validate_node(self):
        """
        Validates the node property keys and other behavior.

        It throws Exception.
        Returns:
            None
        """
        pass

    def validate_config_keys(self, required_keys: list[str], config_name: str, node_config: dict):
        utils.validate_required_keys(required_keys, node_config, config_name)

    def _get_model_name(self, model: Any) -> Optional[str]:
        """
        Extract model name from a model instance.

        Handles wrapped models (RunnableLambda, etc.) and various model types.

        Args:
            model: The model instance to extract name from

        Returns:
            Model name as string, or None if not found
        """
        # Unwrap if model is wrapped
        actual_model = model
        if hasattr(model, "afunc"):
            actual_model = model.afunc
        elif hasattr(model, "bound"):
            actual_model = model.bound

        # Try different ways to get the name
        if hasattr(actual_model, "_get_name"):
            return str(actual_model._get_name())
        elif hasattr(actual_model, "model_name"):
            return str(actual_model.model_name)
        elif hasattr(actual_model, "name"):
            name = actual_model.name() if callable(actual_model.name) else actual_model.name
            return str(name) if name is not None else None
        return None

    def _capture_token_usage(self, model: Any) -> dict[str, int]:
        """
        Capture token usage from a model's last request.

        Args:
            model: The model instance to capture tokens from

        Returns:
            Dictionary with prompt, completion, and total tokens
        """
        tokens = {"prompt": 0, "completion": 0, "total": 0}

        # Unwrap if model is wrapped
        actual_model = model
        if hasattr(model, "afunc"):
            actual_model = model.afunc
        elif hasattr(model, "bound"):
            actual_model = model.bound

        # Capture tokens if available
        if hasattr(actual_model, "_last_request_usage") and actual_model._last_request_usage:
            tokens["prompt"] = actual_model._last_request_usage.get("prompt_tokens", 0)
            tokens["completion"] = actual_model._last_request_usage.get("completion_tokens", 0)
            tokens["total"] = actual_model._last_request_usage.get("total_tokens", 0)

        return tokens

    def _record_execution_metadata(
        self,
        start_time: float,
        success: bool,
        model: Optional[Any] = None,
        captured_tokens: Optional[dict[str, int]] = None,
    ) -> None:
        """
        Record node execution metrics to metadata collector.

        Args:
            start_time: Execution start time from time.time()
            success: Whether execution was successful
            model: Optional model instance for extracting model name
            captured_tokens: Optional pre-captured token usage dict
        """
        latency = time.time() - start_time
        collector = get_metadata_collector()

        # Get model name if model is provided
        model_name = None
        cost_usd = 0.0
        if model is not None:
            model_name = self._get_model_name(model)

            # Calculate cost if model has cost calculation capability
            if hasattr(model, "calculate_cost") and captured_tokens:
                try:
                    cost_usd = model.calculate_cost(
                        captured_tokens.get("prompt", 0), captured_tokens.get("completion", 0)
                    )
                except Exception:
                    # If cost calculation fails, default to 0
                    cost_usd = 0.0

        # Use provided tokens or default to zero
        tokens = captured_tokens or {"prompt": 0, "completion": 0, "total": 0}

        collector.record_node_execution(
            node_name=self.name,
            node_type=self.node_type,
            latency=latency,
            success=success,
            model_name=model_name,
            prompt_tokens=tokens["prompt"],
            completion_tokens=tokens["completion"],
            total_tokens=tokens["total"],
            cost_usd=cost_usd,
        )

    @abstractmethod
    def to_backend(self) -> Any:
        """
        Implement get runnable object specific to backend platform like LangGraph.

        It converts Node to platform(LangGraph) specific object
        Returns:
            Any: runnable node specific to the backend platform
        """
        pass
