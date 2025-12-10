"""
Precision Metric

Precision = TP / (TP + FP)
Measures: Of all predicted positives, how many were actually positive?
"""

from typing import Any, Dict, List

from pydantic import BaseModel, Field, field_validator

from sygra.core.eval.metrics.aggregator_metrics.aggregator_metric_registry import aggregator_metric
from sygra.core.eval.metrics.aggregator_metrics.base_aggregator_metric import BaseAggregatorMetric
from sygra.core.eval.metrics.base_metric_metadata import BaseMetricMetadata
from sygra.core.eval.metrics.unit_metrics.unit_metric_result import UnitMetricResult
from sygra.logger.logger_config import logger


class PrecisionMetricConfig(BaseModel):
    """Configuration for Precision Metric"""

    predicted_key: str = Field(..., min_length=1, description="Key in predicted dict to check")
    positive_class: Any = Field(..., description="Value representing positive class")

    @field_validator("positive_class")
    @classmethod
    def validate_positive_class(cls, v):
        if v is None:
            raise ValueError("positive_class is required (cannot be None)")
        return v


@aggregator_metric("precision")
class PrecisionMetric(BaseAggregatorMetric):
    """
    Precision metric: TP / (TP + FP)

    Measures: Of all predicted positives, how many were actually positive?

    Required configuration:
        predicted_key: Key in predicted dict to check (e.g., "tool")
        positive_class: Value representing the positive class (e.g., "click")
    """

    def __init__(self, **config):
        """Initialize precision metric with two-phase initialization."""
        super().__init__(**config)
        self.validate_config()
        self.metadata = self.get_metadata()

    def validate_config(self):
        """Validate and store precision-specific configuration requirements"""
        # Validate using Pydantic config class
        config_obj = PrecisionMetricConfig(**self.config)

        # Store validated fields as instance attributes
        self.predicted_key = config_obj.predicted_key
        self.positive_class = config_obj.positive_class

    def get_metadata(self) -> BaseMetricMetadata:
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
