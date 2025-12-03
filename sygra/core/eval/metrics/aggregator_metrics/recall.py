"""
Recall Metric

Recall = TP / (TP + FN)
Measures: Of all actual positives, how many were predicted correctly?
"""

from typing import Any, Dict, List

from sygra.core.eval.metrics.aggregator_metrics.aggregator_metric_registry import aggregator_metric
from sygra.core.eval.metrics.aggregator_metrics.base_aggregator_metric import BaseAggregatorMetric
from sygra.core.eval.metrics.base_metric_metadata import BaseMetricMetadata
from sygra.core.eval.metrics.unit_metrics.unit_metric_result import UnitMetricResult
from sygra.logger.logger_config import logger


@aggregator_metric("recall")
class RecallMetric(BaseAggregatorMetric):
    """
    Recall metric: TP / (TP + FN)

    Measures: Of all actual positives, how many were predicted correctly?

    Required configuration:
        golden_key: Key in golden dict to check (e.g., "event", "class")
        positive_class: Value representing positive class (e.g., "click", 1, True)
    """

    def _validate_config(self):
        """Validate recall-specific configuration requirements"""
        if not self.config.golden_key:
            raise ValueError(f"{self.__class__.__name__}: golden_key is required")
        if self.config.positive_class is None:
            raise ValueError(
                f"{self.__class__.__name__}: positive_class is required (cannot be None)"
            )

        # Store validated fields as instance attributes
        self.golden_key = self.config.golden_key
        self.positive_class = self.config.positive_class

    def _get_metadata(self) -> BaseMetricMetadata:
        """Return metadata for recall metric"""
        return BaseMetricMetadata(
            name="recall",
            display_name="Recall",
            description="Proportion of actual positives that were predicted correctly (TP / (TP + FN))",
            range=(0.0, 1.0),
            higher_is_better=True,
            metric_type="industry",
        )

    def calculate(self, results: List[UnitMetricResult]) -> Dict[str, Any]:
        """
        Calculate recall.

        Args:
            results: List of UnitMetricResult

        Returns:
            dict: {"recall": float (0.0 to 1.0)}
        """
        if not results:
            logger.warning(f"{self.__class__.__name__}: No results provided")
            return {"recall": 0.0}

        # Calculate TP and FN
        tp = sum(
            1 for r in results if r.golden.get(self.golden_key) == self.positive_class and r.correct
        )
        fn = sum(
            1
            for r in results
            if r.golden.get(self.golden_key) == self.positive_class and not r.correct
        )

        recall = self._safe_divide(tp, tp + fn)
        return {"recall": recall}
