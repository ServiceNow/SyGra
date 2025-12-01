"""
Recall Metric

Recall = TP / (TP + FN)
Measures: Of all actual positives, how many were predicted correctly?
"""

from typing import List, Dict, Any, Optional
from sygra.core.metrics.aggregator_metrics.base_aggregator_metric import (
    BaseAggregatorMetric,
    register_aggregator_metric
)
from sygra.core.metrics.unit_metrics.unit_metric_result import UnitMetricResult
from sygra.logger.logger_config import logger


@register_aggregator_metric("recall")
class RecallMetric(BaseAggregatorMetric):
    """
    Generic recall metric.

    Caller specifies positive class via golden_key and positive_class.
    """

    def __init__(self, golden_key: str, positive_class: Any):
        """
        Args:
            golden_key: Key in golden dict to check (e.g., "event", "label", "class")
                       This is a required parameter to ensure explicit configuration.
            positive_class: Value that represents positive class (e.g., "click", 1, True)
                          This is a required parameter since recall is a class-wise metric.
                          Without it, the metric would be equivalent to accuracy.
        
        Raises:
            ValueError: If golden_key is empty or positive_class is None
        """
        if not golden_key:
            raise ValueError("RecallMetric: golden_key cannot be empty")
        if positive_class is None:
            raise ValueError("RecallMetric: positive_class is required (cannot be None)")
        
        self.golden_key = golden_key
        self.positive_class = positive_class

    def get_metric_name(self) -> str:
        return "recall"

    def calculate(self, results: List[UnitMetricResult]) -> Dict[str, Any]:
        """
        Calculate recall.

        Args:
            results: List of UnitMetricResult

        Returns:
            dict: {
                "recall": float (0.0 to 1.0),
            }
        """
        if not results:
            logger.warning("RecallMetric: No results provided")
            return {
                "recall": 0.0,
            }

        # Note: positive_class validation now happens at __init__, so this is redundant
        # but kept as a safety check in case of direct attribute manipulation
        if self.positive_class is None:
            raise ValueError("RecallMetric: Positive class is not provided")
        # Calculate tp, fn to compute recall
        tp = sum(1 for r in results if r.golden.get(self.golden_key) == self.positive_class and r.correct)
        fn = sum(1 for r in results if r.golden.get(self.golden_key) == self.positive_class and not r.correct)

        recall = self._safe_divide(tp, tp + fn)

        return {
            "recall": recall
        }
