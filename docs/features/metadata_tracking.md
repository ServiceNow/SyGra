# Metadata Tracking System

> **Comprehensive execution metrics, cost tracking, and performance monitoring for SyGra workflows**

## Overview

SyGra includes an automatic metadata tracking system that captures detailed metrics about every workflow execution. This feature provides complete visibility into costs, performance, and resource usage without requiring any code changes.

**Key Benefits:**
- Real-time cost tracking for multiple LLM models
- Comprehensive token usage and performance metrics
- Multi-level tracking (aggregate, model, and node)
- Timestamp synchronization between outputs and metadata
- Zero configuration - works automatically

---

## Quick Start

### Automatic Collection (Default)

Metadata is collected automatically for all workflows:

**Library Usage:**
```python
from sygra import Workflow, DataSource

# Create workflow
graph = Workflow("my_task")
graph.source(DataSource.memory([{"text": "Hello"}]))
graph.add_llm_node("summarizer", "gpt-4o-mini") \
    .system_message("Summarize") \
    .user_message("{text}") \
    .output_keys("summary")

# Run - metadata collected automatically!
results = graph.run(num_records=10, output_with_ts=True)
```

**CLI Usage:**
```bash
poetry run python main.py --task examples.glaive_code_assistant --num_records=10

# Metadata automatically saved to:
# tasks/examples/glaive_code_assistant/metadata/metadata_*.json
```

### Access Metadata Programmatically

```python
from sygra.metadata.metadata_collector import get_metadata_collector

collector = get_metadata_collector()

# Get full metadata summary
metadata = collector.get_metadata_summary()

# Check aggregate metrics
stats = metadata['aggregate_statistics']
print(f"Total cost: ${stats['cost']['total_cost_usd']:.4f}")
print(f"Total requests: {stats['requests']['total_requests']}")
print(f"Models used: {list(metadata['models'].keys())}")
print(f"Nodes executed: {list(metadata['nodes'].keys())}")
```

---

## Configuration

### Disabling Metadata Collection

By default, metadata collection is **enabled**. You can disable it using three methods:

#### Method 1: CLI Flag (Per-Run)
```bash
# Short form
poetry run python main.py -t mytask -n 1000 -dm True

# Long form
poetry run python main.py --task mytask --num_records 1000 --disable_metadata True
```

#### Method 2: Environment Variable (Global)
```bash
export SYGRA_DISABLE_METADATA=1
poetry run python main.py --task mytask
```

**Accepted values:** `1`, `true`, `yes`, `True`, `YES` (case-insensitive)

#### Method 3: Programmatic (In Code)
```python
from sygra.metadata.metadata_collector import get_metadata_collector

collector = get_metadata_collector()
collector.set_enabled(False)  # Disable
collector.set_enabled(True)   # Re-enable

# Check status
if collector.is_enabled():
    print("Metadata collection is active")
```

### When to Disable Metadata

- **Quick tests and iteration**: Faster execution without I/O overhead
- **CI/CD automated tests**: Reduce test artifacts
- **Privacy requirements**: Avoid storing execution details
- **Storage constraints**: Minimize disk usage
- **Performance benchmarking**: Eliminate metadata overhead (< 1%)

---

## Key Features

### Automatic Cost Tracking

- **Real-Time Calculation**: Automatic cost computation based on token usage
- **Multiple Models Supported**: Uses LangChain Community's official pricing data
- **Multiple Providers**: OpenAI, Azure OpenAI, Anthropic Claude on AWS Bedrock
- **Per-Request & Aggregate**: Track costs at multiple granularities
- **Zero-Cost Fallback**: Returns $0.00 for unsupported models (no stale estimates)

**Supported Models:**
- OpenAI: GPT-4, GPT-4 Turbo, GPT-3.5 Turbo, GPT-4o, GPT-4o-mini
- Azure OpenAI: Same models, different endpoints
- Anthropic: Claude 3 Opus, Sonnet, Haiku (on AWS Bedrock)
- vLLM: Any OpenAI-compatible endpoint (token tracking only, cost = $0.00)

### Comprehensive Metrics

**Token Statistics:**
- Prompt, completion, and total tokens
- Per-model and aggregate totals
- Average tokens per request

**Performance Metrics:**
- Request latency (total and average)
- Latency percentiles (min, max, mean, median, std_dev, p50, p95, p99)
- Throughput (tokens/second)
- Retry and failure rates
- Response code distribution

**Cost Analytics:**
- Total costs in USD
- Per-request costs (model-level)
- Per-execution costs (node-level)
- Per-record costs (aggregate)

