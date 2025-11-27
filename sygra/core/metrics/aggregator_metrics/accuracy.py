"""
Accuracy Metric
Calculates accuracy (correct predictions / total predictions) from unit metric results.
Provides overall accuracy. For specific accuracy caller needs to add code since this is standard metric.
"""

from collections import defaultdict
from typing import Any, Dict, List

from sygra.core.metrics.aggregator_metrics.base_aggregator_metric import (
    BaseAggregatorMetric,
    register_aggregator_metric,
)
from sygra.core.metrics.unit_metrics.unit_metric_result import UnitMetricResult
from sygra.logger.logger_config import logger


# Register the metric using decorator
@register_aggregator_metric("accuracy")
class AccuracyMetric(BaseAggregatorMetric):
    """
    Accuracy metric for evaluation.
    Calculates:
    - Generic accuracy across given list of values
    - Generic enough to work with any task (web agents, desktop agents, etc.)
    """

    def get_metric_name(self) -> str:
        return "accuracy"

    def calculate(self, results: List[UnitMetricResult]) -> Dict[str, Any]:
        """
        Calculate accuracy from unit metric results.
        Args:
            results: List of UnitMetricResult from validators
        Returns:
            dict: {
                "accuracy": float,
            }
        """
        if not results:
            logger.warning("AccuracyMetric: No results provided")
            return self._empty_result()
        # Overall accuracy
        total = len(results)
        correct = self._count_correct(results)
        overall_accuracy = self._safe_divide(correct, total)
        result = {
            "accuracy": overall_accuracy,
        }
        return result

    # Method to default to empty result structure if UnitMetricResult list is empty
    def _empty_result(self) -> Dict[str, Any]:
        """Return empty result structure"""
        result = {
            "accuracy": 0.0,
        }
        return result
