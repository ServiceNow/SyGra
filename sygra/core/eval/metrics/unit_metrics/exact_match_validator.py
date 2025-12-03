"""
Exact Match Validator

Validates exact string match between predicted and golden values.
Supports case sensitivity and whitespace normalization options.
"""

from typing import Any, Dict, List

from sygra.core.eval.metrics.base_metric_metadata import BaseMetricMetadata
from sygra.core.eval.metrics.unit_metrics.base_unit_metric import BaseUnitMetric
from sygra.core.eval.metrics.unit_metrics.unit_metric_result import UnitMetricResult
from sygra.logger.logger_config import logger


class ExactMatchValidator(BaseUnitMetric):
    """
    Exact Match validator.

    Validates that predicted text exactly matches golden text.
    Supports configuration for case sensitivity and whitespace normalization.

    Configuration:
        case_sensitive: Whether to perform case-sensitive comparison (default: False)
        normalize_whitespace: Whether to normalize whitespace (default: True)
        key: Key in dict to extract text for comparison (default: None, compares entire dict as string)

    Example:
        # Case-insensitive with whitespace normalization (default)
        validator = ExactMatchValidator()
        results = validator.evaluate(
            golden=[{"text": "Hello World"}, {"text": "Foo"}],
            predicted=[{"text": "hello  world"}, {"text": "bar"}]
        )
        # results[0].correct = True (case-insensitive, whitespace normalized)
        # results[1].correct = False

        # Case-sensitive
        validator = ExactMatchValidator(case_sensitive=True)
        results = validator.evaluate(
            golden=[{"text": "Hello"}],
            predicted=[{"text": "hello"}]
        )
        # results[0].correct = False
    """

    def _validate_config(self):
        """Validate exact match specific configuration"""
        # Set defaults for optional config
        self.case_sensitive = (
            self.config.case_sensitive if self.config.case_sensitive is not None else False
        )
        self.normalize_whitespace = (
            self.config.normalize_whitespace
            if self.config.normalize_whitespace is not None
            else True
        )
        self.key = self.config.key  # Optional - if None, compare entire dict as string

    def _get_metadata(self) -> BaseMetricMetadata:
        """Return metadata for exact match validator"""
        return BaseMetricMetadata(
            name="exact_match",
            display_name="Exact Match",
            description="Validates exact string match between predicted and golden values",
            range=(0.0, 1.0),
            higher_is_better=True,
            metric_type="industry",
        )

    def evaluate(
        self, golden: List[Dict[str, Any]], predicted: List[Dict[str, Any]]
    ) -> List[UnitMetricResult]:
        """
        Evaluate exact match between golden and predicted values.

        Args:
            golden: List of expected responses (each is a dict)
            predicted: List of model's predicted responses (each is a dict)

        Returns:
            List of UnitMetricResult, one for each golden/predicted pair

        Raises:
            ValueError: If golden and predicted lists have different lengths
        """
        if len(golden) != len(predicted):
            raise ValueError(
                f"{self.__class__.__name__}: golden and predicted must have same length "
                f"(got {len(golden)} and {len(predicted)})"
            )

        results = []
        for g, p in zip(golden, predicted):
            try:
                # Extract text for comparison
                if self.key:
                    # Compare specific key
                    golden_text = g.get(self.key, "")
                    predicted_text = p.get(self.key, "")
                else:
                    # Compare entire dict as string
                    golden_text = str(g)
                    predicted_text = str(p)

                # Perform comparison
                is_match = self._compare_text(golden_text, predicted_text)

                results.append(
                    UnitMetricResult(
                        correct=is_match,
                        golden=g,
                        predicted=p,
                        metadata={
                            "validator": self.metadata.name,
                            "golden_text": golden_text,
                            "predicted_text": predicted_text,
                            "case_sensitive": self.case_sensitive,
                            "normalize_whitespace": self.normalize_whitespace,
                        },
                    )
                )

            except Exception as e:
                logger.error(f"{self.__class__.__name__}: Error during evaluation: {e}")
                results.append(
                    UnitMetricResult(
                        correct=False,
                        golden=g,
                        predicted=p,
                        metadata={
                            "validator": self.metadata.name,
                            "error": str(e),
                        },
                    )
                )

        return results

    def _normalize_text(self, text: str) -> str:
        """
        Normalize text based on configuration.

        Args:
            text: Text to normalize

        Returns:
            Normalized text
        """
        # Convert to string if not already
        text = str(text)

        # Normalize whitespace if configured
        if self.normalize_whitespace:
            text = text.strip()
            # Replace multiple whitespace with single space
            text = " ".join(text.split())

        # Handle case sensitivity
        if not self.case_sensitive:
            text = text.lower()

        return text

    def _compare_text(self, text1: str, text2: str) -> bool:
        """
        Compare two text strings based on configuration.

        Args:
            text1: First text to compare
            text2: Second text to compare

        Returns:
            True if texts match, False otherwise
        """
        # Ensure both are strings
        text1 = str(text1)
        text2 = str(text2)

        # Normalize both texts
        normalized_text1 = self._normalize_text(text1)
        normalized_text2 = self._normalize_text(text2)

        # Compare
        return normalized_text1 == normalized_text2
