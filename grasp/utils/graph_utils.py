import traceback
from typing import Any, Callable

from langchain_core.runnables import RunnableConfig
from langgraph.graph.state import CompiledStateGraph

from grasp.logger.logger_config import logger


def convert_graph_output_to_records(
    graph_results: list,
    output_record_generator: Callable = None,
):
    updated_graph_results = []
    for graph_result in graph_results:
        try:
            if output_record_generator:
                graph_result = output_record_generator(graph_result)
        except Exception as e:
            logger.error(
                f"Exception occured when converting graph output to record: {e}"
            )
            graph_result = None

        if graph_result is None:
            continue
        updated_graph_results.append(graph_result)
    return updated_graph_results


async def execute_graph(
    record: dict,
    graph: CompiledStateGraph,
    debug: bool = False,
    input_record_generator: Callable = None,
) -> dict[str, Any]:
    if input_record_generator:
        record = input_record_generator(record)
    try:
        return await graph.ainvoke(
            record, debug=debug, config=RunnableConfig(recursion_limit=100)
        )
    except Exception as e:
        logger.error(
            f"Exception occured when executing graph for record id {record.get('id', None)}: {e}"
        )
        logger.error(traceback.format_exc())
        return {"execution_error": True}
