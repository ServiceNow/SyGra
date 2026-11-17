from __future__ import annotations

import asyncio
import json
import os
import shutil
import tempfile
import uuid
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Optional, Union

import yaml

from sygra.processors.output_record_generator import BaseOutputGenerator

try:
    from argparse import Namespace

    from sygra.core.base_task_executor import BaseTaskExecutor, DefaultTaskExecutor
    from sygra.core.dataset.dataset_config import DataSourceConfig  # noqa: F401
    from sygra.core.dataset.dataset_config import DataSourceType  # noqa: F401
    from sygra.core.dataset.dataset_config import OutputConfig  # noqa: F401
    from sygra.core.dataset.dataset_config import OutputType  # noqa: F401
    from sygra.core.graph.functions.node_processor import (
        NodePostProcessor,
        NodePostProcessorWithState,
        NodePreProcessor,
    )
    from sygra.core.graph.sygra_message import SygraMessage  # noqa: F401
    from sygra.core.graph.sygra_state import SygraState  # noqa: F401
    from sygra.core.judge_task_executor import JudgeQualityTaskExecutor
    from sygra.logger.logger_config import logger
    from sygra.utils import constants  # noqa: F401
    from sygra.utils import utils as utils

    CORE_AVAILABLE = True
except ImportError:
    CORE_AVAILABLE = False
    from sygra.logger.logger_config import logger

from sygra.core.run_result import CostFn, RunResult
from sygra.exceptions import ConfigurationError, ExecutionError, GraSPError, ModelServerDownError
from sygra.models import ModelConfigBuilder

if TYPE_CHECKING:
    from sygra.core.models.external import LLMProvider


def _read_records(output_file: Optional[str]) -> list[Any]:
    """Read output records from a ``.json`` / ``.jsonl`` file; empty if unavailable."""
    if not output_file or not os.path.exists(output_file):
        return []
    try:
        with open(output_file, "r") as f:
            if output_file.endswith(".jsonl"):
                return [json.loads(line) for line in f if line.strip()]
            data = json.load(f)
    except Exception as e:
        logger.warning(f"Could not read output file {output_file}: {e}")
        return []
    return data if isinstance(data, list) else [data]


# Import node builders with conditional availability
try:
    from sygra.nodes import (
        AgentNodeBuilder,
        LambdaNodeBuilder,
        LLMNodeBuilder,
        MultiLLMNodeBuilder,
        SubgraphNodeBuilder,
        WeightedSamplerNodeBuilder,
    )

    NODE_BUILDERS_AVAILABLE = True
except ImportError:
    NODE_BUILDERS_AVAILABLE = False

# Import data utilities with conditional availability
try:
    from sygra.data import DataSink, DataSource

    DATA_UTILS_AVAILABLE = True
except ImportError:
    DATA_UTILS_AVAILABLE = False


class AutoNestedDict(dict):
    """Dictionary that automatically creates nested dictionaries on access."""

    def __getitem__(self, key):
        if key not in self:
            self[key] = AutoNestedDict()
        return super().__getitem__(key)

    def __setitem__(self, key, value):
        if isinstance(value, dict) and not isinstance(value, AutoNestedDict):
            value = self.convert_dict(value)
        super().__setitem__(key, value)

    @classmethod
    def convert_dict(cls, d):
        """Recursively convert nested dicts to AutoNestedDict."""
        result = cls()
        for k, v in d.items():
            if isinstance(v, dict):
                result[k] = cls.convert_dict(v)
            elif isinstance(v, list):
                result[k] = [
                    cls.convert_dict(item) if isinstance(item, dict) else item for item in v
                ]
            else:
                result[k] = v
        return result

    def to_dict(self) -> dict:
        """Recursively convert AutoNestedDict to regular dict."""
        result: dict[str, Any] = {}
        for k, v in self.items():
            if isinstance(v, AutoNestedDict):
                result[k] = v.to_dict()
            elif isinstance(v, dict):
                result[k] = self._convert_dict_to_regular(v)
            elif isinstance(v, list):
                converted_list: list[Any] = [
                    (
                        item.to_dict()
                        if isinstance(item, AutoNestedDict)
                        else self._convert_dict_to_regular(item) if isinstance(item, dict) else item
                    )
                    for item in v
                ]
                result[k] = converted_list
            else:
                result[k] = v
        return result

    @staticmethod
    def _convert_dict_to_regular(d):
        """Helper to convert any dict to regular dict recursively."""
        if isinstance(d, AutoNestedDict):
            return d.to_dict()
        elif isinstance(d, dict):
            return {k: AutoNestedDict._convert_dict_to_regular(v) for k, v in d.items()}
        elif isinstance(d, list):
            return [AutoNestedDict._convert_dict_to_regular(item) for item in d]
        else:
            return d


