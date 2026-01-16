"""
Execution Manager for SyGra Studio Integration.

Manages workflow execution with real-time progress tracking,
providing updates for UI visualization.
"""
import argparse
import asyncio
import logging
import threading
import uuid
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from studio.models import (
    ExecutionStatus,
    NodeExecutionState,
    WorkflowExecution,
    WorkflowGraph,
)


logger = logging.getLogger(__name__)


class ExecutionCallback:
    """Callbacks for execution events."""

    def __init__(
        self,
        on_start: Optional[Callable[[str], None]] = None,
        on_node_start: Optional[Callable[[str, str], None]] = None,
        on_node_complete: Optional[Callable[[str, str, Any], None]] = None,
        on_node_error: Optional[Callable[[str, str, str], None]] = None,
        on_complete: Optional[Callable[[str, Any], None]] = None,
        on_error: Optional[Callable[[str, str], None]] = None,
    ):
        """
        Initialize execution callbacks.

        Args:
            on_start: Called when execution starts (execution_id).
            on_node_start: Called when a node starts (execution_id, node_id).
            on_node_complete: Called when a node completes (execution_id, node_id, result).
            on_node_error: Called when a node fails (execution_id, node_id, error).
            on_complete: Called when execution completes (execution_id, result).
            on_error: Called when execution fails (execution_id, error).
        """
        self.on_start = on_start
        self.on_node_start = on_node_start
        self.on_node_complete = on_node_complete
        self.on_node_error = on_node_error
        self.on_complete = on_complete
        self.on_error = on_error


