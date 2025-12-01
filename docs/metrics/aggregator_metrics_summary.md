# Aggregator Metrics - Quick Reference

## At a Glance

| Metric | Formula | Required Parameters | Returns | Use Case |
|--------|---------|---------------------|---------|----------|
| **Accuracy** | `correct / total` | None | `{'accuracy': float}` | Overall correctness |
| **Precision** | `TP / (TP + FP)` | `predicted_key`, `positive_class` | `{'precision': float}` | Quality of positives |
| **Recall** | `TP / (TP + FN)` | `golden_key`, `positive_class` | `{'recall': float}` | Coverage of positives |
| **F1 Score** | `2 * (P * R) / (P + R)` | `predicted_key`, `golden_key`, `positive_class` | `{'f1_score': float}` | Balanced measure |

## Quick Examples

### Accuracy
```python
from sygra.core.metrics.aggregator_metrics.accuracy import AccuracyMetric

metric = AccuracyMetric()
result = metric.calculate(validation_results)
# {'accuracy': 0.85}
```

### Precision
```python
from sygra.core.metrics.aggregator_metrics.precision import PrecisionMetric

metric = PrecisionMetric(
    predicted_key="tool",      # What key to check in predicted dict
    positive_class="click"     # What value is "positive"
)
result = metric.calculate(validation_results)
# {'precision': 0.75}
```

### Recall
```python
from sygra.core.metrics.aggregator_metrics.recall import RecallMetric

metric = RecallMetric(
    golden_key="event",        # What key to check in golden dict
    positive_class="click"     # What value is "positive"
)
result = metric.calculate(validation_results)
# {'recall': 0.80}
```

### F1 Score
```python
from sygra.core.metrics.aggregator_metrics.f1_score import F1ScoreMetric

metric = F1ScoreMetric(
    predicted_key="tool",      # Key in predicted dict
    golden_key="event",        # Key in golden dict
    positive_class="click"     # What value is "positive"
)
result = metric.calculate(validation_results)
# {'f1_score': 0.77}
```

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

## Common Patterns

### Pattern 1: Calculate All Metrics
```python
results = [...]  # List of UnitMetricResult

accuracy = AccuracyMetric().calculate(results)
precision = PrecisionMetric("tool", "click").calculate(results)
recall = RecallMetric("event", "click").calculate(results)
f1 = F1ScoreMetric("tool", "event", "click").calculate(results)

print(f"Accuracy:  {accuracy['accuracy']:.2%}")
print(f"Precision: {precision['precision']:.2%}")
print(f"Recall:    {recall['recall']:.2%}")
print(f"F1 Score:  {f1['f1_score']:.2%}")
```

### Pattern 2: Multi-Class Evaluation
```python
classes = ["click", "type", "scroll"]

for cls in classes:
    f1 = F1ScoreMetric("tool", "event", cls)
    score = f1.calculate(results)['f1_score']
    print(f"{cls}: {score:.2%}")
```

### Pattern 3: Using Registry
```python
from sygra.core.metrics.aggregator_metrics.aggregator_metric_registry import AggregatorMetricRegistry

# List available metrics
print(AggregatorMetricRegistry.list_metrics())
# ['accuracy', 'f1_score', 'precision', 'recall']

# Get metric by name
metric = AggregatorMetricRegistry.get_metric(
    "precision",
    predicted_key="tool",
    positive_class="click"
)
```

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
