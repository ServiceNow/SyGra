"""
Unit tests for F1ScoreMetric
Tests F1 score calculation (harmonic mean of precision and recall) from unit metric results.
"""

import os
import sys

# Add project root to sys.path for relative imports to work
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "..")))
import pytest

from sygra.core.eval.metrics.aggregator_metrics.f1_score import F1ScoreMetric
from sygra.core.eval.metrics.unit_metrics.unit_metric_result import UnitMetricResult


class TestF1ScoreMetric:
    """Test suite for F1ScoreMetric"""

    def test_get_metric_name(self):
        """Test that metric name is 'f1_score'"""
        metric = F1ScoreMetric(predicted_key="class", golden_key="class", positive_class="A")
        assert metric.get_metric_name() == "f1_score"

    def test_initialization_with_parameters(self):
        """Test initialization with custom parameters"""
        metric = F1ScoreMetric(predicted_key="tool", golden_key="event", positive_class="click")
        assert metric.predicted_key == "tool"
        assert metric.golden_key == "event"
        assert metric.positive_class == "click"

    def test_initialization_requires_parameters(self):
        """Test that initialization requires predicted_key, golden_key, and positive_class"""
        # Should raise TypeError when parameters are missing
        with pytest.raises(TypeError):
            F1ScoreMetric(golden_key="class", positive_class="A")

        with pytest.raises(TypeError):
            F1ScoreMetric(predicted_key="class", positive_class="A")

        with pytest.raises(TypeError):
            F1ScoreMetric(predicted_key="class", golden_key="class")

        # Should raise ValueError when predicted_key is empty
        with pytest.raises(ValueError) as exc_info:
            F1ScoreMetric(predicted_key="", golden_key="class", positive_class="A")
        assert "predicted_key cannot be empty" in str(exc_info.value)

        # Should raise ValueError when golden_key is empty
        with pytest.raises(ValueError) as exc_info:
            F1ScoreMetric(predicted_key="class", golden_key="", positive_class="A")
        assert "golden_key cannot be empty" in str(exc_info.value)

        # Should raise ValueError when positive_class is None
        with pytest.raises(ValueError) as exc_info:
            F1ScoreMetric(predicted_key="class", golden_key="class", positive_class=None)
        assert "positive_class is required" in str(exc_info.value)

    def test_initialization_creates_precision_and_recall_metrics(self):
        """Test that initialization creates precision and recall metric instances"""
        metric = F1ScoreMetric(predicted_key="tool", golden_key="event", positive_class="click")
        assert metric.precision_metric is not None
        assert metric.recall_metric is not None
        assert metric.precision_metric.predicted_key == "tool"
        assert metric.recall_metric.golden_key == "event"

    def test_calculate_empty_results(self):
        """Test calculate with empty results list"""
        metric = F1ScoreMetric(predicted_key="class", golden_key="class", positive_class="A")
        results = []
        output = metric.calculate(results)

        assert "f1_score" in output
        assert output["f1_score"] == 0.0

    def test_calculate_perfect_f1_score(self):
        """Test calculate with perfect F1 score (precision=1.0, recall=1.0)"""
        metric = F1ScoreMetric(predicted_key="class", golden_key="class", positive_class="click")
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

        assert "f1_score" in output
        assert output["f1_score"] == 1.0

    def test_calculate_zero_f1_score(self):
        """Test calculate with zero F1 score (no true positives)"""
        metric = F1ScoreMetric(predicted_key="class", golden_key="class", positive_class="click")
        results = [
            # False Positives
            UnitMetricResult(
                correct=False,
                golden={"class": "type"},
                predicted={"class": "click"},
            ),
            # False Negatives
            UnitMetricResult(
                correct=False,
                golden={"class": "click"},
                predicted={"class": "type"},
            ),
        ]
        output = metric.calculate(results)

        assert "f1_score" in output
        assert output["f1_score"] == 0.0

    def test_calculate_balanced_f1_score(self):
        """Test calculate with balanced precision and recall"""
        metric = F1ScoreMetric(predicted_key="class", golden_key="class", positive_class="click")
        results = [
            # True Positive
            UnitMetricResult(
                correct=True,
                golden={"class": "click"},
                predicted={"class": "click"},
            ),
            # False Positive
            UnitMetricResult(
                correct=False,
                golden={"class": "type"},
                predicted={"class": "click"},
            ),
            # False Negative
            UnitMetricResult(
                correct=False,
                golden={"class": "click"},
                predicted={"class": "type"},
            ),
        ]
        output = metric.calculate(results)

        # TP=1, FP=1, FN=1
        # Precision = 1/(1+1) = 0.5
        # Recall = 1/(1+1) = 0.5
        # F1 = 2 * (0.5 * 0.5) / (0.5 + 0.5) = 0.5
        assert "f1_score" in output
        assert output["f1_score"] == 0.5

    def test_calculate_high_precision_low_recall(self):
        """Test calculate with high precision but low recall"""
        metric = F1ScoreMetric(predicted_key="class", golden_key="class", positive_class="click")
        results = [
            # True Positive
            UnitMetricResult(
                correct=True,
                golden={"class": "click"},
                predicted={"class": "click"},
            ),
            # False Negatives (missed positives)
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

        # TP=1, FP=0, FN=3
        # Precision = 1/(1+0) = 1.0
        # Recall = 1/(1+3) = 0.25
        # F1 = 2 * (1.0 * 0.25) / (1.0 + 0.25) = 0.4
        assert "f1_score" in output
        assert output["f1_score"] == 0.4

    def test_calculate_low_precision_high_recall(self):
        """Test calculate with low precision but high recall"""
        metric = F1ScoreMetric(predicted_key="class", golden_key="class", positive_class="click")
        results = [
            # True Positive
            UnitMetricResult(
                correct=True,
                golden={"class": "click"},
                predicted={"class": "click"},
            ),
            # False Positives (wrong predictions)
            UnitMetricResult(
                correct=False,
                golden={"class": "type"},
                predicted={"class": "click"},
            ),
            UnitMetricResult(
                correct=False,
                golden={"class": "scroll"},
                predicted={"class": "click"},
            ),
            UnitMetricResult(
                correct=False,
                golden={"class": "hover"},
                predicted={"class": "click"},
            ),
        ]
        output = metric.calculate(results)

        # TP=1, FP=3, FN=0
        # Precision = 1/(1+3) = 0.25
        # Recall = 1/(1+0) = 1.0
        # F1 = 2 * (0.25 * 1.0) / (0.25 + 1.0) = 0.4
        assert "f1_score" in output
        assert output["f1_score"] == 0.4

    def test_calculate_with_different_keys(self):
        """Test calculate with different predicted_key and golden_key"""
        metric = F1ScoreMetric(predicted_key="tool", golden_key="event", positive_class="click")
        results = [
            UnitMetricResult(
                correct=True,
                golden={"event": "click"},
                predicted={"tool": "click"},
            ),
            UnitMetricResult(
                correct=False,
                golden={"event": "type"},
                predicted={"tool": "click"},
            ),
            UnitMetricResult(
                correct=False,
                golden={"event": "click"},
                predicted={"tool": "type"},
            ),
        ]
        output = metric.calculate(results)

        # TP=1, FP=1, FN=1
        # Precision = 1/(1+1) = 0.5
        # Recall = 1/(1+1) = 0.5
        # F1 = 0.5
        assert "f1_score" in output
        assert output["f1_score"] == 0.5

    def test_calculate_with_numeric_positive_class(self):
        """Test calculate with numeric positive class"""
        metric = F1ScoreMetric(predicted_key="label", golden_key="label", positive_class=1)
        results = [
            UnitMetricResult(correct=True, golden={"label": 1}, predicted={"label": 1}),
            UnitMetricResult(correct=True, golden={"label": 1}, predicted={"label": 1}),
            UnitMetricResult(correct=False, golden={"label": 0}, predicted={"label": 1}),
            UnitMetricResult(correct=False, golden={"label": 1}, predicted={"label": 0}),
        ]
        output = metric.calculate(results)

        # TP=2, FP=1, FN=1
        # Precision = 2/(2+1) = 0.666...
        # Recall = 2/(2+1) = 0.666...
        # F1 = 2 * (0.666 * 0.666) / (0.666 + 0.666) = 0.666...
        assert "f1_score" in output
        assert output["f1_score"] == pytest.approx(0.666, rel=1e-2)

    def test_calculate_with_boolean_positive_class(self):
        """Test calculate with boolean positive class"""
        metric = F1ScoreMetric(predicted_key="is_valid", golden_key="is_valid", positive_class=True)
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
                golden={"is_valid": False},
                predicted={"is_valid": True},
            ),
            UnitMetricResult(
                correct=False,
                golden={"is_valid": True},
                predicted={"is_valid": False},
            ),
        ]
        output = metric.calculate(results)

        # TP=2, FP=1, FN=1
        # Precision = 2/(2+1) = 0.666...
        # Recall = 2/(2+1) = 0.666...
        # F1 = 0.666...
        assert "f1_score" in output
        assert output["f1_score"] == pytest.approx(0.666, rel=1e-2)

    def test_calculate_single_true_positive(self):
        """Test calculate with single true positive"""
        metric = F1ScoreMetric(predicted_key="class", golden_key="class", positive_class="A")
        results = [UnitMetricResult(correct=True, golden={"class": "A"}, predicted={"class": "A"})]
        output = metric.calculate(results)

        # TP=1, FP=0, FN=0
        # Precision = 1.0, Recall = 1.0, F1 = 1.0
        assert "f1_score" in output
        assert output["f1_score"] == 1.0

    def test_calculate_with_true_negatives(self):
        """Test calculate with true negatives (shouldn't affect F1)"""
        metric = F1ScoreMetric(predicted_key="class", golden_key="class", positive_class="A")
        results = [
            # True Positive
            UnitMetricResult(correct=True, golden={"class": "A"}, predicted={"class": "A"}),
            # True Negatives (shouldn't affect F1)
            UnitMetricResult(correct=True, golden={"class": "B"}, predicted={"class": "B"}),
            UnitMetricResult(correct=True, golden={"class": "C"}, predicted={"class": "C"}),
            # False Positive
            UnitMetricResult(correct=False, golden={"class": "B"}, predicted={"class": "A"}),
        ]
        output = metric.calculate(results)

        # TP=1, FP=1, FN=0
        # Precision = 1/(1+1) = 0.5
        # Recall = 1/(1+0) = 1.0
        # F1 = 2 * (0.5 * 1.0) / (0.5 + 1.0) = 0.666...
        assert "f1_score" in output
        assert output["f1_score"] == pytest.approx(0.666, rel=1e-2)

    def test_calculate_various_f1_values(self):
        """Test calculate with various F1 score values"""
        metric = F1ScoreMetric(predicted_key="class", golden_key="class", positive_class="A")

        # F1 = 0.8 (Precision=0.8, Recall=0.8)
        # TP=4, FP=1, FN=1
        results = [
            UnitMetricResult(correct=True, golden={"class": "A"}, predicted={"class": "A"}),
            UnitMetricResult(correct=True, golden={"class": "A"}, predicted={"class": "A"}),
            UnitMetricResult(correct=True, golden={"class": "A"}, predicted={"class": "A"}),
            UnitMetricResult(correct=True, golden={"class": "A"}, predicted={"class": "A"}),
            UnitMetricResult(correct=False, golden={"class": "B"}, predicted={"class": "A"}),
            UnitMetricResult(correct=False, golden={"class": "A"}, predicted={"class": "B"}),
        ]
        output = metric.calculate(results)
        assert output["f1_score"] == pytest.approx(0.8, rel=1e-9)

    def test_calculate_harmonic_mean_property(self):
        """Test that F1 is indeed the harmonic mean of precision and recall"""
        metric = F1ScoreMetric(predicted_key="class", golden_key="class", positive_class="A")
        results = [
            UnitMetricResult(correct=True, golden={"class": "A"}, predicted={"class": "A"}),
            UnitMetricResult(correct=True, golden={"class": "A"}, predicted={"class": "A"}),
            UnitMetricResult(correct=False, golden={"class": "B"}, predicted={"class": "A"}),
            UnitMetricResult(correct=False, golden={"class": "A"}, predicted={"class": "B"}),
            UnitMetricResult(correct=False, golden={"class": "A"}, predicted={"class": "C"}),
        ]
        output = metric.calculate(results)

        # TP=2, FP=1, FN=2
        # Precision = 2/(2+1) = 0.666...
        # Recall = 2/(2+2) = 0.5
        # F1 = 2 * (0.666 * 0.5) / (0.666 + 0.5) = 0.571...
        precision = 2 / 3
        recall = 2 / 4
        expected_f1 = 2 * (precision * recall) / (precision + recall)

        assert "f1_score" in output
        assert output["f1_score"] == pytest.approx(expected_f1, rel=1e-2)

    def test_calculate_when_precision_or_recall_is_zero(self):
        """Test calculate when either precision or recall is zero"""
        metric = F1ScoreMetric(predicted_key="class", golden_key="class", positive_class="A")

        # Only false positives (precision=0, recall undefined)
        results = [
            UnitMetricResult(correct=False, golden={"class": "B"}, predicted={"class": "A"}),
            UnitMetricResult(correct=False, golden={"class": "C"}, predicted={"class": "A"}),
        ]
        output = metric.calculate(results)
        assert output["f1_score"] == 0.0

        # Only false negatives (precision undefined, recall=0)
        results = [
            UnitMetricResult(correct=False, golden={"class": "A"}, predicted={"class": "B"}),
            UnitMetricResult(correct=False, golden={"class": "A"}, predicted={"class": "C"}),
        ]
        output = metric.calculate(results)
        assert output["f1_score"] == 0.0