class ExecutionManager:
    """
    Manages SyGra workflow executions with real-time tracking.

    Provides execution lifecycle management and progress updates
    for UI visualization.
    """

    def __init__(self):
        """Initialize the execution manager."""
        self._executions: Dict[str, WorkflowExecution] = {}
        self._callbacks: Dict[str, ExecutionCallback] = {}
        self._lock = threading.Lock()

    def create_execution(
        self,
        workflow: WorkflowGraph,
        input_data: Dict[str, Any],
        callback: Optional[ExecutionCallback] = None,
    ) -> WorkflowExecution:
        """
        Create a new workflow execution.

        Args:
            workflow: The workflow graph to execute.
            input_data: Input data for the workflow.
            callback: Optional callbacks for execution events.

        Returns:
            New WorkflowExecution instance.
        """
        execution_id = str(uuid.uuid4())

        execution = WorkflowExecution(
            id=execution_id,
            workflow_id=workflow.id,
            workflow_name=workflow.name,
            status=ExecutionStatus.PENDING,
            input_data=input_data,
        )

        # Initialize node states
        for node in workflow.nodes:
            execution.node_states[node.id] = NodeExecutionState(
                node_id=node.id,
                status=ExecutionStatus.PENDING,
            )

        with self._lock:
            self._executions[execution_id] = execution
            if callback:
                self._callbacks[execution_id] = callback

        return execution

    def get_execution(self, execution_id: str) -> Optional[WorkflowExecution]:
        """Get an execution by ID."""
        return self._executions.get(execution_id)

    def list_executions(
        self,
        workflow_id: Optional[str] = None,
        status: Optional[ExecutionStatus] = None,
    ) -> List[WorkflowExecution]:
        """List executions with optional filtering."""
        executions = list(self._executions.values())

        if workflow_id:
            executions = [e for e in executions if e.workflow_id == workflow_id]

        if status:
            executions = [e for e in executions if e.status == status]

        return executions

    def start_execution(self, execution_id: str) -> None:
        """Mark an execution as started."""
        execution = self._executions.get(execution_id)
        if not execution:
            return

        execution.status = ExecutionStatus.RUNNING
        execution.started_at = datetime.now()
        execution.logs.append(f"[{datetime.now().isoformat()}] Execution started")

        callback = self._callbacks.get(execution_id)
        if callback and callback.on_start:
            try:
                callback.on_start(execution_id)
            except Exception as e:
                logger.error(f"Error in on_start callback: {e}")

    def start_node(self, execution_id: str, node_id: str) -> None:
        """Mark a node as started."""
        execution = self._executions.get(execution_id)
        if not execution:
            return

        node_state = execution.node_states.get(node_id)
        if not node_state:
            return

        node_state.status = ExecutionStatus.RUNNING
        node_state.started_at = datetime.now()
        execution.current_node = node_id
        execution.logs.append(f"[{datetime.now().isoformat()}] Node '{node_id}' started")

        callback = self._callbacks.get(execution_id)
        if callback and callback.on_node_start:
            try:
                callback.on_node_start(execution_id, node_id)
            except Exception as e:
                logger.error(f"Error in on_node_start callback: {e}")

    def complete_node(
        self,
        execution_id: str,
        node_id: str,
        result: Any = None,
    ) -> None:
        """Mark a node as completed."""
        execution = self._executions.get(execution_id)
        if not execution:
            return

        node_state = execution.node_states.get(node_id)
        if not node_state:
            return

        node_state.status = ExecutionStatus.COMPLETED
        node_state.completed_at = datetime.now()
        node_state.result = result

        if node_state.started_at:
            duration = (node_state.completed_at - node_state.started_at).total_seconds()
            node_state.duration_ms = int(duration * 1000)

        execution.logs.append(
            f"[{datetime.now().isoformat()}] Node '{node_id}' completed "
            f"(duration: {node_state.duration_ms}ms)"
        )

        callback = self._callbacks.get(execution_id)
        if callback and callback.on_node_complete:
            try:
                callback.on_node_complete(execution_id, node_id, result)
            except Exception as e:
                logger.error(f"Error in on_node_complete callback: {e}")

    def fail_node(
        self,
        execution_id: str,
        node_id: str,
        error: str,
    ) -> None:
        """Mark a node as failed."""
        execution = self._executions.get(execution_id)
        if not execution:
            return

        node_state = execution.node_states.get(node_id)
        if not node_state:
            return

        node_state.status = ExecutionStatus.FAILED
        node_state.completed_at = datetime.now()
        node_state.error = error

        execution.error_node = node_id
        execution.logs.append(
            f"[{datetime.now().isoformat()}] Node '{node_id}' failed: {error}"
        )

        callback = self._callbacks.get(execution_id)
        if callback and callback.on_node_error:
            try:
                callback.on_node_error(execution_id, node_id, error)
            except Exception as e:
                logger.error(f"Error in on_node_error callback: {e}")

    def complete_execution(
        self,
        execution_id: str,
        result: Any = None,
    ) -> None:
        """Mark an execution as completed."""
        execution = self._executions.get(execution_id)
        if not execution:
            return

        execution.status = ExecutionStatus.COMPLETED
        execution.completed_at = datetime.now()
        execution.output_data = result
        execution.current_node = None

        if execution.started_at:
            duration = (execution.completed_at - execution.started_at).total_seconds()
            execution.duration_ms = int(duration * 1000)

        execution.logs.append(
            f"[{datetime.now().isoformat()}] Execution completed "
            f"(total duration: {execution.duration_ms}ms)"
        )

        callback = self._callbacks.get(execution_id)
        if callback and callback.on_complete:
            try:
                callback.on_complete(execution_id, result)
            except Exception as e:
                logger.error(f"Error in on_complete callback: {e}")

    def fail_execution(
        self,
        execution_id: str,
        error: str,
    ) -> None:
        """Mark an execution as failed."""
        execution = self._executions.get(execution_id)
        if not execution:
            return

        execution.status = ExecutionStatus.FAILED
        execution.completed_at = datetime.now()
        execution.error = error

        if execution.started_at:
            duration = (execution.completed_at - execution.started_at).total_seconds()
            execution.duration_ms = int(duration * 1000)

        execution.logs.append(
            f"[{datetime.now().isoformat()}] Execution failed: {error}"
        )

        callback = self._callbacks.get(execution_id)
        if callback and callback.on_error:
            try:
                callback.on_error(execution_id, error)
            except Exception as e:
                logger.error(f"Error in on_error callback: {e}")

    def cancel_execution(self, execution_id: str) -> bool:
        """
        Cancel a running execution.

        Returns:
            True if cancellation was successful.
        """
        execution = self._executions.get(execution_id)
        if not execution:
            return False

        if execution.status not in (ExecutionStatus.PENDING, ExecutionStatus.RUNNING):
            return False

        execution.status = ExecutionStatus.CANCELLED
        execution.completed_at = datetime.now()
        execution.logs.append(
            f"[{datetime.now().isoformat()}] Execution cancelled by user"
        )

        return True

    def add_log(self, execution_id: str, message: str) -> None:
        """Add a log message to an execution."""
        execution = self._executions.get(execution_id)
        if execution:
            execution.logs.append(f"[{datetime.now().isoformat()}] {message}")


