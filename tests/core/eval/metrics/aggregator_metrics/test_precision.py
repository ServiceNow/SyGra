"""
Unit tests for PrecisionMetric
Tests precision calculation (TP / (TP + FP)) from unit metric results.
"""

import os
import sys

# Add project root to sys.path for relative imports to work
sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", ".."))
)
import pytest
from pydantic import ValidationError

from sygra.core.eval.metrics.aggregator_metrics.precision import PrecisionMetric
from sygra.core.eval.metrics.unit_metrics.unit_metric_result import UnitMetricResult


class TestPrecisionMetric:
    """Test suite for PrecisionMetric"""

    def test_get_metric_name(self):
        """Test that metric name is 'precision'"""
        metric = PrecisionMetric(predicted_key="class")
        assert metric.get_metric_name() == "precision"

    def test_initialization_requires_predicted_key(self):
        """Test that initialization requires predicted_key"""
        with pytest.raises(ValidationError):
            PrecisionMetric()

        with pytest.raises(ValidationError):
            PrecisionMetric(predicted_key="")

    def test_calculate_empty_results(self):
        """Test calculate with empty results list"""
        metric = PrecisionMetric(predicted_key="class")
        output = metric.calculate([])

        assert output == {"average_precision": 0.0, "precision_per_class": {}}

    def test_calculate_precision_per_class_and_average(self):
        """Test precision per class and macro-average precision"""
        metric = PrecisionMetric(predicted_key="class")
        results = [
            UnitMetricResult(correct=True, golden={"class": "A"}, predicted={"class": "A"}),
            UnitMetricResult(correct=False, golden={"class": "B"}, predicted={"class": "A"}),
            UnitMetricResult(correct=True, golden={"class": "B"}, predicted={"class": "B"}),
            UnitMetricResult(correct=True, golden={"class": "B"}, predicted={"class": "B"}),
        ]
        output = metric.calculate(results)

        # Predicted counts: A=2, B=2
        # True positives by predicted label: A=1, B=2
        # precision(A)=1/2, precision(B)=2/2
        assert output["precision_per_class"] == {"A": 0.5, "B": 1.0}
        assert output["average_precision"] == pytest.approx((0.5 + 1.0) / 2)

    def test_calculate_skips_rows_missing_predicted_key(self):
        """Test that rows missing predicted_key are skipped"""
        metric = PrecisionMetric(predicted_key="class")
        results = [
            UnitMetricResult(correct=False, golden={"class": "A"}, predicted={"other": "A"}),
            UnitMetricResult(correct=True, golden={"class": "A"}, predicted={"class": "A"}),
        ]
        output = metric.calculate(results)

        assert output["precision_per_class"] == {"A": 1.0}
        assert output["average_precision"] == 1.0

    def test_calculate_returns_zero_when_all_rows_missing_predicted_key(self):
        """Test safe behavior when nothing is usable for calculation"""
        metric = PrecisionMetric(predicted_key="class")
        results = [
            UnitMetricResult(correct=True, golden={"class": "A"}, predicted={"other": "A"}),
            UnitMetricResult(correct=False, golden={"class": "B"}, predicted={"other": "B"}),
        ]
        output = metric.calculate(results)

        assert output == {"average_precision": 0.0, "precision_per_class": {}}

    def test_calculate_multi_class_precision(self):
        """Test multi-class precision computation across 3 classes"""
        metric = PrecisionMetric(predicted_key="class")
        results = [
            # Predicted A: 2 total, 1 correct => precision(A)=0.5
            UnitMetricResult(correct=True, golden={"class": "A"}, predicted={"class": "A"}),
            UnitMetricResult(correct=False, golden={"class": "B"}, predicted={"class": "A"}),
            # Predicted B: 3 total, 2 correct => precision(B)=2/3
            UnitMetricResult(correct=True, golden={"class": "B"}, predicted={"class": "B"}),
            UnitMetricResult(correct=True, golden={"class": "B"}, predicted={"class": "B"}),
            UnitMetricResult(correct=False, golden={"class": "C"}, predicted={"class": "B"}),
            # Predicted C: 1 total, 0 correct => precision(C)=0.0
            UnitMetricResult(correct=False, golden={"class": "A"}, predicted={"class": "C"}),
        ]
        output = metric.calculate(results)

        assert output["precision_per_class"] == {
            "A": 0.5,
            "B": pytest.approx(2 / 3),
            "C": 0.0,
        }
        assert output["average_precision"] == pytest.approx((0.5 + (2 / 3) + 0.0) / 3)
