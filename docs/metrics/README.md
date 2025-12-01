# Metrics Documentation

This folder contains documentation for Sygra's metrics system, which provides tools for evaluating and measuring model performance.

## Overview

The metrics system in Sygra is designed around two key concepts:

1. **Unit Metrics (Validators)**: Individual validation operations that produce binary pass/fail results
2. **Aggregator Metrics**: Statistical measures that aggregate multiple unit metric results into performance metrics

## Available Documentation

### [Aggregator Metrics](./aggregator_metrics_summary.md)
Comprehensive guide to statistical aggregation metrics including:
- **AccuracyMetric**: Overall correctness measurement
- **PrecisionMetric**: Quality of positive predictions
- **RecallMetric**: Coverage of actual positives
- **F1ScoreMetric**: Balanced precision-recall measure

**Key Topics Covered:**
- What each metric does and when to use it
- Required initialization parameters and why they're mandatory
- Complete usage examples with dummy tasks
- Understanding `UnitMetricResult` - the standardized input format
- Edge cases and best practices
- Common patterns for multi-class evaluation

## Quick Start

```python
from sygra.core.metrics.unit_metrics.unit_metric_result import UnitMetricResult
from sygra.core.metrics.aggregator_metrics.accuracy import AccuracyMetric

# Create validation results
results = [
    UnitMetricResult(correct=True, golden={'action': 'click'}, predicted={'action': 'click'}),
    UnitMetricResult(correct=False, golden={'action': 'type'}, predicted={'action': 'click'}),
]

# Calculate accuracy
metric = AccuracyMetric()
output = metric.calculate(results)
print(output)  # {'accuracy': 0.5}
```

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

