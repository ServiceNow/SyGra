"""
Unit tests for PrecisionMetric
Tests precision calculation (TP / (TP + FP)) from unit metric results.
"""

import os
import sys

# Add project root to sys.path for relative imports to work
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "..")))
import pytest
from sygra.core.metrics.aggregator_metrics.precision import PrecisionMetric
from sygra.core.metrics.unit_metrics.unit_metric_result import UnitMetricResult


class TestPrecisionMetric:
    """Test suite for PrecisionMetric"""

    def test_get_metric_name(self):
        """Test that metric name is 'precision'"""
        metric = PrecisionMetric(predicted_key="class", positive_class="A")
        assert metric.get_metric_name() == "precision"

    def test_initialization_with_parameters(self):
        """Test initialization with custom parameters"""
        metric = PrecisionMetric(predicted_key="tool", positive_class="click")
        assert metric.predicted_key == "tool"
        assert metric.positive_class == "click"

    def test_initialization_default_parameters(self):
        """Test initialization with default parameters"""
        metric = PrecisionMetric()
        assert metric.predicted_key == "class"
        assert metric.positive_class is None

    def test_calculate_raises_error_without_positive_class(self):
        """Test that calculate raises exception when positive_class is None"""
        metric = PrecisionMetric(predicted_key="class", positive_class=None)
        results = [
            UnitMetricResult(
                correct=True, golden={"class": "A"}, predicted={"class": "A"}
            )
        ]

        with pytest.raises(Exception) as exc_info:
            metric.calculate(results)
        assert "Positive class is not provided" in str(exc_info.value)

    def test_calculate_empty_results(self):
        """Test calculate with empty results list"""
        metric = PrecisionMetric(predicted_key="class", positive_class="A")
        results = []
        output = metric.calculate(results)

        assert "precision" in output
        assert output["precision"] == 0.0

    def test_calculate_perfect_precision(self):
        """Test calculate with perfect precision (all positive predictions are correct)"""
        metric = PrecisionMetric(predicted_key="class", positive_class="click")
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

        assert "precision" in output
        assert output["precision"] == 1.0

    def test_calculate_zero_precision(self):
        """Test calculate with zero precision (all positive predictions are wrong)"""
        metric = PrecisionMetric(predicted_key="class", positive_class="click")
        results = [
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

        assert "precision" in output
        assert output["precision"] == 0.0

    def test_calculate_mixed_precision(self):
        """Test calculate with mixed true positives and false positives"""
        metric = PrecisionMetric(predicted_key="class", positive_class="click")
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
            # True Positive
            UnitMetricResult(
                correct=True,
                golden={"class": "click"},
                predicted={"class": "click"},
            ),
            # False Positive
            UnitMetricResult(
                correct=False,
                golden={"class": "scroll"},
                predicted={"class": "click"},
            ),
        ]
        output = metric.calculate(results)

        # TP = 2, FP = 2, Precision = 2/(2+2) = 0.5
        assert "precision" in output
        assert output["precision"] == 0.5

    def test_calculate_with_negative_class_predictions(self):
        """Test calculate when some predictions are not the positive class"""
        metric = PrecisionMetric(predicted_key="class", positive_class="click")
        results = [
            # True Positive
            UnitMetricResult(
                correct=True,
                golden={"class": "click"},
                predicted={"class": "click"},
            ),
            # True Negative (not predicted as positive class)
            UnitMetricResult(
                correct=True,
                golden={"class": "type"},
                predicted={"class": "type"},
            ),
            # False Positive
            UnitMetricResult(
                correct=False,
                golden={"class": "scroll"},
                predicted={"class": "click"},
            ),
            # True Negative
            UnitMetricResult(
                correct=True,
                golden={"class": "hover"},
                predicted={"class": "hover"},
            ),
        ]
        output = metric.calculate(results)

        # TP = 1, FP = 1, Precision = 1/(1+1) = 0.5
        # True negatives don't affect precision
        assert "precision" in output
        assert output["precision"] == 0.5

    def test_calculate_no_positive_predictions(self):
        """Test calculate when no predictions are the positive class"""
        metric = PrecisionMetric(predicted_key="class", positive_class="click")
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

        # TP = 0, FP = 0, Precision = 0/0 = 0.0 (safe divide)
        assert "precision" in output
        assert output["precision"] == 0.0

    def test_calculate_with_different_predicted_key(self):
        """Test calculate with different predicted_key"""
        metric = PrecisionMetric(predicted_key="tool", positive_class="click")
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
                correct=True,
                golden={"event": "click"},
                predicted={"tool": "click"},
            ),
        ]
        output = metric.calculate(results)

        # TP = 2, FP = 1, Precision = 2/(2+1) = 0.666...
        assert "precision" in output
        assert output["precision"] == pytest.approx(0.666, rel=1e-2)

    def test_calculate_with_numeric_positive_class(self):
        """Test calculate with numeric positive class"""
        metric = PrecisionMetric(predicted_key="label", positive_class=1)
        results = [
            UnitMetricResult(
                correct=True, golden={"label": 1}, predicted={"label": 1}
            ),
            UnitMetricResult(
                correct=False, golden={"label": 0}, predicted={"label": 1}
            ),
            UnitMetricResult(
                correct=True, golden={"label": 1}, predicted={"label": 1}
            ),
            UnitMetricResult(
                correct=True, golden={"label": 0}, predicted={"label": 0}
            ),
        ]
        output = metric.calculate(results)

        # TP = 2, FP = 1, Precision = 2/(2+1) = 0.666...
        assert "precision" in output
        assert output["precision"] == pytest.approx(0.666, rel=1e-2)

    def test_calculate_with_boolean_positive_class(self):
        """Test calculate with boolean positive class"""
        metric = PrecisionMetric(predicted_key="is_valid", positive_class=True)
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
        ]
        output = metric.calculate(results)

        # TP = 2, FP = 1, Precision = 2/(2+1) = 0.666...
        assert "precision" in output
        assert output["precision"] == pytest.approx(0.666, rel=1e-2)

    def test_calculate_single_true_positive(self):
        """Test calculate with single true positive"""
        metric = PrecisionMetric(predicted_key="class", positive_class="A")
        results = [
            UnitMetricResult(
                correct=True, golden={"class": "A"}, predicted={"class": "A"}
            )
        ]
        output = metric.calculate(results)

        assert "precision" in output
        assert output["precision"] == 1.0

    def test_calculate_single_false_positive(self):
        """Test calculate with single false positive"""
        metric = PrecisionMetric(predicted_key="class", positive_class="A")
        results = [
            UnitMetricResult(
                correct=False, golden={"class": "B"}, predicted={"class": "A"}
            )
        ]
        output = metric.calculate(results)

        assert "precision" in output
        assert output["precision"] == 0.0

    def test_calculate_with_missing_predicted_key(self):
        """Test calculate when predicted dict doesn't have the key"""
        metric = PrecisionMetric(predicted_key="class", positive_class="A")
        results = [
            UnitMetricResult(
                correct=False,
                golden={"class": "A"},
                predicted={"other_key": "B"},  # Missing 'class' key
            ),
            UnitMetricResult(
                correct=True, golden={"class": "A"}, predicted={"class": "A"}
            ),
        ]
        output = metric.calculate(results)

        # Only 1 TP (second result), 0 FP
        assert "precision" in output
        assert output["precision"] == 1.0

    def test_calculate_various_precision_values(self):
        """Test calculate with various precision percentages"""
        # 80% precision (4 TP, 1 FP)
        metric = PrecisionMetric(predicted_key="class", positive_class="A")
        results = [
            UnitMetricResult(correct=True, golden={"class": "A"}, predicted={"class": "A"}),
            UnitMetricResult(correct=True, golden={"class": "A"}, predicted={"class": "A"}),
            UnitMetricResult(correct=True, golden={"class": "A"}, predicted={"class": "A"}),
            UnitMetricResult(correct=True, golden={"class": "A"}, predicted={"class": "A"}),
            UnitMetricResult(correct=False, golden={"class": "B"}, predicted={"class": "A"}),
        ]
        output = metric.calculate(results)
        assert output["precision"] == 0.8

        # 25% precision (1 TP, 3 FP)
        results = [
            UnitMetricResult(correct=True, golden={"class": "A"}, predicted={"class": "A"}),
            UnitMetricResult(correct=False, golden={"class": "B"}, predicted={"class": "A"}),
            UnitMetricResult(correct=False, golden={"class": "C"}, predicted={"class": "A"}),
            UnitMetricResult(correct=False, golden={"class": "D"}, predicted={"class": "A"}),
        ]
        output = metric.calculate(results)
        assert output["precision"] == 0.25
