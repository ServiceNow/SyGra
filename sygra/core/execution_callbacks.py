"""
Execution Callbacks for SyGra Workflow Execution.

Provides callback handlers for tracking node-level execution progress,
enabling real-time visualization in Studio and other UIs.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional
from uuid import UUID

from langchain_core.callbacks import AsyncCallbackHandler
from langchain_core.outputs import LLMResult

logger = logging.getLogger(__name__)


@dataclass
class ExecutionCallbacks:
    """
    Callbacks for workflow execution events.

    These callbacks are invoked during workflow execution to provide
    real-time progress updates for UI visualization.

    Example:
        ```python
        def on_node_start(node_name: str, input_data: dict):
            print(f"Node {node_name} starting with {input_data}")

        def on_node_complete(node_name: str, output_data: dict, duration_ms: int):
            print(f"Node {node_name} completed in {duration_ms}ms")

        callbacks = ExecutionCallbacks(
            on_node_start=on_node_start,
            on_node_complete=on_node_complete,
        )
        ```
    """

    # Called when a node starts execution
    on_node_start: Optional[Callable[[str, Dict[str, Any]], None]] = None

    # Called when a node completes successfully
    on_node_complete: Optional[Callable[[str, Dict[str, Any], int], None]] = None

    # Called when a node fails
    on_node_error: Optional[Callable[[str, str, Dict[str, Any]], None]] = None

    # Called when the entire graph execution starts
    on_graph_start: Optional[Callable[[Dict[str, Any]], None]] = None

    # Called when the entire graph execution completes
    on_graph_complete: Optional[Callable[[Dict[str, Any], int], None]] = None

    # Called when the graph execution fails
    on_graph_error: Optional[Callable[[str, Dict[str, Any]], None]] = None

    # Called for log messages during execution
    on_log: Optional[Callable[[str], None]] = None


class NodeExecutionTracker(AsyncCallbackHandler):
    """
    LangChain/LangGraph callback handler that tracks node execution.

    This handler integrates with LangGraph's callback system to provide
    real-time node execution tracking for UI visualization.

    Usage:
        ```python
        from sygra.core.execution_callbacks import NodeExecutionTracker, ExecutionCallbacks

        callbacks = ExecutionCallbacks(
            on_node_start=lambda name, data: print(f"Started: {name}"),
            on_node_complete=lambda name, data, ms: print(f"Done: {name} in {ms}ms"),
        )

        tracker = NodeExecutionTracker(callbacks)

        # Pass to graph execution
        result = await graph.ainvoke(
            input_data,
            config={"callbacks": [tracker]}
        )
        ```
    """

    def __init__(
        self,
        execution_callbacks: Optional[ExecutionCallbacks] = None,
        record_index: int = 0,
    ):
        """
        Initialize the node execution tracker.

        Args:
            execution_callbacks: Callbacks to invoke on execution events.
            record_index: Index of the current record being processed.
        """
        super().__init__()
        self.callbacks = execution_callbacks or ExecutionCallbacks()
        self.record_index = record_index

        # Track node execution times
        self._node_start_times: Dict[str, float] = {}
        self._current_node: Optional[str] = None
        self._graph_start_time: Optional[float] = None

    @property
    def current_node(self) -> Optional[str]:
        """Get the currently executing node name."""
        return self._current_node

    # ============ Chain Events (Node Level) ============

    async def on_chain_start(
        self,
        serialized: Dict[str, Any],
        inputs: Dict[str, Any],
        *,
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> None:
        """Called when a chain (node) starts execution."""
        # Extract node name from serialized data or metadata
        node_name = self._extract_node_name(serialized, metadata, tags)

        if node_name and not self._is_internal_chain(node_name, serialized):
            self._current_node = node_name
            self._node_start_times[node_name] = time.time()

            logger.debug(f"Node '{node_name}' started (record {self.record_index})")

            if self.callbacks.on_node_start:
                try:
                    self.callbacks.on_node_start(node_name, inputs)
                except Exception as e:
                    logger.error(f"Error in on_node_start callback: {e}")

    async def on_chain_end(
        self,
        outputs: Dict[str, Any],
        *,
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        tags: Optional[List[str]] = None,
        **kwargs: Any,
    ) -> None:
        """Called when a chain (node) completes execution."""
        # Use current node name
        node_name = self._current_node

        if node_name and node_name in self._node_start_times:
            start_time = self._node_start_times.pop(node_name, None)
            duration_ms = int((time.time() - start_time) * 1000) if start_time else 0

            logger.debug(
                f"Node '{node_name}' completed in {duration_ms}ms (record {self.record_index})"
            )

            if self.callbacks.on_node_complete:
                try:
                    self.callbacks.on_node_complete(node_name, outputs, duration_ms)
                except Exception as e:
                    logger.error(f"Error in on_node_complete callback: {e}")

    async def on_chain_error(
        self,
        error: BaseException,
        *,
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        tags: Optional[List[str]] = None,
        **kwargs: Any,
    ) -> None:
        """Called when a chain (node) fails."""
        node_name = self._current_node

        if node_name:
            logger.debug(f"Node '{node_name}' failed: {error} (record {self.record_index})")

            if self.callbacks.on_node_error:
                try:
                    self.callbacks.on_node_error(node_name, str(error), {})
                except Exception as e:
                    logger.error(f"Error in on_node_error callback: {e}")

    # ============ LLM Events ============

    async def on_llm_start(
        self,
        serialized: Dict[str, Any],
        prompts: List[str],
        *,
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> None:
        """Called when an LLM call starts."""
        # LLM calls are tracked at the node level via on_chain_start
        pass

    async def on_llm_end(
        self,
        response: LLMResult,
        *,
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        tags: Optional[List[str]] = None,
        **kwargs: Any,
    ) -> None:
        """Called when an LLM call completes."""
        # LLM calls are tracked at the node level via on_chain_end
        pass

    # ============ Helper Methods ============

    def _extract_node_name(
        self,
        serialized: Optional[Dict[str, Any]],
        metadata: Optional[Dict[str, Any]],
        tags: Optional[List[str]],
    ) -> Optional[str]:
        """Extract node name from callback data."""
        # Try metadata first (LangGraph sets this)
        if metadata:
            if "langgraph_node" in metadata:
                return str(metadata["langgraph_node"])
            if "node_name" in metadata:
                return str(metadata["node_name"])

        # Try tags
        if tags:
            for tag in tags:
                if tag.startswith("node:"):
                    return tag[5:]

        # Try serialized data (can be None in some LangGraph callbacks)
        if serialized and isinstance(serialized, dict):
            # LangGraph node name is often in the 'name' field
            name = serialized.get("name")
            if name and isinstance(name, str) and not name.startswith("_"):
                return str(name)

            # Or in the 'id' field
            id_parts = serialized.get("id", [])
            if id_parts and len(id_parts) > 0:
                # Last part is usually the specific name
                return id_parts[-1] if isinstance(id_parts[-1], str) else None

        return None

    def _is_internal_chain(
        self,
        node_name: str,
        serialized: Optional[Dict[str, Any]],
    ) -> bool:
        """Check if this is an internal LangChain/LangGraph chain to ignore."""
        # Ignore internal chains that aren't actual workflow nodes
        internal_prefixes = [
            "RunnableSequence",
            "RunnableParallel",
            "RunnableLambda",
            "ChannelWrite",
            "ChannelRead",
            "_",
        ]

        for prefix in internal_prefixes:
            if node_name.startswith(prefix):
                return True

        # Check serialized ID (serialized can be None in some LangGraph callbacks)
        if serialized and isinstance(serialized, dict):
            id_parts = serialized.get("id", [])
            if id_parts:
                for part in id_parts:
                    if isinstance(part, str) and any(part.startswith(p) for p in internal_prefixes):
                        return True

        return False


def create_execution_tracker(
    on_node_start: Optional[Callable[[str, Dict[str, Any]], None]] = None,
    on_node_complete: Optional[Callable[[str, Dict[str, Any], int], None]] = None,
    on_node_error: Optional[Callable[[str, str, Dict[str, Any]], None]] = None,
    record_index: int = 0,
) -> NodeExecutionTracker:
    """
    Convenience function to create a NodeExecutionTracker with callbacks.

    Args:
        on_node_start: Called when a node starts (node_name, input_data).
        on_node_complete: Called when a node completes (node_name, output_data, duration_ms).
        on_node_error: Called when a node fails (node_name, error_message, context).
        record_index: Index of the current record being processed.

    Returns:
        NodeExecutionTracker instance ready to use with graph.ainvoke().

    Example:
        ```python
        tracker = create_execution_tracker(
            on_node_start=lambda name, _: print(f"Started: {name}"),
            on_node_complete=lambda name, _, ms: print(f"Done: {name} ({ms}ms)"),
        )

        result = await graph.ainvoke(data, config={"callbacks": [tracker]})
        ```
    """
    callbacks = ExecutionCallbacks(
        on_node_start=on_node_start,
        on_node_complete=on_node_complete,
        on_node_error=on_node_error,
    )
    return NodeExecutionTracker(callbacks, record_index)
