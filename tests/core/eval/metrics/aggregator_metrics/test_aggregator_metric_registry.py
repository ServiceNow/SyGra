import os
import sys

# Add project root to sys.path for relative imports to work
sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", ".."))
)


import pytest

from sygra.core.eval.metrics.aggregator_metrics.aggregator_metric_registry import (
    AggregatorMetricRegistry,
    aggregator_metric,
)
from sygra.core.eval.metrics.aggregator_metrics.base_aggregator_metric import BaseAggregatorMetric


class SampleMetric(BaseAggregatorMetric):
    """Sample metric for registry testing"""

    def __init__(self, **config):
        """Initialize with two-phase initialization."""
        super().__init__(**config)
        self.validate_config()
        self.metadata = self.get_metadata()

    def validate_config(self):
        """Store optional params"""
        self.param1 = self.config.get("param1")
        self.param2 = self.config.get("param2")

    def get_metadata(self):
        from sygra.core.eval.metrics.base_metric_metadata import BaseMetricMetadata

        return BaseMetricMetadata(
            name="test_metric",
            display_name="Test Metric",
            description="Test metric for registry testing",
        )

    def calculate(self, results):
        return {"test": 1.0}


class AlternativeMetric(BaseAggregatorMetric):
    """Alternative metric for registry testing"""

    def __init__(self, **config):
        """Initialize with two-phase initialization."""
        super().__init__(**config)
        self.validate_config()
        self.metadata = self.get_metadata()

    def validate_config(self):
        """No config needed"""
        pass

    def get_metadata(self):
        from sygra.core.eval.metrics.base_metric_metadata import BaseMetricMetadata

        return BaseMetricMetadata(
            name="another_test_metric",
            display_name="Another Test Metric",
            description="Another test metric for registry testing",
        )

    def calculate(self, results):
        return {"another_test": 1.0}


