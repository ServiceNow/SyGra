# SyGra Library Documentation

## Overview

The **SyGra Library** provides a high-level Python interface for building and executing complex data processing workflows with LLMs, agents, and advanced orchestration features. This library enables both programmatic workflow creation and existing YAML task execution with override capabilities.

### Key Features

- **Workflow Builder** - Programmatic workflow construction with method chaining
- **Multiple Node Types** - LLM, Multi-LLM, Agent, Lambda, Weighted Sampler, Subgraph nodes
- **Configuration Overrides** - Dynamic runtime modifications with dot notation
- **Data Processing** - Multi-format support (JSON, JSONL, CSV, HuggingFace datasets)
- **Advanced Features** - Quality tagging, OASST mapping, resumable execution
- **Callable Support** - Pass Python functions, classes, and methods directly

---

## Installation

Requirements: Python 3.9-3.11 recommended. We also recommend upgrading `pip` first.

**Install from PyPI**
```bash
python -m pip install -U pip
pip install sygra
```

If your environment uses multiple Python versions, prefer `python -m pip` or a `virtualenv`
```bash
python -m venv .venv && source .venv/bin/activate
python -m pip install -U pip

pip install sygra
```

**Install from source (editable)**
```bash
git clone https://github.com/ServiceNow/SyGra.git
cd SyGra
pip install -U pip

pip install -e .
```

---

## Quick Start

### Basic Workflow

```python
import sygra

# Simple text processing workflow
workflow = sygra.Workflow() \
    .source("data.json") \
    .llm("gpt-4o", "Rewrite this text: {text}") \
    .sink("output.json") \
    .run()
```

### Override Existing Tasks

```python
# Execute existing YAML task with runtime modifications
workflow = sygra.Workflow("my_existing_task") \
    .override_prompt("generate_answer", "user", "Solve: {question}", index=1) \
    .override_model("analyzer", "gpt-4o", temperature=0.8) \
    .run(num_records=100)
```

### Build a Workflow from a Config

`Workflow.from_config()` builds a workflow from a dictionary (or a YAML file) with the
same shape as a task's `graph_config.yaml`. The config doesn't need to be in the
`tasks/` directory, so you can keep workflows in your own project.

```python
config = {
    "data_config": {"source": {"type": "disk", "file_path": "data/input.json"}},
    "graph_config": {
        "nodes": {
            "answer": {
                "node_type": "llm",
                "model": {"name": "gpt-4o"},
                "prompt": [
                    {"system": {"file": "prompts/system.txt"}},  # read from a file
                    {"user": "{question}"},                       # inline text
                ],
                "output_keys": "answer",
            }
        },
        "edges": [{"from": "START", "to": "answer"}, {"from": "answer", "to": "END"}],
    },
}

workflow = sygra.Workflow.from_config(config, base_dir="/srv/my_project")
result = workflow.run(num_records=10)
```

- **Prompts:** a message is inline text or `{"file": path}`. The file's text replaces
  the reference when the workflow is built. Relative files resolve against `base_dir`,
  or the YAML file's directory when you pass a path. They never resolve against the
  working directory: a relative file with no `base_dir` raises `ConfigurationError`.
- **Data paths:** when you give `base_dir`, relative `file_path` values of data sources
  and sinks resolve against it. Without `base_dir` they stay as written.
- **Output:** like other programmatic workflows, output goes to a temporary directory
  unless you pass `run(output_dir=...)`. Nothing is written to a task directory.
- **Config fidelity:** source `transformations` and `graph_properties` in the config
  are applied. The input dictionary is not modified.
- **Name:** `name=` sets the workflow name. The default is the config's `task_name`,
  then the YAML file's directory name.

`ConfigLoader().load_and_create(config)` is the same as `Workflow.from_config(config)`.

---

## API Reference

### Workflow Class

The main entry point for creating and executing workflows.

#### Constructor

```python
sygra.Workflow(name: Optional[str] = None)
```

