import random
from typing import Any

from sygra.core.graph.nodes.base_node import BaseNode
from sygra.utils import utils


class WeightedSamplerNode(BaseNode):
    """
    A node to handle weighted samples defined statically in the graph yaml under weighted_sampler node.
    """

    REQUIRED_KEYS: list[str] = ["attributes"]

    def __init__(self, node_name: str, config: dict):
        """
        WeightedSamplerNode constructor.

        Args:
            node_name: Name of the node, defined as key under "nodes" in the YAML file.
            config: Node configuration defined in YAML file as the node value.
        """

        super().__init__(node_name, config)

        # add weighted sampler variables into node state variables
        self._process_weighted_sampler(self.node_config)

    def _weighted_sampler(self, attr_configs, state: dict[str, Any]):
        sampled_values = {}
        for attr, attr_config in attr_configs.items():
            attr_values = attr_config["values"]
            # now we support datasource as a sampler.
            # instead of static value list provide the data source config and column name to pick as a dict
            """
            my_sampler_node:
              node_type: weighted_sampler
              attributes:
                my_role:
                  values:
                    column: "persona"
                    source:
                      type: "hf"
                      repo_id: "nvidia/Nemotron-Personas"
                      config_name: "default"
                      split: "train"
            You can use 'my_role' as a output variable of this node and use in next node.
            Only difference is the 'values' field, it was static list, now it contains a dictionary
            """
            if isinstance(attr_values, dict):
                column = attr_config["values"]["column"]
                # if list of columns are given, select one column randomly
                if isinstance(column, list):
                    # randomly select a column
                    column = random.choice(column)
                datasrc = attr_config["values"]["source"]
                sampled_values[attr] = utils.fetch_next_record(datasrc, column)
            else:
                # else if static value list
                weights = attr_config.get("weights", [1] * len(attr_values))
                sampled_values[attr] = random.choices(population=attr_values, weights=weights)[0]
        return sampled_values

    def _process_weighted_sampler(self, node_config: dict) -> None:
        """Process 'weighted_sampler' nodes and add their attributes to state variables."""
        if node_config.get("node_type") == "weighted_sampler":
            attributes = node_config.get("attributes")
            if isinstance(attributes, dict):
                self.state_variables.extend(attributes.keys())
            else:
                raise ValueError(
                    f"'attributes' must be a dictionary, but got {type(attributes).__name__}"
                )

    def to_backend(self) -> Any:
        """
        Convert the Node object to backend platform specific Runnable object.

        Returns:
             Any: platform specific runnable object like Runnable in LangGraph.
        """
        return utils.backend_factory.create_weighted_sampler_runnable(
            self._weighted_sampler, self.node_config["attributes"]
        )

    def validate_node(self):
        """
        Override the method to add required validation for this Node type.
        It throws Exception.

        Returns:
           None
        """
        self.validate_config_keys(self.REQUIRED_KEYS, self.node_type, self.node_config)

        # validate each attribute node
        for attr, attr_config in self.node_config["attributes"].items():
            self.validate_config_keys(
                ["values"], f"attribute {attr} for random sampler node", attr_config
            )
