"""
Base Metric Metadata

Pydantic model for structured metadata shared by all metrics (unit and aggregator).
Provides consistent information about metric properties for discovery, validation, and UI display.
"""

from typing import Tuple

from pydantic import BaseModel, ConfigDict, Field


class BaseMetricMetadata(BaseModel):
    """
    Structured metadata for all metrics.

    This metadata enables easy output validation in downstream task(for example say metric dashboard visualization).
    Another advantage is we can filter by type or properties.

    Attributes:
        name: Unique metric identifier (e.g., "precision", "exact_match")
        display_name: Human-readable name for UI display
        description: What this metric measures
        range: Expected value range as (min, max) tuple
        higher_is_better: Whether higher values indicate better performance
        metric_type: Category - "industry" (standard), "custom", "domain-specific"

    Example:
        metadata = BaseMetricMetadata(
            name="precision",
            display_name="Precision",
            description="Proportion of positive predictions that are correct",
            range=(0.0, 1.0),
            higher_is_better=True,
            metric_type="industry"
        )
    """

    name: str = Field(..., description="Unique metric identifier")
    display_name: str = Field(..., description="Human-readable name for display")
    description: str = Field(..., description="What this metric measures")
    range: Tuple[float, float] = Field(
        default=(0.0, 1.0), description="Expected value range [min, max]"
    )
    higher_is_better: bool = Field(
        default=True, description="Whether higher values indicate better performance"
    )
    # This is as per standard eval framework definition
    metric_type: str = Field(default="custom", description="Metric category: 'industry', 'custom'")

    # Setting allow additional fields for extensibility
    model_config = ConfigDict(arbitrary_types_allowed=True, extra="allow")