**Parameters:**
- `name` (str, optional): Workflow name. Auto-generated if not provided.

To build a workflow from a config dictionary or YAML file, use
`sygra.Workflow.from_config(config, base_dir=None, name=None)`. See
[Build a Workflow from a Config](#build-a-workflow-from-a-config).

#### Core Methods

| Method | Description | Returns |
|--------|-------------|---------|
| `source(source)` | Set data source | `Workflow` |
| `sink(sink)` | Set data sink | `Workflow` |
| `llm(model, prompt, **kwargs)` | Add LLM node | `Workflow` |
| `agent(model, tools, prompt, **kwargs)` | Add agent node | `Workflow` |
| `lambda_func(func, output, **kwargs)` | Add lambda node | `Workflow` |
| `run(**kwargs)` | Execute workflow | `RunResult` |
| `await arun(**kwargs)` | Execute workflow inside a running event loop (see [Async Execution](#async-execution)) | `RunResult` |

---

## Node Types

### LLM Nodes

Process text using Large Language Models.

#### Basic Usage

```python
# Simple LLM node
workflow.llm("gpt-4o", "Summarize: {text}")
```

#### Advanced Configuration

```python
workflow.llm(
    model={
        "name": "gpt-4o",
        "parameters": {"temperature": 0.7, "max_tokens": 2000}
    },
    prompt=[
        {"system": "You are an expert analyst"},
        {"user": "Analyze: {data}"}
    ],
    pre_process=preprocess_function,
    post_process=postprocess_function
)
```

#### Model Roles

A node can name a **role** instead of a model: `{"role": "generator"}`. Each run maps
roles to models, so the same graph can run against different model mixes, for example
to cross-check one model family with another, without editing the graph. SyGra only
resolves names; it enforces no policy.

```python
workflow = (
    sygra.Workflow("qa")
    .source(rows)
    .llm({"role": "generator"}, "{question}", output="answer")
    .llm({"role": "reviewer", "parameters": {"temperature": 0.1}}, "{answer}", output="review")
    .model_roles({"generator": "gpt-4o", "reviewer": "claude-sonnet"})  # defaults
)

workflow.run()                                         # gpt-4o + claude-sonnet
workflow.run(model_roles={"generator": "gemini-pro"})  # override one role for this run
```

- **Role values:** a model name from `models.yaml`, or a model config dict with `name`
  (for example `{"name": "gen", "model_type": "external", "provider": "mosaic"}`).
- **Merging:** the node's own keys, such as `parameters`, are applied on top of the
  role's model config.
- **`from_config()`:** a dict config can set defaults with a top-level `model_roles` key.
- **Errors:** an unmapped role, or a model config with both `name` and `role`, raises
  `ConfigurationError`. Roles work in library runs (`run()` / `arun()`), not in the CLI.
- **Usage:** `RunResult.usage_by_model` is keyed by the resolved model names.

### Multi-LLM Nodes

Compare responses from multiple models simultaneously.

```python
workflow.multi_llm(
    models={
        "gpt4": "gpt-4o",
        "claude": "claude-3-sonnet",
        "local": {"name": "llama-3-70b", "endpoint": "localhost:8000"}
    },
    prompt="Generate a story about: {topic}"
)
```

### Agent Nodes

LLM agents with tool access for autonomous task execution.

```python
def calculator(expression: str) -> str:
    """Evaluate mathematical expressions"""
    return str(eval(expression))

def web_search(query: str) -> dict:
    """Search the web for information"""
    return {"results": f"Search results for: {query}"}

# Agent with callable tools
workflow.agent(
    model="gpt-4o",
    tools=[calculator, web_search],
    prompt="Help solve: {problem}",
    chat_history=True
)
```

### Lambda Nodes

Custom processing functions and classes.

#### Using Classes

```python
from sygra.hooks import LambdaFunction

class TextProcessor(LambdaFunction):
    @staticmethod
    def apply(lambda_node_dict: dict, state: SygraState):
        text = state.get("text", "").strip().lower()
        return {
            **state,
            "processed_text": text,
            "word_count": len(text.split())
        }

workflow.lambda_func(TextProcessor, output="processed_data")
```

#### Using Functions

```python
def extract_keywords(data):
    """Extract keywords from text"""
    words = data["text"].split()
    return {"keywords": [w for w in words if len(w) > 5]}

workflow.lambda_func(extract_keywords, output="keywords")
```

#### Using Callable Objects

```python
class DataValidator:
    def __init__(self, config):
        self.config = config

    def __call__(self, data):
        score = len(data["text"]) / 100
        return {
            "quality_score": min(1.0, score),
            "is_valid": score > self.config["threshold"]
        }

validator = DataValidator({"threshold": 0.5})
workflow.lambda_func(validator, output="validation")
```

---

## Configuration System

### Universal Override Method

Modify any configuration parameter using dot notation paths.

```python
workflow = sygra.Workflow("existing_task") \
    .override("graph_config.nodes.llm_1.model.parameters.temperature", 0.9) \
    .override("graph_config.nodes.llm_1.prompt.0.system", "New instructions") \
    .override("data_config.source.repo_id", "new/dataset") \
    .run()
```

### Helper Methods

#### Model Overrides

```python
workflow.override_model(
    node_name="analyzer",
    model_name="gpt-4o",
    temperature=0.8,
    max_tokens=1500
)
```

#### Prompt Overrides

```python
workflow.override_prompt(
    node_name="generator",
    role="system",
    content="You are a helpful assistant",
    index=0
)
```

### Example

```python
# Override glaive_code_assistant task configuration
workflow = sygra.Workflow("examples/glaive_code_assistant") \
    .override_prompt(
        "generate_answer",
        "user",
        "Solve step by step: {question}",
        index=1
    ) \
    .override_prompt(
        "critique_answer",
        "system",
        "Be thorough in your code review",
        index=0
    ) \
    .override_model("generate_answer", "gpt-4o", temperature=0.2) \
    .run(num_records=50)
```

---

## Graph Builder

For complex workflows requiring explicit control flow.

### Basic Construction

```python
# Create graph with callable conditions
import sygra


def quality_gate(state):
    """Route based on quality score"""
    return "approved" if state.get("quality_score", 0) > 0.8 else "needs_review"


graph = sygra.Workflow("advanced_workflow")

# Add and configure nodes
analyzer = graph.add_llm_node("analyzer", "gpt-4o")
    .system_prompt("Analyze the following content")
    .user_prompt("Content: {text}")
    .temperature(0.7)

reviewer = graph.add_agent_node("reviewer", "gpt-4o")
    .tools([fact_checker, web_search])
    .system_prompt("Review and verify the analysis")

# Define control flow
graph.sequence("analyzer", "reviewer")
    .add_conditional_edge(
    "reviewer",
    condition=quality_gate,  # Callable condition
    path_map={
        "approved": "END",
        "needs_review": "analyzer"
    }
)

# Execute
result = graph.set_source("documents.json")
    .set_sink("analyzed_docs.json")
    .enable_quality_tagging()
    .run(num_records=100)
```

---

## Processor Classes

### Pre-Processors

Modify state before node execution.

```python
from sygra.hooks import NodePreProcessor

class InputValidator(NodePreProcessor):
    def apply(self, state: SygraState) -> SygraState:
        # Validate required fields
        if "text" not in state or not state["text"]:
            state["text"] = "[MISSING_TEXT]"

        # Add metadata
        state["validated"] = True
        state["timestamp"] = datetime.now().isoformat()

        return state

# Use in workflow
workflow.llm(
    "gpt-4o",
    "Process: {text}",
    pre_process=InputValidator
)
```

### Post-Processors

Process responses after node execution.

```python
from sygra.hooks import NodePostProcessor

class ResponseFormatter(NodePostProcessor):
    def apply(self, response: SygraMessage) -> SygraState:
        content = response.message.content

        return {
            "formatted_response": content.strip(),
            "response_length": len(content),
            "has_content": len(content.strip()) > 0,
            "word_count": len(content.split())
        }

# Use in workflow
workflow.llm(
    "gpt-4o",
    "Analyze: {text}",
    post_process=ResponseFormatter
)
```

### Post-Processors with State

Access both response and original state.

```python
from sygra.hooks import NodePostProcessorWithState

class QualityAnalyzer(NodePostProcessorWithState):
    def apply(self, response: SygraMessage, state: SygraState) -> SygraState:
        content = response.message.content
        original_text = state.get("text", "")

        # Calculate quality metrics
        quality_score = self._calculate_quality(original_text, content)

        return {
            **state,  # Preserve original state
            "processed_response": content,
            "quality_score": quality_score,
            "is_high_quality": quality_score > 0.7
        }

    def _calculate_quality(self, original, response):
        # Your quality calculation logic
        return 0.85
```

### Hooks as Python Objects

A hook is code that a graph calls: a pre-processor, post-processor, lambda, edge
condition, data transform, output generator or graph post-processor. YAML tasks name
hooks by dotted import path. In library use you can also pass the Python object, in
the builder or in a `Workflow.from_config()` dict:

| You pass | SyGra uses it as |
|---|---|
| Dotted path string | Imported, as in YAML tasks |
| Function or other callable | Called directly |
| Hook class | Instantiated (a new instance per call for processors); lambdas and edge conditions call its static `apply` |
| Hook instance (for example `Tag("v1")`) | Used as is; its constructor state is kept |

```python
from sygra.hooks import EdgeCondition, NodePostProcessorWithState
from sygra.utils import constants

class Tag(NodePostProcessorWithState):
    def __init__(self, label):
        self.label = label

    def apply(self, resp, state):
        state["answer"] = f"{self.label}: {resp.message.content}"
        return state

class Route(EdgeCondition):
    def __init__(self, skip_word):
        self.skip_word = skip_word

    def apply(self, state):
        return constants.SYGRA_END if state["text"] == self.skip_word else "gen"

workflow.llm(model, "{question}", post_process=Tag("v1"))

config["graph_config"]["edges"].append(
    {"from": "start", "condition": Route("skip"), "path_map": {"END": "END", "gen": "gen"}}
)
config["data_config"]["source"]["transformations"] = [
    {"transform": MyTransform(), "params": {"to": "text"}}
]
config["output_config"]["generator"] = MyGenerator(config["output_config"])
config["graph_post_process"] = [MyGraphPostProcessor(field="text")]
```

Notes:

- **Objects are shared, not copied.** SyGra copies the config's dicts and lists, but
  hook objects stay the same objects. An instance may hold a lock or a client. If
  records run concurrently, the instance must be safe to call concurrently.
- **Saving configs.** The builder stores a module-level function or class as its
  dotted path, so `save_config()` still writes plain YAML. Local functions and
  classes, lambdas and instances are stored as objects and can't be written as YAML.
- **Not covered yet:** model-level `post_process` (in a model config) and `tools`
  take dotted paths only. A `structured_output` schema takes a dotted path or a
  schema dict, not a class object.

### Public Hook API

Import hook base classes from `sygra.hooks` (also exported from `sygra`):
`NodePreProcessor`, `NodePostProcessor`, `NodePostProcessorWithState`,
`LambdaFunction`, `AsyncLambdaFunction`, `EdgeCondition`, `DataTransform`,
`BaseOutputGenerator`, `GraphPostProcessor`, `SygraState` and `SygraMessage`.

This is public, versioned API (`sygra.hooks.HOOKS_API_VERSION`, now `1`):

- Within one version, the abstract methods and their signatures don't change.
- A breaking change raises `HOOKS_API_VERSION`. The old form keeps working, with a
  `DeprecationWarning`, for at least one minor release before it's removed.
- The internal modules these classes are defined in (`sygra.core...`,
  `sygra.processors...`) may move. Import from `sygra.hooks`.

---

## Data Sources and Sinks

### Source Options

| Type | Example | Description |
|------|---------|-------------|
| File | `workflow.source("data.json")` | Local files (JSON, JSONL, CSV) |
| Memory | `workflow.source([{"text": "sample"}])` | In-memory data (`type: memory`); never written to disk |
| HuggingFace | `workflow.source({"type": "hf", "repo_id": "dataset/name"})` | HF datasets |

### In-Memory Sources and Record IDs

A list of dicts (or `DataSource.memory(rows)`, or `{"type": "memory", "records": rows}` in a
`from_config()` dict) is read from memory. The records aren't written to a temporary
file, and the run doesn't change your dicts. A memory source can't be resumed: a
resumable run raises `ConfigurationError`.

Every record has an `id` that output records keep, so you can join output to input:

- An `id` field (or the `id_column` field) is used as is.
- A record without one gets `sygra.record_id(record)`: a SHA-256 of the record's
  content after source transformations. Identical records get the same id; give
  records your own `id` if they can repeat or if you use transformations.
- In library runs, each output record keeps its input `id`, even if the
  `output_map` or output generator doesn't map it.

```python
import sygra

rows = [{"id": "kb-1", "text": "..."}, {"text": "..."}]
result = workflow.source(rows).run()
by_id = {r["id"]: r for r in result}
by_id[sygra.record_id({"text": "..."})]   # the second row's output
```

### Advanced Data Sources

```python
from sygra import DataSource, DataSink

# Memory data source
graph.set_source(DataSource.memory([
    {"id": 1, "text": "Sample text"},
    {"id": 2, "text": "Another sample"}
]))

# File data sink
graph.set_sink(DataSink.disk("output/results.jsonl"))
```

---

## Advanced Features

### Quality Control

```python
workflow.quality_tagging(
    enabled=True,
    config={
        "metrics": ["coherence", "relevance", "factuality"],
        "threshold": 0.8,
        "judge_model": "gpt-4o"
    }
)
```

### OASST Conversation Mapping

```python
workflow.oasst_mapping(
    enabled=True,
    config={
        "required": "yes",
        "format": "conversation"
    }
)
```

### Resumable Execution

```python
workflow.resumable(True).run(
    num_records=10000,
    batch_size=50,
    checkpoint_interval=1000,
    resume=True  # Resume from last checkpoint
)
```

### Run Results

`run()` and `arun()` return a `RunResult`. It **is** the list of output records, with the same content as the output file, so you can use it like a list. It also carries details of the run:

```python
result = workflow.run(num_records=100, cost_fn=lambda model, usage: usage.total_tokens * 1e-6)

len(result), result[0]                 # output records
result.failed_records                  # [FailedRecord(id, kind, error), ...]
result.usage_by_model["gpt-4o"]        # UsageStats(requests, failed_requests, *_tokens, ...)
result.usage_by_node, result.usage_by_record
result.total_usage, result.cost_usd    # cost_usd is None without cost_fn
result.output_file                     # None if the output directory was temporary
```

- **`FailedRecord.kind`** is one of:
  - `model_error`: a node got an error response;
  - `exception`: graph execution raised;
  - `schema_validation`: the output was rejected.
- **`UsageStats`** holds:
  - request and failure counts;
  - prompt, completion and total tokens;
  - `estimated`: true if any request reported estimated usage;
  - summed latency;
  - `served_models`: which model actually served each request, when the backend reports it.
- **`cost_fn(model_name, usage) -> float`** prices each model's usage. SyGra ships no price list.

#### Runs Without an Output File

`run(write_output=False)` (or `arun(...)`) keeps output records only in the
`RunResult`: no output file is written, and `result.output_file` is `None`. Features
that read the output file raise `ConfigurationError` before the run: a sink
(`data_config.sink`), data quality, `graph_post_process` and resumable runs.

```python
result = await workflow.source(rows).arun(write_output=False)
```

### Async Execution

`run()` starts its own event loop with `asyncio.run()`, so it can't be called from code that already runs in one: async web apps, job workers or notebooks. Use `await workflow.arun(...)` there. It takes the same arguments and returns the same result as `run()`.

```python
from fastapi import FastAPI

import sygra

app = FastAPI()


@app.post("/generate")
async def generate(rows: list[dict]):
    return await (
        sygra.Workflow("generate")
        .source(rows)
        .llm({"name": "generator", "model_type": "external"}, "{text}", output="answer")
        .llm_provider(my_provider)
        .arun(num_records=len(rows))
    )
```

- **Records run on the caller's event loop.** Model calls are tasks on that loop, so an [external provider](../features/external_llm_providers.md) can use clients, semaphores and other resources bound to it.
- **Blocking steps run in worker threads,** so they don't stall the loop. These are dataset loading, the graph build and post-generation steps (data quality, sinks and metadata).
- **Concurrent runs are isolated.** Each run has its own task name, metadata collector and weighted-sampler state, so several `arun()` calls can run at the same time in one process. Token usage is tracked per request.
- **Signal handlers:** `arun()` never installs them, because the host owns signal handling. `run()` still installs SIGINT/SIGTERM handlers for resumable runs, but only on the main thread, and restores the previous handlers afterwards.
- **Environment:** library runs read model credentials from the existing environment only. They don't load `.env` unless you pass `env_file=".env"`, and they never override variables that are already set. See [Model Configuration](../getting_started/model_configuration.md).
- **`run()` is a thin wrapper:** `asyncio.run(workflow.arun(...))`.
- **For task executors:** `await executor.aexecute()` is the async counterpart of `executor.execute()`.

---

## Examples

### Content Analysis Pipeline

```python
def sentiment_analyzer(data):
    """Analyze text sentiment"""
    text = data.get("text", "")
    # Your sentiment analysis implementation
    return {"sentiment": "positive", "confidence": 0.85}

def topic_extractor(data):
    """Extract topics from text"""  
    # Your topic extraction implementation
    return {"topics": ["technology", "AI"], "primary_topic": "technology"}

# Comprehensive analysis workflow
workflow = sygra.Workflow("content_analysis") \
    .source("articles.json") \
    .lambda_func(sentiment_analyzer, output="sentiment_data") \
    .lambda_func(topic_extractor, output="topic_data") \
    .llm("gpt-4o", [
        {"system": "Create a comprehensive summary report"},
        {"user": "Article: {text}\nSentiment: {sentiment}\nTopics: {topics}"}
    ]) \
    .quality_tagging(enabled=True) \
    .sink("analysis_results.json") \
    .run()
```

### Research Assistant

```python
def search_papers(query: str) -> list:
    """Search academic papers"""
    return [{"title": f"Paper on {query}", "abstract": "Research findings..."}]

def fact_check(claim: str) -> dict:
    """Verify factual claims"""
    return {"claim": claim, "verified": True, "confidence": 0.9}

# Multi-model research workflow
workflow = sygra.Workflow("research_assistant") \
    .source("research_questions.json") \
    .agent(
        model="gpt-4o",
        tools=[search_papers, fact_check],
        prompt="Research thoroughly: {question}",
        chat_history=True
    ) \
    .multi_llm(
        models={
            "summarizer": "gpt-4o",
            "reviewer": "claude-3-sonnet"
        },
        prompt="Synthesize research findings: {messages}"
    ) \
    .sink("research_reports.json") \
    .run()
```

---

## API Reference

### Return Types

| Method | Return Type | Description |
|--------|-------------|-------------|
| `workflow.run()` | `RunResult` (a `list` of records) | Processed results, failures, usage and cost (see [Run Results](#run-results)) |
| `await workflow.arun()` | `RunResult` | Same as `run()`, inside a running event loop |
| `graph.build()` | `ExecutableGraph` | Built graph object |
| `graph.run()` | `List[Dict]` or `Any` | Execution results |
