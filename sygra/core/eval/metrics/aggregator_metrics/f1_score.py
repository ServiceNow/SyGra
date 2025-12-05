"""
F1 Score Metric

F1 = 2 * (Precision * Recall) / (Precision + Recall)
Harmonic mean of precision and recall.
"""

from typing import Any, Dict, List

from pydantic import BaseModel, Field, field_validator

from sygra.core.eval.metrics.aggregator_metrics.aggregator_metric_registry import aggregator_metric
from sygra.core.eval.metrics.aggregator_metrics.base_aggregator_metric import BaseAggregatorMetric
from sygra.core.eval.metrics.aggregator_metrics.precision import PrecisionMetric
from sygra.core.eval.metrics.aggregator_metrics.recall import RecallMetric
from sygra.core.eval.metrics.base_metric_metadata import BaseMetricMetadata
from sygra.core.eval.metrics.unit_metrics.unit_metric_result import UnitMetricResult
from sygra.logger.logger_config import logger


class F1ScoreMetricConfig(BaseModel):
    """Configuration for F1 Score Metric"""

    predicted_key: str = Field(..., min_length=1, description="Key in predicted dict to check")
    golden_key: str = Field(..., min_length=1, description="Key in golden dict to check")
    positive_class: Any = Field(..., description="Value representing positive class")

    @field_validator("positive_class")
    @classmethod
    def validate_positive_class(cls, v):
        if v is None:
            raise ValueError("positive_class is required (cannot be None)")
        return v


@aggregator_metric("f1_score")
class F1ScoreMetric(BaseAggregatorMetric):
    """
    F1 Score metric: 2 * (Precision * Recall) / (Precision + Recall)

    Harmonic mean of precision and recall.

    Required configuration:
        predicted_key: Key in predicted dict (e.g., "tool", "class")
        golden_key: Key in golden dict (e.g., "event", "class")
        positive_class: Value representing positive class (e.g., "click", 1, True)
    """

    def validate_config(self):
        """Validate and store F1-specific configuration requirements"""
        # Validate using Pydantic config class
        config_obj = F1ScoreMetricConfig(**self.config)

        # Store validated fields as instance attributes
        self.predicted_key = config_obj.predicted_key
        self.golden_key = config_obj.golden_key
        self.positive_class = config_obj.positive_class

        # Create precision and recall metrics (reuse implementations)
        self.precision_metric = PrecisionMetric(
            predicted_key=self.predicted_key, positive_class=self.positive_class
        )
        self.recall_metric = RecallMetric(
            golden_key=self.golden_key, positive_class=self.positive_class
        )

    def get_metadata(self) -> BaseMetricMetadata:
        """Return metadata for F1 score metric"""
        return BaseMetricMetadata(
            name="f1_score",
            display_name="F1 Score",
            description="Harmonic mean of precision and recall: 2 * (P * R) / (P + R)",
            range=(0.0, 1.0),
            higher_is_better=True,
            metric_type="industry",
        )

    def calculate(self, results: List[UnitMetricResult]) -> Dict[str, Any]:
        """
        Calculate F1 score using existing Precision and Recall implementations.

        Args:
            results: List of UnitMetricResult

        Returns:
            dict: {"f1_score": float (0.0 to 1.0)}
        """
        if not results:
            logger.warning(f"{self.__class__.__name__}: No results provided")
            return {"f1_score": 0.0}

        # Reuse existing metric implementations
        precision_result = self.precision_metric.calculate(results)
        recall_result = self.recall_metric.calculate(results)

        precision = precision_result.get("precision", 0.0)
        recall = recall_result.get("recall", 0.0)

        # Calculate F1 as harmonic mean of precision and recall
        f1_score = self._safe_divide(2 * precision * recall, precision + recall)

        return {"f1_score": f1_score}
