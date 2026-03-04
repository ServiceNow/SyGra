from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING, Any, Union

import yaml

if TYPE_CHECKING:
    from sygra.workflow import Workflow

try:
    from sygra.core.dataset.dataset_config import DataSourceConfig, OutputConfig  # noqa: F401
    from sygra.core.graph.graph_config import GraphConfig  # noqa: F401
    from sygra.utils import utils
    from sygra.workflow import AutoNestedDict  # noqa: F401

    UTILS_AVAILABLE = True
except ImportError:
    UTILS_AVAILABLE = False


class ConfigLoader:
    """Loads existing SyGra YAML configurations and converts them to library objects."""

    def load(self, config_path: Union[str, Path, dict[str, Any]]) -> dict[str, Any]:
        """Load configuration from file or dictionary."""
        if isinstance(config_path, dict):
            return config_path

        config_path = Path(config_path)
        if not config_path.exists():
            if UTILS_AVAILABLE:
                task_config_path = utils.get_file_in_task_dir(config_path.stem, "graph_config.yaml")
                if os.path.exists(task_config_path):
                    config_path = Path(task_config_path)
                else:
                    raise FileNotFoundError(f"Configuration file not found: {config_path}")
            else:
                raise FileNotFoundError(f"Configuration file not found: {config_path}")

        with open(config_path, "r") as f:
            loaded_config = yaml.safe_load(f)
            if not isinstance(loaded_config, dict):
                raise TypeError(f"Expected dict from YAML, got {type(loaded_config)}")
            config: dict[str, Any] = loaded_config

        return config

    def load_and_create(self, config_path: Union[str, Path, dict[str, Any]]) -> Workflow:
        """Load config and create appropriate Workflow or Graph object."""
        config = self.load(config_path)

        # Import here to avoid circular imports
        from ..workflow import AutoNestedDict, Workflow

        workflow = Workflow()
        workflow._config = AutoNestedDict.convert_dict(config)

        workflow._supports_subgraphs = True
        workflow._supports_multimodal = True
        workflow._supports_resumable = True
        workflow._supports_quality = True
        workflow._supports_oasst = True

        if isinstance(config_path, (str, Path)):
            workflow.name = Path(config_path).parent.name
            workflow._is_existing_task = True
        else:
            workflow.name = config.get("task_name", "loaded_workflow")
            # Mark as existing task if config has nodes defined
            if config.get("graph_config", {}).get("nodes"):
                workflow._is_existing_task = True

        # Track node count from loaded config
        if "graph_config" in config and "nodes" in config["graph_config"]:
            workflow._node_counter = len(config["graph_config"]["nodes"])

        return workflow


__all__ = ["ConfigLoader"]
