"""
Unit tests for PassPowerKMetric
Tests pass^k calculation from unit metric results.
"""

import os
import sys

# Add project root to sys.path for relative imports to work
sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", ".."))
)

import pytest

from sygra.core.eval.metrics.aggregator_metrics.pass_power_k import PassPowerKMetric
from sygra.core.eval.metrics.unit_metrics.unit_metric_result import UnitMetricResult
from sygra.logger.logger_config import logger


class TestPassPowerKMetric:
    """Test suite for PassAtKMetric"""

    def test_get_metric_name(self):
        """Test that metric name is 'pass^k'"""
        metric = PassPowerKMetric(k=1)
        assert metric.get_metric_name() == "pass^k"

    def test_calculate_empty_results(self):
        """Test calculate with empty results list"""
        metric = PassPowerKMetric(k=1)
        results = []
        output = metric.calculate(results)

        assert "pass^k" in output
        assert output["pass^k"] == 0.0

    def test_calculate_all_correct(self):
        """Test calculate when all predictions are correct"""
        metric = PassPowerKMetric(k=1)
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

        assert "pass^k" in output
        assert output["pass^k"] == 1.0

    def test_calculate_all_incorrect(self):
        """Test calculate when all predictions are incorrect"""
        metric = PassPowerKMetric(k=1)
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

        assert "pass^k" in output
        assert output["pass^k"] == 0.0

    def test_calculate_mixed_results(self):
        """Test calculate with mixed correct/incorrect predictions"""
        metric = PassPowerKMetric(k=1)
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

        assert "pass^k" in output
        assert output["pass^k"] == 0.5  # 2 correct out of 4

    def test_calculate_single_correct_result(self):
        """Test calculate with single correct result"""
        metric = PassPowerKMetric(k=1)
        results = [
            UnitMetricResult(
                correct=True,
                golden={"class": "A"},
                predicted={"class": "A"},
                metadata={"id": 1},
            ),
        ]
        output = metric.calculate(results)

        assert "pass^k" in output
        assert output["pass^k"] == 1.0

    def test_calculate_single_incorrect_result(self):
        """Test calculate with single incorrect result"""
        metric = PassPowerKMetric(k=1)
        results = [
            UnitMetricResult(
                correct=False,
                golden={"class": "A"},
                predicted={"class": "B"},
                metadata={"id": 1},
            ),
        ]
        output = metric.calculate(results)

        assert "pass^k" in output
        assert output["pass^k"] == 0.0

    def test_calculate_various_pass_at_k_values(self):
        """Test calculate with various pass^k percentages"""

        # 75% pass^k (3 out of 4)
        results = [
            UnitMetricResult(correct=True, golden={}, predicted={}),
            UnitMetricResult(correct=True, golden={}, predicted={}),
            UnitMetricResult(correct=True, golden={}, predicted={}),
            UnitMetricResult(correct=False, golden={}, predicted={}),
        ]
        output = PassPowerKMetric(k=1).calculate(results)
        assert output["pass^k"] == 0.75

        output = PassPowerKMetric(k=2).calculate(results)
        assert output["pass^k"] == 0.5625

        output = PassPowerKMetric(k=3).calculate(results)
        assert output["pass^k"] == 0.421875

        # 60% pass^k (3 out of 5)
        results = [
            UnitMetricResult(correct=True, golden={}, predicted={}),
            UnitMetricResult(correct=True, golden={}, predicted={}),
            UnitMetricResult(correct=True, golden={}, predicted={}),
            UnitMetricResult(correct=False, golden={}, predicted={}),
            UnitMetricResult(correct=False, golden={}, predicted={}),
        ]
        output = PassPowerKMetric(k=1).calculate(results)
        assert output["pass^k"] == 0.6

        output = PassPowerKMetric(k=2).calculate(results)
        assert output["pass^k"] == 0.36

        # 33.33% pass^k (1 out of 3)
        results = [
            UnitMetricResult(correct=True, golden={}, predicted={}),
            UnitMetricResult(correct=False, golden={}, predicted={}),
            UnitMetricResult(correct=False, golden={}, predicted={}),
        ]
        output = PassPowerKMetric(k=1).calculate(results)
        assert output["pass^k"] == pytest.approx(0.333, rel=1e-2)

        output = PassPowerKMetric(k=2).calculate(results)
        assert output["pass^k"] == pytest.approx(0.111, rel=1e-2)

    def test_calculate_with_complex_metadata(self):
        """Test calculate with complex metadata in results"""
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
        output = PassPowerKMetric(k=1).calculate(results)
        assert "pass^k" in output
        assert output["pass^k"] == 0.5

        output = PassPowerKMetric(k=2).calculate(results)
        assert "pass^k" in output
        assert output["pass^k"] == 0.25

    def test_calculate_with_different_data_types(self):
        """Test calculate with different data types in golden/predicted"""
        logger.info("Testing calculate with different data types in golden/predicted")
        results = [
            UnitMetricResult(correct=True, golden={"value": 1}, predicted={"value": 1}),
            UnitMetricResult(correct=True, golden={"value": "text"}, predicted={"value": "text"}),
            UnitMetricResult(correct=True, golden={"value": True}, predicted={"value": True}),
            UnitMetricResult(correct=False, golden={"value": [1, 2]}, predicted={"value": [1, 3]}),
        ]
        output = PassPowerKMetric(k=1).calculate(results)
        assert "pass^k" in output
        assert output["pass^k"] == 0.75

        output = PassPowerKMetric(k=2).calculate(results)
        assert "pass^k" in output
        assert output["pass^k"] == 0.5625
