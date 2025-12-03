"""
Precision Metric

Precision = TP / (TP + FP)
Measures: Of all predicted positives, how many were actually positive?
"""

from typing import Any, Dict, List

from sygra.core.eval.metrics.aggregator_metrics.aggregator_metric_registry import aggregator_metric
from sygra.core.eval.metrics.aggregator_metrics.base_aggregator_metric import BaseAggregatorMetric
from sygra.core.eval.metrics.base_metric_metadata import BaseMetricMetadata
from sygra.core.eval.metrics.unit_metrics.unit_metric_result import UnitMetricResult
from sygra.logger.logger_config import logger


@aggregator_metric("precision")
class PrecisionMetric(BaseAggregatorMetric):
    """
    Precision metric: TP / (TP + FP)

    Measures: Of all predicted positives, how many were actually positive?

    Required configuration:
        predicted_key: Key in predicted dict to check (e.g., "tool", "class")
        positive_class: Value representing positive class (e.g., "click", 1, True)
    """

    def _validate_config(self):
        """Validate precision-specific configuration requirements"""
        if not self.config.predicted_key:
            raise ValueError(f"{self.__class__.__name__}: predicted_key is required")
        if self.config.positive_class is None:
            raise ValueError(
                f"{self.__class__.__name__}: positive_class is required (cannot be None)"
            )

        # Store validated fields as instance attributes
        self.predicted_key = self.config.predicted_key
        self.positive_class = self.config.positive_class

    def _get_metadata(self) -> BaseMetricMetadata:
        """Return metadata for precision metric"""
        return BaseMetricMetadata(
            name="precision",
            display_name="Precision",
            description="Proportion of positive predictions that are actually correct (TP / (TP + FP))",
            range=(0.0, 1.0),
            higher_is_better=True,
            metric_type="industry",
        )

    def calculate(self, results: List[UnitMetricResult]) -> Dict[str, Any]:
        """
        Calculate precision.

        Args:
            results: List of UnitMetricResult

        Returns:
            dict: {"precision": float (0.0 to 1.0)}
        """
        if not results:
            logger.warning(f"{self.__class__.__name__}: No results provided")
            return {"precision": 0.0}

        # Calculate TP and FP
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
