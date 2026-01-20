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

### [Aggregator Metrics Reference](aggregator_metrics_summary.md)
Technical reference for metric developers and platform code:
- What each metric calculates
- Required parameters (handled by platform code)
- How to instantiate via registry
- Understanding `UnitMetricResult`

### [Unit Metrics Reference](unit_metrics_summary.md)
Technical reference for unit metric developers and platform code:
- What each unit metric validates
- Required parameters (keys, thresholds, etc.)
- How to instantiate and run batch evaluation
- Understanding `UnitMetricResult`

## Quick Start: End User Perspective

### User Configuration (Simple!)
```yaml
# graph_config.yaml
graph_properties:
  metrics:
    - accuracy
    - precision
    - recall
    - f1_score
```

User just lists which metrics they want.

### Basic Usage Example

```python
# 1. Unit Metrics - Validate individual predictions
from sygra.core.eval.metrics.unit_metrics.exact_match import ExactMatchMetric

# Initialize unit metric
validator = ExactMatchMetric(case_sensitive=False, normalize_whitespace=True)

# Evaluate predictions
results = validator.evaluate(
    golden=[{"text": "Hello World"}, {"text": "Foo"}],
    predicted=[{"text": "hello  world"}, {"text": "bar"}]
)
# Returns: [UnitMetricResult(correct=True, ...), UnitMetricResult(correct=False, ...)]

# 2. Aggregator Metrics - Calculate statistics from unit results
from sygra.core.eval.metrics.aggregator_metrics.accuracy import AccuracyMetric
from sygra.core.eval.metrics.aggregator_metrics.precision import PrecisionMetric

# Accuracy (no config needed)
accuracy = AccuracyMetric()
accuracy_score = accuracy.calculate(results)
# Returns: {'accuracy': 0.5}

# Precision (requires config)
precision = PrecisionMetric(predicted_key="tool", positive_class="click")
precision_score = precision.calculate(results)
# Returns: {'precision': 0.75}
```

### How Unit and Aggregator Metrics Work Together

```python
from sygra.core.eval.metrics.unit_metrics.exact_match import ExactMatchMetric
from sygra.core.eval.metrics.aggregator_metrics.accuracy import AccuracyMetric
from sygra.core.eval.metrics.aggregator_metrics.precision import PrecisionMetric

# Step 1: Unit metric validates each prediction
validator = ExactMatchMetric(key="tool")
unit_results = validator.evaluate(
    golden=[{"tool": "click"}, {"tool": "type"}, {"tool": "click"}],
    predicted=[{"tool": "click"}, {"tool": "scroll"}, {"tool": "type"}]
)
# unit_results = [
#   UnitMetricResult(correct=True, golden={...}, predicted={...}),
#   UnitMetricResult(correct=False, golden={...}, predicted={...}),
#   UnitMetricResult(correct=False, golden={...}, predicted={...})
# ]

# Step 2: Aggregator metrics compute statistics
accuracy = AccuracyMetric()
print(accuracy.calculate(unit_results))
# Output: {'accuracy': 0.33}  (1 out of 3 correct)

precision = PrecisionMetric(predicted_key="tool", positive_class="click")
print(precision.calculate(unit_results))
# Output: {'precision': 1.0}  (1 click predicted, 1 was correct)
```

**Key Point**: Unit metrics produce `UnitMetricResult` objects, aggregator metrics consume them to calculate statistics.

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
