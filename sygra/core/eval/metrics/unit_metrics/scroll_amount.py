"""Scroll Amount Metric

Validates that predicted scroll amount is within tolerance of the golden amount.
"""

from typing import Any, Dict, List

from pydantic import BaseModel, Field

from sygra.core.eval.metrics.base_metric_metadata import BaseMetricMetadata
from sygra.core.eval.metrics.unit_metrics.base_unit_metric import BaseUnitMetric
from sygra.core.eval.metrics.unit_metrics.unit_metric_registry import unit_metric
from sygra.core.eval.metrics.unit_metrics.unit_metric_result import UnitMetricResult
from sygra.logger.logger_config import logger


class ScrollAmountMetricConfig(BaseModel):
    """Configuration for ScrollAmountMetric"""

    golden_amount_key: str = Field(
        default="amount", description="Key in golden dict for scroll amount"
    )
    predicted_amount_key: str = Field(
        default="amount", description="Key in predicted dict for scroll amount"
    )
    tolerance_percent: float = Field(
        default=20.0,
        ge=0.0,
        description="Acceptable percentage tolerance for non-zero golden amounts",
    )
    scroll_threshold: float = Field(
        default=10.0,
        ge=0.0,
        description="Absolute tolerance used when golden amount is 0",
    )


@unit_metric("scroll_amount")
class ScrollAmountMetric(BaseUnitMetric):
    """Validate scroll amount correctness within tolerance."""

    def __init__(self, **config):
        super().__init__(**config)
        self.validate_config()
        self.metadata = self.get_metadata()

    def validate_config(self):
        config_obj = ScrollAmountMetricConfig(**self.config)
        self.golden_amount_key = config_obj.golden_amount_key
        self.predicted_amount_key = config_obj.predicted_amount_key
        self.tolerance_percent = config_obj.tolerance_percent
        self.scroll_threshold = config_obj.scroll_threshold

    def get_metadata(self) -> BaseMetricMetadata:
        return BaseMetricMetadata(
            name="scroll_amount",
            display_name="Scroll Amount",
            description="Validates predicted scroll amount is within tolerance of golden amount",
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
        for g, p in zip(golden, predicted):
            golden_dict: Dict[str, Any] = g if isinstance(g, dict) else {"value": g}
            predicted_dict: Dict[str, Any] = p if isinstance(p, dict) else {"value": p}

            try:
                golden_amount = float(golden_dict.get(self.golden_amount_key, 0.0))
                predicted_amount = float(predicted_dict.get(self.predicted_amount_key, 0.0))

                detail = self._is_scroll_amount_valid(
                    golden_amount,
                    predicted_amount,
                    tolerance_percent=self.tolerance_percent,
                    scroll_threshold=self.scroll_threshold,
                )

                results.append(
                    UnitMetricResult(
                        correct=bool(detail["is_valid"]),
                        golden=golden_dict,
                        predicted=predicted_dict,
                        metadata={
                            "validator": self.metadata.name,
                            **detail,
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

    def _is_scroll_amount_valid(
        self,
        golden_scroll_amount: float,
        predicted_scroll_amount: float,
        tolerance_percent: float,
        scroll_threshold: float,
    ) -> Dict[str, Any]:
        if golden_scroll_amount == 0:
            is_valid = abs(predicted_scroll_amount) <= scroll_threshold
            difference = abs(predicted_scroll_amount)
            difference_percent = float("inf") if predicted_scroll_amount != 0 else 0.0
        else:
            difference = abs(golden_scroll_amount - predicted_scroll_amount)
            difference_percent = (difference / abs(golden_scroll_amount)) * 100
            is_valid = difference_percent <= tolerance_percent

        return {
            "is_valid": is_valid,
            "difference": difference,
            "difference_percent": difference_percent,
            "tolerance_used": tolerance_percent,
            "scroll_threshold": scroll_threshold,
            "golden_scroll_amount": golden_scroll_amount,
            "predicted_scroll_amount": predicted_scroll_amount,
        }
