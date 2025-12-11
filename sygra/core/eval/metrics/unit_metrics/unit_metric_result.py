"""
Unit Metric Result

Standardized output from unit metrics (validators) to provide consistent interface for validation results.
In other words, this is a list of binary results(True,False) sent to any metric for calculation.
"""

from dataclasses import dataclass, field
from typing import Any, Dict


@dataclass
class UnitMetricResult:
    """
    Standardized result from a unit metric (validator).

    This class represents the output of a single validation operation,
    containing boolean flags for correctness and contextual information.(True/False)

    Attributes:
        correct: Boolean indicating correctness (True/False)
        golden: Expected/golden response (dict)
        predicted: Model's predicted response (dict)
        metadata: Additional context (mission_id, step_id, retry_number, etc.)

    Usage:
        result = UnitMetricResult(
            correct=True,
            golden={'event': 'click', 'properties': {'x': 100, 'y': 200}},
            predicted={'tool': 'click', 'x': 105, 'y': 195},
            metadata={'mission_id': 'mission_01', 'step_id': 'step_1', 'validation_type': 'tool_only'}
        )

        # Example: Tool-only correctness
        result = UnitMetricResult(
            correct=True,  # Tool is correct
            golden={'event': 'click'},
            predicted={'tool': 'click'},
            metadata={'mission_id': 'mission_01', 'step_id': 'step_1','validation_type': 'tool_only'}
        )
    """

    # Core validation results
    correct: bool

    # Context
    golden: Dict[str, Any]
    predicted: Dict[str, Any]

    # Metadata (extensible for any task)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """Validate the result structure"""
        # Ensure metadata is a dict
        if not isinstance(self.metadata, dict):
            self.metadata = {}

        # Ensure golden and predicted are dicts
        if not isinstance(self.golden, dict):
            raise ValueError("golden must be a dictionary")
        if not isinstance(self.predicted, dict):
            raise ValueError("predicted must be a dictionary")

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert to dictionary for serialization.

        Returns:
            dict representation of the result
        """
        return {
            "correct": self.correct,
            "golden": self.golden,
            "predicted": self.predicted,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "UnitMetricResult":
        """
        Create UnitMetricResult from dictionary.

        Args:
            data: Dictionary with result data

        Returns:
            UnitMetricResult instance
        """
        return cls(
            correct=data.get("correct", False),
            golden=data.get("golden", {}),
            predicted=data.get("predicted", {}),
            metadata=data.get("metadata", {}),
        )

    def __repr__(self) -> str:
        """String representation for debugging"""
        return (
            f"UnitMetricResult("
            f"correct={self.correct}, "
            f"golden={self.golden}, "
            f"predicted={self.predicted}"
            f"metadata={self.metadata}"
            f")"
        )
