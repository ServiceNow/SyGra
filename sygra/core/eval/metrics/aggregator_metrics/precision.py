"""
Precision Metric

Precision = TP / (TP + FP)
Measures: Of all predicted positives, how many were actually positive?
"""

from collections import defaultdict
from typing import Any, DefaultDict, Dict, List

from pydantic import BaseModel, Field

from sygra.core.eval.metrics.aggregator_metrics.aggregator_metric_registry import aggregator_metric
from sygra.core.eval.metrics.aggregator_metrics.base_aggregator_metric import BaseAggregatorMetric
from sygra.core.eval.metrics.base_metric_metadata import BaseMetricMetadata
from sygra.core.eval.metrics.unit_metrics.unit_metric_result import UnitMetricResult
from sygra.logger.logger_config import logger


class PrecisionMetricConfig(BaseModel):
    """Configuration for Precision Metric"""

    predicted_key: str = Field(..., min_length=1, description="Key in predicted dict to check")


@aggregator_metric("precision")
class PrecisionMetric(BaseAggregatorMetric):
    """
    Precision metric: TP / (TP + FP)

    Measures: Of all predicted positives, how many were actually positive?

    Required configuration:
        predicted_key: Key in predicted dict to check (e.g., "tool")
    """

    def __init__(self, **config):
        """Initialize precision metric with two-phase initialization."""
        super().__init__(**config)
        self.predicted_key = None
        self.validate_config()
        self.metadata = self.get_metadata()

    def validate_config(self):
        """Validate and store precision-specific configuration requirements"""
        # Validate using Pydantic config class
        config_obj = PrecisionMetricConfig(**self.config)

        # Store validated fields as instance attributes
        self.predicted_key = config_obj.predicted_key

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
            dict: {
            "average_precision": float (0.0 to 1.0)
            "precision_per_class": {
                "class_1": float (0.0 to 1.0),
                "class_2": float (0.0 to 1.0),
                ...
                "class_n": float (0.0 to 1.0)
            }
            }
        """
        if not results:
            logger.warning(f"{self.__class__.__name__}: No results provided")
            return {"average_precision": 0.0, "precision_per_class": {}}

        predicted_count: DefaultDict[str, int] = defaultdict(int)
        true_positive: DefaultDict[str, int] = defaultdict(int)

        for r in results:
            try:
                predicted_key = self.predicted_key
                if predicted_key is None:
                    logger.warning(f"{self.__class__.__name__}: predicted_key is not configured")
                    continue
                label = r.predicted[predicted_key]
            except KeyError:
                logger.warning(
                    f"{self.__class__.__name__}: Missing predicted_key '{self.predicted_key}' in result"
                )
                continue

            if not isinstance(label, str):
                label = str(label)

            predicted_count[label] += 1
            if r.correct:
                true_positive[label] += 1

        precision_per_class = {
            label: self._safe_divide(true_positive[label], count)
            for label, count in predicted_count.items()
        }

        average_precision = self._safe_divide(
            sum(precision_per_class.values()),
            len(precision_per_class),
        )

        return {
            "average_precision": average_precision,
            "precision_per_class": precision_per_class,
        }
