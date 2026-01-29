import asyncio
import time
from inspect import isclass
from typing import Any

from sygra.core.graph.nodes.base_node import BaseNode
from sygra.utils import utils


class LambdaNode(BaseNode):
    REQUIRED_KEYS: list[str] = ["lambda"]

    def __init__(self, node_name: str, config: dict):
        """
        LambdaNode constructor.

        Args:
            node_name: Name of the node, defined as key under "nodes" in the YAML file.
            config: Node configuration defined in YAML file as the node value.
        """
        super().__init__(node_name, config)

        # specific variable for this node type
        self.func_to_execute = utils.get_func_from_str(self.node_config["lambda"])
        if isclass(self.func_to_execute):
            self.func_to_execute = self.func_to_execute.apply
        # deduce if the function type is sync or async
        if asyncio.iscoroutinefunction(self.func_to_execute):
            self.func_type = "async"
        else:
            self.func_type = "sync"

    async def _async_exec_wrapper(self, state: dict[str, Any]) -> dict[str, Any]:
        """
        Wrapper to track lambda node execution.

        Args:
            state: State of the node.

        Returns:
            Updated state
        """
        start_time = time.time()
        success = True

        try:
            result: dict[str, Any] = await self.func_to_execute(self.node_config, state)
            return result
        except Exception:
            success = False
            raise
        finally:
            self._record_execution_metadata(start_time, success)

    def _sync_exec_wrapper(self, state: dict[str, Any]) -> dict[str, Any]:
        """
        Wrapper to track lambda node execution.

        Args:
            state: State of the node.

        Returns:
            Updated state
        """
        start_time = time.time()
        success = True

        try:
            result: dict[str, Any] = self.func_to_execute(self.node_config, state)
            return result
        except Exception:
            success = False
            raise
        finally:
            self._record_execution_metadata(start_time, success)

    def to_backend(self) -> Any:
        """
        Convert the Node object to backend platform specific Runnable object.

        Returns:
             Any: platform specific runnable object like Runnable in LangGraph.
        """
        if self.func_type == "sync":
            return utils.backend_factory.create_lambda_runnable(
                self._sync_exec_wrapper, async_func=False
            )
        elif self.func_type == "async":
            # default to async function as old behavior(default async_func is True)
            return utils.backend_factory.create_lambda_runnable(self._async_exec_wrapper)
        else:
            raise Exception("Invalid function type")

    def validate_node(self):
        """
        Override the method to add required validation for this Node type.
        It throws Exception.

        Returns:
            None
        """
        self.validate_config_keys(self.REQUIRED_KEYS, self.node_type, self.node_config)
