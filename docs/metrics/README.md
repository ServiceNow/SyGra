# Metrics Documentation

This folder contains documentation for Sygra's metrics system, which provides tools for evaluating and measuring model performance.

## Overview

The metrics system in Sygra is designed with a **three-layer architecture**:

### Layer 1: Unit Metrics (Validators)
Individual validation operations that produce binary pass/fail results:
- Compare predicted output vs expected output for a single step
- Return `UnitMetricResult` objects containing:
  - `correct` (bool): Was the prediction correct?
  - `golden` (dict): Expected/ground truth data
  - `predicted` (dict): Model's predicted data
  - `metadata` (dict): Additional context

**Example**: Validate if predicted tool matches expected event.

### Layer 2: Aggregator Metrics (Statistical Primitives)
Statistical measures that calculate metrics for a **single class** from multiple unit results:
- **AccuracyMetric**: Overall correctness measurement
- **PrecisionMetric**: Quality of positive predictions for a specific class
- **RecallMetric**: Coverage of actual positives for a specific class
- **F1ScoreMetric**: Balanced precision-recall measure for a specific class

These are **building blocks** that consume `UnitMetricResult` lists.

### Layer 3: Platform Orchestration (High-Level)
Platform code that:
- Reads user's simple metric list from `graph_config.yaml`
- Collects `UnitMetricResult` objects from validators
- Discovers all classes from validation results
- Iterates over classes automatically
- Calls aggregator metrics with appropriate parameters
- Aggregates results across all classes

**User never specifies classes or keys - platform handles it.**


## Available Documentation

### [Aggregator Metrics Reference](./aggregator_metrics_summary.md)
Technical reference for metric developers and platform code:
- What each metric calculates
- Required parameters (handled by platform code)
- How to instantiate via registry
- Understanding `UnitMetricResult`

## Quick Start: End User Perspective

### User Configuration (Simple!)
```yaml
# graph_config.yaml
graph_properties:
  metrics:
    - "accuracy"
    - "precision"
    - "recall"
    - "f1_score"
```

User just lists which metrics they want.

### What Platform Code Does (Behind the Scenes)

```python
# Platform code (to be implemented in graph execution layer)
from sygra.core.metrics.aggregator_metrics.aggregator_metric_registry import AggregatorMetricRegistry

def run_evaluation(validation_results, metric_names):
    """
    Platform orchestration layer.
    User provides metric_names = ["accuracy", "precision", "recall"]
    Platform handles the rest.
    """
    # 1. Discover classes from validation results
    classes = discover_classes(validation_results)  # e.g., ["click", "type", "scroll"]
    
    # 2. For each metric, iterate over all classes
    results = {}
    for metric_name in metric_names:
        if metric_name == "accuracy":
            metric = AggregatorMetricRegistry.get_metric("accuracy")
            results["accuracy"] = metric.calculate(validation_results)
        
        elif metric_name == "precision":
            results["precision"] = {}
            for cls in classes:
                metric = AggregatorMetricRegistry.get_metric(
                    "precision",
                    predicted_key="tool",  # Platform knows task structure
                    positive_class=cls
                )
                results["precision"][cls] = metric.calculate(validation_results)
        
        # Similar for recall, f1_score...
    
    return results

# Output:
# {
#   "accuracy": {"accuracy": 0.85},
#   "precision": {"click": 0.75, "type": 0.80, "scroll": 0.70},
#   "recall": {"click": 0.78, "type": 0.82, "scroll": 0.68},
#   "f1_score": {"click": 0.76, "type": 0.81, "scroll": 0.69}
# }
```

**Key Point**: Platform code iterates over classes and calls metrics. User doesn't specify classes!

## Design Philosophy

The metrics system follows these principles:

1. **Fail Fast**: Required parameters must be provided at initialization to catch errors early
2. **Explicit Configuration**: No default values for keys/classes to prevent silent bugs
3. **Task Agnostic**: Works with any task through flexible `UnitMetricResult` structure
4. **Composability**: Complex metrics reuse simpler ones for consistency

## Contributing

When adding new metrics documentation:
1. Follow the existing structure (What, Parameters, Usage, Examples)
2. Include complete, runnable code examples
3. Explain the "why" behind design decisions
4. Cover edge cases and common pitfalls
5. Provide real-world use case scenarios

