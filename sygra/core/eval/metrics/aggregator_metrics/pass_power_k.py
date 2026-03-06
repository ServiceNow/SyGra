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
        """Calculate Pass^k scores for all k values from 1 to configured k.

        Args:
            results: List of UnitMetricResult

        Returns:
            dict: {"success_rate": float, "pass^1": float, "pass^2": float, ..., "pass^k": float}

         Raises:
            ValueError: If invalid parameters are provided
        """
        if not results:
            logger.warning(f"{self.__class__.__name__}: No results provided")
            result_dict = {"success_rate": 0.0}
            result_dict.update({f"pass^{i}": 0.0 for i in range(1, self.k + 1)})
            return result_dict

        # Total number of attempts/samples
        n = len(results)
        # Number of correct solutions
        c = self._count_correct(results)

        if n <= 0:
            raise ValueError("Total attempts (n) must be positive")
        if c < 0:
            raise ValueError("Correct solutions (c) must be non-negative")
        if c > n:
            raise ValueError("Correct solutions (c) cannot exceed total attempts (n)")

        success_rate = self._safe_divide(c, n)

        # Calculate pass^k for all values from 1 to k
        result_dict = {"success_rate": success_rate}
        for k_val in range(1, self.k + 1):
            result_dict[f"pass^{k_val}"] = self.pass_power_k(success_rate, k_val)

        return result_dict

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

        return success_rate**k
