"""
Step Efficiency Metric

Calculates step efficiency based on which retry number is correct.
- First retry correct: no penalty (efficiency = 1.0)
- No correct answer: add penalty (efficiency = 0.0)
- Later retries correct: efficiency decreases based on retry number
"""

from typing import Any, Dict, List

from pydantic import BaseModel, Field, field_validator

from sygra.core.eval.metrics.aggregator_metrics.aggregator_metric_registry import aggregator_metric
from sygra.core.eval.metrics.aggregator_metrics.base_aggregator_metric import BaseAggregatorMetric
from sygra.core.eval.metrics.base_metric_metadata import BaseMetricMetadata
from sygra.core.eval.metrics.unit_metrics.unit_metric_result import UnitMetricResult
from sygra.logger.logger_config import logger


class StepEfficiencyMetricConfig(BaseModel):
    """Configuration for Step Efficiency Metric"""

    penalty_per_retry: float = Field(
        default=0.2,
        description="Penalty to apply per retry attempt (default: 0.2, meaning 20% reduction per retry)",
    )

    @field_validator("penalty_per_retry")
    @classmethod
    def validate_penalty(cls, v):
        if v is None or v < 0 or v > 1:
            raise ValueError(
                "penalty_per_retry must be between 0 and 1 (e.g., 0.2 for 20% penalty per retry)"
            )
        return v


@aggregator_metric("step_efficiency")
class StepEfficiencyMetric(BaseAggregatorMetric):
    """Calculate step efficiency based on retry number when correct answer is found.

    Efficiency calculation:
    - First attempt correct (retry_number = 0): efficiency = 1.0 (no penalty)
    - Second attempt correct (retry_number = 1): efficiency = 1.0 - penalty_per_retry
    - Third attempt correct (retry_number = 2): efficiency = 1.0 - 2 * penalty_per_retry
    - No correct answer: efficiency = 0.0

    Required metadata in UnitMetricResult:
        - retry_number: int (0-indexed, where 0 is first attempt)

    Optional configuration:
        penalty_per_retry: float (default: 0.2) - penalty applied per retry
    """

    def __init__(self, **config):
        """Initialize step efficiency metric with two-phase initialization."""
        super().__init__(**config)
        self.validate_config()
        self.metadata = self.get_metadata()

    def validate_config(self):
        """Validate and store step efficiency configuration requirements"""
        # Validate using Pydantic config class
        config_obj = StepEfficiencyMetricConfig(**self.config)

        # Store validated fields as instance attributes
        self.penalty_per_retry = config_obj.penalty_per_retry

    def get_metadata(self) -> BaseMetricMetadata:
        """Return metadata for step efficiency metric"""
        return BaseMetricMetadata(
            name="step_efficiency",
            display_name="Step Efficiency",
            description="Efficiency score based on which retry attempt produces correct answer. "
            "First attempt = 1.0, later attempts have penalties, no correct = 0.0",
            range=(0.0, 1.0),
            higher_is_better=True,
            metric_type="custom",
        )

    def calculate(self, results: List[UnitMetricResult]) -> Dict[str, Any]:
        """Calculate step efficiency from unit metric results.

        Args:
            results: List of UnitMetricResult from validators
                    Each result should have metadata['retry_number'] indicating attempt number

        Returns:
            dict: {
                "step_efficiency": float (0.0 to 1.0),
                "total_steps": int,
                "first_attempt_correct": int,
                "retry_correct": int,
                "never_correct": int,
                "avg_retries_when_correct": float
            }
        """
        if not results:
            logger.warning(f"{self.__class__.__name__}: No results provided")
            return self._empty_result()

        # Group results by step (mission_id + step_id)
        steps = self._group_by_step(results)

        total_steps = len(steps)
        first_attempt_correct = 0
        retry_correct = 0
        never_correct = 0
        total_efficiency = 0.0
        total_retries_when_correct = 0
        steps_with_correct = 0

        for step_id, step_results in steps.items():
            # Sort by retry number to process in order
            sorted_results = sorted(step_results, key=lambda r: self._get_retry_number(r))

            # Find first correct result
            first_correct_idx = None
            first_correct_retry_num = None

            for idx, result in enumerate(sorted_results):
                if result.correct:
                    first_correct_idx = idx
                    first_correct_retry_num = self._get_retry_number(result)
                    break

            if first_correct_idx is not None and first_correct_retry_num is not None:
                # Calculate efficiency for this step
                retry_num = first_correct_retry_num
                step_efficiency = max(0.0, 1.0 - (retry_num * self.penalty_per_retry))
                total_efficiency += step_efficiency

                # Track statistics
                if retry_num == 0:
                    first_attempt_correct += 1
                else:
                    retry_correct += 1

                total_retries_when_correct += retry_num
                steps_with_correct += 1
            else:
                # No correct answer found for this step
                never_correct += 1
                # Efficiency is 0.0 for this step (already added as 0)

        # Calculate overall metrics
        overall_efficiency = self._safe_divide(total_efficiency, total_steps)
        avg_retries_when_correct = (
            self._safe_divide(total_retries_when_correct, steps_with_correct)
            if steps_with_correct > 0
            else 0.0
        )

        return {
            "step_efficiency": overall_efficiency,
            "total_steps": total_steps,
            "first_attempt_correct": first_attempt_correct,
            "retry_correct": retry_correct,
            "never_correct": never_correct,
            "avg_retries_when_correct": avg_retries_when_correct,
        }

    def _get_retry_number(self, result: UnitMetricResult) -> int:
        """Extract retry number from metadata.

        Supports two formats:
        1. retry_number: int (direct value)
        2. retry_id: str (e.g., "retry_0" -> 0)

        Args:
            result: UnitMetricResult with metadata

        Returns:
            int: Retry number (0-indexed)
        """
        # Check if retry_number is directly available
        if "retry_number" in result.metadata:
            retry_num = result.metadata.get("retry_number", 0)
            return retry_num if retry_num is not None else 0

        # Extract from retry_id if available
        retry_id = result.metadata.get("retry_id", "retry_0")
        if isinstance(retry_id, str) and "_" in retry_id:
            try:
                return int(retry_id.split("_")[-1])
            except (ValueError, IndexError):
                return 0

        return 0

    def _group_by_step(self, results: List[UnitMetricResult]) -> Dict[str, List[UnitMetricResult]]:
        """Group results by step identifier (mission_id + step_id)"""
        steps: Dict[str, List[UnitMetricResult]] = {}
        for result in results:
            mission_id = result.metadata.get("mission_id", "unknown")
            step_id = result.metadata.get("step_id", "unknown")
            step_key = f"{mission_id}_{step_id}"

            if step_key not in steps:
                steps[step_key] = []
            steps[step_key].append(result)

        return steps

    def _empty_result(self) -> Dict[str, Any]:
        """Return empty result structure when no results provided"""
        return {
            "step_efficiency": 0.0,
            "total_steps": 0,
            "first_attempt_correct": 0,
            "retry_correct": 0,
            "never_correct": 0,
            "avg_retries_when_correct": 0.0,
        }
