"""
Precision Metric

Precision = TP / (TP + FP)
Measures: Of all predicted positives, how many were actually positive?
"""

from typing import List, Dict, Any, Optional
from sygra.core.metrics.aggregator_metrics.base_aggregator_metric import (
    BaseAggregatorMetric,
    register_aggregator_metric
)
from sygra.core.metrics.unit_metrics.unit_metric_result import UnitMetricResult
from sygra.logger.logger_config import logger


@register_aggregator_metric("precision")
class PrecisionMetric(BaseAggregatorMetric):
    """
    Generic precision metric.

    Caller specifies positive class via predicted_key and positive_class.
    """

    def __init__(self, predicted_key: str = "class", positive_class: Optional[Any] = None):
        """
        Args:
            predicted_key: Key in predicted dict to check (e.g., "tool", "event", "class")
            positive_class: Value that represents positive class (e.g., "click", 1, True)
                          If None, we throw an error since precision is a class wise metric
                          otherwise it becomes accuracy.
        """
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

        # If positive class is not provided, raise an exception
        if self.positive_class is None:
            raise Exception(f"PrecisionMetric: Positive class is not provided")
        # We calculate tp, fp to calculate precision
        tp = sum(1 for r in results if r.predicted.get(self.predicted_key) == self.positive_class and r.correct)
        fp = sum(1 for r in results if r.predicted.get(self.predicted_key) == self.positive_class and not r.correct)

        precision = self._safe_divide(tp, tp + fp)

        return {
            "precision": precision
        }
