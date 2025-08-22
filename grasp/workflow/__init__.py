import os
import json
import yaml
import uuid
import tempfile
import shutil
from typing import Union, Dict, Any, Optional, List, Callable
from pathlib import Path


try:
    from grasp.core.base_task_executor import DefaultTaskExecutor
    from grasp.core.judge_task_executor import JudgeQualityTaskExecutor
    from grasp.core.dataset.dataset_config import (
        DataSourceConfig,
        OutputConfig,
        DataSourceType,
        OutputType,
    )
    from argparse import Namespace
    from grasp.utils import utils as utils, constants
    from grasp.logger.logger_config import logger

    CORE_AVAILABLE = True
except ImportError:
    CORE_AVAILABLE = False
    import logging

    logger = logging.getLogger(__name__)

from grasp.exceptions import GraSPError, ConfigurationError, ExecutionError
from grasp.models import ModelConfigBuilder


class Workflow:
    """
    High-level workflow builder with full GraSP feature support.

    Examples:
        >>> import grasp
        >>>
        >>> # Simple workflow with resumable execution
        >>> workflow = grasp.Workflow()
        >>> workflow.source("data.json") \\
        >>>         .llm("gpt-4", "Rewrite: {text}") \\
        >>>         .sink("output.json") \\
        >>>         .resumable(True) \\
        >>>         .run()
        >>>
        >>> # Advanced workflow with multimodal, quality, and OASST
        >>> workflow = grasp.Workflow() \\
        >>>         .source({"type": "hf", "repo_id": "dataset/name"}) \\
        >>>         .llm(model_config, "Process: {text} {image}") \\
        >>>         .quality_tagging(True) \\
        >>>         .oasst_mapping(True) \\
        >>>         .sink("output.json") \\
        >>>         .run(num_records=1000)
    """

    def __init__(self, name: Optional[str] = None):
        self.name = name or f"workflow_{uuid.uuid4().hex[:8]}"
        self._config = {
            "graph_config": {"nodes": {}, "edges": []},
            "data_config": {},
            "output_config": {},
        }
        self._node_counter = 0
        self._last_node = None
        self._temp_files = []
        self._overrides = {}

        self._supports_subgraphs = True
        self._supports_multimodal = True
        self._supports_resumable = True
        self._supports_quality = True
        self._supports_oasst = True

    def source(
        self, source: Union[str, Path, Dict[str, Any], List[Dict[str, Any]]]
    ) -> "Workflow":
        """Add data source with full framework support."""
        if isinstance(source, (str, Path)):
            source_config = {
                "type": "disk",
                "file_path": str(source),
                "file_format": self._detect_file_format(str(source)),
            }
        elif isinstance(source, list):
            temp_file = self._create_temp_file(source)
            source_config = {
                "type": "disk",
                "file_path": temp_file,
                "file_format": "json",
            }
        elif isinstance(source, dict):
            if "data" in source:
                temp_file = self._create_temp_file(source["data"])
                source_config = {
                    "type": "disk",
                    "file_path": temp_file,
                    "file_format": "json",
                }
            else:
                source_config = source
        else:
            raise ValueError(f"Unsupported source type: {type(source)}")

        self._config["data_config"]["source"] = source_config
        return self

    def sink(self, sink: Union[str, Path, Dict[str, Any]]) -> "Workflow":
        """Add data sink with full framework support."""
        if isinstance(sink, (str, Path)):
            output_path = str(sink)
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            sink_config = {
                "type": "json" if output_path.endswith(".json") else "jsonl",
                "file_path": output_path,
            }
        elif isinstance(sink, dict):
            sink_config = sink
        else:
            raise ValueError(f"Unsupported sink type: {type(sink)}")

        self._config["data_config"]["sink"] = sink_config
        return self

    def llm(
            self,
            model: Union[str, Dict[str, Any]],
            prompt: Union[str, List[Dict[str, str]]],
            output: str = "messages",
            pre_process: Union[str, Callable] = None,
            post_process: Union[str, Callable] = None,
            **kwargs,
    ) -> "Workflow":
        """Add LLM node with full feature support."""
        node_name = self._generate_node_name("llm")

        if isinstance(model, str):
            model_config = ModelConfigBuilder.from_name(model, **kwargs)
        else:
            model_config = ModelConfigBuilder.validate_config(model)

        if isinstance(prompt, str):
            prompt_config = [{"user": prompt}]
        else:
            prompt_config = prompt

        node_config = {
            "node_type": "llm",
            "model": model_config,
            "prompt": prompt_config,
        }

        if output != "messages":
            node_config["output_keys"] = output

        if kwargs.get("chat_history"):
            node_config["chat_history"] = True

        if pre_process:
            if callable(pre_process):
                node_config["pre_process"] = self._callable_to_string_path(pre_process)
            else:
                node_config["pre_process"] = pre_process

        if post_process:
            if callable(post_process):
                node_config["post_process"] = self._callable_to_string_path(post_process)
            else:
                node_config["post_process"] = post_process

        if kwargs.get("structured_output"):
            node_config["structured_output"] = kwargs["structured_output"]

        self._add_node_with_edge(node_name, node_config)
        return self


    def multi_llm(
        self,
        models: Dict[str, Union[str, Dict[str, Any]]],
        prompt: Union[str, List[Dict[str, str]]],
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
            node_config["multi_llm_post_process"] = kwargs["multi_llm_post_process"]

        self._add_node_with_edge(node_name, node_config)
        return self

    def agent(
        self, model: Union[str, Dict[str, Any]], tools: List[Any], prompt: str, **kwargs
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
            node_config["chat_history"] = True

        self._add_node_with_edge(node_name, node_config)
        return self

    @staticmethod
    def _callable_to_string_path(func: Union[str, Callable]) -> str:
        """Convert callable to string path for YAML serialization."""
        if callable(func):
            if hasattr(func, '__module__') and hasattr(func, '__name__'):
                return f"{func.__module__}.{func.__name__}"
            elif hasattr(func, '__class__'):
                return f"{func.__class__.__module__}.{func.__class__.__name__}"
            else:
                class_name = func.__class__.__name__
                return f"__main__.{class_name}"
        return func

    def lambda_func(
        self, func: Union[str, Callable], output: str = "result", **kwargs
    ) -> "Workflow":
        """Add lambda function node."""
        node_name = self._generate_node_name("lambda")

        if callable(func):
            func_path = self._callable_to_string_path(func)
        else:
            func_path = func

        node_config = {
            "node_type": "lambda",
            "lambda": func_path,
            "output_keys": output,
        }

        self._add_node_with_edge(node_name, node_config)
        return self

    def weighted_sampler(
        self, attributes: Dict[str, Dict[str, Any]], **kwargs
    ) -> "Workflow":
        """Add weighted sampler node."""
        node_name = self._generate_node_name("weighted_sampler")

        node_config = {"node_type": "weighted_sampler", "attributes": attributes}

        self._add_node_with_edge(node_name, node_config)
        return self

    def subgraph(
        self, subgraph_name: str, node_config_map: Optional[Dict[str, Any]] = None
    ) -> "Workflow":
        """Add subgraph node."""
        node_name = self._generate_node_name("subgraph")

        node_config = {"node_type": "subgraph", "subgraph": subgraph_name}

        if node_config_map:
            node_config["node_config_map"] = node_config_map

        self._add_node_with_edge(node_name, node_config)
        return self

    def resumable(self, enabled: bool = True) -> "Workflow":
        """Enable/disable resumable execution."""
        if "data_config" not in self._config:
            self._config["data_config"] = {}
        self._config["data_config"]["resumable"] = enabled
        return self

    def quality_tagging(
        self, enabled: bool = True, config: Optional[Dict[str, Any]] = None
    ) -> "Workflow":
        """Enable quality tagging."""
        if "output_config" not in self._config:
            self._config["output_config"] = {}

        if enabled:
            try:
                from grasp.utils import utils

                post_generation_tasks = utils.load_yaml_file("config/grasp.yaml")[
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
        self, enabled: bool = True, config: Optional[Dict[str, Any]] = None
    ) -> "Workflow":
        """Enable OASST mapping."""
        if "output_config" not in self._config:
            self._config["output_config"] = {}

        if enabled:
            try:
                from grasp.utils import utils

                post_generation_tasks = utils.load_yaml_file("config/grasp.yaml")[
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

    def output_generator(self, generator: Union[str, Dict[str, Any]]) -> "Workflow":
        """Set output generator."""
        if "output_config" not in self._config:
            self._config["output_config"] = {}

        if isinstance(generator, str):
            self._config["output_config"]["generator"] = generator
        else:
            self._config["output_config"].update(generator)
        return self

    def id_column(self, column: str) -> "Workflow":
        """Set ID column for data."""
        if "data_config" not in self._config:
            self._config["data_config"] = {}
        self._config["data_config"]["id_column"] = column
        return self

    def _callable_to_string_path(self, func: Callable) -> str:
        """Convert a callable to its string path."""
        if hasattr(func, "__module__") and hasattr(func, "__name__"):
            return f"{func.__module__}.{func.__name__}"

        elif hasattr(func, "__class__"):
            return f"{func.__class__.__module__}.{func.__class__.__name__}"

        elif hasattr(func, "__module__") and hasattr(func, "__qualname__"):
            return f"{func.__module__}.{func.__qualname__}"

        else:
            raise ValueError(f"Cannot determine string path for callable: {func}")

    def transformations(self, transforms: List[Dict[str, Any]]) -> "Workflow":
        """Add data transformations."""
        if "data_config" not in self._config:
            self._config["data_config"] = {}
        if "source" not in self._config["data_config"]:
            self._config["data_config"]["source"] = {}

        transformations = []

        for transform in transforms:
            if callable(transform):
                transformations.append(self._callable_to_string_path(transform))
            else:
                transformations.append(transform)

        self._config["data_config"]["source"]["transformations"] = transformations
        return self

    def graph_properties(self, properties: Dict[str, Any]) -> "Workflow":
        """Set graph properties like chat conversation type."""
        if "graph_config" not in self._config:
            self._config["graph_config"] = {}
        if "graph_state" not in self._config["graph_config"]:
            self._config["graph_config"]["graph_state"] = {}

        self._config["graph_config"]["graph_state"].update(properties)
        return self

    def chat_conversation(
        self, conv_type: str = "multiturn", window_size: int = 5
    ) -> "Workflow":
        """Configure chat conversation settings."""
        return self.graph_properties(
            {"chat_conversation": conv_type, "chat_history_window_size": window_size}
        )

    def run(
        self,
        num_records: Optional[int] = None,
        start_index: int = 0,
        output_dir: Optional[str] = None,
        **kwargs,
    ) -> Any:
        """Execute workflow with full framework feature support."""
        if not CORE_AVAILABLE:
            raise GraSPError("Core framework not available")

        has_source = "source" in self._config.get("data_config", {})
        has_nodes = len(self._config["graph_config"]["nodes"]) > 0

        if has_source and has_nodes:
            return self._execute_programmatic_workflow(
                num_records, start_index, output_dir, **kwargs
            )
        elif not has_source and not has_nodes:
            return self._execute_existing_task(
                num_records, start_index, output_dir, **kwargs
            )
        else:
            raise ConfigurationError(
                "Incomplete workflow. Add both source and processing nodes."
            )

    def override(self, path: str, value: Any) -> "Workflow":
        """
        Universal override method using dot notation paths.

        Examples:
            .override("nodes.llm_1.model.parameters.temperature", 0.9)
            .override("nodes.llm_1.prompt.0.user", "New prompt: {text}")
            .override("nodes.llm_1.model.name", "gpt-4o")
            .override("data_config.source.repo_id", "new/dataset")
            .override("nodes.critique_answer.model.parameters", {"temperature": 0.1, "max_tokens": 2000})
        """
        if not hasattr(self, '_overrides'):
            self._overrides = {}

        self._overrides[path] = value
        return self

    def override_model(self, node_name: str, model_name: str = None, **params) -> "Workflow":
        """Convenient method for model overrides."""
        if model_name:
            self.override(f"graph_config.nodes.{node_name}.model.name", model_name)

        for param, value in params.items():
            self.override(f"graph_config.nodes.{node_name}.model.parameters.{param}", value)

        return self

    def override_prompt(self, node_name: str, role: str, content: str, index: int = 0) -> "Workflow":
        """Convenient method for prompt overrides."""
        self.override(f"graph_config.nodes.{node_name}.prompt.{index}.{role}", content)
        return self

    def _apply_overrides(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Apply all overrides to the loaded configuration."""
        if not hasattr(self, '_overrides') or not self._overrides:
            return config

        import copy
        modified_config = copy.deepcopy(config)

        for path, value in self._overrides.items():
            self._set_nested_value(modified_config, path, value)

        logger.info(f"Applied {len(self._overrides)} configuration overrides")
        return modified_config

    def _set_nested_value(self, config: Dict[str, Any], path: str, value: Any) -> None:
        """Set a nested value using dot notation path."""
        keys = path.split('.')
        current = config

        # Navigate through all keys except the last one
        for i, key in enumerate(keys[:-1]):
            if key.isdigit():
                key = int(key)
                if not isinstance(current, list):
                    # Build the current path for better error reporting
                    current_path = '.'.join(keys[:i+1])
                    raise ValueError(f"Expected list at path {current_path}, got {type(current)}")
                # Extend list if needed
                while key >= len(current):
                    current.append({})
                current = current[key]
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
            final_key = int(final_key)
            if not isinstance(current, list):
                raise ValueError(f"Expected list for index {final_key} at path {path}")
            # Extend list if needed
            while final_key >= len(current):
                current.append(None)
            current[final_key] = value
        else:
            current[final_key] = value

    def _execute_existing_task(
        self,
        num_records: Optional[int],
        start_index: int,
        output_dir: Optional[str],
        **kwargs,
    ) -> Any:
        """Execute existing YAML-based task with full feature support."""
        task_name = self.name
        current_task = utils.get_dot_walk_path(task_name)
        utils.current_task = current_task

        task_dir = os.path.join(constants.ROOT_DIR, f"tasks/{task_name}")
        config_file = f"{task_dir}/graph_config.yaml"

        if not os.path.exists(config_file):
            available_tasks = self._list_available_tasks()
            raise ConfigurationError(
                f"Task '{task_name}' not found.\n"
                f"Expected config file: {config_file}\n"
                f"{available_tasks}\n"
                f"Or create a programmatic workflow: workflow.source(...).llm(...).run()"
            )

        logger.info(f"Executing existing YAML task with full features: {task_name}")

        import yaml
        with open(config_file, 'r') as f:
            original_config = yaml.safe_load(f)

        modified_config = self._apply_overrides(original_config)

        args = Namespace(
            task=current_task,
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

        try:
            if kwargs.get("quality_only", False):
                executor = JudgeQualityTaskExecutor(args, kwargs.get("quality_config"))
            else:
                executor = DefaultTaskExecutor(args)

            executor.config = modified_config

            result = executor.execute()
            logger.info(f"Successfully executed task with all features: {task_name}")
            return result
        except Exception as e:
            if "model_type" in str(e).lower() or "model" in str(e).lower():
                logger.error(f"Model configuration error in {config_file}")
            elif "current task name is not initialized" in str(e).lower():
                logger.error(f"Task context initialization failed for '{task_name}'")
            raise ExecutionError(f"Failed to execute task '{task_name}': {e}")

    def disable_default_transforms(self) -> "Workflow":
        """Disable default transformations."""
        if "data_config" not in self._config:
            self._config["data_config"] = {}
        if "source" not in self._config["data_config"]:
            self._config["data_config"]["source"] = {}

        self._config["data_config"]["source"]["transformations"] = []
        return self

    def _execute_programmatic_workflow(
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
            task_dir = os.path.join(constants.ROOT_DIR, f"tasks/{task_name}")
            os.makedirs(task_dir, exist_ok=True)
            self._temp_files.append(task_dir)

            if not kwargs.get("enable_default_transforms", False):
                self.disable_default_transforms()

            config_file = f"{task_dir}/graph_config.yaml"
            with open(config_file, "w") as f:
                yaml.dump(self._config, f, default_flow_style=False)

            utils.current_task = self.name

            args = Namespace(
                task=self.name,
                num_records=num_records,
                start_index=start_index,
                output_dir=output_dir or task_dir,
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

            if kwargs.get("quality_only", False):
                executor = JudgeQualityTaskExecutor(args, kwargs.get("quality_config"))
            else:
                executor = DefaultTaskExecutor(args)

            result = executor.execute()


            output_file = None
            if self._config.get("data_config", {}).get("sink", {}).get("file_path"):
                output_file = self._config["data_config"]["sink"]["file_path"]
            elif args.output_dir:
                import glob
                pattern = os.path.join(args.output_dir, f"*output*.json*")
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

        except Exception as e:
            raise ExecutionError(f"Programmatic workflow execution failed: {e}")
        finally:
            self._cleanup()

    def _detect_file_format(self, file_path: str) -> str:
        """Detect file format from extension."""
        ext = Path(file_path).suffix.lower()
        return ext[1:] if ext in [".json", ".jsonl", ".csv", ".parquet"] else "json"

    def _create_temp_file(self, data: List[Dict[str, Any]]) -> str:
        """Create temporary file for data."""
        temp_file = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
        with temp_file as f:
            json.dump(data, f, indent=2)
        self._temp_files.append(temp_file.name)
        return temp_file.name

    def _generate_node_name(self, node_type: str) -> str:
        """Generate unique node name."""
        self._node_counter += 1
        return f"{node_type}_{self._node_counter}"

    def _add_node_with_edge(self, node_name: str, node_config: Dict[str, Any]) -> None:
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

    def _list_available_tasks(self) -> str:
        """List available tasks in the tasks directory."""
        tasks_dir = os.path.join(constants.ROOT_DIR, "tasks") or "tasks"
        if not os.path.exists(tasks_dir):
            return "No tasks directory found"

        available_tasks = []
        for item in os.listdir(tasks_dir):
            task_path = os.path.join(tasks_dir, item)
            if os.path.isdir(task_path) and not item.startswith("_"):
                config_file = os.path.join(task_path, "graph_config.yaml")
                if os.path.exists(config_file):
                    available_tasks.append(item)

        return (
            f"Available: {', '.join(available_tasks[:10])}"
            if available_tasks
            else "No valid tasks found"
        )

    def _cleanup(self):
        """Clean up temporary files."""
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


class Graph:
    """Advanced graph builder with full GraSP feature support."""

    def __init__(self, name: Optional[str] = None):
        self.name = name or f"graph_{uuid.uuid4().hex[:8]}"
        self._workflow = Workflow(self.name)
        self._node_builders = {}

    def add_node(self, name: str, node_config: Dict[str, Any]) -> "Graph":
        """Add node with explicit configuration."""
        self._workflow._config["graph_config"]["nodes"][name] = node_config
        return self

    def add_llm_node(
        self, name: str, model: Union[str, Dict[str, Any]]
    ) -> "LLMNodeBuilder":
        """Add LLM node and return builder for chaining."""
        from ..nodes import LLMNodeBuilder

        builder = LLMNodeBuilder(name, model)
        self._node_builders[name] = builder
        return builder

    def add_agent_node(
        self, name: str, model: Union[str, Dict[str, Any]]
    ) -> "AgentNodeBuilder":
        """Add agent node and return builder for chaining."""
        from ..nodes import AgentNodeBuilder

        builder = AgentNodeBuilder(name, model)
        self._node_builders[name] = builder
        return builder

    def add_multi_llm_node(self, name: str) -> "MultiLLMNodeBuilder":
        """Add multi-LLM node and return builder for chaining."""
        from ..nodes import MultiLLMNodeBuilder

        builder = MultiLLMNodeBuilder(name)
        self._node_builders[name] = builder
        return builder

    def add_lambda_node(
        self, name: str, func: Union[str, Callable]
    ) -> "LambdaNodeBuilder":
        """Add lambda node and return builder for chaining."""
        from ..nodes import LambdaNodeBuilder

        builder = LambdaNodeBuilder(name, func)
        self._node_builders[name] = builder
        return builder

    def add_weighted_sampler_node(self, name: str) -> "WeightedSamplerNodeBuilder":
        """Add weighted sampler node and return builder for chaining."""
        from ..nodes import WeightedSamplerNodeBuilder

        builder = WeightedSamplerNodeBuilder(name)
        self._node_builders[name] = builder
        return builder

    def add_subgraph_node(self, name: str, subgraph: str) -> "SubgraphNodeBuilder":
        """Add subgraph node and return builder for chaining."""
        from ..nodes import SubgraphNodeBuilder

        builder = SubgraphNodeBuilder(name, subgraph)
        self._node_builders[name] = builder
        return builder

    def add_edge(self, from_node: str, to_node: str) -> "Graph":
        """Add simple edge."""
        edge_config = {"from": from_node, "to": to_node}
        self._workflow._config["graph_config"]["edges"].append(edge_config)
        return self

    def add_conditional_edge(
        self, from_node: str, condition: Union[str, Callable], path_map: Dict[str, str]
    ) -> "Graph":
        """Add conditional edge."""
        if callable(condition):
            condition_path = f"{condition.__module__}.{condition.__name__}"
        else:
            condition_path = condition

        edge_config = {
            "from": from_node,
            "condition": condition_path,
            "path_map": path_map,
        }
        self._workflow._config["graph_config"]["edges"].append(edge_config)
        return self

    def sequence(self, *nodes: str) -> "Graph":
        """Connect nodes in sequence."""
        for i in range(len(nodes) - 1):
            self.add_edge(nodes[i], nodes[i + 1])
        return self

    def set_source(self, source) -> "Graph":
        """Set data source using DataSource object or config."""
        if hasattr(source, "to_config"):
            source_config = source.to_config()
        else:
            source_config = source
        self._workflow._config["data_config"]["source"] = source_config
        return self

    def set_sink(self, sink) -> "Graph":
        """Set data sink using DataSink object or config."""
        if hasattr(sink, "to_config"):
            sink_config = sink.to_config()
        else:
            sink_config = sink
        self._workflow._config["data_config"]["sink"] = sink_config
        return self

    def enable_resumable(self, enabled: bool = True) -> "Graph":
        """Enable resumable execution."""
        self._workflow.resumable(enabled)
        return self

    def enable_quality_tagging(
        self, enabled: bool = True, config: Optional[Dict[str, Any]] = None
    ) -> "Graph":
        """Enable quality tagging."""
        self._workflow.quality_tagging(enabled, config)
        return self

    def enable_oasst_mapping(
        self, enabled: bool = True, config: Optional[Dict[str, Any]] = None
    ) -> "Graph":
        """Enable OASST mapping."""
        self._workflow.oasst_mapping(enabled, config)
        return self

    def set_output_generator(self, generator: Union[str, Dict[str, Any]]) -> "Graph":
        """Set output generator."""
        self._workflow.output_generator(generator)
        return self

    def set_chat_conversation(
        self, conv_type: str = "multiturn", window_size: int = 5
    ) -> "Graph":
        """Configure chat conversation settings."""
        self._workflow.chat_conversation(conv_type, window_size)
        return self

    def build(self) -> "ExecutableGraph":
        """Build executable graph from current configuration."""
        # Apply all node builders
        for name, builder in self._node_builders.items():
            node_config = builder.build()
            self._workflow._config["graph_config"]["nodes"][name] = node_config

        return ExecutableGraph(self._workflow)

    def run(self, **kwargs) -> Any:
        """Build and execute graph immediately."""
        return self.build().run(**kwargs)

    def save_config(self, path: Union[str, Path]) -> None:
        """Save as YAML config."""
        # Build first to include all node configurations
        for name, builder in self._node_builders.items():
            node_config = builder.build()
            self._workflow._config["graph_config"]["nodes"][name] = node_config

        with open(path, "w") as f:
            yaml.dump(self._workflow._config, f, default_flow_style=False)


class ExecutableGraph:
    """Executable graph wrapper with full feature support."""

    def __init__(self, workflow: Workflow):
        self._workflow = workflow

    def run(self, **kwargs) -> Any:
        """Execute the graph with full framework features."""
        return self._workflow.run(**kwargs)


def create_graph(name: str) -> Graph:
    """Factory function to create a new graph builder."""
    return Graph(name)


__all__ = ["Workflow", "Graph", "ExecutableGraph", "create_graph"]