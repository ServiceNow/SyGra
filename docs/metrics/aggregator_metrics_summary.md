# Aggregator Metrics - Technical Reference

> **Note**: This is a technical reference for platform developers. End users only need to list metric names in `graph_config.yaml`.

## Architecture Overview

Aggregator metrics are **low-level primitives** that calculate metrics for a **single class** at a time. They require explicit parameters (predicted_key, golden_key, positive_class) which are provided by **platform orchestration code**, not by end users.

**Two-Layer Design:**
1. **Aggregator Metrics** (this module) - Calculate for one class with explicit params
2. **Platform Code** (graph execution layer) - Discovers classes, iterates, calls metrics

## Metrics Reference

| Metric | Formula | Required Parameters | Returns | Use Case |
|--------|---------|---------------------|---------|----------|
| **Accuracy** | `correct / total` | None | `{'accuracy': float}` | Overall correctness |
| **Precision** | `TP / (TP + FP)` | `predicted_key`, `positive_class` | `{'precision': float}` | Quality of positives |
| **Recall** | `TP / (TP + FN)` | `golden_key`, `positive_class` | `{'recall': float}` | Coverage of positives |
| **F1 Score** | `2 * (P * R) / (P + R)` | `predicted_key`, `golden_key`, `positive_class` | `{'f1_score': float}` | Balanced measure |

## End User Configuration

Users only specify which metrics they want:

```yaml
# graph_config.yaml
graph_properties:
  metrics:
    - "accuracy"
    - "precision"
    - "recall"
    - "f1_score"
```

## Platform Code Responsibility

Platform code (to be implemented in graph execution layer) handles:

### 1. Class Discovery
```python
def discover_classes(validation_results):
    """Extract all unique classes from validation results."""
    predicted_classes = set()
    golden_classes = set()
    
    for result in validation_results:
        if 'tool' in result.predicted:
            predicted_classes.add(result.predicted['tool'])
        if 'event' in result.golden:
            golden_classes.add(result.golden['event'])
    
    return predicted_classes.union(golden_classes)
```

### 2. Metric Orchestration
```python
from sygra.core.metrics.aggregator_metrics.aggregator_metric_registry import AggregatorMetricRegistry

def run_evaluation(validation_results, metric_names):
    """
    Platform orchestration layer.
    User provides: ["accuracy", "precision", "recall"]
    Platform handles: class iteration, parameter passing
    """
    # Discover classes from data
    classes = discover_classes(validation_results)  # ["click", "type", "scroll"]
    
    results = {}
    
    for metric_name in metric_names:
        if metric_name == "accuracy":
            # Accuracy is class-agnostic
            metric = AggregatorMetricRegistry.get_metric("accuracy")
            results["accuracy"] = metric.calculate(validation_results)
        
        elif metric_name == "precision":
            # Platform iterates over all classes
            results["precision"] = {}
            for cls in classes:
                metric = AggregatorMetricRegistry.get_metric(
                    "precision",
                    predicted_key="tool",  # Platform knows task structure
                    positive_class=cls      # Platform iterates classes
                )
                results["precision"][cls] = metric.calculate(validation_results)
        
        elif metric_name == "recall":
            results["recall"] = {}
            for cls in classes:
                metric = AggregatorMetricRegistry.get_metric(
                    "recall",
                    golden_key="event",
                    positive_class=cls
                )
                results["recall"][cls] = metric.calculate(validation_results)
        
        elif metric_name == "f1_score":
            results["f1_score"] = {}
            for cls in classes:
                metric = AggregatorMetricRegistry.get_metric(
                    "f1_score",
                    predicted_key="tool",
                    golden_key="event",
                    positive_class=cls
                )
                results["f1_score"][cls] = metric.calculate(validation_results)
    
    return results

# Example Output:
# {
#   "accuracy": {"accuracy": 0.85},
#   "precision": {
#     "click": 0.75,
#     "type": 0.80,
#     "scroll": 0.70
#   },
#   "recall": {
#     "click": 0.78,
#     "type": 0.82,
#     "scroll": 0.68
#   },
#   "f1_score": {
#     "click": 0.76,
#     "type": 0.81,
#     "scroll": 0.69
#   }
# }
```

**Key Point**: Platform code discovers classes and iterates. Metrics are just building blocks.

## Creating UnitMetricResult

