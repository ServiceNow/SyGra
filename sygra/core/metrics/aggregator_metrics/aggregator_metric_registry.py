"""
Aggregator Metric Registry
Singleton registry for discovering and instantiating aggregator metrics.
Provides centralized service locator for all metrics (built-in and custom).
"""

from typing import Dict, List, Optional, Type

from sygra.core.metrics.aggregator_metrics.base_aggregator_metric import BaseAggregatorMetric
from sygra.logger.logger_config import logger


class AggregatorMetricRegistry:
    """
    This registry maintains a mapping of metric names to metric classes,
    allowing runtime discovery without hard coding.
    Features:
    1. Auto-registration using @register_aggregator_metric decorator
    2. Runtime metric discovery(and use case being read from graph_config)
    3. Factory method for metric instantiation
    4. List available metrics
    5. Check metric existence
    Usage:
        # Register a metric (add decorator)
        AggregatorMetricRegistry.register("precision", PrecisionMetric)
        # Get metric instance
        metric = AggregatorMetricRegistry.get_metric("precision")
        # List all available metrics
        all_metrics = AggregatorMetricRegistry.list_metrics()
        # Check if metric exists, for example
        if AggregatorMetricRegistry.has_metric("f1"):
            metric = AggregatorMetricRegistry.get_metric("f1")
    """

    # Class-level storage (create singleton to have central control)
    _metrics: Dict[str, Type[BaseAggregatorMetric]] = {}

    @classmethod
    def register(cls, name: str, metric_class: Type[BaseAggregatorMetric]) -> None:
        """
        Register an aggregator metric class.
        This method is typically called automatically by the @register_aggregator_metric
        decorator, but can also be called manually if needed.
        Args:
            name: Unique identifier for the metric (e.g., "precision", "f1")
            metric_class: Class that implements BaseAggregatorMetric
        Raises:
            ValueError: If name is empty or metric_class is invalid
        Example:
            AggregatorMetricRegistry.register("precision", PrecisionMetric)
        """
        # Validation
        if not name or not isinstance(name, str):
            raise ValueError("Metric name must be a non-empty string")

        if not isinstance(metric_class, type):
            raise ValueError(f"metric_class must be a class, got {type(metric_class)}")

        if not issubclass(metric_class, BaseAggregatorMetric):
            raise ValueError(
                f"metric_class must inherit from BaseAggregatorMetric, "
                f"got {metric_class.__name__}"
            )

        # Check for duplicate registration
        if name in cls._metrics:
            logger.warning(
                f"Aggregator metric '{name}' is already registered. "
                f"Overwriting {cls._metrics[name].__name__} with {metric_class.__name__}"
            )

        # Register
        cls._metrics[name] = metric_class
        logger.debug(f"Registered aggregator metric: '{name}' -> {metric_class.__name__}")

    @classmethod
    def get_metric(cls, name: str, **kwargs) -> BaseAggregatorMetric:
        """
        Get an instance of a registered metric.
        This is a factory method that creates and returns a metric instance
        without the caller needing to know the concrete class.
        Args:
            name: Metric name (e.g., "precision", "recall", "f1")
            **kwargs: Optional arguments to pass to metric constructor
        Returns:
            Instance of the requested metric
        Raises:
            KeyError: If metric name is not registered
        Example:
            # Get metric with default parameters
            precision = AggregatorMetricRegistry.get_metric("precision")
            # Get metric with custom parameters
            topk = AggregatorMetricRegistry.get_metric("top_k_accuracy", k=5)
        """
        if name not in cls._metrics:
            available = cls.list_metrics()
            raise KeyError(
                f"Aggregator metric '{name}' not found in registry. "
                f"Available metrics: {available}"
            )

        metric_class = cls._metrics[name]

        try:
            # Instantiate metric with optional kwargs
            metric_instance = metric_class(**kwargs)
            logger.debug(f"Instantiated aggregator metric: '{name}'")
            return metric_instance
        except Exception as e:
            logger.error(
                f"Failed to instantiate metric '{name}' " f"({metric_class.__name__}): {e}"
            )
            raise

    @classmethod
    def list_metrics(cls) -> List[str]:
        """
        List all registered metric names.
        Returns:
         List of metric names
        Example:
            AggregatorMetricRegistry.list_metrics()
            ['accuracy', 'confusion_matrix', 'f1', 'precision', 'recall']
        """
        return sorted(cls._metrics.keys())

    @classmethod
    def has_metric(cls, name: str) -> bool:
        """
        Check if a metric is registered.
        Args:
            name: Metric name to check
        Returns:
            True if metric is registered, False otherwise
        Example:
            if AggregatorMetricRegistry.has_metric("f1"):
                metric = AggregatorMetricRegistry.get_metric("f1")
        """
        return name in cls._metrics

    @classmethod
    def get_metric_class(cls, name: str) -> Type[BaseAggregatorMetric]:
        """
        Get the class (not instance) of a registered metric.
        Adding this for now for inspection purposes on which metric is being used.
        Args:
            name: Metric name
        Returns:
            Metric class
        Raises:
            KeyError: If metric name is not registered
        """
        if name not in cls._metrics:
            available = cls.list_metrics()
            raise KeyError(
                f"Aggregator metric '{name}' not found in registry. "
                f"Available metrics: {available}"
            )
        return cls._metrics[name]

    @classmethod
    def unregister(cls, name: str) -> bool:
        """
        Unregister a metric. This is added feature if we want to deprecate or test, there could be a better way to achieve this using decorator.
        Args:
            name: Metric name to unregister
        Returns:
            True if metric was unregistered, False if it wasn't registered
        Example:
            AggregatorMetricRegistry.unregister("old_metric")
        """
        if name in cls._metrics:
            del cls._metrics[name]
            logger.debug(f"Unregistered aggregator metric: '{name}'")
            return True
        return False

    @classmethod
    def clear(cls) -> None:
        """
        Clear all registered metrics.
        Adding this because it is standard practice to have an evict option to test registry in unit testing.
        """
        cls._metrics.clear()
        logger.warning("Cleared all registered aggregator metrics")

    @classmethod
    def get_metrics_info(cls) -> Dict[str, Dict[str, str]]:
        """
        Get information about all registered metrics in dict format, basically the registered name and module path where code is written for it.
        This is just for debugging purposes for now, may have some use case in the future.
        Returns:
            dict: {metric_name: {"class": class_name, "module": module_name}}
        Example:
            AggregatorMetricRegistry.get_metrics_info()
            {
                'precision': {
                    'class': 'PrecisionMetric',
                    'module': 'core.aggregator_metrics.precision'
                },
                'recall': {
                    'class': 'RecallMetric',
                    'module': 'core.aggregator_metrics.recall'
                }
            }
        """
        info = {}
        for name, metric_class in cls._metrics.items():
            info[name] = {"class": metric_class.__name__, "module": metric_class.__module__}
        return info
