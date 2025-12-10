"""
Recall Metric

Recall = TP / (TP + FN)
Measures: Of all actual positives, how many were predicted correctly?
"""

from typing import Any, Dict, List

from pydantic import BaseModel, Field, field_validator

from sygra.core.eval.metrics.aggregator_metrics.aggregator_metric_registry import aggregator_metric
from sygra.core.eval.metrics.aggregator_metrics.base_aggregator_metric import BaseAggregatorMetric
from sygra.core.eval.metrics.base_metric_metadata import BaseMetricMetadata
from sygra.core.eval.metrics.unit_metrics.unit_metric_result import UnitMetricResult
from sygra.logger.logger_config import logger


class RecallMetricConfig(BaseModel):
    """Configuration for Recall Metric"""

    golden_key: str = Field(..., min_length=1, description="Key in golden dict to check")
    positive_class: Any = Field(..., description="Value representing positive class")

    @field_validator("positive_class")
    @classmethod
    def validate_positive_class(cls, v):
        if v is None:
            raise ValueError("positive_class is required (cannot be None)")
        return v


@aggregator_metric("recall")
class RecallMetric(BaseAggregatorMetric):
    """
    Recall metric: TP / (TP + FN)

    Measures: Of all actual positives, how many were predicted correctly?

    Required configuration:
        golden_key: Key in golden dict to check (e.g., "event")
        positive_class: Value representing the positive class (e.g., "click")
    """

    def __init__(self, **config):
        """Initialize recall metric with two-phase initialization."""
        super().__init__(**config)
        self.validate_config()
        self.metadata = self.get_metadata()

    def validate_config(self):
        """Validate and store recall-specific configuration requirements"""
        # Validate using Pydantic config class
        config_obj = RecallMetricConfig(**self.config)

        # Store validated fields as instance attributes
        self.golden_key = config_obj.golden_key
        self.positive_class = config_obj.positive_class

    def get_metadata(self) -> BaseMetricMetadata:
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