```python
from sygra.core.metrics.unit_metrics.unit_metric_result import UnitMetricResult

result = UnitMetricResult(
    correct=True,                          # Required: Was prediction correct?
    golden={'event': 'click'},            # Required: Ground truth
    predicted={'tool': 'click'},          # Required: Model prediction
    metadata={'step_id': 1}               # Optional: Additional context
)
```

## Registry Usage (For Platform Developers)

### Discovering Available Metrics
```python
from sygra.core.metrics.aggregator_metrics.aggregator_metric_registry import AggregatorMetricRegistry

# List all registered metrics
available_metrics = AggregatorMetricRegistry.list_metrics()
print(available_metrics)
# Output: ['accuracy', 'f1_score', 'precision', 'recall']

# Check if specific metric exists
if AggregatorMetricRegistry.has_metric("precision"):
    print("Precision metric is available")

# Get metric info
info = AggregatorMetricRegistry.get_metrics_info()
# Returns: {'precision': {'class': 'PrecisionMetric', 'module': '...'}}
```

### Direct Instantiation (Low-Level)
```python
# Platform code instantiates metrics with explicit parameters
metric = AggregatorMetricRegistry.get_metric(
    "precision",
    predicted_key="tool",
    positive_class="click"
)

# Calculate for validation results
output = metric.calculate(validation_results)
# Returns: {'precision': 0.75}
```

**Note**: End users never call these methods directly. Platform code handles it.

## Parameter Validation

### ✅ Valid Initialization
```python
# All required parameters provided
PrecisionMetric(predicted_key="tool", positive_class="click")
RecallMetric(golden_key="event", positive_class="click")
F1ScoreMetric(predicted_key="tool", golden_key="event", positive_class="click")
```

### ❌ Invalid Initialization
```python
# Missing parameters - raises TypeError
PrecisionMetric()
PrecisionMetric(predicted_key="tool")
PrecisionMetric(positive_class="click")

# Empty key - raises ValueError
PrecisionMetric(predicted_key="", positive_class="click")

# None positive_class - raises ValueError
PrecisionMetric(predicted_key="tool", positive_class=None)
```

## Edge Cases

### Empty Results
```python
metric = AccuracyMetric()
result = metric.calculate([])
# Returns: {'accuracy': 0.0}
```

### No Positive Predictions
```python
metric = PrecisionMetric("tool", "click")
results = [
    UnitMetricResult(correct=True, golden={'event': 'type'}, predicted={'tool': 'type'})
]
result = metric.calculate(results)
# Returns: {'precision': 0.0}  (no clicks predicted)
```

### No Actual Positives
```python
metric = RecallMetric("event", "click")
results = [
    UnitMetricResult(correct=True, golden={'event': 'type'}, predicted={'tool': 'type'})
]
result = metric.calculate(results)
# Returns: {'recall': 0.0}  (no clicks in ground truth)
```

## Confusion Matrix Reference

For binary classification with positive class "click":

|                    | Predicted: click | Predicted: other |
|--------------------|------------------|------------------|
| **Actual: click**  | TP (correct=True) | FN (correct=False) |
| **Actual: other**  | FP (correct=False) | TN (correct=True) |

- **TP (True Positive)**: Predicted click, actually click, correct=True
- **FP (False Positive)**: Predicted click, actually other, correct=False
- **FN (False Negative)**: Predicted other, actually click, correct=False
- **TN (True Negative)**: Predicted other, actually other, correct=True

**Precision** = TP / (TP + FP) - "Of predicted positives, how many were right?"
**Recall** = TP / (TP + FN) - "Of actual positives, how many did we find?"

## Recommended Practices

1. **Always specify parameters explicitly** - No defaults to prevent bugs
2. **Use F1 when precision and recall matter equally** - Balances both metrics
3. **Check for empty results** - All metrics return 0.0 for empty lists
4. **Metadata is optional** - Use it for tracking but not required for calculations
5. **Keys can be any string** - "tool", "action", "class", "label", etc.
6. **Positive class can be any type** - String, int, bool, etc.

## Common Issues

| Error | Cause | Solution |
|-------|-------|----------|
| `TypeError: missing required argument` | Missing parameter | Provide all required parameters |
| `ValueError: predicted_key cannot be empty` | Empty string for key | Use non-empty key name |
| `ValueError: positive_class is required` | None for positive_class | Provide actual positive class value |
| Returns 0.0 unexpectedly | Key doesn't exist in data | Check key names match your data |
| Returns 0.0 unexpectedly | Positive class doesn't match | Check positive_class value matches data |
