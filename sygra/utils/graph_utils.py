import traceback
from typing import TYPE_CHECKING, Any, Callable, List, Optional

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.runnables import RunnableConfig
from langgraph.graph.state import CompiledStateGraph

from sygra.logger.logger_config import logger

if TYPE_CHECKING:
    from sygra.core.execution_callbacks import ExecutionCallbacks


def convert_graph_output_to_records(
    graph_results: list,
    output_record_generator: Optional[Callable[[Any], Any]] = None,
):
    updated_graph_results = []
    for graph_result in graph_results:
        try:
            if output_record_generator is not None:
                graph_result = output_record_generator(graph_result)
        except Exception as e:
            logger.error(f"Exception occured when converting graph output to record: {e}")
            graph_result = None

        if graph_result is None:
            continue
        updated_graph_results.append(graph_result)
    return updated_graph_results


async def execute_graph(
    record: dict,
    graph: CompiledStateGraph,
    debug: bool = False,
    input_record_generator: Optional[Callable[[dict], dict]] = None,
    callbacks: Optional[List[BaseCallbackHandler]] = None,
    execution_callbacks: Optional["ExecutionCallbacks"] = None,
    record_index: int = 0,
) -> dict[str, Any]:
    """
    Execute a compiled graph on a single record.

    Args:
        record: Input record to process.
        graph: Compiled LangGraph StateGraph.
        debug: Enable debug mode.
        input_record_generator: Optional function to transform input record.
        callbacks: Optional list of LangChain callback handlers.
        execution_callbacks: Optional ExecutionCallbacks for node-level tracking.
        record_index: Index of the record being processed (for logging).

    Returns:
        Graph execution result or error dict.
    """
    if input_record_generator is not None:
        record = input_record_generator(record)

    # Build callback list
    all_callbacks: List[BaseCallbackHandler] = []

    # Add user-provided callbacks
    if callbacks:
        all_callbacks.extend(callbacks)

    # Add execution tracker if ExecutionCallbacks provided
    if execution_callbacks:
        from sygra.core.execution_callbacks import NodeExecutionTracker

        tracker = NodeExecutionTracker(execution_callbacks, record_index)
        all_callbacks.append(tracker)

    # Build config with callbacks
    config = RunnableConfig(
        recursion_limit=100,
        callbacks=all_callbacks if all_callbacks else None,
    )

    try:
        return await graph.ainvoke(record, debug=debug, config=config)
    except Exception as e:
        logger.error(
            f"Exception occured when executing graph for record id {record.get('id', None)}: {e}"
        )
        logger.error(traceback.format_exc())
        return {"execution_error": True}
