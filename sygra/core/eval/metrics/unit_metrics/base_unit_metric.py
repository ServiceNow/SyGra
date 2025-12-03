"""
Base Unit Metric

Abstract base class for all unit metrics (validators) in the evaluation system.
Unit metrics validate individual predictions and return UnitMetricResult objects.

Key Design:
1. Common __init__(**config) signature across all unit metrics
2. Single UnitMetricConfig class (not multiple config classes)
3. Each metric validates its specific requirements in _validate_config()
4. Structured metadata following standard eval convention
5. evaluate() method returns UnitMetricResult
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List

from sygra.core.eval.metrics.base_metric_metadata import BaseMetricMetadata
from sygra.core.eval.metrics.unit_metrics.unit_metric_config import UnitMetricConfig
from sygra.core.eval.metrics.unit_metrics.unit_metric_result import UnitMetricResult


class BaseUnitMetric(ABC):
    """
    Abstract base class for all unit metrics (validators).

    All unit metrics use the same initialization pattern:
    1. __init__(**config) - common signature
    2. Config validated by UnitMetricConfig (Pydantic)
    3. Metric-specific validation in _validate_config()
    4. Metadata initialized via _get_metadata()

    Subclasses must implement:
    - _validate_config(): Validate metric-specific requirements
    - _get_metadata(): Return metric metadata
    - evaluate(): Validate a single prediction and return UnitMetricResult
    """

    def __init__(self, **config):
        """
        Common initialization for all unit metrics.

        This follows the idea of having one __init__ signature for
        all metrics, config structure being validated by pydantic and
        subclasses implementing their own validation method as required.

        Args:
            **config: Configuration parameters (validated by subclass)

        Example:
            # ExactMatch with case sensitivity
            validator = ExactMatchValidator(case_sensitive=True)

            # ExactMatch with normalization
            validator = ExactMatchValidator(normalize_whitespace=True)

            # From config dict
            config = {"case_sensitive": False, "normalize_whitespace": True}
            validator = ExactMatchValidator(**config)
        """
        # Validate config structure using Pydantic
        self.config = UnitMetricConfig(**config)

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
                # Store config as instance attributes
                self.case_sensitive = self.config.case_sensitive or False
                self.normalize_whitespace = self.config.normalize_whitespace or True
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
                    name="exact_match",
                    display_name="Exact Match",
                    description="Validates exact string match between predicted and golden values",
                    range=(0.0, 1.0),
                    higher_is_better=True,
                    metric_type="industry"
                )
        """
        pass

    @abstractmethod
    def evaluate(
        self, golden: List[Dict[str, Any]], predicted: List[Dict[str, Any]]
    ) -> List[UnitMetricResult]:
        """
        Evaluate predictions against golden references.

        This is the core method that subclasses must implement.
        It validates predictions and returns a list of UnitMetricResult objects.

        Args:
            golden: List of expected/reference responses (each is a dict with task-specific keys)
            predicted: List of model's predicted responses (each is a dict with task-specific keys)

        Returns:
            List of UnitMetricResult, one for each golden/predicted pair:
                - correct: bool (whether prediction is correct)
                - golden: dict (expected response)
                - predicted: dict (model response)
                - metadata: dict (validation details, scores, etc.)

        Raises:
            ValueError: If golden and predicted lists have different lengths

        Example:
            def evaluate(self, golden, predicted):
                if len(golden) != len(predicted):
                    raise ValueError(f"{self.__class__.__name__}: golden and predicted must have same length")

                results = []
                for g, p in zip(golden, predicted):
                    golden_text = g.get("text", "")
                    predicted_text = p.get("text", "")

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
