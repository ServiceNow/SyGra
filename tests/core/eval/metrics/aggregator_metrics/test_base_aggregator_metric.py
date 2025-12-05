"""
Unit tests for BaseAggregatorMetric
Tests the abstract base class and its helper methods.
"""

import os
import sys

# Add project root to sys.path for relative imports to work
sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", ".."))
)

import pytest

from sygra.core.eval.metrics.aggregator_metrics.aggregator_metric_registry import aggregator_metric
from sygra.core.eval.metrics.aggregator_metrics.base_aggregator_metric import BaseAggregatorMetric
from sygra.core.eval.metrics.unit_metrics.unit_metric_result import UnitMetricResult


class ConcreteMetric(BaseAggregatorMetric):
    """Concrete implementation for testing abstract base class"""

    def validate_config(self):
        """No config validation needed for test metric"""
        pass

    def get_metadata(self):
        """Return test metadata"""
        from sygra.core.eval.metrics.base_metric_metadata import BaseMetricMetadata

        return BaseMetricMetadata(
            name="test_metric",
            display_name="Test Metric",
            description="Test metric for unit tests",
            range=(0.0, 1.0),
            higher_is_better=True,
            metric_type="custom",
        )

    def calculate(self, results):
        return {"test": 1.0}


class TestBaseAggregatorMetric:
    """Test suite for BaseAggregatorMetric"""

    def test_cannot_instantiate_abstract_class(self):
        """Test that BaseAggregatorMetric cannot be instantiated directly"""
        with pytest.raises(TypeError):
            BaseAggregatorMetric()

    def test_concrete_implementation_can_be_instantiated(self):
        """Test that concrete implementations can be instantiated"""
        metric = ConcreteMetric()
        assert metric is not None
        assert metric.get_metric_name() == "test_metric"

    def test_count_correct_empty_list(self):
        """Test _count_correct with empty list"""
        metric = ConcreteMetric()
        results = []
        assert metric._count_correct(results) == 0

    def test_count_correct_all_correct(self):
        """Test _count_correct when all results are correct"""
        metric = ConcreteMetric()
        results = [
            UnitMetricResult(correct=True, golden={"class": "A"}, predicted={"class": "A"}),
            UnitMetricResult(correct=True, golden={"class": "B"}, predicted={"class": "B"}),
            UnitMetricResult(correct=True, golden={"class": "C"}, predicted={"class": "C"}),
        ]
        assert metric._count_correct(results) == 3

    def test_count_correct_mixed_results(self):
        """Test _count_correct with mixed correct/incorrect results"""
        metric = ConcreteMetric()
        results = [
            UnitMetricResult(correct=True, golden={"class": "A"}, predicted={"class": "A"}),
            UnitMetricResult(correct=False, golden={"class": "B"}, predicted={"class": "C"}),
            UnitMetricResult(correct=True, golden={"class": "D"}, predicted={"class": "D"}),
            UnitMetricResult(correct=False, golden={"class": "E"}, predicted={"class": "F"}),
        ]
        assert metric._count_correct(results) == 2

    def test_count_correct_all_incorrect(self):
        """Test _count_correct when all results are incorrect"""
        metric = ConcreteMetric()
        results = [
            UnitMetricResult(correct=False, golden={"class": "A"}, predicted={"class": "B"}),
            UnitMetricResult(correct=False, golden={"class": "C"}, predicted={"class": "D"}),
        ]
        assert metric._count_correct(results) == 0

    def test_safe_divide_normal_case(self):
        """Test _safe_divide with normal values"""
        metric = ConcreteMetric()
        assert metric._safe_divide(10, 2) == 5.0
        assert metric._safe_divide(7, 3) == pytest.approx(2.333, rel=1e-2)
        assert metric._safe_divide(1, 4) == 0.25

    def test_safe_divide_zero_numerator(self):
        """Test _safe_divide with zero numerator"""
        metric = ConcreteMetric()
        assert metric._safe_divide(0, 5) == 0.0

    def test_safe_divide_zero_denominator(self):
        """Test _safe_divide with zero denominator (should return 0.0)"""
        metric = ConcreteMetric()
        assert metric._safe_divide(10, 0) == 0.0
        assert metric._safe_divide(0, 0) == 0.0

    def test_safe_divide_negative_values(self):
        """Test _safe_divide with negative values"""
        metric = ConcreteMetric()
        assert metric._safe_divide(-10, 2) == -5.0
        assert metric._safe_divide(10, -2) == -5.0
        assert metric._safe_divide(-10, -2) == 5.0

    def test_safe_divide_float_values(self):
        """Test _safe_divide with float values"""
        metric = ConcreteMetric()
        assert metric._safe_divide(10.5, 2.5) == 4.2
        assert metric._safe_divide(0.1, 0.2) == 0.5


class TestAggregatorMetricDecorator:
    """Test suite for aggregator_metric decorator"""

    def test_decorator_registers_metric(self):
        """Test that decorator registers the metric"""
        from sygra.core.eval.metrics.aggregator_metrics.aggregator_metric_registry import (
            AggregatorMetricRegistry,
        )

        # Clear registry first
        AggregatorMetricRegistry.clear()

        @aggregator_metric("test_decorator_metric")
        class TestDecoratorMetric(BaseAggregatorMetric):
            def validate_config(self):
                pass

            def get_metadata(self):
                from sygra.core.eval.metrics.base_metric_metadata import BaseMetricMetadata

                return BaseMetricMetadata(
                    name="test_decorator_metric",
                    display_name="Test Decorator Metric",
                    description="Test",
                )

            def calculate(self, results):
                return {"value": 1.0}

        # Check if registered
        assert AggregatorMetricRegistry.has_metric("test_decorator_metric")
        metric = AggregatorMetricRegistry.get_metric("test_decorator_metric")
        assert isinstance(metric, TestDecoratorMetric)

        # Cleanup
        AggregatorMetricRegistry.unregister("test_decorator_metric")

    def test_decorator_returns_class(self):
        """Test that decorator returns the class unchanged"""
        from sygra.core.eval.metrics.aggregator_metrics.aggregator_metric_registry import (
            AggregatorMetricRegistry,
        )

        # Clear registry first
        AggregatorMetricRegistry.clear()

        @aggregator_metric("test_return_class")
        class TestReturnClass(BaseAggregatorMetric):
            def validate_config(self):
                pass

            def get_metadata(self):
                from sygra.core.eval.metrics.base_metric_metadata import BaseMetricMetadata

                return BaseMetricMetadata(
                    name="test_return_class",
                    display_name="Test Return Class",
                    description="Test",
                )

            def calculate(self, results):
                return {"value": 1.0}

        # Should be able to instantiate directly
        instance = TestReturnClass()
        assert instance.get_metric_name() == "test_return_class"

        # Cleanup
        AggregatorMetricRegistry.unregister("test_return_class")
