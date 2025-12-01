"""
Unit tests for AccuracyMetric
Tests accuracy calculation from unit metric results.
"""

import os
import sys

# Add project root to sys.path for relative imports to work
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "..")))

import pytest

from sygra.core.metrics.aggregator_metrics.accuracy import AccuracyMetric
from sygra.core.metrics.unit_metrics.unit_metric_result import UnitMetricResult
from sygra.logger.logger_config import logger


class TestAccuracyMetric:
    """Test suite for AccuracyMetric"""

    def test_get_metric_name(self):
        """Test that metric name is 'accuracy'"""
        metric = AccuracyMetric()
        assert metric.get_metric_name() == "accuracy"

    def test_calculate_empty_results(self):
        """Test calculate with empty results list"""
        metric = AccuracyMetric()
        results = []
        output = metric.calculate(results)

        assert "accuracy" in output
        assert output["accuracy"] == 0.0

    def test_calculate_all_correct(self):
        """Test calculate when all predictions are correct"""
        metric = AccuracyMetric()
        results = [
            UnitMetricResult(
                correct=True,
                golden={"class": "A"},
                predicted={"class": "A"},
                metadata={"id": 1},
            ),
            UnitMetricResult(
                correct=True,
                golden={"class": "B"},
                predicted={"class": "B"},
                metadata={"id": 2},
            ),
            UnitMetricResult(
                correct=True,
                golden={"class": "C"},
                predicted={"class": "C"},
                metadata={"id": 3},
            ),
        ]
        output = metric.calculate(results)

        assert "accuracy" in output
        assert output["accuracy"] == 1.0

    def test_calculate_all_incorrect(self):
        """Test calculate when all predictions are incorrect"""
        metric = AccuracyMetric()
        results = [
            UnitMetricResult(
                correct=False,
                golden={"class": "A"},
                predicted={"class": "B"},
                metadata={"id": 1},
            ),
            UnitMetricResult(
                correct=False,
                golden={"class": "B"},
                predicted={"class": "C"},
                metadata={"id": 2},
            ),
            UnitMetricResult(
                correct=False,
                golden={"class": "C"},
                predicted={"class": "A"},
                metadata={"id": 3},
            ),
        ]
        output = metric.calculate(results)

        assert "accuracy" in output
        assert output["accuracy"] == 0.0

    def test_calculate_mixed_results(self):
        """Test calculate with mixed correct/incorrect predictions"""
        metric = AccuracyMetric()
        results = [
            UnitMetricResult(
                correct=True,
                golden={"class": "A"},
                predicted={"class": "A"},
                metadata={"id": 1},
            ),
            UnitMetricResult(
                correct=False,
                golden={"class": "B"},
                predicted={"class": "C"},
                metadata={"id": 2},
            ),
            UnitMetricResult(
                correct=True,
                golden={"class": "C"},
                predicted={"class": "C"},
                metadata={"id": 3},
            ),
            UnitMetricResult(
                correct=False,
                golden={"class": "D"},
                predicted={"class": "A"},
                metadata={"id": 4},
            ),
        ]
        output = metric.calculate(results)

        assert "accuracy" in output
        assert output["accuracy"] == 0.5  # 2 correct out of 4

    def test_calculate_single_correct_result(self):
        """Test calculate with single correct result"""
        metric = AccuracyMetric()
        results = [
            UnitMetricResult(
                correct=True,
                golden={"class": "A"},
                predicted={"class": "A"},
                metadata={"id": 1},
            ),
        ]
        output = metric.calculate(results)

        assert "accuracy" in output
        assert output["accuracy"] == 1.0

    def test_calculate_single_incorrect_result(self):
        """Test calculate with single incorrect result"""
        metric = AccuracyMetric()
        results = [
            UnitMetricResult(
                correct=False,
                golden={"class": "A"},
                predicted={"class": "B"},
                metadata={"id": 1},
            ),
        ]
        output = metric.calculate(results)

        assert "accuracy" in output
        assert output["accuracy"] == 0.0

    def test_calculate_various_accuracy_values(self):
        """Test calculate with various accuracy percentages"""
        metric = AccuracyMetric()

        # 75% accuracy (3 out of 4)
        results = [
            UnitMetricResult(correct=True, golden={}, predicted={}),
            UnitMetricResult(correct=True, golden={}, predicted={}),
            UnitMetricResult(correct=True, golden={}, predicted={}),
            UnitMetricResult(correct=False, golden={}, predicted={}),
        ]
        output = metric.calculate(results)
        assert output["accuracy"] == 0.75

        # 60% accuracy (3 out of 5)
        results = [
            UnitMetricResult(correct=True, golden={}, predicted={}),
            UnitMetricResult(correct=True, golden={}, predicted={}),
            UnitMetricResult(correct=True, golden={}, predicted={}),
            UnitMetricResult(correct=False, golden={}, predicted={}),
            UnitMetricResult(correct=False, golden={}, predicted={}),
        ]
        output = metric.calculate(results)
        assert output["accuracy"] == 0.6

        # 33.33% accuracy (1 out of 3)
        results = [
            UnitMetricResult(correct=True, golden={}, predicted={}),
            UnitMetricResult(correct=False, golden={}, predicted={}),
            UnitMetricResult(correct=False, golden={}, predicted={}),
        ]
        output = metric.calculate(results)
        assert output["accuracy"] == pytest.approx(0.333, rel=1e-2)

    def test_empty_result_method(self):
        """Test _empty_result method"""
        metric = AccuracyMetric()
        empty_result = metric._empty_result()

        assert "accuracy" in empty_result
        assert empty_result["accuracy"] == 0.0

    def test_calculate_with_complex_metadata(self):
        """Test calculate with complex metadata in results"""
        metric = AccuracyMetric()
        results = [
            UnitMetricResult(
                correct=True,
                golden={"event": "click", "x": 100, "y": 200},
                predicted={"tool": "click", "x": 105, "y": 195},
                metadata={
                    "mission_id": "mission_01",
                    "step_id": "step_1",
                    "validation_type": "tool_only",
                },
            ),
            UnitMetricResult(
                correct=False,
                golden={"event": "type", "text": "hello"},
                predicted={"tool": "click", "text": "world"},
                metadata={
                    "mission_id": "mission_01",
                    "step_id": "step_2",
                    "validation_type": "full",
                },
            ),
        ]
        output = metric.calculate(results)

        assert "accuracy" in output
        assert output["accuracy"] == 0.5

    def test_calculate_with_different_data_types(self):
        """Test calculate with different data types in golden/predicted"""
        logger.info("Testing calculate with different data types in golden/predicted")
        metric = AccuracyMetric()
        results = [
            UnitMetricResult(correct=True, golden={"value": 1}, predicted={"value": 1}),
            UnitMetricResult(correct=True, golden={"value": "text"}, predicted={"value": "text"}),
            UnitMetricResult(correct=True, golden={"value": True}, predicted={"value": True}),
            UnitMetricResult(correct=False, golden={"value": [1, 2]}, predicted={"value": [1, 3]}),
        ]
        output = metric.calculate(results)

        assert "accuracy" in output
        assert output["accuracy"] == 0.75
