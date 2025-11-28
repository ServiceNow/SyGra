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

    def __init__(self, golden_key: str = "class", positive_class: Optional[Any] = None):
        """
        Args:
            golden_key: Key in golden dict to check (e.g., "event", "label", "class")
            positive_class: Value that represents positive class (e.g., "click", 1, True)
                          If None, we throw an error since precision is a class wise metric
                          otherwise it becomes accuracy.
        """
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

        # If positive class is not provided, raise an exception
        if self.positive_class is None:
            raise Exception(f"RecallMetric: Positive class is not provided")
        # Calculate tp, fn to compute recall
        tp = sum(1 for r in results if r.golden.get(self.golden_key) == self.positive_class and r.correct)
        fn = sum(1 for r in results if r.golden.get(self.golden_key) == self.positive_class and not r.correct)

        recall = self._safe_divide(tp, tp + fn)

        return {
            "recall": recall
        }
