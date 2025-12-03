"""
Base Aggregator Metric

Abstract base class for all aggregator metrics in the evaluation system.
Aggregator metrics consume UnitMetricResults (T/F from validators) and produce
statistical measures (precision, recall, F1, accuracy, etc.).

Key Refactoring:
1. Common __init__(**config) signature across all metrics
2. Single AggregatorMetricConfig class (not multiple config classes)
3. Each metric validates its specific requirements in _validate_config()
4. Structured metadata following standard eval convention
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List

from sygra.core.eval.metrics.aggregator_metrics.aggregator_metric_config import (
    AggregatorMetricConfig,
)
from sygra.core.eval.metrics.base_metric_metadata import BaseMetricMetadata
from sygra.core.eval.metrics.unit_metrics.unit_metric_result import UnitMetricResult


class BaseAggregatorMetric(ABC):
    """
    Abstract base class for all aggregator metrics.

    All metrics use the same initialization pattern:
    1. __init__(**config) - common signature
    2. Config validated by AggregatorMetricConfig (Pydantic)
    3. Metric-specific validation in _validate_config()
    4. Metadata initialized via _get_metadata()

    Subclasses must implement:
    - _validate_config(): Validate metric-specific requirements
    - _get_metadata(): Return metric metadata
    - calculate(): Compute metric from results
    """

    def __init__(self, **config):
        """
        Common initialization for all metrics.

        This follows the idea of having one __init__ signature for
        all metrics, config structure being validated by pydantic and
        subclasses implementing their own validation method as required.

        Args:
            **config: Configuration parameters (validated by subclass)

        Example:
            # Precision
            metric = PrecisionMetric(predicted_key="tool", positive_class="click")

            # Accuracy (no config needed)
            metric = AccuracyMetric()

            # From config dict
            config = {"predicted_key": "tool", "positive_class": "click"}
            metric = PrecisionMetric(**config)
        """
        # Validate config structure using Pydantic
        self.config = AggregatorMetricConfig(**config)

        # Let subclass validate its specific requirements
        self._validate_config()

        # Initialize metadata
        self.metadata = self._get_metadata()

    @abstractmethod
    def _validate_config(self):
        """
        Validate metric-specific configuration requirements.

        Subclasses override this to check for their required fields.
        Should raise ValueError with clear message if validation fails.
        Use self.__class__.__name__ for consistency.

        Example:
            def _validate_config(self):
                if not self.config.predicted_key:
                    raise ValueError(f"{self.__class__.__name__}: predicted_key is required")
                if self.config.positive_class is None:
                    raise ValueError(f"{self.__class__.__name__}: positive_class is required")

                # Store validated fields as instance attributes
                self.predicted_key = self.config.predicted_key
                self.positive_class = self.config.positive_class
        """
        pass

    @abstractmethod
    def _get_metadata(self) -> BaseMetricMetadata:
        """
        Return metadata for this metric.

        Returns:
            BaseMetricMetadata with name, description, range, etc.

        Example:
            def _get_metadata(self) -> BaseMetricMetadata:
                return BaseMetricMetadata(
                    name="precision",
                    display_name="Precision",
                    description="Proportion of positive predictions that are correct",
                    range=(0.0, 1.0),
                    higher_is_better=True,
                    metric_type="industry"
                )
        """
        pass

    @abstractmethod
    def calculate(self, results: List[UnitMetricResult]) -> Dict[str, Any]:
        """
        Calculate the metric from unit metric results.
        This is the core method that subclasses must implement.
        It receives validation results (T/F) and computes statistical measures.
        Args:
            results: List of UnitMetricResult objects from validators
                    Each result contains:
                    - correct: bool (overall correctness)
                    - golden: dict (expected response)
                    - predicted: dict (model response)
                    - metadata: dict (mission_id, step_id, retry_number, etc.)
        Returns:
            dict: Metric results. Structure depends on metric type.
                 Examples:
                 - {"precision": 0.85}
                 - {"f1": 0.78, "per_class": {"click": 0.9, "type": 0.7}}
                 - {"confusion_matrix": {...}}
        """
        pass

    def get_metric_name(self) -> str:
        """
        Return the unique name of this metric.

        Gets name from metadata for consistency.

        Returns:
            str: Metric name (e.g., "precision", "recall", "f1")
        """
        return self.metadata.name

    # Helper methods common across metrics

    def _count_correct(self, results: List[UnitMetricResult]) -> int:
        """Count number of correct results"""
        return sum(1 for r in results if r.correct)

    def _safe_divide(self, numerator: float, denominator: float) -> float:
        """Safe division that returns 0.0 if denominator is 0"""
        return numerator / denominator if denominator != 0 else 0.0
