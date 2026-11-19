import os
from pathlib import Path
from typing import Any, Optional, Union

import yaml

from sygra.exceptions import ConfigurationError

try:
    from sygra.core.dataset.dataset_config import DataSourceConfig, OutputConfig  # noqa: F401
    from sygra.core.graph.graph_config import GraphConfig  # noqa: F401
    from sygra.utils import utils

    UTILS_AVAILABLE = True
except ImportError:
    UTILS_AVAILABLE = False


class ConfigLoader:
    """Loads existing SyGra YAML configurations and converts them to library objects."""

    def load(self, config_path: Union[str, Path, dict[str, Any]]) -> dict[str, Any]:
        """Load configuration from file or dictionary."""
        if isinstance(config_path, dict):
            return config_path

        with open(self.resolve_path(config_path), "r") as f:
            loaded_config = yaml.safe_load(f)
            if not isinstance(loaded_config, dict):
                raise TypeError(f"Expected dict from YAML, got {type(loaded_config)}")
            config: dict[str, Any] = loaded_config

        return config

    def resolve_path(self, config_path: Union[str, Path]) -> Path:
        """Return the YAML file for ``config_path``, falling back to the task directory."""
        config_path = Path(config_path)
        if not config_path.exists():
            if UTILS_AVAILABLE:
                task_config_path = utils.get_file_in_task_dir(config_path.stem, "graph_config.yaml")
                if os.path.exists(task_config_path):
                    return Path(task_config_path)
            raise FileNotFoundError(f"Configuration file not found: {config_path}")
        return config_path

    def load_and_create(self, config_path: Union[str, Path, dict[str, Any]]):
        """Load config and create a Workflow. Same as ``Workflow.from_config(config_path)``."""
        # Import here to avoid circular imports
        from ..workflow import Workflow

        return Workflow.from_config(config_path)


PROMPT_FILE_KEY = "file"


def resolve_prompt_files(config: dict[str, Any], base_dir: Optional[Path]) -> None:
    """Replace ``{"file": path}`` prompt messages with the file's text, in place.

    Relative paths are resolved against ``base_dir``, never the working directory.
    Covers each node's ``prompt`` and the ``prompt`` of subgraph ``node_config_map``
    overrides.
    """
    nodes = (config.get("graph_config") or {}).get("nodes") or {}
    for node_name, node in nodes.items():
        if not isinstance(node, dict):
            continue
        _resolve_messages(node.get("prompt"), base_dir, node_name)
        for override_name, override in (node.get("node_config_map") or {}).items():
            if isinstance(override, dict):
                _resolve_messages(override.get("prompt"), base_dir, f"{node_name}.{override_name}")


def _resolve_messages(messages: Any, base_dir: Optional[Path], node_name: str) -> None:
    if not isinstance(messages, list):
        return
    for message in messages:
        if not isinstance(message, dict):
            continue
        for role, content in message.items():
            if isinstance(content, dict) and set(content) == {PROMPT_FILE_KEY}:
                message[role] = _read_prompt_file(content[PROMPT_FILE_KEY], base_dir, node_name)


def _read_prompt_file(path_value: Any, base_dir: Optional[Path], node_name: str) -> str:
    path = Path(str(path_value)).expanduser()
    if not path.is_absolute():
        if base_dir is None:
            raise ConfigurationError(
                f"Prompt file '{path_value}' in node '{node_name}' is a relative path; "
                "pass base_dir to resolve it"
            )
        path = base_dir / path
    if not path.is_file():
        raise ConfigurationError(f"Prompt file for node '{node_name}' not found: {path}")
    return path.read_text(encoding="utf-8")


def resolve_data_paths(config: dict[str, Any], base_dir: Path) -> None:
    """Make relative ``file_path`` values of data sources and sinks absolute, in place."""
    data_config = config.get("data_config") or {}
    for key in ("source", "sink"):
        entries = data_config.get(key)
        for entry in entries if isinstance(entries, list) else [entries]:
            if isinstance(entry, dict) and isinstance(entry.get("file_path"), str):
                path = Path(entry["file_path"]).expanduser()
                if not path.is_absolute():
                    entry["file_path"] = str(base_dir / path)


__all__ = ["ConfigLoader", "resolve_data_paths", "resolve_prompt_files"]