class Workflow:
    """
    Unified workflow builder supporting all SyGra paradigms and use cases.

    Supports:
    - Fluent API building with custom processors
    - Existing YAML task execution
    - Explicit graph building with node builders
    - Direct function references and lambda processing
    - Complex conditional workflows and edge routing

    Examples:
        # Fluent API with custom processors
        >>> workflow = Workflow("my_workflow")
        >>> result = workflow.source(data) \\
        >>>         .llm("gpt-4", "Create haiku: {text}",
        >>>              post_process=TextExtractionPostProcessor) \\
        >>>         .sink("output.json") \\
        >>>         .run()

        # Execute existing YAML task
        >>> workflow = Workflow("tasks/examples/glaive_code_assistant")
        >>> workflow.run(num_records=1)

        # Explicit graph building
        >>> graph = create_graph("complex_workflow")
        >>> summarizer = graph.add_llm_node("summarizer", "gpt-4o") \\
        >>>                   .system_message("Create summaries") \\
        >>>                   .user_message("Summarize: {text}")
        >>> graph.sequence("START", "summarizer", "END")
        >>> results = graph.run()

        # Direct function references
        >>> workflow.source(data) \\
        >>>         .lambda_func(TextCleanerLambda, output="cleaned") \\
        >>>         .llm("gpt-4", "Process: {cleaned}",
        >>>              pre_process=PromptTemplatePreProcessor) \\
        >>>         .run()
    """

    def __init__(self, name: Optional[str] = None):
        self.name: str = name or f"workflow_{uuid.uuid4().hex[:8]}"
        self._config: AutoNestedDict = AutoNestedDict(
            {
                "graph_config": {"nodes": {}, "edges": [], "graph_properties": {}},
                "data_config": {},
                "output_config": {},
            }
        )
        self._node_counter: int = 0
        self._last_node: Optional[str] = None
        self._temp_files: list[str] = []
        self._node_builders: dict[str, Any] = {}
        self._messages: list[str] = []
        self._is_existing_task: bool = False
        self._from_config: bool = False
        self._llm_providers: dict[str, LLMProvider] = {}

        # Feature support flags
        self._supports_subgraphs = True
        self._supports_multimodal = True
        self._supports_resumable = True
        self._supports_quality = True
        self._supports_oasst = True

        self._load_existing_config_if_present()

    @classmethod
    def from_config(
        cls,
        config: Union[str, Path, dict[str, Any]],
        *,
        base_dir: Optional[Union[str, Path]] = None,
        name: Optional[str] = None,
    ) -> "Workflow":
        """Create a Workflow from a config dictionary or a YAML file.

        The config has the same shape as a task's ``graph_config.yaml``. It doesn't need
        to live in a task directory: like other programmatic workflows, output goes to a
        temporary directory unless ``run(output_dir=...)`` is given.

        A prompt message can be inline text or ``{"file": path}``, which is replaced by
        the file's text. Relative prompt files are resolved against ``base_dir`` or, for
        a YAML file, the file's directory. They are never resolved against the working
        directory.

        When ``base_dir`` is given, relative ``file_path`` values of data sources and
        sinks are resolved against it too. Without it they are left unchanged.

        Args:
            config: Config dictionary, or path to a YAML config file. The dictionary is
                not modified.
            base_dir: Directory for relative prompt files and data paths.
            name: Workflow name. Defaults to the config's ``task_name``, then the YAML
                file's directory name.

        Returns:
            Workflow: A workflow ready to ``run()``.

        Example:
            >>> config = {
            ...     "data_config": {"source": {"type": "disk", "file_path": "data.json"}},
            ...     "graph_config": {
            ...         "nodes": {
            ...             "gen": {
            ...                 "node_type": "llm",
            ...                 "model": {"name": "gpt-4o"},
            ...                 "prompt": [
            ...                     {"system": {"file": "prompts/system.txt"}},
            ...                     {"user": "{text}"},
            ...                 ],
            ...             }
            ...         },
            ...         "edges": [{"from": "START", "to": "gen"}, {"from": "gen", "to": "END"}],
            ...     },
            ... }
            >>> workflow = Workflow.from_config(config, base_dir="/srv/my_flow")
        """
        from sygra.configuration.loader import (
            ConfigLoader,
            resolve_data_paths,
            resolve_prompt_files,
        )

        loader = ConfigLoader()
        config_dir: Optional[Path] = None
        if isinstance(config, dict):
            loaded = utils.copy_config(config)
        else:
            config_dir = loader.resolve_path(config).resolve().parent
            loaded = loader.load(config)

        base = Path(base_dir).expanduser().resolve() if base_dir is not None else None
        resolve_prompt_files(loaded, base or config_dir)
        if base is not None:
            resolve_data_paths(loaded, base)

        workflow = cls(name or loaded.get("task_name") or (config_dir.name if config_dir else None))
        workflow._config = AutoNestedDict.convert_dict(loaded)
        workflow._is_existing_task = False
        workflow._from_config = True
        workflow._node_counter = len((loaded.get("graph_config") or {}).get("nodes") or {})
        return workflow

    def _load_existing_config_if_present(self):
        """Load existing task configuration if this appears to be a task path."""
        if self.name and (os.path.exists(self.name) or "/" in self.name or "\\" in self.name):
            task_path = self.name
            config_file = os.path.join(task_path, "graph_config.yaml")

            if not os.path.isabs(task_path):
                config_file = os.path.join(os.getcwd(), config_file)

            if os.path.exists(config_file):
                try:
                    with open(config_file, "r") as f:
                        loaded_config = yaml.safe_load(f)

                    if loaded_config:
                        self._config = AutoNestedDict.convert_dict(loaded_config)
                        self._is_existing_task = True

                        if (
                            "graph_config" in self._config
                            and "nodes" in self._config["graph_config"]
                        ):
                            self._node_counter = len(self._config["graph_config"]["nodes"])

                        logger.info(f"Loaded existing task config: {self.name}")

                except Exception as e:
                    logger.warning(f"Failed to load existing config from {config_file}: {e}")

    def source(
        self, source: Union[str, Path, dict[str, Any], list[dict[str, Any]], DataSource]
    ) -> "Workflow":
        """Add data source with full framework support.

        A list of dicts (or ``{"data": [...]}``) is an in-memory source: the records
        are read from memory and never written to disk.
        """
        source_config: dict[str, Any]
        if isinstance(source, (str, Path)):
            source_config = {
                "type": "disk",
                "file_path": str(source),
                "file_format": self._detect_file_format(str(source)),
            }
        elif isinstance(source, list):
            source_config = {"type": "memory", "records": source}
        elif isinstance(source, dict):
            if "data" in source:
                source_config = {"type": "memory", "records": source["data"]}
            else:
                source_config = source
        elif DATA_UTILS_AVAILABLE and isinstance(source, DataSource):
            source_config = source.to_config()
        else:
            raise ValueError(f"Unsupported source type: {type(source)}")

        self._config["data_config"]["source"] = source_config
        return self

    def sink(self, sink: Union[str, Path, dict[str, Any], DataSink]) -> "Workflow":
        """Add data sink with full framework support."""
        if isinstance(sink, (str, Path)):
            output_path = str(sink)
            path_dir = os.path.dirname(output_path)
            if path_dir == "":
                path_dir = os.getcwd()
            os.makedirs(path_dir, exist_ok=True)
            sink_config = {
                "type": "json" if output_path.endswith(".json") else "jsonl",
                "file_path": output_path,
            }
        elif isinstance(sink, dict):
            sink_config = sink
        elif DATA_UTILS_AVAILABLE and isinstance(sink, DataSink):
            sink_config = sink.to_config()
        else:
            raise ValueError(f"Unsupported sink type: {type(sink)}")

        self._config["data_config"]["sink"] = sink_config
        return self

    def llm(
        self,
        model: Union[str, dict[str, Any]],
        prompt: Union[str, list[dict[str, str]]],
        output: str = "messages",
        pre_process: Optional[Union[str, Callable, NodePreProcessor]] = None,
        post_process: Optional[
            Union[str, Callable, NodePostProcessor, NodePostProcessorWithState]
        ] = None,
        **kwargs,
    ) -> "Workflow":
        """Add LLM node with full feature support including custom processors."""
        node_name: str = self._generate_node_name("llm")

        if isinstance(model, str):
            model_config = ModelConfigBuilder.from_name(model, **kwargs)
        else:
            model_config = ModelConfigBuilder.validate_config(model)

        if isinstance(prompt, str):
            prompt_config = [{"user": prompt}]
        else:
            prompt_config = prompt

        node_config: dict[str, Any] = {
            "node_type": "llm",
            "model": model_config,
            "prompt": prompt_config,
        }

        if output != "messages":
            node_config["output_keys"] = output

        if kwargs.get("chat_history"):
            node_config["chat_history"] = True

        # Processors: dotted path, function, class or configured instance
        if pre_process:
            node_config["pre_process"] = utils.hook_reference(pre_process)

        if post_process:
            node_config["post_process"] = utils.hook_reference(post_process)

        if kwargs.get("structured_output"):
            node_config["structured_output"] = kwargs["structured_output"]

        self._add_node_with_edge(node_name, node_config)
        return self

    def multi_llm(
        self,
        models: dict[str, Any],
        prompt: Union[str, list[dict[str, str]]],
        **kwargs,
    ) -> "Workflow":
        """Add Multi-LLM node."""
        node_name = self._generate_node_name("multi_llm")

        models_config = {}
        for label, model in models.items():
            if isinstance(model, str):
                models_config[label] = ModelConfigBuilder.from_name(model)
            else:
                models_config[label] = ModelConfigBuilder.validate_config(model)

        if isinstance(prompt, str):
            prompt_config = [{"user": prompt}]
        else:
            prompt_config = prompt

        node_config = {
            "node_type": "multi_llm",
            "models": models_config,
            "prompt": prompt_config,
        }

        if kwargs.get("output_keys"):
            node_config["output_keys"] = kwargs["output_keys"]

        if kwargs.get("multi_llm_post_process"):
            node_config["multi_llm_post_process"] = utils.hook_reference(
                kwargs["multi_llm_post_process"]
            )

        self._add_node_with_edge(node_name, node_config)
        return self

    def agent(
        self,
        model: Union[str, dict[str, Any]],
        tools: list[Any],
        prompt: Union[str, list[dict[str, str]]],
        **kwargs,
    ) -> "Workflow":
        """Add agent node with full feature support."""
        node_name = self._generate_node_name("agent")

        if isinstance(model, str):
            model_config = ModelConfigBuilder.from_name(model, **kwargs)
        else:
            model_config = ModelConfigBuilder.validate_config(model)

        node_config = {
            "node_type": "agent",
            "model": model_config,
            "tools": tools,
            "prompt": [{"user": prompt}] if isinstance(prompt, str) else prompt,
        }

        if kwargs.get("inject_system_messages"):
            node_config["inject_system_messages"] = kwargs["inject_system_messages"]

        if kwargs.get("chat_history"):
            node_config["chat_history"] = True  # type: ignore[assignment]

        self._add_node_with_edge(node_name, node_config)
        return self

    def lambda_func(
        self, func: Union[str, Callable, type], output: str = "result", **kwargs
    ) -> "Workflow":
        """Add lambda function node supporting direct function/class references."""
        node_name = self._generate_node_name("lambda")

        node_config = {
            "node_type": "lambda",
            "lambda": utils.hook_reference(func),
            "output_keys": output,
        }

        self._add_node_with_edge(node_name, node_config)
        return self

    def weighted_sampler(self, attributes: dict[str, dict[str, Any]], **kwargs) -> "Workflow":
        """Add weighted sampler node."""
        node_name = self._generate_node_name("weighted_sampler")

        node_config = {"node_type": "weighted_sampler", "attributes": attributes}

        self._add_node_with_edge(node_name, node_config)
        return self

    def subgraph(
        self, subgraph_name: str, node_config_map: Optional[dict[str, Any]] = None
    ) -> "Workflow":
        """Add subgraph node."""
        node_name = self._generate_node_name("subgraph")

        node_config: dict[str, Any] = {"node_type": "subgraph", "subgraph": subgraph_name}

        if node_config_map:
            node_config["node_config_map"] = node_config_map

        self._add_node_with_edge(node_name, node_config)
        return self

    def add_node(self, name: str, node_config: dict[str, Any]) -> "Workflow":
        """Add node with explicit configuration."""
        self._config["graph_config"]["nodes"][name] = node_config
        return self

    def add_llm_node(self, name: str, model: Union[str, dict[str, Any]]) -> "LLMNodeBuilder":
        """Add LLM node and return builder for chaining."""
        if not NODE_BUILDERS_AVAILABLE:
            raise GraSPError("Node builders not available.")

        builder = LLMNodeBuilder(name, model)
        self._node_builders[name] = builder
        return builder

    def add_agent_node(self, name: str, model: Union[str, dict[str, Any]]) -> "AgentNodeBuilder":
        """Add agent node and return builder for chaining."""
        if not NODE_BUILDERS_AVAILABLE:
            raise GraSPError("Node builders not available.")

        builder = AgentNodeBuilder(name, model)
        self._node_builders[name] = builder
        return builder

    def add_multi_llm_node(self, name: str) -> "MultiLLMNodeBuilder":
        """Add multi-LLM node and return builder for chaining."""
        if not NODE_BUILDERS_AVAILABLE:
            raise GraSPError("Node builders not available.")

        builder = MultiLLMNodeBuilder(name)
        self._node_builders[name] = builder
        return builder

    def add_lambda_node(self, name: str, func: Union[str, Callable]) -> "LambdaNodeBuilder":
        """Add lambda node and return builder for chaining."""
        if not NODE_BUILDERS_AVAILABLE:
            raise GraSPError("Node builders not available.")

        builder = LambdaNodeBuilder(name, func)
        self._node_builders[name] = builder
        return builder

    def add_weighted_sampler_node(self, name: str) -> "WeightedSamplerNodeBuilder":
        """Add weighted sampler node and return builder for chaining."""
        if not NODE_BUILDERS_AVAILABLE:
            raise GraSPError("Node builders not available.")

        builder = WeightedSamplerNodeBuilder(name)
        self._node_builders[name] = builder
        return builder

    def add_subgraph_node(self, name: str, subgraph: str) -> "SubgraphNodeBuilder":
        """Add subgraph node and return builder for chaining."""
        if not NODE_BUILDERS_AVAILABLE:
            raise GraSPError("Node builders not available.")

        builder = SubgraphNodeBuilder(name, subgraph)
        self._node_builders[name] = builder
        return builder

    def add_edge(self, from_node: str, to_node: str) -> "Workflow":
        """Add simple edge between nodes."""
        edge_config = {"from": from_node, "to": to_node}
        self._config["graph_config"]["edges"].append(edge_config)
        return self

    def add_conditional_edge(
        self, from_node: str, condition: Union[str, Callable], path_map: dict[str, str]
    ) -> "Workflow":
        """Add conditional edge with path mapping."""
        edge_config = {
            "from": from_node,
            "condition": utils.hook_reference(condition),
            "path_map": path_map,
        }
        self._config["graph_config"]["edges"].append(edge_config)
        return self

    def sequence(self, *nodes: str) -> "Workflow":
        """Connect nodes in sequence. Adds START and END nodes if not already added."""
        if nodes[0] != "START":
            self.add_edge("START", nodes[0])
        if nodes[-1] != "END":
            self.add_edge(nodes[-1], "END")
        for i in range(len(nodes) - 1):
            self.add_edge(nodes[i], nodes[i + 1])
        return self

    def build(self) -> "Workflow":
        """Build workflow by applying all node builders and return self for execution."""
        # Apply all node builders to finalize configuration
        for name, builder in self._node_builders.items():
            node_config = builder.build()
            self._config["graph_config"]["nodes"][name] = node_config

        # Clear builders since they're now applied
        self._node_builders.clear()
        return self

    def resumable(self, enabled: bool = True) -> "Workflow":
        """Enable/disable resumable execution."""
        if "data_config" not in self._config:
            self._config["data_config"] = {}
        self._config["data_config"]["resumable"] = enabled
        return self

    def quality_tagging(
        self, enabled: bool = True, config: Optional[dict[str, Any]] = None
    ) -> "Workflow":
        """Enable quality tagging."""
        if "output_config" not in self._config:
            self._config["output_config"] = {}

        if enabled:
            try:
                from sygra.utils import utils

                post_generation_tasks = utils.load_yaml_file("config/sygra.yaml")[
                    "post_generation_tasks"
                ]
                quality_config = config or post_generation_tasks["data_quality"]
                self._config["output_config"]["data_quality"] = quality_config
            except Exception:
                self._config["output_config"]["data_quality"] = config or {
                    "enabled": True,
                    "metrics": ["coherence", "relevance", "factuality"],
                }
        return self

    def oasst_mapping(
        self, enabled: bool = True, config: Optional[dict[str, Any]] = None
    ) -> "Workflow":
        """Enable OASST mapping."""
        if "output_config" not in self._config:
            self._config["output_config"] = {}

        if enabled:
            try:
                from sygra.utils import utils

                post_generation_tasks = utils.load_yaml_file("config/sygra.yaml")[
                    "post_generation_tasks"
                ]
                oasst_config = config or post_generation_tasks["oasst_mapper"]
                self._config["output_config"]["oasst_mapper"] = oasst_config
            except Exception:
                # Fallback configuration
                self._config["output_config"]["oasst_mapper"] = config or {
                    "required": "yes",
                    "intermediate_writing": "no",
                }
        return self

    def id_column(self, column: str) -> "Workflow":
        """Set ID column for data."""
        if "data_config" not in self._config:
            self._config["data_config"] = {}
        self._config["data_config"]["id_column"] = column
        return self

    def transformations(self, transforms: list[dict[str, Any]]) -> "Workflow":
        """Add data transformations."""
        if "data_config" not in self._config:
            self._config["data_config"] = {}
        if "source" not in self._config["data_config"]:
            self._config["data_config"]["source"] = {}

        transformations_list: list[dict[str, Any]] = []

        for transform in transforms:
            if isinstance(transform, dict):
                transformations_list.append(
                    {**transform, "transform": utils.hook_reference(transform["transform"])}
                )
            else:
                # DataTransform class or instance, without params
                transformations_list.append({"transform": utils.hook_reference(transform)})

        self._config["data_config"]["source"]["transformations"] = transformations_list
        return self

    def graph_properties(self, properties: dict[str, Any]) -> "Workflow":
        """Set graph properties like chat conversation type."""
        if "graph_config" not in self._config:
            self._config["graph_config"] = {}
        if "graph_properties" not in self._config["graph_config"]:
            self._config["graph_config"]["graph_properties"] = {}

        self._config["graph_config"]["graph_properties"].update(properties)
        return self

    def chat_conversation(self, conv_type: str = "multiturn", window_size: int = 5) -> "Workflow":
        """Configure chat conversation settings."""
        return self.graph_properties(
            {"chat_conversation": conv_type, "chat_history_window_size": window_size}
        )

    def disable_default_transforms(self) -> "Workflow":
        """Disable default transformations."""
        if "data_config" not in self._config:
            self._config["data_config"] = {}
        if "source" not in self._config["data_config"]:
            self._config["data_config"]["source"] = {}

        self._config["data_config"]["source"]["transformations"] = []
        return self

    def enable_resumable(self, enabled: bool = True) -> "Workflow":
        """Enable resumable execution (backward compatibility)."""
        return self.resumable(enabled)

    def enable_quality_tagging(
        self, enabled: bool = True, config: Optional[dict[str, Any]] = None
    ) -> "Workflow":
        """Enable quality tagging (backward compatibility)."""
        return self.quality_tagging(enabled, config)

    def enable_oasst_mapping(
        self, enabled: bool = True, config: Optional[dict[str, Any]] = None
    ) -> "Workflow":
        """Enable OASST mapping (backward compatibility)."""
        return self.oasst_mapping(enabled, config)

    def set_output_generator(self, generator: Union[str, type, BaseOutputGenerator]) -> "Workflow":
        """Set output generator (backward compatibility)."""
        return self.output_generator(generator)

    def set_chat_conversation(
        self, conv_type: str = "multiturn", window_size: int = 5
    ) -> "Workflow":
        """Configure chat conversation settings (backward compatibility)."""
        return self.chat_conversation(conv_type, window_size)

    def override(self, path: str, value: Any) -> "Workflow":
        """
        Universal override method using dot notation paths.

        Examples:
            .override("graph_config.nodes.llm_1.model.parameters.temperature", 0.9)
            .override("graph_config.nodes.llm_1.prompt.0.user", "New prompt: {text}")
            .override("graph_config.nodes.llm_1.model.name", "gpt-4o")
            .override("data_config.source.repo_id", "new/dataset")
        """
        self._set_nested_value(self._config, path, value)
        return self

    def override_model(
        self, node_name: str, model_name: Optional[str] = None, **params
    ) -> "Workflow":
        """Convenient method for model overrides."""
        if model_name:
            self.override(f"graph_config.nodes.{node_name}.model.name", model_name)

        for param, value in params.items():
            self.override(f"graph_config.nodes.{node_name}.model.parameters.{param}", value)

        return self

    def output_generator(self, generator: Union[str, type, BaseOutputGenerator]) -> "Workflow":
        """Set output record generator cleanly."""
        if "output_config" not in self._config:
            self._config["output_config"] = {}

        self._config["output_config"]["generator"] = utils.hook_reference(generator)
        return self

    def preserve_fields(self, *field_names: str) -> "Workflow":
        """Preserve input fields in output."""
        if "output_config" not in self._config:
            self._config["output_config"] = {}
        if "output_map" not in self._config["output_config"]:
            self._config["output_config"]["output_map"] = {}

        for field in field_names:
            self._config["output_config"]["output_map"][field] = {"from": field}

        return self

    def output_field(
        self,
        name: str,
        from_key: Optional[str] = None,
        value: Optional[Any] = None,
        transform: Optional[str] = None,
    ) -> "Workflow":
        """Add custom output field."""
        if "output_config" not in self._config:
            self._config["output_config"] = {}
        if "output_map" not in self._config["output_config"]:
            self._config["output_config"]["output_map"] = {}

        field_config = {}
        if from_key:
            field_config["from"] = from_key
        elif value is not None:
            field_config["value"] = value

        if transform:
            field_config["transform"] = transform

        self._config["output_config"]["output_map"][name] = field_config
        return self

    def output_metadata(self, metadata: dict[str, Any]) -> "Workflow":
        """
        Add static metadata to all output records.

        Args:
            metadata: Dictionary of metadata to add

        Returns:
            Workflow: Self for method chaining

        Example:
            >>> workflow.output_metadata({
            ...     "workflow_version": "1.0",
            ...     "processing_date": "2024-01-01"
            ... })
        """
        for key, value in metadata.items():
            self.output_field(key, value=value)

        return self

    def override_prompt(
        self, node_name: str, role: str, content: str, index: int = 0
    ) -> "Workflow":
        """Convenient method for prompt overrides."""
        self.override(f"graph_config.nodes.{node_name}.prompt.{index}.{role}", content)
        return self

    def run(
        self,
        num_records: Optional[int] = None,
        start_index: int = 0,
        output_dir: Optional[str] = None,
        env_file: Optional[Union[str, Path]] = None,
        cost_fn: Optional[CostFn] = None,
        write_output: bool = True,
        **kwargs,
    ) -> RunResult:
        """Execute workflow with full framework feature support.

        Synchronous wrapper around :meth:`arun`. It starts its own event loop, so it
        can't be called from code that is already running in one (async web apps,
        job workers, notebooks): use ``await workflow.arun(...)`` there.

        Args:
            env_file: Optional ``.env`` file to load before the run (for example
                ``".env"``). Variables that are already set are not overridden.
                Without it, the run reads only the existing environment.
            cost_fn: Optional ``cost_fn(model_name, usage) -> float`` used to price
                each model's usage in the returned :class:`RunResult`. SyGra ships
                no prices.
            write_output: If ``False``, output records are kept only in the returned
                :class:`RunResult`; no output file is written. Sinks, data quality,
                ``graph_post_process`` and resumable runs need the output file, so
                they raise :class:`ConfigurationError` with ``write_output=False``.

        Returns:
            A :class:`RunResult`: the list of output records, plus failed records,
            usage per model, node and record, and cost.
        """
        return asyncio.run(
            self._arun(
                num_records,
                start_index,
                output_dir,
                install_signal_handlers=True,
                env_file=env_file,
                cost_fn=cost_fn,
                write_output=write_output,
                **kwargs,
            )
        )

    async def arun(
        self,
        num_records: Optional[int] = None,
        start_index: int = 0,
        output_dir: Optional[str] = None,
        env_file: Optional[Union[str, Path]] = None,
        cost_fn: Optional[CostFn] = None,
        write_output: bool = True,
        **kwargs,
    ) -> RunResult:
        """Execute the workflow on the running event loop.

        Takes the same arguments and returns the same result as :meth:`run`. Records
        are processed as tasks on the caller's loop, so LLM providers can use
        loop-bound clients. Blocking setup (dataset loading, graph build) and
        post-processing run in worker threads.

        Each run has its own state (task name, metadata collector, sampler cache), so
        several ``arun()`` calls can run concurrently in one process. Unlike
        :meth:`run`, ``arun()`` never installs signal handlers; the host owns them.

        Example:
            >>> records = await Workflow("demo").source([...]).llm(...).arun(num_records=10)
        """
        return await self._arun(
            num_records,
            start_index,
            output_dir,
            install_signal_handlers=False,
            env_file=env_file,
            cost_fn=cost_fn,
            write_output=write_output,
            **kwargs,
        )

    def _check_no_output_file_needed(self, kwargs: dict[str, Any]) -> None:
        """Raise if a configured feature reads the output file (``write_output=False``)."""
        config = self._config.to_dict()
        data_config = config.get("data_config") or {}
        output_config = config.get("output_config") or {}
        needs_file = {
            "a sink (data_config.sink)": bool(data_config.get("sink")),
            "data quality": bool(
                output_config.get("data_quality")
                or kwargs.get("quality")
                or kwargs.get("quality_only")
            ),
            "graph_post_process": bool(config.get("graph_post_process")),
            "resumable execution": bool(kwargs.get("resume", data_config.get("resumable"))),
        }
        blocking = [name for name, used in needs_file.items() if used]
        if blocking:
            raise ConfigurationError(
                "write_output=False can't be used with "
                + ", ".join(blocking)
                + ": these read the output file"
            )

    async def _arun(
        self,
        num_records: Optional[int],
        start_index: int,
        output_dir: Optional[str],
        *,
        install_signal_handlers: bool,
        env_file: Optional[Union[str, Path]] = None,
        cost_fn: Optional[CostFn] = None,
        write_output: bool = True,
        **kwargs,
    ) -> RunResult:
        if not CORE_AVAILABLE:
            raise GraSPError("Core framework not available")

        if env_file is not None:
            from sygra.utils.dotenv import load_dotenv

            if not load_dotenv(dotenv_path=str(env_file), override=False):
                raise ConfigurationError(f"env_file not found: {env_file}")

        # Apply node builders before execution
        self.build()
        if not write_output:
            self._check_no_output_file_needed(kwargs)

        has_nodes = len(self._config["graph_config"]["nodes"]) > 0

        from sygra.core.models.external.provider import use_llm_providers
        from sygra.core.models.server_down import server_down_action
        from sygra.core.run_context import RunContext, run_context
        from sygra.metadata.metadata_collector import MetadataCollector, get_metadata_collector

        collector = MetadataCollector.create_isolated()
        if not get_metadata_collector().is_enabled():
            collector.set_enabled(False)
        context = RunContext(
            task_name=self.name,
            metadata_collector=collector,
            install_signal_handlers=install_signal_handlers,
            graph_properties=dict(
                self._config.to_dict().get("graph_config", {}).get("graph_properties") or {}
            ),
            write_output=write_output,
        )

        try:
            with use_llm_providers(self._llm_providers), server_down_action("raise"):
                with run_context(context):
                    if self._is_existing_task:
                        output = await self._execute_existing_task(
                            num_records, start_index, output_dir, **kwargs
                        )
                    elif has_nodes:
                        output = await self._execute_programmatic_workflow(
                            num_records, start_index, output_dir, **kwargs
                        )
                    else:
                        raise ConfigurationError("Incomplete workflow. Add processing nodes.")
        finally:
            # Keep get_metadata_collector() after a run returning that run's metadata.
            get_metadata_collector().load_from(collector)

        if not write_output:
            output_file = None
            records = context.output_records
        else:
            output_file = context.output_file
            if output_file and not os.path.exists(output_file):
                output_file = None  # temporary output directory, already removed
            records = output if isinstance(output, list) else _read_records(output_file)
        return RunResult(
            records,
            failed_records=context.failed_records,
            usage=context.usage,
            output_file=output_file,
            cost_fn=cost_fn,
        )

    def llm_provider(self, provider: LLMProvider, name: str = "default") -> "Workflow":
        """Serve this workflow's ``model_type: external`` models with ``provider``.

        The provider is registered only for the duration of :meth:`run` / :meth:`arun`
        and only in the calling context, so different workflows (or threads) can use
        different providers. Models select a provider by name via the ``provider`` key
        of their model config (default ``"default"``).

        Args:
            provider: Object with an async ``generate(LLMRequest) -> ModelResponse`` method.
            name: Name that model configs refer to.

        Example:
            >>> workflow = Workflow("demo") \\
            ...     .source([{"text": "hi"}]) \\
            ...     .llm({"name": "gen", "model_type": "external"}, "Echo: {text}") \\
            ...     .llm_provider(FakeProvider("hello"))
        """
        from sygra.core.models.external.provider import _validate

        self._llm_providers[name] = _validate(provider)
        return self

    def save_config(self, path: Union[str, Path]) -> None:
        """Save workflow configuration as YAML file."""
        # Apply all node builders first
        self.build()

        with open(path, "w") as f:
            yaml.dump(self._config.to_dict(), f, default_flow_style=False)

    async def _execute_existing_task(
        self,
        num_records: Optional[int],
        start_index: int,
        output_dir: Optional[str],
        **kwargs,
    ) -> Any:
        """Execute existing YAML-based task with full feature support."""
        task_name: str = self.name
        utils.current_task = task_name

        logger.info(f"Executing existing YAML task with full features: {task_name}")

        modified_config = self._config.to_dict()

        args = Namespace(
            task=task_name,
            num_records=num_records,
            start_index=start_index,
            output_dir=output_dir,
            batch_size=kwargs.get("batch_size", 50),
            checkpoint_interval=kwargs.get("checkpoint_interval", 100),
            debug=kwargs.get("debug", False),
            resume=kwargs.get("resume", False),
            output_with_ts=kwargs.get("output_with_ts", False),
            run_name=kwargs.get("run_name"),
            oasst=kwargs.get("oasst", False),
            quality=kwargs.get("quality", False),
        )

        def create_executor() -> BaseTaskExecutor:
            executor: BaseTaskExecutor
            if kwargs.get("quality_only", False):
                executor = JudgeQualityTaskExecutor(args, kwargs.get("quality_config"))
            else:
                executor = DefaultTaskExecutor(args, modified_config)
            return executor

        try:
            executor = await asyncio.to_thread(create_executor)
            result = await executor.aexecute()
            logger.info(f"Successfully executed task: {task_name}")
            return result
        except ModelServerDownError:
            raise
        except Exception as e:
            if "model_type" in str(e).lower() or "model" in str(e).lower():
                logger.error("Model configuration error")
            elif "current task name is not initialized" in str(e).lower():
                logger.error(f"Task context initialization failed for '{task_name}'")
            raise ExecutionError(f"Failed to execute task '{task_name}': {e}")

    async def _execute_programmatic_workflow(
        self,
        num_records: Optional[int],
        start_index: int,
        output_dir: Optional[str],
        **kwargs,
    ) -> Any:
        """Execute programmatic workflow with full framework features."""
        try:
            task_name = self.name
            utils.current_task = self.name

            # Determine output directory
            if output_dir is None:
                output_dir = tempfile.mkdtemp(prefix=f"sygra_output_{task_name}_")
                self._temp_files.append(output_dir)
            else:
                os.makedirs(output_dir, exist_ok=True)

            # Keep transformations the workflow declares (config or .transformations()).
            source = self._config.to_dict().get("data_config", {}).get("source")
            declares_transforms = isinstance(source, dict) and bool(source.get("transformations"))
            if (
                not self._from_config
                and not declares_transforms
                and not kwargs.get("enable_default_transforms", False)
            ):
                self.disable_default_transforms()

            config_dict = self._config.to_dict()

            utils.current_task = self.name

            args = Namespace(
                task=self.name,
                num_records=num_records,
                start_index=start_index,
                output_dir=output_dir or task_name,
                batch_size=kwargs.get("batch_size", 50),
                checkpoint_interval=kwargs.get("checkpoint_interval", 100),
                debug=kwargs.get("debug", False),
                resume=kwargs.get(
                    "resume",
                    self._config.get("data_config", {}).get("resumable", False),
                ),
                output_with_ts=kwargs.get("output_with_ts", False),
                run_name=kwargs.get("run_name"),
                oasst=kwargs.get(
                    "oasst",
                    bool(self._config.get("output_config", {}).get("oasst_mapper")),
                ),
                quality=kwargs.get(
                    "quality",
                    bool(self._config.get("output_config", {}).get("data_quality")),
                ),
            )

            def create_executor() -> BaseTaskExecutor:
                if kwargs.get("quality_only", False):
                    return JudgeQualityTaskExecutor(args, kwargs.get("quality_config"))
                return DefaultTaskExecutor(args, config_dict)

            executor = await asyncio.to_thread(create_executor)
            result = await executor.aexecute()

            output_file = None
            if self._config.get("data_config", {}).get("sink", {}).get("file_path"):
                output_file = self._config["data_config"]["sink"]["file_path"]
            elif args.output_dir:
                import glob

                pattern = os.path.join(args.output_dir, "*output*.json*")
                output_files = glob.glob(pattern)
                if output_files:
                    output_file = output_files[0]

            if output_file and os.path.exists(output_file):
                try:
                    with open(output_file, "r") as f:
                        if output_file.endswith(".jsonl"):
                            return [json.loads(line) for line in f if line.strip()]
                        else:
                            return json.load(f)
                except Exception as e:
                    logger.warning(f"Could not read output file {output_file}: {e}")

            return result

        except (ModelServerDownError, ConfigurationError):
            raise
        except Exception as e:
            raise ExecutionError(f"Programmatic workflow execution failed: {e}")
        finally:
            self._cleanup()

    def _set_nested_value(self, config: dict[str, Any], path: str, value: Any) -> None:
        """Set a nested value using dot notation path."""
        keys = path.split(".")
        current = config

        # Navigate through all keys except the last one
        for i, key in enumerate(keys[:-1]):
            if key.isdigit():
                key_index = int(key)
                if not isinstance(current, list):
                    # Build the current path for better error reporting
                    current_path = ".".join(keys[: i + 1])
                    raise ValueError(f"Expected list at path {current_path}, got {type(current)}")
                # Extend list if needed
                while key_index >= len(current):
                    current.append({})
                current = current[key_index]
            else:
                if key not in current:
                    current[key] = {}
                elif not isinstance(current[key], (dict, list)):
                    # If the key exists but is not a container, replace it
                    current[key] = {}
                current = current[key]

        # Set the final value
        final_key = keys[-1]
        if final_key.isdigit():
            final_key_index = int(final_key)
            if not isinstance(current, list):
                raise ValueError(f"Expected list for index {final_key} at path {path}")
            # Extend list if needed
            while final_key_index >= len(current):
                current.append(None)
            current[final_key_index] = value
        else:
            current[final_key] = value

    def _detect_file_format(self, file_path: str) -> str:
        """Detect file format from extension."""
        ext = Path(file_path).suffix.lower()
        return ext[1:] if ext in [".json", ".jsonl", ".csv", ".parquet"] else "json"

    def _generate_node_name(self, node_type: str) -> str:
        """Generate unique node name."""
        self._node_counter += 1
        return f"{node_type}_{self._node_counter}"

    def _add_node_with_edge(self, node_name: str, node_config: dict[str, Any]) -> None:
        """Add node and create edges."""
        self._config["graph_config"]["nodes"][node_name] = node_config

        # Create edges
        if self._last_node is None:
            edge_config = {"from": "START", "to": node_name}
        else:
            edge_config = {"from": self._last_node, "to": node_name}

        self._config["graph_config"]["edges"].append(edge_config)
        self._last_node = node_name

        # Add edge to END
        end_edge = {"from": node_name, "to": "END"}
        self._config["graph_config"]["edges"] = [
            e for e in self._config["graph_config"]["edges"] if e.get("to") != "END"
        ]
        self._config["graph_config"]["edges"].append(end_edge)

    def _cleanup(self):
        """Clean up temporary files."""
        if not self._temp_files:
            return

        logger.info(f"Cleaning up {len(self._temp_files)} temporary files")
        for temp_file in self._temp_files:
            try:
                if os.path.isfile(temp_file):
                    os.remove(temp_file)
                elif os.path.isdir(temp_file):
                    shutil.rmtree(temp_file)
            except Exception as e:
                logger.warning(f"Could not clean up {temp_file}: {e}")
        self._temp_files.clear()

    def __del__(self):
        """Cleanup on destruction."""
        self._cleanup()


def create_graph(name: str) -> Workflow:
    """Factory function to create a new workflow builder (backward compatibility)."""
    return Workflow(name)


__all__ = ["Workflow", "create_graph"]
