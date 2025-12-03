"""
Aggregator Metric Configuration
Single Pydantic configuration class for all aggregator metrics.
Each metric validates only the fields it needs in its _validate_config() method, init remains common.


"""

from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


class AggregatorMetricConfig(BaseModel):
    """
    Single configuration class for all aggregator metrics.
    Adding this to have common __init__ across all metrics, with only validation overridden in each metric class.

    Common Fields:
        predicted_key: Key in predicted dict to check (e.g., "tool", "class")
        golden_key: Key in golden dict to check (e.g., "event", "class")
        positive_class: Value representing positive class (e.g., "click", 1, True)
        threshold: Threshold for classification or matching
        normalize: Whether to normalize values before comparison

    Note that threshold and normalize were added later to allow metrics other than precision, recall, f1 to be
    incorporated.

    Example Usage:
        # Precision needs: predicted_key, positive_class
        config = AggregatorMetricConfig(predicted_key="tool", positive_class="click")

        # Recall needs: golden_key, positive_class
        config = AggregatorMetricConfig(golden_key="event", positive_class="click")

        # Accuracy needs: nothing
        config = AggregatorMetricConfig()
    """

    # Common fields (all optional - metrics validate what they need)
    predicted_key: Optional[str] = Field(
        None, description="Key in predicted dict to check (e.g., 'tool', 'class')"
    )
    golden_key: Optional[str] = Field(
        None, description="Key in golden dict to check (e.g., 'event', 'class')"
    )
    positive_class: Optional[Any] = Field(
        None, description="Value representing positive class (e.g., 'click', 1, True)"
    )
    threshold: Optional[float] = Field(None, description="Threshold for classification or matching")
    normalize: Optional[bool] = Field(
        None, description="Whether to normalize values before comparison"
    )

    # Pydantic config
    model_config = ConfigDict(arbitrary_types_allowed=True, extra="allow")
