# Metrics System - Technical Reference

> **Note**: This is a technical reference for developers working with the metrics system.

## Architecture Overview

The metrics system has two main components:

### 1. Unit Metrics
Validate individual predictions and return `UnitMetricResult` objects:
- **ExactMatchMetric**: Validates exact string match between predicted and golden values
- Supports flexible input types: dicts, strings, numbers, etc.
- Returns list of `UnitMetricResult` with `correct` (bool), `golden`, `predicted`, and `metadata`

### 2. Aggregator Metrics
Calculate statistics from lists of `UnitMetricResult` objects:
- **AccuracyMetric**: Overall correctness (no config needed)
- **PrecisionMetric**: Quality of positive predictions (requires `predicted_key`, `positive_class`)
- **RecallMetric**: Coverage of actual positives (requires `golden_key`, `positive_class`)
- **F1ScoreMetric**: Balanced precision-recall (requires `predicted_key`, `golden_key`, `positive_class`)

## Metrics Reference

| Metric | Formula | Required Parameters | Returns | Use Case |
|--------|---------|---------------------|---------|----------|
| **Accuracy** | `correct / total` | None | `{'accuracy': float}` | Overall correctness |
| **Precision** | `TP / (TP + FP)` | `predicted_key`, `positive_class` | `{'precision': float}` | Quality of positives |
| **Recall** | `TP / (TP + FN)` | `golden_key`, `positive_class` | `{'recall': float}` | Coverage of positives |
| **F1 Score** | `2 * (P * R) / (P + R)` | `predicted_key`, `golden_key`, `positive_class` | `{'f1_score': float}` | Balanced measure |

## Basic Usage

### Unit Metrics

```python
from sygra.core.eval.metrics.unit_metrics.exact_match import ExactMatchMetric

# Initialize with config
metric = ExactMatchMetric(
    case_sensitive=False,
    normalize_whitespace=True,
    key="text"  # Optional: extract specific key from dict
)

# Evaluate predictions (supports any type: dict, str, int, etc.)
results = metric.evaluate(
    golden=[{"text": "Hello World"}, {"text": "Foo"}],
    predicted=[{"text": "hello  world"}, {"text": "bar"}]
)

# Returns list of UnitMetricResult objects:
# [
#   UnitMetricResult(correct=True, golden={...}, predicted={...}, metadata={...}),
#   UnitMetricResult(correct=False, golden={...}, predicted={...}, metadata={...})
# ]
```

### Aggregator Metrics

```python
from sygra.core.eval.metrics.aggregator_metrics.accuracy import AccuracyMetric
from sygra.core.eval.metrics.aggregator_metrics.precision import PrecisionMetric
from sygra.core.eval.metrics.aggregator_metrics.recall import RecallMetric
from sygra.core.eval.metrics.aggregator_metrics.f1_score import F1ScoreMetric

# Accuracy - no config needed
accuracy = AccuracyMetric()
result = accuracy.calculate(unit_results)
# Returns: {'accuracy': 0.85}

# Precision - requires predicted_key and positive_class
precision = PrecisionMetric(
    predicted_key="tool",
    positive_class="click"
)
result = precision.calculate(unit_results)
# Returns: {'precision': 0.75}

# Recall - requires golden_key and positive_class
recall = RecallMetric(
    golden_key="event",
    positive_class="click"
)
result = recall.calculate(unit_results)
# Returns: {'recall': 0.78}

# F1 Score - requires both keys and positive_class
f1 = F1ScoreMetric(
    predicted_key="tool",
    golden_key="event",
    positive_class="click"
)
result = f1.calculate(unit_results)
# Returns: {'f1_score': 0.76}
```

### Complete Example

