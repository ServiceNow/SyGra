"""
Unit Metric Configuration

Single Pydantic configuration class for all unit metrics.
Each metric validates only the fields it needs in its _validate_config() method, init remains common.
"""

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class UnitMetricConfig(BaseModel):
    """
    Single configuration class for all unit metrics.
    Adding this to have common __init__ across all metrics, with only validation overridden in each metric class.

    Common Fields:
        case_sensitive: Whether to perform case-sensitive comparison
        normalize_whitespace: Whether to normalize whitespace before comparison
        ignore_punctuation: Whether to ignore punctuation in comparison
        threshold: Threshold for similarity/matching (e.g., IoU threshold for bbox)
        tolerance: Numerical tolerance for floating-point comparisons
        key: Key in dict to extract value for comparison

    Note that these fields cover common validation scenarios. Additional fields can be added
    via extra="allow" for metric-specific needs.

    Example Usage:
        # ExactMatch with case sensitivity
        config = UnitMetricConfig(case_sensitive=True)

        # BBox validator with IoU threshold
        config = UnitMetricConfig(threshold=0.5)

        # Numerical validator with tolerance
        config = UnitMetricConfig(tolerance=0.001)
    """

    # Common fields (all optional - metrics validate what they need)
    case_sensitive: Optional[bool] = Field(
        None, description="Whether to perform case-sensitive comparison"
    )
    normalize_whitespace: Optional[bool] = Field(
        None, description="Whether to normalize whitespace before comparison"
    )
    ignore_punctuation: Optional[bool] = Field(
        None, description="Whether to ignore punctuation in comparison"
    )
    threshold: Optional[float] = Field(
        None, description="Threshold for similarity/matching (e.g., IoU threshold)"
    )
    tolerance: Optional[float] = Field(
        None, description="Numerical tolerance for floating-point comparisons"
    )
    key: Optional[str] = Field(None, description="Key in dict to extract value for comparison")

    # Pydantic config
    model_config = ConfigDict(arbitrary_types_allowed=True, extra="allow")
