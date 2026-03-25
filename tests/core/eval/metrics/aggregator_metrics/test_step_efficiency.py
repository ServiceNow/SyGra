"""
Unit tests for StepEfficiencyMetric
Tests the step efficiency aggregator metric that calculates efficiency based on retry attempts.
"""

import os
import sys

sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", ".."))
)

import pytest

from sygra.core.eval.metrics.aggregator_metrics.step_efficiency import StepEfficiencyMetric
from sygra.core.eval.metrics.unit_metrics.unit_metric_result import UnitMetricResult


class TestStepEfficiencyMetric:
    """Test suite for StepEfficiencyMetric"""

    def test_default_penalty(self):
        """Test metric with default penalty (0.2)"""
        metric = StepEfficiencyMetric()
        assert metric.penalty_per_retry == 0.2

    def test_custom_penalty(self):
        """Test metric with custom penalty"""
        metric = StepEfficiencyMetric(penalty_per_retry=0.3)
        assert metric.penalty_per_retry == 0.3

    def test_invalid_penalty_negative(self):
        """Test that negative penalty raises error"""
        with pytest.raises(ValueError):
            StepEfficiencyMetric(penalty_per_retry=-0.1)

    def test_invalid_penalty_greater_than_one(self):
        """Test that penalty > 1 raises error"""
        with pytest.raises(ValueError):
            StepEfficiencyMetric(penalty_per_retry=1.5)

    def test_empty_results(self):
        """Test with empty results list"""
        metric = StepEfficiencyMetric()
        result = metric.calculate([])
        assert result["step_efficiency"] == 0.0
        assert result["total_steps"] == 0
        assert result["first_attempt_correct"] == 0
        assert result["retry_correct"] == 0
        assert result["never_correct"] == 0

    def test_all_first_attempt_correct(self):
        """Test when all steps are correct on first attempt (no penalty)"""
        metric = StepEfficiencyMetric()
        results = [
            UnitMetricResult(
                correct=True,
                golden={"answer": "A"},
                predicted={"answer": "A"},
                metadata={"mission_id": "m1", "step_id": "s1", "retry_number": 0},
            ),
            UnitMetricResult(
                correct=True,
                golden={"answer": "B"},
                predicted={"answer": "B"},
                metadata={"mission_id": "m1", "step_id": "s2", "retry_number": 0},
            ),
            UnitMetricResult(
                correct=True,
                golden={"answer": "C"},
                predicted={"answer": "C"},
                metadata={"mission_id": "m1", "step_id": "s3", "retry_number": 0},
            ),
        ]

        result = metric.calculate(results)
        assert result["step_efficiency"] == 1.0
        assert result["total_steps"] == 3
        assert result["first_attempt_correct"] == 3
        assert result["retry_correct"] == 0
        assert result["never_correct"] == 0
        assert result["avg_retries_when_correct"] == 0.0

    def test_second_attempt_correct(self):
        """Test when answer is correct on second attempt (retry_number=1)"""
        metric = StepEfficiencyMetric(penalty_per_retry=0.2)
        results = [
            UnitMetricResult(
                correct=False,
                golden={"answer": "A"},
                predicted={"answer": "B"},
                metadata={"mission_id": "m1", "step_id": "s1", "retry_number": 0},
            ),
            UnitMetricResult(
                correct=True,
                golden={"answer": "A"},
                predicted={"answer": "A"},
                metadata={"mission_id": "m1", "step_id": "s1", "retry_number": 1},
            ),
        ]

        result = metric.calculate(results)
        assert result["step_efficiency"] == 0.8
        assert result["total_steps"] == 1
        assert result["first_attempt_correct"] == 0
        assert result["retry_correct"] == 1
        assert result["never_correct"] == 0
        assert result["avg_retries_when_correct"] == 1.0

    def test_third_attempt_correct(self):
        """Test when answer is correct on third attempt (retry_number=2)"""
        metric = StepEfficiencyMetric(penalty_per_retry=0.2)
        results = [
            UnitMetricResult(
                correct=False,
                golden={"answer": "A"},
                predicted={"answer": "B"},
                metadata={"mission_id": "m1", "step_id": "s1", "retry_number": 0},
            ),
            UnitMetricResult(
                correct=False,
                golden={"answer": "A"},
                predicted={"answer": "C"},
                metadata={"mission_id": "m1", "step_id": "s1", "retry_number": 1},
            ),
            UnitMetricResult(
                correct=True,
                golden={"answer": "A"},
                predicted={"answer": "A"},
                metadata={"mission_id": "m1", "step_id": "s1", "retry_number": 2},
            ),
        ]

        result = metric.calculate(results)
        assert result["step_efficiency"] == 0.6
        assert result["total_steps"] == 1
        assert result["first_attempt_correct"] == 0
        assert result["retry_correct"] == 1
        assert result["never_correct"] == 0
        assert result["avg_retries_when_correct"] == 2.0

    def test_never_correct(self):
        """Test when no correct answer is found (full penalty)"""
        metric = StepEfficiencyMetric()
        results = [
            UnitMetricResult(
                correct=False,
                golden={"answer": "A"},
                predicted={"answer": "B"},
                metadata={"mission_id": "m1", "step_id": "s1", "retry_number": 0},
            ),
            UnitMetricResult(
                correct=False,
                golden={"answer": "A"},
                predicted={"answer": "C"},
                metadata={"mission_id": "m1", "step_id": "s1", "retry_number": 1},
            ),
            UnitMetricResult(
                correct=False,
                golden={"answer": "A"},
                predicted={"answer": "D"},
                metadata={"mission_id": "m1", "step_id": "s1", "retry_number": 2},
            ),
        ]

        result = metric.calculate(results)
        assert result["step_efficiency"] == 0.0
        assert result["total_steps"] == 1
        assert result["first_attempt_correct"] == 0
        assert result["retry_correct"] == 0
        assert result["never_correct"] == 1
        assert result["avg_retries_when_correct"] == 0.0

    def test_mixed_steps(self):
        """Test with mixed results across multiple steps"""
        metric = StepEfficiencyMetric(penalty_per_retry=0.2)
        results = [
            # Step 1: correct on first attempt
            UnitMetricResult(
                correct=True,
                golden={"answer": "A"},
                predicted={"answer": "A"},
                metadata={"mission_id": "m1", "step_id": "s1", "retry_number": 0},
            ),
            # Step 2: correct on second attempt
            UnitMetricResult(
                correct=False,
                golden={"answer": "B"},
                predicted={"answer": "X"},
                metadata={"mission_id": "m1", "step_id": "s2", "retry_number": 0},
            ),
            UnitMetricResult(
                correct=True,
                golden={"answer": "B"},
                predicted={"answer": "B"},
                metadata={"mission_id": "m1", "step_id": "s2", "retry_number": 1},
            ),
            # Step 3: never correct
            UnitMetricResult(
                correct=False,
                golden={"answer": "C"},
                predicted={"answer": "Y"},
                metadata={"mission_id": "m1", "step_id": "s3", "retry_number": 0},
            ),
            UnitMetricResult(
                correct=False,
                golden={"answer": "C"},
                predicted={"answer": "Z"},
                metadata={"mission_id": "m1", "step_id": "s3", "retry_number": 1},
            ),
        ]

        result = metric.calculate(results)
        # Step 1: 1.0, Step 2: 0.8, Step 3: 0.0 -> Average: 1.8/3 = 0.6
        assert result["step_efficiency"] == pytest.approx(0.6, rel=1e-6)
        assert result["total_steps"] == 3
        assert result["first_attempt_correct"] == 1
        assert result["retry_correct"] == 1
        assert result["never_correct"] == 1
        assert result["avg_retries_when_correct"] == 0.5

    def test_multiple_missions(self):
        """Test with multiple missions and steps"""
        metric = StepEfficiencyMetric(penalty_per_retry=0.25)
        results = [
            # Mission 1, Step 1: first attempt correct
            UnitMetricResult(
                correct=True,
                golden={"answer": "A"},
                predicted={"answer": "A"},
                metadata={"mission_id": "m1", "step_id": "s1", "retry_number": 0},
            ),
            # Mission 2, Step 1: second attempt correct
            UnitMetricResult(
                correct=False,
                golden={"answer": "B"},
                predicted={"answer": "X"},
                metadata={"mission_id": "m2", "step_id": "s1", "retry_number": 0},
            ),
            UnitMetricResult(
                correct=True,
                golden={"answer": "B"},
                predicted={"answer": "B"},
                metadata={"mission_id": "m2", "step_id": "s1", "retry_number": 1},
            ),
        ]

        result = metric.calculate(results)
        # Step m1_s1: 1.0, Step m2_s1: 0.75 -> Average: 1.75/2 = 0.875
        assert result["step_efficiency"] == pytest.approx(0.875, rel=1e-6)
        assert result["total_steps"] == 2
        assert result["first_attempt_correct"] == 1
        assert result["retry_correct"] == 1

    def test_efficiency_cannot_go_negative(self):
        """Test that efficiency is clamped at 0.0 even with many retries"""
        metric = StepEfficiencyMetric(penalty_per_retry=0.2)
        results = [
            UnitMetricResult(
                correct=False,
                golden={"answer": "A"},
                predicted={"answer": "B"},
                metadata={"mission_id": "m1", "step_id": "s1", "retry_number": 0},
            ),
            UnitMetricResult(
                correct=False,
                golden={"answer": "A"},
                predicted={"answer": "C"},
                metadata={"mission_id": "m1", "step_id": "s1", "retry_number": 1},
            ),
            UnitMetricResult(
                correct=False,
                golden={"answer": "A"},
                predicted={"answer": "D"},
                metadata={"mission_id": "m1", "step_id": "s1", "retry_number": 2},
            ),
            UnitMetricResult(
                correct=False,
                golden={"answer": "A"},
                predicted={"answer": "E"},
                metadata={"mission_id": "m1", "step_id": "s1", "retry_number": 3},
            ),
            UnitMetricResult(
                correct=False,
                golden={"answer": "A"},
                predicted={"answer": "F"},
                metadata={"mission_id": "m1", "step_id": "s1", "retry_number": 4},
            ),
            UnitMetricResult(
                correct=True,
                golden={"answer": "A"},
                predicted={"answer": "A"},
                metadata={"mission_id": "m1", "step_id": "s1", "retry_number": 10},
            ),
        ]

        result = metric.calculate(results)
        # 1.0 - 10*0.2 = -1.0, but should be clamped to 0.0
        assert result["step_efficiency"] == 0.0
        assert result["retry_correct"] == 1
        assert result["never_correct"] == 0

    def test_metadata_name(self):
        """Test metric metadata"""
        metric = StepEfficiencyMetric()
        assert metric.get_metric_name() == "step_efficiency"
        assert metric.metadata.display_name == "Step Efficiency"
        assert metric.metadata.higher_is_better is True
        assert metric.metadata.range == (0.0, 1.0)

    def test_missing_retry_number_defaults_to_zero(self):
        """Test that missing retry_number in metadata defaults to 0"""
        metric = StepEfficiencyMetric()
        results = [
            UnitMetricResult(
                correct=True,
                golden={"answer": "A"},
                predicted={"answer": "A"},
                metadata={"mission_id": "m1", "step_id": "s1"},
            ),
        ]

        result = metric.calculate(results)
        assert result["step_efficiency"] == 1.0
        assert result["first_attempt_correct"] == 1
