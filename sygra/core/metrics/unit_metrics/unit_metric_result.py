"""
Unit Metric Result

Standardized output from unit metrics (validators) to provide consistent interface for validation results.
In other words, this is a list of binary results(True,False) sent to any metric for calculation.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass
class UnitMetricResult:
    """
    Standardized result from a unit metric (validator).

    This class represents the output of a single validation operation,
    containing boolean flags for correctness and contextual information.(True/False)

    Attributes:
        correct: Overall correctness (tool + params both correct)
        tool_correct: Tool/action type is correct
        params_correct: Parameters are correct (only meaningful if tool_correct=True)
        golden: Expected/golden response (dict)
        predicted: Model's predicted response (dict)
        metadata: Additional context (mission_id, step_id, retry_number, etc.)
        reason: Optional human-readable reason for the result

    Usage:
        result = UnitMetricResult(
            correct=True,
            tool_correct=True,
            params_correct=True,
            golden={'event': 'click', 'properties': {'x': 100, 'y': 200}},
            predicted={'tool': 'click', 'x': 105, 'y': 195},
            metadata={'mission_id': 'mission_01', 'step_id': 'step_1', 'retry_number': 0}
        )
    """

    # Core validation results
    correct: bool
    tool_correct: bool
    params_correct: bool

    # Context
    golden: Dict[str, Any]
    predicted: Dict[str, Any]

    # Metadata (extensible for any task)
    metadata: Dict[str, Any] = field(default_factory=dict)

    # Optional explanation
    reason: Optional[str] = None

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

        # Logical validation: if tool is wrong, params can't be correct
        if not self.tool_correct and self.params_correct:
            raise ValueError(
                "Logical error: params_correct cannot be True if tool_correct is False"
            )

        # Overall correctness should match tool + params
        expected_correct = self.tool_correct and self.params_correct
        if self.correct != expected_correct:
            # Allow override but warn
            import warnings

            warnings.warn(
                f"Inconsistent correctness: correct={self.correct} but "
                f"tool_correct={self.tool_correct} and params_correct={self.params_correct}"
            )

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert to dictionary for serialization.

        Returns:
            dict representation of the result
        """
        return {
            "correct": self.correct,
            "tool_correct": self.tool_correct,
            "params_correct": self.params_correct,
            "golden": self.golden,
            "predicted": self.predicted,
            "metadata": self.metadata,
            "reason": self.reason,
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
            tool_correct=data.get("tool_correct", False),
            params_correct=data.get("params_correct", False),
            golden=data.get("golden", {}),
            predicted=data.get("predicted", {}),
            metadata=data.get("metadata", {}),
            reason=data.get("reason"),
        )

    def __repr__(self) -> str:
        """String representation for debugging"""
        return (
            f"UnitMetricResult("
            f"correct={self.correct}, "
            f"tool_correct={self.tool_correct}, "
            f"params_correct={self.params_correct}, "
            f"golden_event={self.golden.get('event', 'unknown')}, "
            f"predicted_tool={self.predicted.get('tool', 'unknown')}"
            f")"
        )
