# Evaluation Tasks

SyGra is a graph-oriented workflow framework for synthetic data generation **and evaluation**. This guide explains how to build, configure, and run evaluation tasks.

---

## Table of Contents

1. [Quick Start](#quick-start)
2. [Core Concepts](#core-concepts)
3. [Evaluation Workflow](#evaluation-workflow)
4. [Configuration Guide](#configuration-guide)
5. [Output Files](#output-files)
6. [Complete Examples](#complete-examples)
7. [Extending Evaluation](#extending-evaluation)
8. [Troubleshooting](#troubleshooting)

[//]: # (9. [Best Practices]&#40;#best-practices&#41;)

---

## Quick Start

### Running an Evaluation Task

```bash
# Basic usage
uv run python main.py --task tasks.eval.question_answering.simpleqa --num_records 50

# Alternative path format
uv run python main.py --task eval/classification/simpleqa --num_records 50

# Specify output directory
uv run python main.py \
  --task tasks.eval.question_answering.simpleqa \
  --num_records 50 \
  --output_dir /abs/path/to/my_eval_outputs
```

### What You Get

Every evaluation run produces two main outputs:

1. **`output_*.json`** - Per-record results with unit metric evaluations
2. **`MetricCollatorPostProcessor_*.json`** - Aggregated metrics report

---

## Core Concepts

### Two-Layer Metric Architecture

SyGra evaluation uses a two-layer architecture:

```
┌─────────────────────────────────────────────────────────────┐
│  Layer 1: Unit Metrics (Per-Record Validation)             │
│  ─────────────────────────────────────────────────────────  │
│  • Computed INSIDE the graph during execution               │
│  • Validate individual predictions (e.g., exact_match)      │
│  • Stored in state: exact_match, fuzzy_match, etc.          │
│  • Output: UnitMetricResult objects                         │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  Layer 2: Aggregator Metrics (Dataset-Level Statistics)    │
│  ─────────────────────────────────────────────────────────  │
│  • Computed AFTER the run via post-processing               │
│  • Aggregate unit results (e.g., accuracy, precision)       │
│  • Consume UnitMetricResult lists                           │
│  • Output: Statistical summaries                            │
└─────────────────────────────────────────────────────────────┘
```

### Key Components

| Component | Location | Purpose |
|-----------|----------|---------|
| **UnitMetrics** | `tasks/eval/utils.py` | Generic lambda node for computing unit metrics |
| **MetricCollatorPostProcessor** | `tasks/eval/utils.py` | Generic post-processor for aggregating metrics |
| **UnitMetricRegistry** | `sygra.core.eval.metrics.unit_metrics.unit_metric_registry` | Auto-discovers and instantiates unit metrics |
| **AggregatorMetricRegistry** | `sygra.core.eval.metrics.aggregator_metrics.aggregator_metric_registry` | Auto-discovers and instantiates aggregator metrics |

---

## Evaluation Workflow

### Step-by-Step Execution

```
1. Load Configuration
   ├─ Read graph_config.yaml
   └─ Load dataset from data_config.source

2. Execute Graph (Per Record)
   ├─ Run LLM/lambda/sampler nodes
   ├─ Generate predictions
   └─ Compute unit metrics (inside graph)
       └─ Store results in state (e.g., exact_match, fuzzy_match)

3. Write Per-Record Output
   └─ Save output_*.json with all state fields

4. Run Post-Processors
   ├─ Load output_*.json
   ├─ Apply each graph_post_process processor
   └─ MetricCollatorPostProcessor aggregates metrics

5. Write Aggregated Report
   └─ Save MetricCollatorPostProcessor_*.json
```

### Data Flow

```
Input Dataset
    ↓
┌───────────────────────────────────────┐
│  Graph Execution (Per Record)        │
│  ├─ LLM generates prediction          │
│  └─ UnitMetrics evaluates             │
│      ├─ exact_match: True/False       │
│      └─ fuzzy_match: True/False       │
└───────────────────────────────────────┘
    ↓
output_*.json
    ├─ Record 1: {prediction, exact_match, fuzzy_match}
    ├─ Record 2: {prediction, exact_match, fuzzy_match}
    └─ Record N: {prediction, exact_match, fuzzy_match}
    ↓
┌───────────────────────────────────────┐
│  MetricCollatorPostProcessor          │
│  ├─ exact_match-accuracy: 0.85        │
│  ├─ exact_match-precision: 0.90       │
│  ├─ fuzzy_match-accuracy: 0.92        │
│  └─ fuzzy_match-precision: 0.94       │
└───────────────────────────────────────┘
    ↓
MetricCollatorPostProcessor_*.json
```

---

## Configuration Guide

### Unit Metrics Configuration

Unit metrics are configured in the graph as a lambda node.

#### Basic Example: Single Unit Metric

```yaml
unit_metrics:
  node_type: lambda
  lambda: tasks.eval.utils.UnitMetrics
  golden_key: "answer"
  predicted_key: "predicted_answer"
  unit_metrics_map:
    - name: "exact_match"
      params:
        key: "text"
  output_keys:
    - exact_match
```

**What this does:**
- Compares `answer.text` (golden) with `predicted_answer.text` (predicted)
- Stores result in state as `exact_match`
- Includes `exact_match` in output file

#### Advanced Example: Multiple Unit Metrics

```yaml
unit_metrics:
  node_type: lambda
  lambda: tasks.eval.utils.UnitMetrics
  golden_key: "answer"
  predicted_key: "predicted_answer"
  unit_metrics_map:
    - name: "exact_match"
      params:
        key: "text"
    - name: "fuzzy_match"
      params:
        key: "text"
        threshold: 0.8
  output_keys:
    - exact_match
    - fuzzy_match
```

**What this does:**
- Evaluates both exact and fuzzy matching
- `exact_match`: Requires perfect string match
- `fuzzy_match`: Requires ≥80% similarity
- Both results stored in state and output

#### Available Unit Metrics

| Metric | Purpose | Key Parameters |
|--------|---------|----------------|
| `exact_match` | Exact string matching | `key`, `case_sensitive`, `normalize_whitespace` |
| `fuzzy_match` | Similarity-based matching | `key`, `threshold` (0.0-1.0), `case_sensitive` |
| `action_within_bbox` | Coordinate validation | `tolerance` |
| `typed_value_match` | Text input validation | `case_sensitive`, `normalize_whitespace` |
| `scroll_direction` | Direction validation | - |

### Aggregator Metrics Configuration

Aggregator metrics are configured in `graph_post_process`.

#### Basic Example: Single Unit Metric Source

```yaml
graph_post_process:
  - processor: tasks.eval.utils.MetricCollatorPostProcessor
    params:
      aggregator_metrics_map:
        - name: "accuracy"
          params:
            key: "text"
          unit_metrics_results:
            - "exact_match"
```

**What this does:**
- Computes accuracy from `exact_match` results
- Output key: `exact_match-accuracy`

#### Advanced Example: Multiple Unit Metric Sources

```yaml
graph_post_process:
  - processor: tasks.eval.utils.MetricCollatorPostProcessor
    params:
      aggregator_metrics_map:
        # Metrics for exact match
        - name: "accuracy"
          params:
            key: "text"
          unit_metrics_results:
            - "exact_match"
        - name: "precision"
          params:
            predicted_key: "text"
          unit_metrics_results:
            - "exact_match"
        
        # Metrics for fuzzy match
        - name: "accuracy"
          params:
            key: "text"
          unit_metrics_results:
            - "fuzzy_match"
        - name: "precision"
          params:
            predicted_key: "text"
          unit_metrics_results:
            - "fuzzy_match"
```

**What this does:**
- Computes accuracy and precision for both exact and fuzzy matching
- Output keys: `exact_match-accuracy`, `exact_match-precision`, `fuzzy_match-accuracy`, `fuzzy_match-precision`
- Allows comparison of different validation criteria

#### Available Aggregator Metrics

| Metric | Purpose | Required Parameters |
|--------|---------|---------------------|
| `accuracy` | Overall correctness | `key` |
| `precision` | Quality of positive predictions | `predicted_key` |
| `recall` | Coverage of actual positives | `golden_key` |
| `f1_score` | Balanced precision-recall | `predicted_key`, `golden_key` |

### Output Mapping

Always include unit metric fields in `output_config`:

```yaml
output_config:
  output_map:
    id:
      from: "id"
    answer:
      from: "answer"
    predicted_answer:
      from: "predicted_answer"
    exact_match:
      from: "exact_match"
    fuzzy_match:
      from: "fuzzy_match"
```

---

## Output Files

### 1. Per-Record Output: `output_*.json`

Contains individual record results with unit metric evaluations.

**Structure:**
```json
[
  {
    "id": "q001",
    "answer": {"text": "Paris"},
    "predicted_answer": {"text": "paris"},
    "exact_match": {
      "correct": true,
      "golden": {"text": "Paris"},
      "predicted": {"text": "paris"},
      "metadata": {
        "validator": "exact_match",
        "case_sensitive": false
      }
    },
    "fuzzy_match": {
      "correct": true,
      "golden": {"text": "Paris"},
      "predicted": {"text": "paris"},
      "metadata": {
        "validator": "fuzzy_match",
        "similarity": 1.0,
        "threshold": 0.8
      }
    }
  }
]
```

**Key Points:**
- One entry per evaluated record
- Contains original data + predictions + unit metric results
- Unit metric results are `UnitMetricResult` objects (serialized as dicts)

### 2. Aggregated Report: `MetricCollatorPostProcessor_*.json`

Contains dataset-level statistics aggregated from unit metrics.

**Structure:**
```json
[
  {
    "evaluation_summary": {
      "total_records": 1000,
      "timestamp": "2026-02-20 00:17:57",
      "status": "success"
    },
    "results": {
      "exact_match-accuracy": {
        "accuracy": 0.737
      },
      "exact_match-precision": {
        "average_precision": 0.828,
        "precision_per_class": {
          "Music": 0.968,
          "Politics": 0.967,
          "Other": 0.672
        }
      },
      "fuzzy_match-accuracy": {
        "accuracy": 0.856
      },
      "fuzzy_match-precision": {
        "average_precision": 0.901,
        "precision_per_class": {
          "Music": 0.985,
          "Politics": 0.978,
          "Other": 0.740
        }
      }
    }
  }
]
```

**Key Points:**
- Single report object (in a list)
- `evaluation_summary`: Metadata about the run
- `results`: Keyed as `{unit_metric}-{aggregator_metric}`
- Classification metrics include per-class breakdowns

**Status Values:**
- `success`: All records processed
- `no_data`: No records to evaluate
- `fatal_error`: Critical error (includes error message)

**Result Key Format:**
```
{unit_metrics_field}-{aggregator_metric_name}

Examples:
- exact_match-accuracy
- exact_match-precision
- fuzzy_match-accuracy
- fuzzy_match-f1_score
```

---

## Complete Examples

### Example 1: Question Answering with Multiple Validators

**File:** `tasks/eval/question_answering/simpleqa/graph_config.yaml`

```yaml
# Unit metrics node
unit_metrics:
  node_type: lambda
  lambda: tasks.eval.utils.UnitMetrics
  golden_key: "answer"
  predicted_key: "predicted_answer"
  unit_metrics_map:
    - name: "exact_match"
      params:
        key: "text"
    - name: "fuzzy_match"
      params:
        key: "text"
        threshold: 0.8
  output_keys:
    - exact_match
    - fuzzy_match

# Output configuration
output_config:
  output_map:
    id:
      from: "id"
    answer:
      from: "answer"
    predicted_answer:
      from: "predicted_answer"
    exact_match:
      from: "exact_match"
    fuzzy_match:
      from: "fuzzy_match"

# Aggregator metrics
graph_post_process:
  - processor: tasks.eval.utils.MetricCollatorPostProcessor
    params:
      aggregator_metrics_map:
        - name: "accuracy"
          params:
            key: "text"
          unit_metrics_results:
            - "exact_match"
        - name: "accuracy"
          params:
            key: "text"
          unit_metrics_results:
            - "fuzzy_match"
```

**Output:**
- `output_*.json`: Contains `exact_match` and `fuzzy_match` for each question
- `MetricCollatorPostProcessor_*.json`: Contains `exact_match-accuracy` and `fuzzy_match-accuracy`

### Example 2: Classification with Multiple Metrics

**File:** `tasks/eval/classification/simpleqa/graph_config.yaml`

```yaml
# Unit metrics node
unit_metrics:
  node_type: lambda
  lambda: tasks.eval.utils.UnitMetrics
  golden_key: "topic"
  predicted_key: "predicted_topic"
  unit_metrics_map:
    - name: "exact_match"
      params:
        key: "text"
  output_keys:
    - exact_match

# Aggregator metrics
graph_post_process:
  - processor: tasks.eval.utils.MetricCollatorPostProcessor
    params:
      aggregator_metrics_map:
        - name: "accuracy"
          params:
            key: "text"
          unit_metrics_results:
            - "exact_match"
        - name: "precision"
          params:
            predicted_key: "text"
          unit_metrics_results:
            - "exact_match"
        - name: "recall"
          params:
            golden_key: "text"
          unit_metrics_results:
            - "exact_match"
        - name: "f1_score"
          params:
            predicted_key: "text"
            golden_key: "text"
          unit_metrics_results:
            - "exact_match"
```

**Output:**
- `MetricCollatorPostProcessor_*.json`: Contains accuracy, precision, recall, and F1 score with per-class breakdowns

---

## Extending Evaluation

### Adding a New Unit Metric

**Steps:**

1. **Create metric class** in `sygra/core/eval/metrics/unit_metrics/`

```python
from sygra.core.eval.metrics.unit_metrics.base_unit_metric import BaseUnitMetric
from sygra.core.eval.metrics.unit_metrics.unit_metric_registry import unit_metric
from sygra.core.eval.metrics.unit_metrics.unit_metric_result import UnitMetricResult

@unit_metric("my_custom_metric")
class MyCustomMetric(BaseUnitMetric):
    def __init__(self, **config):
        super().__init__(**config)
        self.validate_config()
        self.metadata = self.get_metadata()
    
    def validate_config(self):
        # Validate configuration
        pass
    
    def get_metadata(self):
        # Return metric metadata
        pass
    
    def evaluate(self, golden, predicted):
        # Implement evaluation logic
        results = []
        for g, p in zip(golden, predicted):
            is_correct = # your logic
            results.append(UnitMetricResult(
                correct=is_correct,
                golden=g,
                predicted=p,
                metadata={"validator": "my_custom_metric"}
            ))
        return results
```

2. **Use in graph config**

```yaml
unit_metrics_map:
  - name: "my_custom_metric"
    params:
      # your parameters
```

**Auto-Discovery:** The `UnitMetricRegistry` automatically discovers and registers all metrics in the `unit_metrics` directory.

### Custom Lambda Node for Unit Metrics

For more complex evaluation logic or when you need full control over the unit metric calculation process, you can create a **custom lambda node** instead of using the generic `tasks.eval.utils.UnitMetrics`.

**When to use a custom lambda node:**

- Complex validation logic that doesn't fit standard unit metrics
- Need to access multiple state fields or external resources
- Custom data transformations before evaluation
- Domain-specific evaluation requirements

**Example: Custom Unit Metrics Lambda**

```python
# tasks/eval/my_task/custom_evaluator.py

from typing import Any, Dict
from sygra.core.state import SygraState

class CustomUnitMetricsLambda:
    """Custom lambda for specialized unit metric calculation."""
    
    def __init__(self, golden_key: str, predicted_key: str, **config):
        self.golden_key = golden_key
        self.predicted_key = predicted_key
        self.config = config
    
    def __call__(self, state: SygraState) -> Dict[str, Any]:
        """
        Compute custom unit metrics.
        
        Returns:
            Dict with metric results to be stored in state
        """
        golden = state.get(self.golden_key)
        predicted = state.get(self.predicted_key)
        
        # Custom evaluation logic
        custom_result = self._evaluate_custom(golden, predicted)
        
        # Store results in state
        state["custom_metric"] = custom_result
        
        return {"custom_metric": custom_result}
    
    def _evaluate_custom(self, golden, predicted):
        """Implement your custom evaluation logic."""
        # Example: Complex multi-field validation
        return {
            "correct": self._check_correctness(golden, predicted),
            "golden": golden,
            "predicted": predicted,
            "metadata": {
                "validator": "custom_metric",
                "confidence": self._calculate_confidence(predicted)
            }
        }
```

**Use in graph config:**

```yaml
unit_metrics:
  node_type: lambda
  lambda: tasks.eval.my_task.custom_evaluator.CustomUnitMetricsLambda
  golden_key: "answer"
  predicted_key: "predicted_answer"
  output_keys:
    - custom_metric

output_config:
  output_map:
    custom_metric:
      from: "custom_metric"
```

**Benefits:**

- Full control over evaluation logic
- Access to entire state and graph context
- Can perform multi-step validation
- Easier debugging for complex scenarios

### Adding a New Aggregator Metric

**Steps:**

1. **Create metric class** in `sygra/core/eval/metrics/aggregator_metrics/`

```python
from sygra.core.eval.metrics.aggregator_metrics.base_aggregator_metric import BaseAggregatorMetric
from sygra.core.eval.metrics.aggregator_metrics.aggregator_metric_registry import aggregator_metric

@aggregator_metric("my_aggregator")
class MyAggregatorMetric(BaseAggregatorMetric):
    def calculate(self, unit_metric_results):
        # Aggregate unit metric results
        # Return dict with metric values
        return {"my_metric": value}
```

2. **Use in graph config**

```yaml
aggregator_metrics_map:
  - name: "my_aggregator"
    params:
      # your parameters
    unit_metrics_results:
      - "exact_match"
```

### Custom Post-Processor for Aggregator Metrics

For advanced aggregation requirements or custom report formats, you can create a **custom graph post-processor** instead of using the generic `tasks.eval.utils.MetricCollatorPostProcessor`.

**When to use a custom post-processor:**

- Need custom report format or structure
- Complex aggregation logic beyond standard metrics
- Multiple data sources or external integrations
- Custom statistical analysis or visualizations
- Domain-specific reporting requirements

**Example: Custom Aggregator Post-Processor**

```python
# tasks/eval/my_task/custom_aggregator.py

import json
from typing import Any, Dict, List
from sygra.core.graph.graph_postprocessor import GraphPostProcessor

class CustomMetricAggregator(GraphPostProcessor):
    """Custom post-processor for specialized metric aggregation."""
    
    def __init__(self, **config):
        """
        Initialize custom aggregator.
        
        Args:
            config: Custom configuration parameters
        """
        super().__init__()
        self.config = config
        self.custom_threshold = config.get("threshold", 0.8)
    
    def process(self, output_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Process output data and compute custom aggregated metrics.
        
        Args:
            output_data: List of records from output_*.json
            
        Returns:
            Dict with aggregated results
        """
        # Extract unit metric results
        unit_results = [
            record.get("custom_metric") 
            for record in output_data 
            if "custom_metric" in record
        ]
        
        # Custom aggregation logic
        total = len(unit_results)
        correct = sum(1 for r in unit_results if r.get("correct", False))
        
        # Calculate custom metrics
        accuracy = correct / total if total > 0 else 0.0
        high_confidence = sum(
            1 for r in unit_results 
            if r.get("metadata", {}).get("confidence", 0) >= self.custom_threshold
        )
        
        # Build custom report structure
        report = {
            "evaluation_summary": {
                "total_records": total,
                "correct_predictions": correct,
                "status": "success" if total > 0 else "no_data"
            },
            "metrics": {
                "accuracy": accuracy,
                "high_confidence_rate": high_confidence / total if total > 0 else 0.0
            },
            "custom_analysis": self._perform_custom_analysis(unit_results)
        }
        
        return report
    
    def _perform_custom_analysis(self, results: List[Dict]) -> Dict:
        """Perform domain-specific analysis."""
        # Example: Custom statistical analysis
        return {
            "distribution": self._calculate_distribution(results),
            "confidence_stats": self._calculate_confidence_stats(results)
        }
```

**Use in graph config:**

```yaml
graph_post_process:
  - processor: tasks.eval.my_task.custom_aggregator.CustomMetricAggregator
    params:
      threshold: 0.85
      # any custom parameters
```

**Output file:** `CustomMetricAggregator_*.json`

**Benefits:**

- Complete control over aggregation logic
- Custom report structure and format
- Can integrate external data sources
- Flexible statistical analysis
- Domain-specific metrics and visualizations

**Example: Combining Standard and Custom Post-Processors**

You can use both standard and custom post-processors together:

```yaml
graph_post_process:
  # Standard metrics for common analysis
  - processor: tasks.eval.utils.MetricCollatorPostProcessor
    params:
      aggregator_metrics_map:
        - name: "accuracy"
          params:
            key: "text"
          unit_metrics_results:
            - "exact_match"
  
  # Custom metrics for specialized analysis
  - processor: tasks.eval.my_task.custom_aggregator.CustomMetricAggregator
    params:
      threshold: 0.85
```

This produces two output files:

- `MetricCollatorPostProcessor_*.json` - Standard metrics
- `CustomMetricAggregator_*.json` - Custom analysis

---

## Troubleshooting

### Common Issues

#### Missing Unit Metric Fields

**Error:**
```
KeyError: 'exact_match' not found in output columns
```

**Solution:**
Ensure unit metric fields are in `output_config.output_map`:

```yaml
output_config:
  output_map:
    exact_match:
      from: "exact_match"
```

#### Mismatched Unit Metrics Configuration

**Error:**
```
unit_metrics_results field 'fuzzy_match' not found
```

**Solution:**
Ensure `unit_metrics_results` matches `output_keys`:

```yaml
# Unit metrics node
output_keys:
  - exact_match
  - fuzzy_match

# Aggregator config
unit_metrics_results:
  - "exact_match"  # ✓ Matches output_keys
  - "fuzzy_match"  # ✓ Matches output_keys
```

#### Memory Issues with Large Datasets

**Issue:** Post-processing loads entire output file into memory

**Solutions:**

- Process in batches
- Use JSONL format with custom streaming post-processor
- Filter records before post-processing

[//]: # (### Best Practices)

[//]: # ()
[//]: # (**Always validate configuration**)

[//]: # ()
[//]: # (- Run with small `--num_records` first)

[//]: # (- Check output files before full run)

[//]: # ()
[//]: # (**Use descriptive names**)

[//]: # ()
[//]: # (- Name unit metrics clearly &#40;e.g., `exact_match`, `fuzzy_match_80`&#41;)

[//]: # (- Use consistent naming conventions)

[//]: # ()
[//]: # (**Document thresholds**)

[//]: # ()
[//]: # (- Comment threshold values in config)

[//]: # (- Track threshold changes in version control)

[//]: # ()
[//]: # (**Monitor output sizes**)

[//]: # ()
[//]: # (- Large unit metric metadata can bloat output files)

[//]: # (- Consider removing verbose metadata for production runs)

[//]: # (---)

[//]: # ()
[//]: # (## Additional Resources)

[//]: # ()
[//]: # (- **Unit Metrics Reference:** `docs/eval/metrics/unit_metrics_summary.md`)

[//]: # (- **Aggregator Metrics Reference:** `docs/eval/metrics/aggregator_metrics_summary.md`)

[//]: # (- **Metrics Overview:** `docs/eval/metrics/README.md`)

[//]: # ()
[//]: # (---)

[//]: # ()
[//]: # (**Last Updated:** February 2026)
