# Unit Metrics - Technical Reference

> **Note**: This is a technical reference for developers working with unit metrics (validators).

## Architecture Overview

Unit metrics validate individual predictions and return `UnitMetricResult` objects.

- **Input**: Two lists of equal length: `golden` and `predicted`
- **Output**: A list of `UnitMetricResult` objects, one per golden/predicted pair
- **Core output signal**: `UnitMetricResult.correct` (bool) - whether the prediction passed validation (`True/False`)

Unit metrics are designed to be:
- Modular (each metric in its own module)
- Extensible (easy to add new validators)
- Task-agnostic (inputs can be any type; validation logic decides how to interpret them)

## Unit Metrics Reference

| Metric | Purpose | Typical Inputs | Returns | Notes |
|--------|---------|----------------|---------|-------|
| **ExactMatchMetric** | Exact string equality check | dict/string/any | `List[UnitMetricResult]` | Supports case sensitivity + whitespace normalization; optional key extraction |
| **ActionWithinBboxMetric** | Validate predicted `(x, y)` inside golden bbox | dicts with bbox + coordinates | `List[UnitMetricResult]` | Bbox expects `x, y, width, height` |
| **TypedValueMatchMetric** | Validate typed value using exact + fuzzy matching | dicts with typed strings | `List[UnitMetricResult]` | Returns `True` if exact or fuzzy passes |
| **ScrollDirectionMetric** | Validate scroll direction matches golden | dicts with direction | `List[UnitMetricResult]` | Valid directions: `up/down/left/right` |
| **ScrollAmountMetric** | Validate scroll amount within tolerance | dicts with numeric amount | `List[UnitMetricResult]` | Percentage tolerance; special-case for golden `0` |

## Basic Usage

### Unit Metrics

```python
from sygra.core.eval.metrics.unit_metrics.exact_match import ExactMatchMetric

metric = ExactMatchMetric(
    case_sensitive=False,
    normalize_whitespace=True,
    key="text",
)

results = metric.evaluate(
    golden=[{"text": "Hello World"}, {"text": "Foo"}],
    predicted=[{"text": "hello  world"}, {"text": "bar"}],
)

# results = [
#   UnitMetricResult(correct=True, golden={...}, predicted={...}, metadata={...}),
#   UnitMetricResult(correct=False, golden={...}, predicted={...}, metadata={...})
# ]
```

### How Unit Metrics and Aggregator Metrics Work Together

```python
from sygra.core.eval.metrics.unit_metrics.exact_match import ExactMatchMetric
from sygra.core.eval.metrics.aggregator_metrics.accuracy import AccuracyMetric

validator = ExactMatchMetric(key="tool")
unit_results = validator.evaluate(
    golden=[{"tool": "click"}, {"tool": "type"}],
    predicted=[{"tool": "click"}, {"tool": "scroll"}],
)

accuracy = AccuracyMetric()
print(accuracy.calculate(unit_results))
# Output: {'accuracy': 0.5}
```

## Creating UnitMetricResult

```python
from sygra.core.eval.metrics.unit_metrics.unit_metric_result import UnitMetricResult

result = UnitMetricResult(
    correct=True,
    golden={"event": "click"},
    predicted={"tool": "click"},
    metadata={"step_id": 1},
)
```

## Initialization Patterns

### Direct Import (Recommended)

```python
from sygra.core.eval.metrics.unit_metrics.typed_value_match import TypedValueMatchMetric

metric = TypedValueMatchMetric(
    golden_text_key="text",
    predicted_text_key="text",
    fuzzy_match_threshold=0.8,
)
```

### From Config Dict

```python
from sygra.core.eval.metrics.unit_metrics.scroll_amount import ScrollAmountMetric

config = {
    "tolerance_percent": 20.0,
    "scroll_threshold": 10.0,
}
metric = ScrollAmountMetric(**config)
```

## Parameter Validation

Each unit metric defines its own Pydantic config class in the same module. Validation errors come from Pydantic and surface as `ValidationError`.

### ✅ Valid Initialization

```python
from sygra.core.eval.metrics.unit_metrics.action_within_bbox import ActionWithinBboxMetric

ActionWithinBboxMetric(predicted_x_key="x", predicted_y_key="y", golden_bbox_key="bbox")
```

### ❌ Invalid Initialization

```python
from sygra.core.eval.metrics.unit_metrics.typed_value_match import TypedValueMatchMetric

# threshold out of range -> ValidationError
TypedValueMatchMetric(fuzzy_match_threshold=1.5)
```

## Common Issues

| Symptom | Cause | Solution |
|--------|-------|----------|
| `ValueError: golden and predicted must have same length` | Input list lengths mismatch | Ensure both lists align per-item |
| Always returns `correct=False` | Key mismatch or unexpected input shape | Confirm keys (`*_key`) match your data |
| Fuzzy match passes unexpectedly | Threshold too low | Increase `fuzzy_match_threshold` |

## Configuration Architecture

Each metric file is self-contained and includes:
- A Pydantic config model (`*MetricConfig`)
- The metric implementation (`*Metric`)
- Helper methods for normalization / comparison

This keeps metrics modular and makes it easy to add additional validators without modifying shared config classes.