### Multi-Level Tracking

**Aggregate Statistics:**
- Overall execution metrics across all models and nodes
- Total tokens, costs, requests, failures
- Success rates and retry rates

**Model-Level Metrics:**
- Per-model token usage and costs
- Performance characteristics (latency, throughput)
- Failure rates and response codes
- Model configuration captured

**Node-Level Metrics:**
- Per-node execution counts and timing
- Success/failure tracking
- Token usage per node
- Associated model information

**Dataset Metadata:**
- Source type (HuggingFace, disk, memory)
- Source path and version
- Number of records processed
- Dataset hash for versioning

### Timestamp Synchronization

Output and metadata files share identical timestamps for easy correlation:

```
Format: YYYY-MM-DD_HH-MM-SS

Output:   tasks/my_task/output_2025-10-30_18-19-07.json
Metadata: tasks/my_task/metadata/metadata_my_task_2025-10-30_18-19-07.json
```

---

## Metadata Output Format

### Complete Structure

```json
{
  "metadata_version": "1.0.0",
  "generated_at": "2025-10-30T18:19:11.658190",

  "execution": {
    "task_name": "tasks.examples.my_task",
    "run_name": "",
    "output_dir": "/path/to/output",
    "batch_size": 25,
    "checkpoint_interval": 100,
    "resumable": false,
    "debug": false,

    "timing": {
      "start_time": "2025-10-30T18:19:07.899389",
      "end_time": "2025-10-30T18:19:11.657968",
      "duration_seconds": 3.759
    },

    "environment": {
      "python_version": "3.11.12",
      "sygra_version": "1.0.0"
    },

    "git": {
      "commit_hash": "b81c39a3db4d12342cc50415342abc2b2b",
      "branch": "main",
      "is_dirty": false
    }
  },

  "dataset": {
    "source_type": "hf",
    "source_path": "glaiveai/glaive-code-assistant-v2",
    "num_records_processed": 10,
    "start_index": 0,
    "dataset_version": "0.0.0",
    "dataset_hash": "4b023d2345d21e2d"
  },

  "aggregate_statistics": {
    "records": {
      "total_processed": 10,
      "total_failed": 0,
      "success_rate": 1.0
    },

    "tokens": {
      "total_prompt_tokens": 440,
      "total_completion_tokens": 920,
      "total_tokens": 1360
    },

    "requests": {
      "total_requests": 20,
      "total_retries": 2,
      "total_failures": 0,
      "retry_rate": 0.1,
      "failure_rate": 0.0
    },

    "cost": {
      "total_cost_usd": 0.00062,
      "average_cost_per_record": 0.000062
    }
  },

  "models": {
    "gpt-4o-mini": {
      "model_name": "gpt-4o-mini",
      "model_type": "OpenAI",
      "model_url": "https://api.openai.com/v1",

      "token_statistics": {
        "total_prompt_tokens": 440,
        "total_completion_tokens": 920,
        "total_tokens": 1360,
        "avg_prompt_tokens": 44.0,
        "avg_completion_tokens": 92.0,
        "avg_total_tokens": 136.0
      },

      "performance": {
        "total_requests": 20,
        "total_retries": 2,
        "total_failures": 0,
        "failure_rate": 0.0,
        "total_latency_seconds": 64.06,
        "average_latency_seconds": 3.203,
        "tokens_per_second": 21.23,
        "latency_statistics": {
          "min": 2.105,
          "max": 4.821,
          "mean": 3.203,
          "median": 3.150,
          "std_dev": 0.652,
          "p50": 3.150,
          "p95": 4.512,
          "p99": 4.759
        }
      },

      "cost": {
        "total_cost_usd": 0.00062,
        "average_cost_per_request": 0.000031
      },

      "response_code_distribution": {
        "200": 18,
        "429": 2
      },

      "parameters": {
        "max_tokens": 500,
        "temperature": 0.7
      }
    }
  },

  "nodes": {
    "summarizer": {
      "node_name": "summarizer",
      "node_type": "llm",
      "model_name": "gpt-4o-mini",
      "total_executions": 10,
      "total_failures": 0,
      "failure_rate": 0.0,
      "total_latency_seconds": 32.03,
      "average_latency_seconds": 3.203,
      "latency_statistics": {
        "min": 2.105,
        "max": 4.821,
        "mean": 3.203,
        "median": 3.150,
        "std_dev": 0.652,
        "p50": 3.150,
        "p95": 4.512,
        "p99": 4.759
      },

      "cost": {
        "total_cost_usd": 0.00031,
        "average_cost_per_execution": 0.000031
      },

      "token_statistics": {
        "total_prompt_tokens": 220,
        "total_completion_tokens": 460,
        "total_tokens": 680,
        "avg_prompt_tokens": 22.0,
        "avg_completion_tokens": 46.0,
        "avg_total_tokens": 68.0
      }
    }
  }
}
```

