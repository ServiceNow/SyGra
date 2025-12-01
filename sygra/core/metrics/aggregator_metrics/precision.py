"""
Precision Metric

Precision = TP / (TP + FP)
Measures: Of all predicted positives, how many were actually positive?
"""

from typing import Any, Dict, List

from sygra.core.metrics.aggregator_metrics.base_aggregator_metric import (
    BaseAggregatorMetric,
    register_aggregator_metric,
)
from sygra.core.metrics.unit_metrics.unit_metric_result import UnitMetricResult
from sygra.logger.logger_config import logger


@register_aggregator_metric("precision")
class PrecisionMetric(BaseAggregatorMetric):
    """
    Generic precision metric.

    Caller specifies positive class via predicted_key and positive_class.
    """

    def __init__(self, predicted_key: str, positive_class: Any):
        """
        Args:
            predicted_key: Key in predicted dict to check (e.g., "tool", "event", "class")
                          This is a required parameter to ensure explicit configuration.
            positive_class: Value that represents positive class (e.g., "click", 1, True)
                          This is a required parameter since precision is a class-wise metric.
                          Without it, the metric would be equivalent to accuracy.

        Raises:
            ValueError: If predicted_key is empty or positive_class is None
        """
        if not predicted_key:
            raise ValueError("PrecisionMetric: predicted_key cannot be empty")
        if positive_class is None:
            raise ValueError("PrecisionMetric: positive_class is required (cannot be None)")

        self.predicted_key = predicted_key
        self.positive_class = positive_class

    def get_metric_name(self) -> str:
        return "precision"

    def calculate(self, results: List[UnitMetricResult]) -> Dict[str, Any]:
        """
        Calculate precision.
        Args:
            results: List of UnitMetricResult
        Returns:
            dict: {
                "precision": float (0.0 to 1.0)
            }
        """
        if not results:
            logger.warning("PrecisionMetric: No results provided")
            return {
                "precision": 0.0,
            }

        # Note: positive_class validation now happens at __init__, so this is redundant
        # but kept as a safety check in case of direct attribute manipulation
        if self.positive_class is None:
            raise ValueError("PrecisionMetric: Positive class is not provided")
        # We calculate tp, fp to calculate precision
        tp = sum(
            1
            for r in results
            if r.predicted.get(self.predicted_key) == self.positive_class and r.correct
        )
        fp = sum(
            1
            for r in results
            if r.predicted.get(self.predicted_key) == self.positive_class and not r.correct
        )

        precision = self._safe_divide(tp, tp + fp)

        return {"precision": precision}
