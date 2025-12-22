"""
Pass@k Metrics
"""

import math
from typing import Any, Dict, List

from pydantic import BaseModel, Field, field_validator

from sygra.core.eval.metrics.aggregator_metrics.aggregator_metric_registry import aggregator_metric
from sygra.core.eval.metrics.aggregator_metrics.base_aggregator_metric import BaseAggregatorMetric
from sygra.core.eval.metrics.base_metric_metadata import BaseMetricMetadata
from sygra.core.eval.metrics.unit_metrics.unit_metric_result import UnitMetricResult
from sygra.logger.logger_config import logger


class PassAtKMetricConfig(BaseModel):
    """Configuration for PassAtK Metric"""
    k: int = Field(..., description="Number of samples to draw")

    @field_validator("k")
    @classmethod
    def validate_k(cls, v):
        if v is None or v < 0:
            raise ValueError("value of k is required and must be positive (cannot be None or less than equal to 0)")
        return v


@aggregator_metric("pass@k")
class PassAtKMetric(BaseAggregatorMetric):
    """Calculate pass@k metric: probability that at least one of k independent attempts will succeed.

    Required configuration:
        k: Number of samples to draw
    """

    def __init__(self, **config):
        """Initialize F1 score metric with two-phase initialization."""
        super().__init__(**config)
        self.validate_config()
        self.metadata = self.get_metadata()

    def validate_config(self):
        """Validate and store F1-specific configuration requirements"""
        # Validate using Pydantic config class
        config_obj = PassAtKMetricConfig(**self.config)

        # Store validated fields as instance attributes
        self.k = config_obj.k

    def get_metadata(self) -> BaseMetricMetadata:
        """Return metadata for F1 score metric"""
        return BaseMetricMetadata(
            name="pass@k",
            display_name="Pass@k",
            description="Probability that at least one of k independent attempts will succeed.",
            range=(0.0, 1.0),
            higher_is_better=True,
            metric_type="industry",
        )

    def calculate(self, results: List[UnitMetricResult]) -> Dict[str, Any]:
        """Calculate  Pass@k score.

        Args:
            results: List of UnitMetricResult

        Returns:
            dict: {"pass@k": float (0.0 to 1.0)}
        """
        if not results:
            logger.warning(f"{self.__class__.__name__}: No results provided")
            return {
                "pass@k": 0.0,
            }
        # Total number of attempts/samples
        n = len(results)
        # Number of correct solutions
        c = self._count_correct(results)
        pass_at_k_value = self.pass_at_k(n, c, self.k)

        return {
            "pass@k": pass_at_k_value,
        }

    @staticmethod
    def pass_at_k(n: int, c: int, k: int) -> float:
        """Calculate pass@k metric: probability that at least one of k independent attempts will succeed.

        Args:
            n (int): Total number of attempts/samples
            c (int): Number of correct solutions
            k (int): Number of samples to draw

        Returns:
            float: Pass@k probability (0 to 1)

        Raises:
            ValueError: If invalid parameters are provided
        """
        if n <= 0 or c < 0 or k <= 0:
            raise ValueError("n and k must be positive, c must be non-negative")
        if c > n:
            raise ValueError("Number of correct solutions (c) cannot exceed total attempts (n)")
        if k > n:
            raise ValueError("Sample size (k) cannot exceed total attempts (n)")

        # If all solutions are correct, pass@k = 1
        if c == n:
            return 1.0

        # If no solutions are correct, pass@k = 0
        if c == 0:
            return 0.0

        # Calculate using the complement: 1 - P(all k samples are incorrect)
        # P(all incorrect) = C(n-c, k) / C(n, k)
        try:
            prob_all_incorrect = math.comb(n - c, k) / math.comb(n, k)
            return 1.0 - prob_all_incorrect
        except (ValueError, ZeroDivisionError):
            # Handle edge cases where combinations are invalid
            return 0.0