```python
from sygra.core.eval.metrics.unit_metrics.exact_match import ExactMatchMetric
from sygra.core.eval.metrics.aggregator_metrics.accuracy import AccuracyMetric
from sygra.core.eval.metrics.aggregator_metrics.precision import PrecisionMetric

# Step 1: Validate predictions with unit metric
validator = ExactMatchMetric(key="tool")
unit_results = validator.evaluate(
    golden=[{"tool": "click"}, {"tool": "type"}, {"tool": "click"}],
    predicted=[{"tool": "click"}, {"tool": "scroll"}, {"tool": "type"}]
)

# Step 2: Calculate statistics with aggregator metrics
accuracy = AccuracyMetric()
print(accuracy.calculate(unit_results))
# Output: {'accuracy': 0.33}

precision = PrecisionMetric(predicted_key="tool", positive_class="click")
print(precision.calculate(unit_results))
# Output: {'precision': 1.0}
```

## Creating UnitMetricResult

```python
from sygra.core.eval.metrics.unit_metrics.unit_metric_result import UnitMetricResult

result = UnitMetricResult(
    correct=True,  # Required: Was prediction correct?
    golden={'event': 'click'},  # Required: Ground truth
    predicted={'tool': 'click'},  # Required: Model prediction
    metadata={'step_id': 1}  # Optional: Additional context
)
```

## Initialization Patterns

### Direct Import (Recommended)
```python
# Import specific metrics
from sygra.core.eval.metrics.aggregator_metrics.accuracy import AccuracyMetric
from sygra.core.eval.metrics.aggregator_metrics.precision import PrecisionMetric

# Initialize with config
accuracy = AccuracyMetric()
precision = PrecisionMetric(predicted_key="tool", positive_class="click")
```

### Via Registry (Advanced)
```python
from sygra.core.eval.metrics.aggregator_metrics.aggregator_metric_registry import AggregatorMetricRegistry

# List all registered metrics
available_metrics = AggregatorMetricRegistry.list_metrics()
# Output: ['accuracy', 'f1_score', 'precision', 'recall']

# Get metric via registry
metric = AggregatorMetricRegistry.get_metric(
    "precision",
    predicted_key="tool",
    positive_class="click"
)
result = metric.calculate(unit_results)
```

### From Config Dict
```python
# Useful for dynamic configuration
config = {
    "predicted_key": "tool",
    "positive_class": "click"
}
precision = PrecisionMetric(**config)
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
# Missing parameters - raises ValidationError
PrecisionMetric()
PrecisionMetric(predicted_key="tool")
PrecisionMetric(positive_class="click")

# Empty key - raises ValidationError
PrecisionMetric(predicted_key="", positive_class="click")

# None positive_class - raises ValidationError
PrecisionMetric(predicted_key="tool", positive_class=None)
```

**Note**: All validation is handled by Pydantic, which raises `ValidationError` with detailed messages.

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
| `ValidationError: Field required` | Missing parameter | Provide all required parameters |
| `ValidationError: String should have at least 1 character` | Empty string for key | Use non-empty key name |
| `ValidationError: positive_class is required` | None for positive_class | Provide actual positive class value |
| Returns 0.0 unexpectedly | Key doesn't exist in data | Check key names match your data |
| Returns 0.0 unexpectedly | Positive class doesn't match | Check positive_class value matches data |

## Configuration Architecture

Each metric has its own Pydantic config class defined within the same module:

```python
# Inside precision.py
class PrecisionMetricConfig(BaseModel):
    predicted_key: str = Field(..., min_length=1)
    positive_class: Any = Field(...)
    
    @field_validator("positive_class")
    @classmethod
    def validate_positive_class(cls, v):
        if v is None:
            raise ValueError("positive_class is required (cannot be None)")
        return v

class PrecisionMetric(BaseAggregatorMetric):
    def validate_config(self):
        config_obj = PrecisionMetricConfig(**self.config)
        self.predicted_key = config_obj.predicted_key
        self.positive_class = config_obj.positive_class
```

**Benefits:**
- Self-contained: Each metric file has everything it needs
- Type-safe: Pydantic provides validation and clear error messages
- Extensible: Add new metrics without modifying shared config classes
