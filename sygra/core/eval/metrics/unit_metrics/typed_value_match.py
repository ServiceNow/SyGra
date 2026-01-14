"""Typed Value Match Metric

Compares a golden typed value vs predicted typed value using exact and fuzzy matching.
"""

import re
from difflib import SequenceMatcher
from typing import Any, Dict, List

from pydantic import BaseModel, Field

from sygra.core.eval.metrics.base_metric_metadata import BaseMetricMetadata
from sygra.core.eval.metrics.unit_metrics.base_unit_metric import BaseUnitMetric
from sygra.core.eval.metrics.unit_metrics.unit_metric_result import UnitMetricResult
from sygra.logger.logger_config import logger


class TypedValueMatchMetricConfig(BaseModel):
    """Configuration for TypedValueMatchMetric"""

    golden_text_key: str = Field(
        default="text", description="Key in golden dict containing typed value"
    )
    predicted_text_key: str = Field(
        default="text", description="Key in predicted dict containing typed value"
    )
    fuzzy_match_threshold: float = Field(
        default=0.8,
        ge=0.0,
        le=1.0,
        description="Minimum similarity (0-1) for fuzzy match acceptance",
    )


class TypedValueMatchMetric(BaseUnitMetric):
    """Validate typed value correctness using exact and fuzzy matching."""

    def __init__(self, **config):
        super().__init__(**config)
        self.validate_config()
        self.metadata = self.get_metadata()

    def validate_config(self):
        config_obj = TypedValueMatchMetricConfig(**self.config)
        self.golden_text_key = config_obj.golden_text_key
        self.predicted_text_key = config_obj.predicted_text_key
        self.fuzzy_match_threshold = config_obj.fuzzy_match_threshold

    def get_metadata(self) -> BaseMetricMetadata:
        return BaseMetricMetadata(
            name="typed_value_match",
            display_name="Typed Value Match",
            description="Validates typed value using exact and fuzzy match",
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
                golden_text = str(golden_dict.get(self.golden_text_key, ""))
                predicted_text = str(predicted_dict.get(self.predicted_text_key, ""))

                detail = self._is_typed_value_correct(
                    golden_text, predicted_text, threshold=self.fuzzy_match_threshold
                )

                results.append(
                    UnitMetricResult(
                        correct=bool(detail["exact_match"] or detail["fuzzy_match"]),
                        golden=golden_dict,
                        predicted=predicted_dict,
                        metadata={
                            "validator": self.metadata.name,
                            "golden_text": golden_text,
                            "predicted_text": predicted_text,
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

    def _normalize_text(self, text: str) -> str:
        return re.sub(r"\s+", " ", text.strip().lower())

    def _is_typed_value_correct(
        self, golden: str, predicted: str, threshold: float
    ) -> Dict[str, Any]:
        golden_norm = self._normalize_text(golden)
        predicted_norm = self._normalize_text(predicted)

        exact = golden_norm == predicted_norm

        similarity = SequenceMatcher(None, golden_norm, predicted_norm).ratio()
        fuzzy = similarity >= threshold

        differences: List[Dict[str, Any]] = []
        if not exact:
            for opcode, i1, i2, j1, j2 in SequenceMatcher(
                None, golden_norm, predicted_norm
            ).get_opcodes():
                if opcode != "equal":
                    differences.append(
                        {
                            "operation": opcode,
                            "golden": golden_norm[i1:i2],
                            "predicted": predicted_norm[j1:j2],
                        }
                    )

        return {
            "exact_match": exact,
            "similarity_score": similarity,
            "fuzzy_match": fuzzy,
            "differences": differences,
        }
