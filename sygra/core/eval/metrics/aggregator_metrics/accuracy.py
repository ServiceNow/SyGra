"""
Accuracy Metric
Calculates accuracy (correct predictions / total predictions) from unit metric results.
Provides overall accuracy. For specific accuracy caller needs to add code since this is standard metric.
"""

from typing import Any, Dict, List

from sygra.core.eval.metrics.aggregator_metrics.aggregator_metric_registry import aggregator_metric
from sygra.core.eval.metrics.aggregator_metrics.base_aggregator_metric import BaseAggregatorMetric
from sygra.core.eval.metrics.base_metric_metadata import BaseMetricMetadata
from sygra.core.eval.metrics.unit_metrics.unit_metric_result import UnitMetricResult
from sygra.logger.logger_config import logger


@aggregator_metric("accuracy")
class AccuracyMetric(BaseAggregatorMetric):
    """
    Accuracy metric for evaluation.

    Calculates: correct predictions / total predictions
    Generic enough to work with any task (web agents, desktop agents, etc.)

    No configuration required - works with any UnitMetricResult list.
    """

    def _validate_config(self):
        """
        Accuracy needs no configuration.
        All validation happens in the UnitMetricResult objects.
        """
        pass

    def _get_metadata(self) -> BaseMetricMetadata:
        """Return metadata for accuracy metric"""
        return BaseMetricMetadata(
            name="accuracy",
            display_name="Accuracy",
            description="Proportion of correct predictions out of total predictions",
            range=(0.0, 1.0),
            higher_is_better=True,
            metric_type="industry",
        )

    def calculate(self, results: List[UnitMetricResult]) -> Dict[str, Any]:
        """
        Calculate accuracy from unit metric results.

        Args:
            results: List of UnitMetricResult from validators

        Returns:
            dict: {"accuracy": float (0.0 to 1.0)}
        """
        if not results:
            logger.warning(f"{self.__class__.__name__}: No results provided")
            return self._empty_result()

        # Calculate overall accuracy
        total = len(results)
        correct = self._count_correct(results)
        overall_accuracy = self._safe_divide(correct, total)

        return {"accuracy": overall_accuracy}

    def _empty_result(self) -> Dict[str, Any]:
        """Return empty result structure when no results provided"""
        return {"accuracy": 0.0}
