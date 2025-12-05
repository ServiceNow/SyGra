"""
Base Aggregator Metric

Abstract base class for all aggregator metrics in the evaluation system.
Aggregator metrics consume UnitMetricResults (T/F from validators) and produce
statistical measures (precision, recall, F1, accuracy, etc.).

Key Design:
1. Common __init__(**config) signature across all metrics
2. Each metric stores and validates its own configuration requirements
3. Structured metadata following standard eval convention
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List

from sygra.core.eval.metrics.base_metric_metadata import BaseMetricMetadata
from sygra.core.eval.metrics.unit_metrics.unit_metric_result import UnitMetricResult


class BaseAggregatorMetric(ABC):
    """
    Abstract base class for all aggregator metrics.

    All metrics use the same initialization pattern:
    1. __init__(**config) - common signature
    2. Each metric stores and validates its own config requirements
    3. Metadata initialized via get_metadata()

    Subclasses must implement:
    - validate_config(): Validate and store metric-specific requirements
    - get_metadata(): Return metric metadata
    - calculate(): Compute metric from results
    """

    def __init__(self, **config):
        """
        Common initialization for all metrics.

        Each metric validates and stores its own configuration requirements.

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
        # Store raw config
        self.config = config

        # Let subclass validate and store its specific requirements
        self.validate_config()

        # Initialize metadata
        self.metadata = self.get_metadata()

    @abstractmethod
    def validate_config(self):
        """
        Validate and store metric-specific configuration requirements.

        Subclasses override this to check for their required fields and store them as instance attributes.
        Should raise ValueError with clear message if validation fails.
        Use self.__class__.__name__ for consistency.

        Example:
            def validate_config(self):
                predicted_key = self.config.get("predicted_key")
                positive_class = self.config.get("positive_class")

                if not predicted_key:
                    raise ValueError(f"{self.__class__.__name__}: predicted_key is required")
                if positive_class is None:
                    raise ValueError(f"{self.__class__.__name__}: positive_class is required")

                # Store validated fields as instance attributes
                self.predicted_key = predicted_key
                self.positive_class = positive_class
        """
        pass

    @abstractmethod
    def get_metadata(self) -> BaseMetricMetadata:
        """
        Return metadata for this metric.

        Returns:
            BaseMetricMetadata with name, description, range, etc.

        Example:
            def get_metadata(self) -> BaseMetricMetadata:
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
