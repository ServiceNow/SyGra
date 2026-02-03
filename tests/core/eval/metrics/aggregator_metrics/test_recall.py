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
from pydantic import ValidationError

from sygra.core.eval.metrics.aggregator_metrics.recall import RecallMetric
from sygra.core.eval.metrics.unit_metrics.unit_metric_result import UnitMetricResult


class TestRecallMetric:
    """Test suite for RecallMetric"""

    def test_get_metric_name(self):
        """Test that metric name is 'recall'"""
        metric = RecallMetric(golden_key="class")
        assert metric.get_metric_name() == "recall"

    def test_initialization_requires_golden_key(self):
        """Test that initialization requires golden_key"""
        with pytest.raises(ValidationError):
            RecallMetric()

        with pytest.raises(ValidationError):
            RecallMetric(golden_key="")

    def test_calculate_empty_results(self):
        """Test calculate with empty results list"""
        metric = RecallMetric(golden_key="class")
        output = metric.calculate([])

        assert output == {"average_recall": 0.0, "recall_per_class": {}}

    def test_calculate_recall_per_class_and_average(self):
        """Test recall per class and macro-average recall"""
        metric = RecallMetric(golden_key="class")
        results = [
            UnitMetricResult(correct=True, golden={"class": "A"}, predicted={"class": "A"}),
            UnitMetricResult(correct=False, golden={"class": "A"}, predicted={"class": "B"}),
            UnitMetricResult(correct=True, golden={"class": "B"}, predicted={"class": "B"}),
            UnitMetricResult(correct=True, golden={"class": "B"}, predicted={"class": "B"}),
        ]
        output = metric.calculate(results)

        # Golden counts: A=2, B=2
        # True positives by golden label: A=1, B=2
        # recall(A)=1/2, recall(B)=2/2
        assert output["recall_per_class"] == {"A": 0.5, "B": 1.0}
        assert output["average_recall"] == pytest.approx((0.5 + 1.0) / 2)

    def test_calculate_skips_rows_missing_golden_key(self):
        """Test that rows missing golden_key are skipped"""
        metric = RecallMetric(golden_key="class")
        results = [
            UnitMetricResult(correct=False, golden={"other": "A"}, predicted={"class": "A"}),
            UnitMetricResult(correct=True, golden={"class": "A"}, predicted={"class": "A"}),
        ]
        output = metric.calculate(results)

        assert output["recall_per_class"] == {"A": 1.0}
        assert output["average_recall"] == 1.0

    def test_calculate_returns_zero_when_all_rows_missing_golden_key(self):
        """Test safe behavior when nothing is usable for calculation"""
        metric = RecallMetric(golden_key="class")
        results = [
            UnitMetricResult(correct=True, golden={"other": "A"}, predicted={"class": "A"}),
            UnitMetricResult(correct=False, golden={"other": "B"}, predicted={"class": "B"}),
        ]
        output = metric.calculate(results)

        assert output == {"average_recall": 0.0, "recall_per_class": {}}

    def test_calculate_multi_class_recall(self):
        """Test multi-class recall computation across 3 classes"""
        metric = RecallMetric(golden_key="class")
        results = [
            # Golden A: 2 total, 1 correct => recall(A)=0.5
            UnitMetricResult(correct=True, golden={"class": "A"}, predicted={"class": "A"}),
            UnitMetricResult(correct=False, golden={"class": "A"}, predicted={"class": "B"}),
            # Golden B: 3 total, 2 correct => recall(B)=2/3
            UnitMetricResult(correct=True, golden={"class": "B"}, predicted={"class": "B"}),
            UnitMetricResult(correct=True, golden={"class": "B"}, predicted={"class": "B"}),
            UnitMetricResult(correct=False, golden={"class": "B"}, predicted={"class": "C"}),
            # Golden C: 1 total, 0 correct => recall(C)=0.0
            UnitMetricResult(correct=False, golden={"class": "C"}, predicted={"class": "A"}),
        ]
        output = metric.calculate(results)

        assert output["recall_per_class"] == {
            "A": 0.5,
            "B": pytest.approx(2 / 3),
            "C": 0.0,
        }
        assert output["average_recall"] == pytest.approx((0.5 + (2 / 3) + 0.0) / 3)
