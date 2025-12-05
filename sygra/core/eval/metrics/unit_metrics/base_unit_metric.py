"""
Base Unit Metric

Abstract base class for all unit metrics (validators) in the evaluation system.
Unit metrics validate individual predictions and return UnitMetricResult objects.

Key Design:
1. Common __init__(**config) signature across all unit metrics
2. Each metric stores and validates its own configuration requirements
3. Structured metadata following standard eval convention
4. evaluate() method accepts lists and returns list of UnitMetricResult objects
"""

from abc import ABC, abstractmethod
from typing import Any, List

from sygra.core.eval.metrics.base_metric_metadata import BaseMetricMetadata
from sygra.core.eval.metrics.unit_metrics.unit_metric_result import UnitMetricResult


class BaseUnitMetric(ABC):
    """
    Abstract base class for all unit metrics (validators).

    All unit metrics use the same initialization pattern:
    1. __init__(**config) - common signature
    2. Each metric stores and validates its own config requirements
    3. Metadata initialized via get_metadata()

    Subclasses must implement:
    - validate_config(): Validate and store metric-specific requirements
    - get_metadata(): Return metric metadata
    - evaluate(): Validate predictions and return list of UnitMetricResult objects
    """

    def __init__(self, **config):
        """
        Common initialization for all unit metrics.

        Each metric validates and stores its own configuration requirements.

        Args:
            **config: Configuration parameters (validated by subclass)

        Example:
            # ExactMatch with case sensitivity
            metric = ExactMatchMetric(case_sensitive=True)

            # ExactMatch with normalization
            metric = ExactMatchMetric(normalize_whitespace=True)

            # From config dict
            config = {"case_sensitive": False, "normalize_whitespace": True}
            metric = ExactMatchMetric(**config)
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
                # Get config values with defaults
                self.case_sensitive = self.config.get("case_sensitive", False)
                self.normalize_whitespace = self.config.get("normalize_whitespace", True)
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
                    name="exact_match",
                    display_name="Exact Match",
                    description="Validates exact string match",
                    range=(0.0, 1.0),
                    higher_is_better=True,
                    metric_type="industry"
                )
        """
        pass

    @abstractmethod
    def evaluate(self, golden: List[Any], predicted: List[Any]) -> List[UnitMetricResult]:
        """
        Evaluate predictions against golden references.

        This is the core method that subclasses must implement.
        It validates predictions and returns a list of UnitMetricResult objects.

        Args:
            golden: List of expected/reference responses (can be any type - dict, str, int, etc.)
            predicted: List of model's predicted responses (can be any type - dict, str, int, etc.)

        Returns:
            List of UnitMetricResult, one for each golden/predicted pair:
                - correct: bool (whether prediction is correct)
                - golden: original golden value (any type)
                - predicted: original predicted value (any type)
                - metadata: dict (validation details, scores, etc.)

        Raises:
            ValueError: If golden and predicted lists have different lengths

        Example:
            def evaluate(self, golden, predicted):
                if len(golden) != len(predicted):
                    raise ValueError(f"{self.__class__.__name__}: golden and predicted must have same length")

                results = []
                for g, p in zip(golden, predicted):
                    # Check type and extract text
                    if isinstance(g, dict):
                        golden_text = g.get("text", "")
                    else:
                        golden_text = str(g)

                    if isinstance(p, dict):
                        predicted_text = p.get("text", "")
                    else:
                        predicted_text = str(p)

                    is_match = self._compare_text(golden_text, predicted_text)

                    results.append(UnitMetricResult(
                        correct=is_match,
                        golden=g,
                        predicted=p,
                        metadata={
                            "validator": self.metadata.name,
                            "golden_text": golden_text,
                            "predicted_text": predicted_text
                        }
                    ))

                return results
        """
        pass

    def get_metric_name(self) -> str:
        """
        Return the unique name of this metric.

        Gets name from metadata for consistency.

        Returns:
            str: Metric name (e.g., "exact_match", "bbox_iou")
        """
        return self.metadata.name
