"""
Base Aggregator Metric

Abstract base class for all aggregator metrics in the evaluation system.
Aggregator metrics consume UnitMetricResults (T/F from validators) and produce
statistical measures (precision, recall, F1, accuracy, etc.).

This is a template in the sense that we define calculate() interface for subclasses to implement.
Subclasses can then implement their own calculation strategy.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from sygra.core.metrics.unit_metrics.unit_metric_result import UnitMetricResult


class BaseAggregatorMetric(ABC):
    """
    Abstract base class for all aggregator metrics.
    Aggregator metrics take a list of UnitMetricResults (boolean validation results)
    and compute statistical measures like precision, recall, F1, accuracy, etc.
    """

    @abstractmethod
    def get_metric_name(self) -> str:
        """
        Return the unique name of this metric.
        Used for registry lookup and result keys.
        Returns:
            str: Metric name (e.g., "precision", "recall", "f1")
        """
        pass

    @abstractmethod
    def calculate(self, results: List[UnitMetricResult]) -> Dict[str, Any]:
        """
        Calculate the metric from unit metric results.
        This is the core method that subclasses must implement.
        It receives validation results (T/F) and computes statistical measures.
        Args:
            results: List of UnitMetricResult objects from validators
                    Each result contains:
                    - correct: bool (overall correctness)
                    - tool_correct: bool (tool/action type correct)
                    - params_correct: bool (parameters correct)
                    - golden: dict (expected response)
                    - predicted: dict (model response)
                    - metadata: dict (mission_id, step_id, retry_number, etc.)
        Returns:
            dict: Metric results. Structure depends on metric type.
                 Examples:
                 - {"precision": 0.85}
                 - {"f1": 0.78, "per_class": {"click": 0.9, "type": 0.7}}
                 - {"confusion_matrix": {...}}
        """
        pass

    # Additional helper methods that could be common across metrics based on current flow

    def _count_correct(self, results: List[UnitMetricResult]) -> int:
        """Count number of correct results"""
        return sum(1 for r in results if r.correct)

    def _count_tool_correct(self, results: List[UnitMetricResult]) -> int:
        """Count number of results with correct tool/action"""
        return sum(1 for r in results if r.tool_correct)

    def _count_params_correct(self, results: List[UnitMetricResult]) -> int:
        """Count number of results with correct parameters"""
        return sum(1 for r in results if r.params_correct)

    def _safe_divide(self, numerator: float, denominator: float) -> float:
        """Safe division that returns 0.0 if denominator is 0"""
        return numerator / denominator if denominator > 0 else 0.0


# Define decorator for metric registration
def register_aggregator_metric(name: str):
    """
    Decorator to auto-register aggregator metrics with the registry.
    Usage:
        @register_aggregator_metric("precision")
        class PrecisionMetric(BaseAggregatorMetric):
            def calculate(self, results):
                # Implementation
                pass
    Args:
        name: Unique name for the metric (used for registry lookup)
    Returns:
        Decorator function that registers the class
    """

    def decorator(cls):
        # Import here to avoid circular dependency
        from sygra.core.metrics.aggregator_metrics.aggregator_metric_registry import (
            AggregatorMetricRegistry,
        )

        AggregatorMetricRegistry.register(name, cls)
        return cls

    return decorator