class SygraExecutionRunner:
    """
    Runs SyGra workflows with execution tracking.

    Integrates with SyGra's BaseTaskExecutor while providing
    real-time progress updates.
    """

    def __init__(self, execution_manager: ExecutionManager):
        """
        Initialize the execution runner.

        Args:
            execution_manager: The execution manager for tracking.
        """
        self.execution_manager = execution_manager

    async def run_workflow(
        self,
        execution_id: str,
        workflow: WorkflowGraph,
        input_data: Dict[str, Any],
        max_samples: int = 1,
    ) -> Any:
        """
        Run a SyGra workflow with tracking.

        Args:
            execution_id: The execution ID for tracking.
            workflow: The workflow graph to execute.
            input_data: Input data for the workflow.
            max_samples: Maximum samples to process.

        Returns:
            Workflow execution result.
        """
        self.execution_manager.start_execution(execution_id)

        try:
            # Import SyGra components
            from sygra.core.base_task_executor import BaseTaskExecutor

            # Start tracking
            self.execution_manager.start_node(execution_id, "START")
            self.execution_manager.complete_node(execution_id, "START")

            if not workflow.source_path:
                raise ValueError("Workflow source path not available")

            # Create and run executor
            self.execution_manager.add_log(
                execution_id,
                f"Initializing workflow from {workflow.source_path}"
            )

            args = argparse.Namespace()
            args.config_path = workflow.source_path
            args.output_dir = "./output"
            args.num_records = max_samples
            executor = BaseTaskExecutor(args=args)

            # Track each node execution
            # Note: This is a simplified approach - ideally we'd hook into
            # LangGraph's execution events for real-time node tracking
            for node in workflow.nodes:
                if node.id in ("START", "END"):
                    continue

                self.execution_manager.start_node(execution_id, node.id)

            # Run the workflow
            result = await asyncio.to_thread(
                executor.run,
                data=[input_data] if input_data else None,
            )

            # Mark all nodes as completed
            for node in workflow.nodes:
                if node.id == "END":
                    continue

                node_state = self.execution_manager.get_execution(execution_id)
                if node_state:
                    ns = node_state.node_states.get(node.id)
                    if ns and ns.status == ExecutionStatus.RUNNING:
                        self.execution_manager.complete_node(execution_id, node.id)

            self.execution_manager.start_node(execution_id, "END")
            self.execution_manager.complete_node(execution_id, "END")
            self.execution_manager.complete_execution(execution_id, result)

            return result

        except Exception as e:
            logger.error(f"Workflow execution failed: {e}")

            # Find and mark the current node as failed
            execution = self.execution_manager.get_execution(execution_id)
            if execution and execution.current_node:
                self.execution_manager.fail_node(
                    execution_id,
                    execution.current_node,
                    str(e)
                )

            self.execution_manager.fail_execution(execution_id, str(e))
            raise


# Global execution manager instance
_execution_manager: Optional[ExecutionManager] = None


def get_execution_manager() -> ExecutionManager:
    """Get the global execution manager instance."""
    global _execution_manager
    if _execution_manager is None:
        _execution_manager = ExecutionManager()
    return _execution_manager
