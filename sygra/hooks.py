"""Public base classes for code that plugs into a SyGra graph.

Subclass these to write pre-processors, post-processors, lambdas, edge conditions,
data transforms, output generators and graph post-processors. A workflow accepts
each hook as a dotted import path (as in YAML tasks) or, in library use, as the
Python object itself: a function, a class, or a configured instance.

Stability: this module is public API, versioned by ``HOOKS_API_VERSION``.

- Import hook base classes from ``sygra.hooks`` (or ``sygra``), not from internal
  modules, which may move.
- Within one major version, the abstract methods and their signatures don't change.
- A breaking change raises ``HOOKS_API_VERSION``. The old form keeps working, with a
  ``DeprecationWarning``, for at least one minor release before removal.

Example:
    >>> from sygra.hooks import NodePostProcessorWithState
    >>> class Tag(NodePostProcessorWithState):
    ...     def __init__(self, label):
    ...         self.label = label
    ...     def apply(self, resp, state):
    ...         state["answer"] = f"{self.label}: {resp.message.content}"
    ...         return state
    >>> workflow.llm(model, "{question}", post_process=Tag("v1"))  # doctest: +SKIP
"""

from sygra.core.graph.functions.edge_condition import EdgeCondition
from sygra.core.graph.functions.lambda_function import AsyncLambdaFunction, LambdaFunction
from sygra.core.graph.functions.node_processor import (
    NodePostProcessor,
    NodePostProcessorWithState,
    NodePreProcessor,
)
from sygra.core.graph.graph_postprocessor import GraphPostProcessor
from sygra.core.graph.sygra_message import SygraMessage
from sygra.core.graph.sygra_state import SygraState
from sygra.processors.data_transform import DataTransform
from sygra.processors.output_record_generator import BaseOutputGenerator

HOOKS_API_VERSION = 1

__all__ = [
    "HOOKS_API_VERSION",
    "AsyncLambdaFunction",
    "BaseOutputGenerator",
    "DataTransform",
    "EdgeCondition",
    "GraphPostProcessor",
    "LambdaFunction",
    "NodePostProcessor",
    "NodePostProcessorWithState",
    "NodePreProcessor",
    "SygraMessage",
    "SygraState",
]
