from inspect import isclass
from typing import Any

from sygra.core.graph.nodes.base_node import BaseNode
from sygra.core.graph.nodes.llm_node import LLMNode
from sygra.utils import constants, utils


class MultiLLMNode(BaseNode):
    REQUIRED_KEYS: list[str] = ["models", "prompt"]

    def __init__(self, node_name: str, config: dict):
        """
        MultiLLMNode constructor.

        Args:
            node_name: Name of the node, defined as key under "nodes" in the YAML file.
            config: Node configuration defined in YAML file as the node value.
        """
        super().__init__(node_name, config)

        # multi llm node specific variable initialization
        self.output_key = self.node_config.get(constants.GRAPH_OUTPUT_KEY, "messages")

        self.llm_dict = {}
        for model_label, model_config in self.node_config["models"].items():
            node_config_copy = self.node_config.copy()
            node_config_copy["model"] = model_config
            llm_node = LLMNode(node_name, node_config_copy)
            self.llm_dict[model_label] = llm_node

        self.multi_llm_post_process = self._default_multi_llm_post_process
        if "multi_llm_post_process" in self.node_config:
            self.multi_llm_post_process = utils.get_func_from_str(
                self.node_config["multi_llm_post_process"]
            )
            # it can be a method or a class with apply method
            if isclass(self.multi_llm_post_process):
                self.multi_llm_post_process = self.multi_llm_post_process().apply

    def _default_multi_llm_post_process(self, model_outputs: dict[str, Any]) -> dict[str, Any]:
        updated_model_outputs = {}
        for model, messages in model_outputs.items():
            updated_model_outputs[model] = messages[self.output_key]
        return {self.output_key: [updated_model_outputs]}

    def to_backend(self) -> Any:
        """
        Convert the Node object to backend platform specific Runnable object.

        Returns:
             Any: platform specific runnable object like Runnable in LangGraph.
        """
        return utils.backend_factory.create_multi_llm_runnable(
            self.llm_dict, self.multi_llm_post_process
        )

    def validate_node(self):
        """
        Override the method to add required validation for this Node type.

        It throws Exception.
        Returns:
            None
        """
        self.validate_config_keys(self.REQUIRED_KEYS, self.node_type, self.node_config)
