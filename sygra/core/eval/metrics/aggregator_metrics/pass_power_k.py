"""
Pass^K Metrics
"""

from typing import Any, Dict, List

from sygra.core.eval.metrics.aggregator_metrics.aggregator_metric_registry import aggregator_metric
from sygra.core.eval.metrics.aggregator_metrics.base_aggregator_metric import BaseAggregatorMetric
from sygra.core.eval.metrics.aggregator_metrics.pass_at_k import PassAtKMetricConfig
from sygra.core.eval.metrics.base_metric_metadata import BaseMetricMetadata
from sygra.core.eval.metrics.unit_metrics.unit_metric_result import UnitMetricResult
from sygra.logger.logger_config import logger


@aggregator_metric("pass^k")
class PassPowerKMetric(BaseAggregatorMetric):
    """Calculate pass^k metric: probability that an agent would succeed on all k independent attempts.

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
            name="pass^k",
            display_name="Pass^k",
            description="Probability that an agent would succeed on all k independent attempts.",
            range=(0.0, 1.0),
            higher_is_better=True,
            metric_type="industry",
        )

    def calculate(self, results: List[UnitMetricResult]) -> Dict[str, Any]:
        """Calculate Pass^k score.

        Args:
            results: List of UnitMetricResult

        Returns:
            dict: Dictionary containing metrics and related information
                 {"success_rate": float (0.0 to 1.0), "pass^k": float (0.0 to 1.0)}
        """
        if not results:
            logger.warning(f"{self.__class__.__name__}: No results provided")
            return {
                "success_rate": 0.0,
                "pass^k": 0.0
            }
        # Total number of attempts/samples
        n = len(results)
        # Number of correct solutions
        c = self._count_correct(results)
        success_rate = self.calculate_success_rate(n, c)
        pass_power_k_value = self.pass_power_k(success_rate, self.k)

        return {
            "success_rate": success_rate,
            "pass^k": pass_power_k_value
        }

    @staticmethod
    def pass_power_k(success_rate: float, k: int) -> float:
        """Calculate pass^k metric: probability that an agent would succeed on all k independent attempts.

        Args:
            success_rate (float): Raw success rate on a single attempt (0 to 1)
            k (int): Number of consecutive attempts

        Returns:
            float: Pass^k probability (0 to 1)

        Raises:
            ValueError: If invalid parameters are provided
        """
        if not 0 <= success_rate <= 1:
            raise ValueError("Success rate must be between 0 and 1")
        if k <= 0:
            raise ValueError("k must be positive")

        return success_rate ** k

    @staticmethod
    def calculate_success_rate(n: int, c: int) -> float:
        """Calculate raw success rate from total attempts and correct solutions.

        Args:
            n (int): Total number of attempts
            c (int): Number of correct solutions

        Returns:
            float: Success rate (0 to 1)
        """
        if n <= 0:
            raise ValueError("Total attempts (n) must be positive")
        if c < 0:
            raise ValueError("Correct solutions (c) must be non-negative")
        if c > n:
            raise ValueError("Correct solutions (c) cannot exceed total attempts (n)")

        return c / n