### Field Descriptions

#### Execution Context
- `task_name`: Full task identifier
- `timing`: Start time, end time, and total duration
- `environment`: Python and SyGra versions for reproducibility
- `git`: Git commit hash, branch, and dirty status

#### Dataset Metadata
- `source_type`: Dataset source (hf, disk, memory)
- `source_path`: Path or identifier for the dataset
- `num_records_processed`: Total records processed
- `dataset_hash`: Hash for dataset version tracking

#### Aggregate Statistics
- `records`: Total processed, failed, and success rate
- `tokens`: Aggregate token usage across all models
- `requests`: Total requests, retries, failures, and rates
- `cost`: Total cost and average cost per record

#### Model Metrics
- `token_statistics`: Detailed token usage for this model
- `performance`: Latency, throughput (completion tokens per second for successful requests), failure rates
- `latency_statistics`: Min, max, mean, median, std_dev, p50, p95, p99 for request latency
- `cost`: Total cost and average cost per request
- `response_code_distribution`: HTTP status codes (keys are strings in JSON output)
- `parameters`: Model configuration used

#### Node Metrics
- `total_executions`: Number of times node was executed
- `total_failures`: Number of failed executions
- `failure_rate`: Percentage of failed executions
- `total_latency_seconds`: Cumulative execution time
- `average_latency_seconds`: Average time per execution
- `latency_statistics`: Min, max, mean, median, std_dev, p50, p95, p99 for node execution latency
- `cost`: Total cost and average cost per execution (only present if node has costs)
- `token_statistics`: Token usage for this node (only present if node uses tokens)

---

## Architecture

### Core Components

#### 1. MetadataCollector
Central singleton class managing all metadata collection:

```python
from sygra.metadata.metadata_collector import get_metadata_collector

collector = get_metadata_collector()
```

**Features:**
- Thread-safe singleton pattern
- Centralized storage for all metrics
- Automatic initialization via `BaseTaskExecutor`
- JSON export with structured format
- Toggle support (enable/disable)

#### 2. Tracking Mechanisms

**For Custom Models (LLM Nodes):**
```python
@track_model_request
async def _generate_response(self, input, model_params):
    response = await self.model.ainvoke(input)
    return response, 200
```

The `@track_model_request` decorator automatically captures:
- Token usage (prompt, completion, total)
- Request latency
- Response status codes
- Cost calculations
- Retry attempts and failures

**For LangChain Agents:**
```python
from sygra.metadata.langchain_callback import MetadataTrackingCallback

callback = MetadataTrackingCallback(model_name="gpt-4o")
response = await agent.ainvoke(input, config={"callbacks": [callback]})
```

**For Node Execution:**
All node types automatically track execution via `BaseNode`:
- Execution count
- Total execution time
- Success/failure rates
- Associated model information

#### 3. Token Usage Extraction

**OpenAI-Compatible APIs:**
```python
def _extract_token_usage(self, response: Any) -> None:
    if hasattr(response, "usage") and response.usage:
        self._last_request_usage = {
            "prompt_tokens": getattr(response.usage, "prompt_tokens", 0),
            "completion_tokens": getattr(response.usage, "completion_tokens", 0),
            "total_tokens": getattr(response.usage, "total_tokens", 0),
        }
```

Works with: OpenAI, Azure OpenAI, vLLM, any OpenAI-compatible API

**TGI (Text Generation Inference):**
```python
def _extract_tgi_token_usage(self, response_data: dict) -> None:
    """
    Extract token usage from TGI response details.

    TGI returns token statistics in the 'details' field when details=true:
    - details.generated_tokens: completion tokens
    - len(details.prefill): prompt tokens (if available)
    """
    if "details" in response_data and response_data["details"]:
        details = response_data["details"]

        # Get completion tokens
        completion_tokens = details.get("generated_tokens", 0)

        # Get prompt tokens from prefill length
        prompt_tokens = 0
        if "prefill" in details and details["prefill"]:
            prompt_tokens = len(details["prefill"])

        # Calculate total
        total_tokens = prompt_tokens + completion_tokens

        # Store in the standard format
        self._last_request_usage = {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
        }
```

**Note**: TGI requires `details=true` in the request parameters to return token statistics.
