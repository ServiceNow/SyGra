"""
Unit tests for RecallMetric
Tests recall calculation (TP / (TP + FN)) from unit metric results.
"""

import os
import sys

# Add project root to sys.path for relative imports to work
sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", ".."))
)
import pytest

from sygra.core.eval.metrics.aggregator_metrics.recall import RecallMetric
from sygra.core.eval.metrics.unit_metrics.unit_metric_result import UnitMetricResult


class TestRecallMetric:
    """Test suite for RecallMetric"""

    def test_get_metric_name(self):
        """Test that metric name is 'recall'"""
        metric = RecallMetric(golden_key="class", positive_class="A")
        assert metric.get_metric_name() == "recall"

    def test_initialization_with_parameters(self):
        """Test initialization with custom parameters"""
        metric = RecallMetric(golden_key="event", positive_class="click")
        assert metric.golden_key == "event"
        assert metric.positive_class == "click"

    def test_initialization_requires_parameters(self):
        """Test that initialization requires both golden_key and positive_class"""
        # Should raise ValueError when golden_key is missing
        with pytest.raises(ValueError):
            RecallMetric(positive_class="A")

        # Should raise ValueError when positive_class is missing
        with pytest.raises(ValueError):
            RecallMetric(golden_key="class")

        # Should raise ValueError when golden_key is empty
        with pytest.raises(ValueError) as exc_info:
            RecallMetric(golden_key="", positive_class="A")
        assert "golden_key is required" in str(exc_info.value)

        # Should raise ValueError when positive_class is None
        with pytest.raises(ValueError) as exc_info:
            RecallMetric(golden_key="class", positive_class=None)
        assert "positive_class is required" in str(exc_info.value)

    def test_calculate_empty_results(self):
        """Test calculate with empty results list"""
        metric = RecallMetric(golden_key="class", positive_class="A")
        results = []
        output = metric.calculate(results)

        assert "recall" in output
        assert output["recall"] == 0.0

    def test_calculate_perfect_recall(self):
        """Test calculate with perfect recall (all actual positives are found)"""
        metric = RecallMetric(golden_key="class", positive_class="click")
        results = [
            UnitMetricResult(
                correct=True,
                golden={"class": "click"},
                predicted={"class": "click"},
            ),
            UnitMetricResult(
                correct=True,
                golden={"class": "click"},
                predicted={"class": "click"},
            ),
            UnitMetricResult(
                correct=True,
                golden={"class": "click"},
                predicted={"class": "click"},
            ),
        ]
        output = metric.calculate(results)

        assert "recall" in output
        assert output["recall"] == 1.0

    def test_calculate_zero_recall(self):
        """Test calculate with zero recall (all actual positives are missed)"""
        metric = RecallMetric(golden_key="class", positive_class="click")
        results = [
            UnitMetricResult(
                correct=False,
                golden={"class": "click"},
                predicted={"class": "type"},
            ),
            UnitMetricResult(
                correct=False,
                golden={"class": "click"},
                predicted={"class": "scroll"},
            ),
            UnitMetricResult(
                correct=False,
                golden={"class": "click"},
                predicted={"class": "hover"},
            ),
        ]
        output = metric.calculate(results)

        assert "recall" in output
        assert output["recall"] == 0.0

    def test_calculate_mixed_recall(self):
        """Test calculate with mixed true positives and false negatives"""
        metric = RecallMetric(golden_key="class", positive_class="click")
        results = [
            # True Positive
            UnitMetricResult(
                correct=True,
                golden={"class": "click"},
                predicted={"class": "click"},
            ),
            # False Negative
            UnitMetricResult(
                correct=False,
                golden={"class": "click"},
                predicted={"class": "type"},
            ),
            # True Positive
            UnitMetricResult(
                correct=True,
                golden={"class": "click"},
                predicted={"class": "click"},
            ),
            # False Negative
            UnitMetricResult(
                correct=False,
                golden={"class": "click"},
                predicted={"class": "scroll"},
            ),
        ]
        output = metric.calculate(results)

        # TP = 2, FN = 2, Recall = 2/(2+2) = 0.5
        assert "recall" in output
        assert output["recall"] == 0.5

    def test_calculate_with_negative_class_in_golden(self):
        """Test calculate when some golden values are not the positive class"""
        metric = RecallMetric(golden_key="class", positive_class="click")
        results = [
            # True Positive
            UnitMetricResult(
                correct=True,
                golden={"class": "click"},
                predicted={"class": "click"},
            ),
            # True Negative (golden is not positive class)
            UnitMetricResult(
                correct=True,
                golden={"class": "type"},
                predicted={"class": "type"},
            ),
            # False Negative
            UnitMetricResult(
                correct=False,
                golden={"class": "click"},
                predicted={"class": "scroll"},
            ),
            # True Negative
            UnitMetricResult(
                correct=True,
                golden={"class": "hover"},
                predicted={"class": "hover"},
            ),
        ]
        output = metric.calculate(results)

        # TP = 1, FN = 1, Recall = 1/(1+1) = 0.5
        # True negatives don't affect recall
        assert "recall" in output
        assert output["recall"] == 0.5

    def test_calculate_no_actual_positives(self):
        """Test calculate when no golden values are the positive class"""
        metric = RecallMetric(golden_key="class", positive_class="click")
        results = [
            UnitMetricResult(
                correct=True,
                golden={"class": "type"},
                predicted={"class": "type"},
            ),
            UnitMetricResult(
                correct=True,
                golden={"class": "scroll"},
                predicted={"class": "scroll"},
            ),
            UnitMetricResult(
                correct=True,
                golden={"class": "hover"},
                predicted={"class": "hover"},
            ),
        ]
        output = metric.calculate(results)

        # TP = 0, FN = 0, Recall = 0/0 = 0.0 (safe divide)
        assert "recall" in output
        assert output["recall"] == 0.0

    def test_calculate_with_different_golden_key(self):
        """Test calculate with different golden_key"""
        metric = RecallMetric(golden_key="event", positive_class="click")
        results = [
            UnitMetricResult(
                correct=True,
                golden={"event": "click"},
                predicted={"tool": "click"},
            ),
            UnitMetricResult(
                correct=False,
                golden={"event": "click"},
                predicted={"tool": "type"},
            ),
            UnitMetricResult(
                correct=True,
                golden={"event": "click"},
                predicted={"tool": "click"},
            ),
        ]
        output = metric.calculate(results)

        # TP = 2, FN = 1, Recall = 2/(2+1) = 0.666...
        assert "recall" in output
        assert output["recall"] == pytest.approx(0.666, rel=1e-2)

    def test_calculate_with_numeric_positive_class(self):
        """Test calculate with numeric positive class"""
        metric = RecallMetric(golden_key="label", positive_class=1)
        results = [
            UnitMetricResult(correct=True, golden={"label": 1}, predicted={"label": 1}),
            UnitMetricResult(correct=False, golden={"label": 1}, predicted={"label": 0}),
            UnitMetricResult(correct=True, golden={"label": 1}, predicted={"label": 1}),
            UnitMetricResult(correct=True, golden={"label": 0}, predicted={"label": 0}),
        ]
        output = metric.calculate(results)

        # TP = 2, FN = 1, Recall = 2/(2+1) = 0.666...
        assert "recall" in output
        assert output["recall"] == pytest.approx(0.666, rel=1e-2)

    def test_calculate_with_boolean_positive_class(self):
        """Test calculate with boolean positive class"""
        metric = RecallMetric(golden_key="is_valid", positive_class=True)
        results = [
            UnitMetricResult(
                correct=True,
                golden={"is_valid": True},
                predicted={"is_valid": True},
            ),
            UnitMetricResult(
                correct=True,
                golden={"is_valid": True},
                predicted={"is_valid": True},
            ),
            UnitMetricResult(
                correct=False,
                golden={"is_valid": True},
                predicted={"is_valid": False},
            ),
        ]
        output = metric.calculate(results)

        # TP = 2, FN = 1, Recall = 2/(2+1) = 0.666...
        assert "recall" in output
        assert output["recall"] == pytest.approx(0.666, rel=1e-2)

    def test_calculate_single_true_positive(self):
        """Test calculate with single true positive"""
        metric = RecallMetric(golden_key="class", positive_class="A")
        results = [UnitMetricResult(correct=True, golden={"class": "A"}, predicted={"class": "A"})]
        output = metric.calculate(results)

        assert "recall" in output
        assert output["recall"] == 1.0

    def test_calculate_single_false_negative(self):
        """Test calculate with single false negative"""
        metric = RecallMetric(golden_key="class", positive_class="A")
        results = [UnitMetricResult(correct=False, golden={"class": "A"}, predicted={"class": "B"})]
        output = metric.calculate(results)

        assert "recall" in output
        assert output["recall"] == 0.0

    def test_calculate_with_missing_golden_key(self):
        """Test calculate when golden dict doesn't have the key"""
        metric = RecallMetric(golden_key="class", positive_class="A")
        results = [
            UnitMetricResult(
                correct=False,
                golden={"other_key": "B"},  # Missing 'class' key
                predicted={"class": "A"},
            ),
            UnitMetricResult(correct=True, golden={"class": "A"}, predicted={"class": "A"}),
        ]
        output = metric.calculate(results)

        # Only 1 TP (second result), 0 FN
        assert "recall" in output
        assert output["recall"] == 1.0

    def test_calculate_various_recall_values(self):
        """Test calculate with various recall percentages"""
        # 80% recall (4 TP, 1 FN)
        metric = RecallMetric(golden_key="class", positive_class="A")
        results = [
            UnitMetricResult(correct=True, golden={"class": "A"}, predicted={"class": "A"}),
            UnitMetricResult(correct=True, golden={"class": "A"}, predicted={"class": "A"}),
            UnitMetricResult(correct=True, golden={"class": "A"}, predicted={"class": "A"}),
            UnitMetricResult(correct=True, golden={"class": "A"}, predicted={"class": "A"}),
            UnitMetricResult(correct=False, golden={"class": "A"}, predicted={"class": "B"}),
        ]
        output = metric.calculate(results)
        assert output["recall"] == 0.8

        # 25% recall (1 TP, 3 FN)
        results = [
            UnitMetricResult(correct=True, golden={"class": "A"}, predicted={"class": "A"}),
            UnitMetricResult(correct=False, golden={"class": "A"}, predicted={"class": "B"}),
            UnitMetricResult(correct=False, golden={"class": "A"}, predicted={"class": "C"}),
            UnitMetricResult(correct=False, golden={"class": "A"}, predicted={"class": "D"}),
        ]
        output = metric.calculate(results)
        assert output["recall"] == 0.25

    def test_calculate_with_false_positives_not_affecting_recall(self):
        """Test that false positives don't affect recall calculation"""
        metric = RecallMetric(golden_key="class", positive_class="A")
        results = [
            # True Positive
            UnitMetricResult(correct=True, golden={"class": "A"}, predicted={"class": "A"}),
            # False Positive (doesn't affect recall)
            UnitMetricResult(correct=False, golden={"class": "B"}, predicted={"class": "A"}),
            # False Positive (doesn't affect recall)
            UnitMetricResult(correct=False, golden={"class": "C"}, predicted={"class": "A"}),
        ]
        output = metric.calculate(results)

        # TP = 1, FN = 0, Recall = 1/(1+0) = 1.0
        # False positives don't affect recall
        assert "recall" in output
        assert output["recall"] == 1.0
