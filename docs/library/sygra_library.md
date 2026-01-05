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

Requirements: Python 3.11-3.13 recommended. We also recommend upgrading `pip` first.

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

#### Core Methods

| Method | Description | Returns |
|--------|-------------|---------|
| `source(source)` | Set data source | `Workflow` |
| `sink(sink)` | Set data sink | `Workflow` |
| `llm(model, prompt, **kwargs)` | Add LLM node | `Workflow` |
| `agent(model, tools, prompt, **kwargs)` | Add agent node | `Workflow` |
| `lambda_func(func, output, **kwargs)` | Add lambda node | `Workflow` |
| `run(**kwargs)` | Execute workflow | `Any` |

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
from sygra.core.graph.functions.lambda_function import LambdaFunction

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
from sygra.core.graph.functions.node_processor import NodePreProcessor

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
from sygra.core.graph.functions.node_processor import NodePostProcessor

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
from sygra.core.graph.functions.node_processor import NodePostProcessorWithState

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

---

## Data Sources and Sinks

### Source Options

| Type | Example | Description |
|------|---------|-------------|
| File | `workflow.source("data.json")` | Local files (JSON, JSONL, CSV) |
| Memory | `workflow.source([{"text": "sample"}])` | In-memory data |
| HuggingFace | `workflow.source({"type": "hf", "repo_id": "dataset/name"})` | HF datasets |

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
| `workflow.run()` | `List[Dict]` or `Any` | Processed results |
| `graph.build()` | `ExecutableGraph` | Built graph object |
| `graph.run()` | `List[Dict]` or `Any` | Execution results |