class TestAggregatorMetricRegistry:
    """Test suite for AggregatorMetricRegistry"""

    def setup_method(self):
        """Clear registry before each test"""
        AggregatorMetricRegistry.clear()

    def teardown_method(self):
        """Clear registry after each test"""
        AggregatorMetricRegistry.clear()

    def test_register_metric(self):
        """Test registering a metric"""
        AggregatorMetricRegistry.register("test_metric", SampleMetric)
        assert AggregatorMetricRegistry.has_metric("test_metric")

    def test_register_multiple_metrics(self):
        """Test registering multiple metrics"""
        AggregatorMetricRegistry.register("test_metric", SampleMetric)
        AggregatorMetricRegistry.register("another_test_metric", AlternativeMetric)

        assert AggregatorMetricRegistry.has_metric("test_metric")
        assert AggregatorMetricRegistry.has_metric("another_test_metric")

    def test_register_raises_error_for_empty_name(self):
        """Test that registering with empty name raises ValueError"""
        with pytest.raises(ValueError) as exc_info:
            AggregatorMetricRegistry.register("", SampleMetric)
        assert "non-empty string" in str(exc_info.value)

    def test_register_raises_error_for_non_string_name(self):
        """Test that registering with non-string name raises ValueError"""
        with pytest.raises(ValueError) as exc_info:
            AggregatorMetricRegistry.register(123, SampleMetric)
        assert "non-empty string" in str(exc_info.value)

    def test_register_raises_error_for_non_class(self):
        """Test that registering with non-class raises ValueError"""
        with pytest.raises(ValueError) as exc_info:
            AggregatorMetricRegistry.register("test", "not_a_class")
        assert "must be a class" in str(exc_info.value)

    def test_register_raises_error_for_non_subclass(self):
        """Test that registering non-BaseAggregatorMetric subclass raises ValueError"""

        class NotAMetric:
            pass

        with pytest.raises(ValueError) as exc_info:
            AggregatorMetricRegistry.register("test", NotAMetric)
        assert "inherit from BaseAggregatorMetric" in str(exc_info.value)

    def test_register_duplicate_metric_logs_warning(self):
        """Test that registering duplicate metric overwrites and logs warning"""
        AggregatorMetricRegistry.register("test_metric", SampleMetric)
        # Register again with different class
        AggregatorMetricRegistry.register("test_metric", AlternativeMetric)

        # Should be overwritten
        metric = AggregatorMetricRegistry.get_metric("test_metric")
        assert isinstance(metric, AlternativeMetric)

    def test_get_metric_returns_instance(self):
        """Test that get_metric returns an instance of the metric"""
        AggregatorMetricRegistry.register("test_metric", SampleMetric)
        metric = AggregatorMetricRegistry.get_metric("test_metric")

        assert isinstance(metric, SampleMetric)
        assert metric.get_metric_name() == "test_metric"

    def test_get_metric_with_kwargs(self):
        """Test that get_metric passes kwargs to constructor"""
        AggregatorMetricRegistry.register("test_metric", SampleMetric)
        metric = AggregatorMetricRegistry.get_metric(
            "test_metric", param1="value1", param2="value2"
        )

        assert metric.param1 == "value1"
        assert metric.param2 == "value2"

    def test_get_metric_raises_error_for_unregistered_metric(self):
        """Test that get_metric raises KeyError for unregistered metric"""
        with pytest.raises(KeyError) as exc_info:
            AggregatorMetricRegistry.get_metric("nonexistent_metric")
        assert "not found in registry" in str(exc_info.value)
        assert "Available metrics" in str(exc_info.value)

    def test_get_metric_raises_error_on_instantiation_failure(self):
        """Test that get_metric raises error when instantiation fails"""

        class FailingMetric(BaseAggregatorMetric):
            def __init__(self, **config):
                super().__init__(**config)
                self.validate_config()
                self.metadata = self.get_metadata()

            def validate_config(self):
                # This will fail if required_param is not provided
                if "required_param" not in self.config:
                    raise ValueError("required_param is required")
                self.required_param = self.config["required_param"]

            def get_metadata(self):
                from sygra.core.eval.metrics.base_metric_metadata import BaseMetricMetadata

                return BaseMetricMetadata(
                    name="failing_metric",
                    display_name="Failing Metric",
                    description="Test",
                )

            def calculate(self, results):
                return {}

        AggregatorMetricRegistry.register("failing_metric", FailingMetric)

        with pytest.raises(Exception):
            # Should fail because required_param is not provided
            AggregatorMetricRegistry.get_metric("failing_metric")

    def test_list_metrics_empty_registry(self):
        """Test list_metrics with empty registry"""
        metrics = AggregatorMetricRegistry.list_metrics()
        assert metrics == []

    def test_list_metrics_returns_sorted_names(self):
        """Test that list_metrics returns sorted metric names"""
        AggregatorMetricRegistry.register("zebra_metric", SampleMetric)
        AggregatorMetricRegistry.register("alpha_metric", AlternativeMetric)
        AggregatorMetricRegistry.register("beta_metric", SampleMetric)

        metrics = AggregatorMetricRegistry.list_metrics()
        assert metrics == ["alpha_metric", "beta_metric", "zebra_metric"]

    def test_has_metric_returns_true_for_registered(self):
        """Test that has_metric returns True for registered metrics"""
        AggregatorMetricRegistry.register("test_metric", SampleMetric)
        assert AggregatorMetricRegistry.has_metric("test_metric") is True

    def test_has_metric_returns_false_for_unregistered(self):
        """Test that has_metric returns False for unregistered metrics"""
        assert AggregatorMetricRegistry.has_metric("nonexistent_metric") is False

    def test_get_metric_class_returns_class(self):
        """Test that get_metric_class returns the class, not instance"""
        AggregatorMetricRegistry.register("test_metric", SampleMetric)
        metric_class = AggregatorMetricRegistry.get_metric_class("test_metric")

        assert metric_class is SampleMetric
        assert isinstance(metric_class, type)

    def test_get_metric_class_raises_error_for_unregistered(self):
        """Test that get_metric_class raises KeyError for unregistered metric"""
        with pytest.raises(KeyError) as exc_info:
            AggregatorMetricRegistry.get_metric_class("nonexistent_metric")
        assert "not found in registry" in str(exc_info.value)

    def test_unregister_existing_metric(self):
        """Test unregistering an existing metric"""
        AggregatorMetricRegistry.register("test_metric", SampleMetric)
        assert AggregatorMetricRegistry.has_metric("test_metric")

        result = AggregatorMetricRegistry.unregister("test_metric")
        assert result is True
        assert not AggregatorMetricRegistry.has_metric("test_metric")

    def test_unregister_nonexistent_metric(self):
        """Test unregistering a nonexistent metric"""
        result = AggregatorMetricRegistry.unregister("nonexistent_metric")
        assert result is False

    def test_clear_removes_all_metrics(self):
        """Test that clear removes all metrics"""
        AggregatorMetricRegistry.register("test_metric1", SampleMetric)
        AggregatorMetricRegistry.register("test_metric2", AlternativeMetric)
        assert len(AggregatorMetricRegistry.list_metrics()) == 2

        AggregatorMetricRegistry.clear()
        assert len(AggregatorMetricRegistry.list_metrics()) == 0

    def test_get_metrics_info_empty_registry(self):
        """Test get_metrics_info with empty registry"""
        info = AggregatorMetricRegistry.get_metrics_info()
        assert info == {}

    def test_get_metrics_info_returns_correct_structure(self):
        """Test that get_metrics_info returns correct structure"""
        AggregatorMetricRegistry.register("test_metric", SampleMetric)
        AggregatorMetricRegistry.register("another_test_metric", AlternativeMetric)

        info = AggregatorMetricRegistry.get_metrics_info()

        assert "test_metric" in info
        assert "another_test_metric" in info

        assert info["test_metric"]["class"] == "SampleMetric"
        assert "test_aggregator_metric_registry" in info["test_metric"]["module"]

        assert info["another_test_metric"]["class"] == "AlternativeMetric"
        assert "test_aggregator_metric_registry" in info["another_test_metric"]["module"]

    def test_registry_is_singleton(self):
        """Test that registry maintains state across multiple accesses"""
        AggregatorMetricRegistry.register("test_metric", SampleMetric)

        # Access from different reference should see the same registry
        assert AggregatorMetricRegistry.has_metric("test_metric")

        metrics1 = AggregatorMetricRegistry.list_metrics()
        metrics2 = AggregatorMetricRegistry.list_metrics()
        assert metrics1 == metrics2

    def test_decorator_integration(self):
        """Test that decorator properly registers metrics"""
        # Clear first
        AggregatorMetricRegistry.clear()

        @aggregator_metric("decorated_metric")
        class DecoratedMetric(BaseAggregatorMetric):
            def __init__(self, **config):
                super().__init__(**config)
                self.validate_config()
                self.metadata = self.get_metadata()

            def validate_config(self):
                pass

            def get_metadata(self):
                from sygra.core.eval.metrics.base_metric_metadata import BaseMetricMetadata

                return BaseMetricMetadata(
                    name="decorated_metric",
                    display_name="Decorated Metric",
                    description="Test",
                )

            def calculate(self, results):
                return {"decorated": 1.0}

        # Should be automatically registered
        assert AggregatorMetricRegistry.has_metric("decorated_metric")
        metric = AggregatorMetricRegistry.get_metric("decorated_metric")
        assert isinstance(metric, DecoratedMetric)

        # Cleanup
        AggregatorMetricRegistry.unregister("decorated_metric")

    def test_multiple_instances_from_same_registration(self):
        """Test that multiple instances can be created from same registration"""
        AggregatorMetricRegistry.register("test_metric", SampleMetric)

        metric1 = AggregatorMetricRegistry.get_metric("test_metric", param1="value1")
        metric2 = AggregatorMetricRegistry.get_metric("test_metric", param1="value2")

        assert metric1 is not metric2
        assert metric1.param1 == "value1"
        assert metric2.param1 == "value2"

    def test_registry_with_built_in_metrics(self):
        """Test registry with actual built-in metrics"""
        # Import built-in metrics to trigger their registration
        # Note: Imports must happen after setup_method clears the registry
        # We need to reload the modules to re-trigger the decorator registration
        import importlib

        from sygra.core.eval.metrics.aggregator_metrics import accuracy, f1_score, precision, recall

        # Reload modules to re-trigger decorator registration after registry was cleared
        importlib.reload(accuracy)
        importlib.reload(precision)
        importlib.reload(recall)
        importlib.reload(f1_score)

        from sygra.core.eval.metrics.aggregator_metrics.accuracy import AccuracyMetric
        from sygra.core.eval.metrics.aggregator_metrics.precision import PrecisionMetric

        # Check that built-in metrics are registered
        assert AggregatorMetricRegistry.has_metric("accuracy")
        assert AggregatorMetricRegistry.has_metric("precision")
        assert AggregatorMetricRegistry.has_metric("recall")
        assert AggregatorMetricRegistry.has_metric("f1_score")

        # Test instantiation
        accuracy_metric = AggregatorMetricRegistry.get_metric("accuracy")
        assert isinstance(accuracy_metric, AccuracyMetric)

        precision = AggregatorMetricRegistry.get_metric(
            "precision", predicted_key="class", positive_class="A"
        )
        assert isinstance(precision, PrecisionMetric)

    def test_get_metric_class_can_be_used_for_manual_instantiation(self):
        """Test that get_metric_class can be used to manually instantiate metrics"""
        AggregatorMetricRegistry.register("test_metric", SampleMetric)

        metric_class = AggregatorMetricRegistry.get_metric_class("test_metric")
        manual_instance = metric_class(param1="manual_value")

        assert isinstance(manual_instance, SampleMetric)
        assert manual_instance.param1 == "manual_value"

    def test_registry_handles_metrics_with_no_init_params(self):
        """Test registry with metrics that don't require init parameters"""

        class SimpleMetric(BaseAggregatorMetric):
            def __init__(self, **config):
                super().__init__(**config)
                self.validate_config()
                self.metadata = self.get_metadata()

            def validate_config(self):
                pass

            def get_metadata(self):
                from sygra.core.eval.metrics.base_metric_metadata import BaseMetricMetadata

                return BaseMetricMetadata(
                    name="simple_metric",
                    display_name="Simple Metric",
                    description="Test",
                )

            def calculate(self, results):
                return {"simple": 1.0}

        AggregatorMetricRegistry.register("simple_metric", SimpleMetric)
        metric = AggregatorMetricRegistry.get_metric("simple_metric")

        assert isinstance(metric, SimpleMetric)
