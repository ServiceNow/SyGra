"""
Action Within BBox Metric

Validates that a predicted coordinate-based action (x, y) falls inside a golden bounding box.
"""

from typing import Any, Dict, List

from pydantic import BaseModel, Field

from sygra.core.eval.metrics.base_metric_metadata import BaseMetricMetadata
from sygra.core.eval.metrics.unit_metrics.base_unit_metric import BaseUnitMetric
from sygra.core.eval.metrics.unit_metrics.unit_metric_registry import unit_metric
from sygra.core.eval.metrics.unit_metrics.unit_metric_result import UnitMetricResult
from sygra.logger.logger_config import logger


class ActionWithinBboxMetricConfig(BaseModel):
    """Configuration for ActionWithinBboxMetric"""

    predicted_x_key: str = Field(default="x", description="Key in predicted dict for x coordinate")
    predicted_y_key: str = Field(default="y", description="Key in predicted dict for y coordinate")
    golden_bbox_key: str = Field(
        default="bbox", description="Key in golden dict that contains bbox (x, y, width, height)"
    )


@unit_metric("action_within_bbox")
class ActionWithinBboxMetric(BaseUnitMetric):
    """Validate that the predicted (x, y) is within the golden bbox."""

    def __init__(self, **config):
        super().__init__(**config)
        self.validate_config()
        self.metadata = self.get_metadata()

    def validate_config(self):
        config_obj = ActionWithinBboxMetricConfig(**self.config)
        self.predicted_x_key = config_obj.predicted_x_key
        self.predicted_y_key = config_obj.predicted_y_key
        self.golden_bbox_key = config_obj.golden_bbox_key

    def get_metadata(self) -> BaseMetricMetadata:
        return BaseMetricMetadata(
            name="action_within_bbox",
            display_name="Action Within BBox",
            description="Validates predicted (x, y) falls inside golden bounding box",
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
                bbox = golden_dict.get(self.golden_bbox_key)
                x = predicted_dict.get(self.predicted_x_key)
                y = predicted_dict.get(self.predicted_y_key)

                is_valid = self._is_action_within_bbox(x, y, bbox)

                results.append(
                    UnitMetricResult(
                        correct=is_valid,
                        golden=golden_dict,
                        predicted=predicted_dict,
                        metadata={
                            "validator": self.metadata.name,
                            "predicted_x_key": self.predicted_x_key,
                            "predicted_y_key": self.predicted_y_key,
                            "golden_bbox_key": self.golden_bbox_key,
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

    def _is_action_within_bbox(self, action_x: Any, action_y: Any, bbox: Any) -> bool:
        if not isinstance(bbox, dict):
            return False

        try:
            x = float(action_x)
            y = float(action_y)
        except (TypeError, ValueError):
            return False

        try:
            x_min = float(bbox["x"])
            y_min = float(bbox["y"])
            x_max = x_min + float(bbox["width"])
            y_max = y_min + float(bbox["height"])
        except (KeyError, TypeError, ValueError):
            return False

        return x_min <= x <= x_max and y_min <= y <= y_max
