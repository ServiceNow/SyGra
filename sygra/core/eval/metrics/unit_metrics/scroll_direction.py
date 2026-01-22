"""Scroll Direction Metric

Validates that predicted scroll direction matches the golden direction.
"""

from typing import Any, Dict, List

from pydantic import BaseModel, Field

from sygra.core.eval.metrics.base_metric_metadata import BaseMetricMetadata
from sygra.core.eval.metrics.unit_metrics.base_unit_metric import BaseUnitMetric
from sygra.core.eval.metrics.unit_metrics.unit_metric_registry import unit_metric
from sygra.core.eval.metrics.unit_metrics.unit_metric_result import UnitMetricResult
from sygra.logger.logger_config import logger


class ScrollDirectionMetricConfig(BaseModel):
    """Configuration for ScrollDirectionMetric"""

    golden_direction_key: str = Field(
        default="direction", description="Key in golden dict for direction"
    )
    predicted_direction_key: str = Field(
        default="direction", description="Key in predicted dict for direction"
    )


@unit_metric("scroll_direction")
class ScrollDirectionMetric(BaseUnitMetric):
    """Validate scroll direction correctness."""

    def __init__(self, **config):
        super().__init__(**config)
        self.validate_config()
        self.metadata = self.get_metadata()

    def validate_config(self):
        config_obj = ScrollDirectionMetricConfig(**self.config)
        self.golden_direction_key = config_obj.golden_direction_key
        self.predicted_direction_key = config_obj.predicted_direction_key

    def get_metadata(self) -> BaseMetricMetadata:
        return BaseMetricMetadata(
            name="scroll_direction",
            display_name="Scroll Direction",
            description="Validates predicted scroll direction matches golden direction",
            range=(0.0, 1.0),
            higher_is_better=True,
            metric_type="industry",
        )

    def evaluate(self, golden: List[Any], predicted: List[Any]) -> List[UnitMetricResult]:
        if len(golden) != len(predicted):
            raise ValueError(
                f"{self.__class__.__name__}: golden and predicted must have same length "
                f"(got {len(golden)} and {len(predicted)})"
            )

        results: List[UnitMetricResult] = []
        valid_directions = {"up", "down", "left", "right"}

        for g, p in zip(golden, predicted):
            golden_dict: Dict[str, Any] = g if isinstance(g, dict) else {"value": g}
            predicted_dict: Dict[str, Any] = p if isinstance(p, dict) else {"value": p}

            try:
                golden_dir = golden_dict.get(self.golden_direction_key)
                predicted_dir = predicted_dict.get(self.predicted_direction_key)

                is_valid = (
                        predicted_dir == golden_dir
                        and isinstance(predicted_dir, str)
                        and predicted_dir in valid_directions
                )

                results.append(
                    UnitMetricResult(
                        correct=is_valid,
                        golden=golden_dict,
                        predicted=predicted_dict,
                        metadata={
                            "validator": self.metadata.name,
                            "golden_direction": golden_dir,
                            "predicted_direction": predicted_dir,
                        },
                    )
                )
            except Exception as e:
                logger.error(f"{self.__class__.__name__}: Error during evaluation: {e}")
                results.append(
                    UnitMetricResult(
                        correct=False,
                        golden=golden_dict,
                        predicted=predicted_dict,
                        metadata={
                            "validator": self.metadata.name,
                            "error": str(e),
                        },
                    )
                )

        return results
