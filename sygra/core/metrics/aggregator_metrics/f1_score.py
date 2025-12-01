"""
F1 Score Metric

F1 = 2 * (Precision * Recall) / (Precision + Recall)
Harmonic mean of precision and recall.
"""

from typing import Any, Dict, List, Optional

from sygra.core.metrics.aggregator_metrics.base_aggregator_metric import (
    BaseAggregatorMetric,
    register_aggregator_metric,
)
from sygra.core.metrics.aggregator_metrics.precision import PrecisionMetric
from sygra.core.metrics.aggregator_metrics.recall import RecallMetric
from sygra.core.metrics.unit_metrics.unit_metric_result import UnitMetricResult
from sygra.logger.logger_config import logger


@register_aggregator_metric("f1_score")
class F1ScoreMetric(BaseAggregatorMetric):
    """
    Generic F1 score metric.

    Caller specifies positive class via keys and values.
    """

    def __init__(self, predicted_key: str, golden_key: str, positive_class: Any):
        """
        Args:
            predicted_key: Key in predicted dict (e.g., "tool", "class")
                          This is a required parameter to ensure explicit configuration.
            golden_key: Key in golden dict (e.g., "event", "class")
                       This is a required parameter to ensure explicit configuration.
            positive_class: Value representing positive class (e.g., "click", 1, True)
                          This is a required parameter since F1 is a class-wise metric.
                          Without it, the metric would be equivalent to accuracy.

        Raises:
            ValueError: If predicted_key/golden_key is empty or positive_class is None
        """
        if not predicted_key:
            raise ValueError("F1ScoreMetric: predicted_key cannot be empty")
        if not golden_key:
            raise ValueError("F1ScoreMetric: golden_key cannot be empty")
        if positive_class is None:
            raise ValueError("F1ScoreMetric: positive_class is required (cannot be None)")

        self.predicted_key = predicted_key
        self.golden_key = golden_key
        self.positive_class = positive_class

        # Reuse existing precision and recall implementations
        self.precision_metric = PrecisionMetric(
            predicted_key=predicted_key, positive_class=positive_class
        )
        self.recall_metric = RecallMetric(golden_key=golden_key, positive_class=positive_class)

    def get_metric_name(self) -> str:
        return "f1_score"

    def calculate(self, results: List[UnitMetricResult]) -> Dict[str, Any]:
        """
        Calculate F1 score using existing Precision and Recall implementations.

        Args:
            results: List of UnitMetricResult

        Returns:
            dict: {
                "f1_score": float (0.0 to 1.0)
            }
        """
        if not results:
            logger.warning("F1ScoreMetric: No results provided")
            return {"f1_score": 0.0}

        # Reuse existing metric implementations
        precision_result = self.precision_metric.calculate(results)
        recall_result = self.recall_metric.calculate(results)

        precision = precision_result.get("precision", 0.0)
        recall = recall_result.get("recall", 0.0)

        # Calculate F1 as harmonic mean of precision and recall
        f1_score = self._safe_divide(2 * precision * recall, precision + recall)

        return {"f1_score": f1_score}
