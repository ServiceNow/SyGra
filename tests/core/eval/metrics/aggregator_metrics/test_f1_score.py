"""
Unit tests for F1ScoreMetric
Tests F1 score calculation (harmonic mean of precision and recall) from unit metric results.
"""

import os
import sys

# Add project root to sys.path for relative imports to work
sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", ".."))
)
import pytest
from pydantic import ValidationError

from sygra.core.eval.metrics.aggregator_metrics.f1_score import F1ScoreMetric
from sygra.core.eval.metrics.unit_metrics.unit_metric_result import UnitMetricResult


class TestF1ScoreMetric:
    """Test suite for F1ScoreMetric"""

    def test_get_metric_name(self):
        """Test that metric name is 'f1_score'"""
        metric = F1ScoreMetric(predicted_key="class", golden_key="class")
        assert metric.get_metric_name() == "f1_score"

    def test_initialization_requires_parameters(self):
        """Test that initialization requires predicted_key and golden_key"""
        with pytest.raises(ValidationError):
            F1ScoreMetric(golden_key="class")

        with pytest.raises(ValidationError):
            F1ScoreMetric(predicted_key="class")

        with pytest.raises(ValidationError):
            F1ScoreMetric(predicted_key="", golden_key="class")

        with pytest.raises(ValidationError):
            F1ScoreMetric(predicted_key="class", golden_key="")

    def test_initialization_creates_precision_and_recall_metrics(self):
        """Test that initialization creates precision and recall metric instances"""
        metric = F1ScoreMetric(predicted_key="tool", golden_key="event")
        assert metric.precision_metric is not None
        assert metric.recall_metric is not None
        assert metric.precision_metric.predicted_key == "tool"
        assert metric.recall_metric.golden_key == "event"

    def test_calculate_empty_results(self):
        """Test calculate with empty results list"""
        metric = F1ScoreMetric(predicted_key="class", golden_key="class")
        output = metric.calculate([])

        assert output == {"average_f1_score": 0.0, "f1_score_per_class": {}}

    def test_calculate_f1_per_class_and_average(self):
        """Test per-class F1 and macro-average F1"""
        metric = F1ScoreMetric(predicted_key="class", golden_key="class")
        results = [
            UnitMetricResult(correct=True, golden={"class": "A"}, predicted={"class": "A"}),
            UnitMetricResult(correct=False, golden={"class": "A"}, predicted={"class": "B"}),
            UnitMetricResult(correct=False, golden={"class": "B"}, predicted={"class": "A"}),
            UnitMetricResult(correct=True, golden={"class": "B"}, predicted={"class": "B"}),
        ]
        output = metric.calculate(results)

        assert set(output.keys()) == {"average_f1_score", "f1_score_per_class"}
        assert output["f1_score_per_class"]["A"] == pytest.approx(0.5)
        assert output["f1_score_per_class"]["B"] == pytest.approx(0.5)
        assert output["average_f1_score"] == pytest.approx(0.5)

    def test_calculate_union_of_classes(self):
        """Test that per-class output uses union of precision and recall classes"""
        metric = F1ScoreMetric(predicted_key="class", golden_key="class")
        results = [
            UnitMetricResult(correct=False, golden={"class": "A"}, predicted={"class": "B"}),
        ]
        output = metric.calculate(results)

        assert output["f1_score_per_class"] == {"A": 0.0, "B": 0.0}
        assert output["average_f1_score"] == 0.0

    def test_calculate_skips_rows_missing_keys(self):
        """Test that rows missing predicted or golden keys are skipped by underlying metrics"""
        metric = F1ScoreMetric(predicted_key="class", golden_key="class")
        results = [
            UnitMetricResult(correct=True, golden={"class": "A"}, predicted={"other": "A"}),
            UnitMetricResult(correct=True, golden={"other": "A"}, predicted={"class": "A"}),
            UnitMetricResult(correct=True, golden={"class": "A"}, predicted={"class": "A"}),
        ]
        output = metric.calculate(results)

        assert output["f1_score_per_class"] == {"A": 1.0}
        assert output["average_f1_score"] == 1.0

    def test_calculate_multi_class_f1(self):
        """Test multi-class F1 computation across 3 classes"""
        metric = F1ScoreMetric(predicted_key="class", golden_key="class")
        results = [
            # Class A:
            # predicted A: 2 total, 1 correct => P(A)=0.5
            # golden A: 2 total, 1 correct => R(A)=0.5
            UnitMetricResult(correct=True, golden={"class": "A"}, predicted={"class": "A"}),
            UnitMetricResult(correct=False, golden={"class": "A"}, predicted={"class": "B"}),
            UnitMetricResult(correct=False, golden={"class": "B"}, predicted={"class": "A"}),
            # Class B:
            # predicted B: 2 total, 1 correct => P(B)=0.5
            # golden B: 2 total, 1 correct => R(B)=0.5
            UnitMetricResult(correct=True, golden={"class": "B"}, predicted={"class": "B"}),
            # Class C:
            # predicted C: 1 total, 0 correct => P(C)=0
            # golden C: 1 total, 0 correct => R(C)=0
            UnitMetricResult(correct=False, golden={"class": "C"}, predicted={"class": "C"}),
        ]
        output = metric.calculate(results)

        assert output["f1_score_per_class"] == {
            "A": pytest.approx(0.5),
            "B": pytest.approx(0.5),
            "C": 0.0,
        }
        assert output["average_f1_score"] == pytest.approx((0.5 + 0.5 + 0.0) / 3)
