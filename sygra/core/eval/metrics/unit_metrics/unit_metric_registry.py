"""
Unit Metric Registry
Singleton registry for discovering and instantiating unit metrics.
Provides centralized service locator for all metrics (built-in and custom).
"""

# Avoid circular imports
from __future__ import annotations

import importlib
import pkgutil
from typing import TYPE_CHECKING, Dict, List, Type

from sygra.logger.logger_config import logger

# This prevents circular imports while still providing type safety.
if TYPE_CHECKING:
    from sygra.core.eval.metrics.unit_metrics.base_unit_metric import (
        BaseUnitMetric,
    )


class UnitMetricRegistry:
    """
    This registry maintains a mapping of metric names to metric classes,
    allowing runtime discovery without hard coding.
    Features:
    1. Auto-registration using @register_unit_metric decorator
    2. Runtime metric discovery(and use case being read from graph_config)
    3. Factory method for metric instantiation
    4. List available metrics
    5. Check metric existence
    Usage:
        # Register a metric (add decorator)
        UnitMetricRegistry.register("precision", PrecisionMetric)
        # Get metric instance
        metric = UnitMetricRegistry.get_metric("precision")
        # List all available metrics
        all_metrics = UnitMetricRegistry.list_metrics()
        # Check if metric exists, for example
        if UnitMetricRegistry.has_metric("f1"):
            metric = UnitMetricRegistry.get_metric("f1")
    """

    # Class-level storage (create singleton to have central control)
    _metrics: Dict[str, Type[BaseUnitMetric]] = {}
    _discovered: bool = False

    @classmethod
    def _ensure_discovered(cls) -> None:
        if cls._discovered:
            return

        try:
            import sygra.core.eval.metrics.unit_metrics as unit_metrics_pkg

            for module_info in pkgutil.iter_modules(
                    unit_metrics_pkg.__path__, unit_metrics_pkg.__name__ + "."
            ):
                module_name = module_info.name
                if module_name.endswith(
                        (
                                ".base_unit_metric",
                                ".unit_metric_registry",
                                ".unit_metric_result",
                        )
                ):
                    continue
                importlib.import_module(module_name)

            cls._discovered = True
        except Exception as e:
            logger.error(f"Failed to auto-discover unit metrics: {e}")
            cls._discovered = True

    @classmethod
    def register(cls, name: str, metric_class: Type[BaseUnitMetric]) -> None:
        """
        Register a unit metric class.
        This method is typically called automatically by the @register_unit_metric
        decorator, but can also be called manually if needed.
        Args:
            name: Unique identifier for the metric (e.g., "precision", "f1")
            metric_class: Class that implements BaseUnitMetric
        Raises:
            ValueError: If name is empty or metric_class is invalid
        Example:
            UnitMetricRegistry.register("precision", PrecisionMetric)
        """
        # Validation
        if not name or not isinstance(name, str):
            raise ValueError("Metric name must be a non-empty string")

        if not isinstance(metric_class, type):
            raise ValueError(f"metric_class must be a class, got {type(metric_class)}")

        # Import at runtime (inside function) instead of at module level to avoid circular dependency
        from sygra.core.eval.metrics.unit_metrics.base_unit_metric import (
            BaseUnitMetric,
        )

        if not issubclass(metric_class, BaseUnitMetric):
            raise ValueError(
                f"metric_class must inherit from BaseUnitMetric, "
                f"got {metric_class.__name__}"
            )

        # Check for duplicate registration
        if name in cls._metrics:
            logger.warning(
                f"Unit metric '{name}' is already registered. "
                f"Overwriting {cls._metrics[name].__name__} with {metric_class.__name__}"
            )

        # Register
        cls._metrics[name] = metric_class
        logger.debug(f"Registered unit metric: '{name}' -> {metric_class.__name__}")

    @classmethod
    def get_metric(cls, name: str, **kwargs) -> BaseUnitMetric:
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
            precision = UnitMetricRegistry.get_metric("precision")
            # Get metric with custom parameters
            topk = UnitMetricRegistry.get_metric("top_k_accuracy", k=5)
        """
        cls._ensure_discovered()

        if name not in cls._metrics:
            available = cls.list_metrics()
            raise KeyError(
                f"Unit metric '{name}' not found in registry. "
                f"Available metrics: {available}"
            )

        metric_class = cls._metrics[name]

        try:
            # Instantiate metric with optional kwargs
            metric_instance = metric_class(**kwargs)
            logger.debug(f"Instantiated unit metric: '{name}'")
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
            UnitMetricRegistry.list_metrics()
            ['accuracy', 'confusion_matrix', 'f1', 'precision', 'recall']
        """
        cls._ensure_discovered()
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
            if UnitMetricRegistry.has_metric("f1"):
                metric = UnitMetricRegistry.get_metric("f1")
        """
        cls._ensure_discovered()
        return name in cls._metrics

    @classmethod
    def get_metric_class(cls, name: str) -> Type[BaseUnitMetric]:
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
        cls._ensure_discovered()

        if name not in cls._metrics:
            available = cls.list_metrics()
            raise KeyError(
                f"Unit metric '{name}' not found in registry. "
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
            UnitMetricRegistry.unregister("old_metric")
        """
        if name in cls._metrics:
            del cls._metrics[name]
            logger.debug(f"Unregistered unit metric: '{name}'")
            return True
        return False

    @classmethod
    def clear(cls) -> None:
        """
        Clear all registered metrics.
        Adding this because it is standard practice to have an evict option to test registry in unit testing.
        """
        cls._metrics.clear()
        logger.warning("Cleared all registered unit metrics")

    @classmethod
    def get_metrics_info(cls) -> Dict[str, Dict[str, str]]:
        """
        Get information about all registered metrics in dict format, basically the registered name and module path where code is written for it.
        This is just for debugging purposes for now, may have some use case in the future.
        Returns:
            dict: {metric_name: {"class": class_name, "module": module_name}}
        Example:
            UnitMetricRegistry.get_metrics_info()
            {
                'precision': {
                    'class': 'PrecisionMetric',
                    'module': 'core.unit_metrics.precision'
                },
                'recall': {
                    'class': 'RecallMetric',
                    'module': 'core.unit_metrics.recall'
                }
            }
        """
        info = {}
        for name, metric_class in cls._metrics.items():
            info[name] = {"class": metric_class.__name__, "module": metric_class.__module__}
        return info


# Decorator for metric registration
def unit_metric(name: str):
    """
    Decorator to auto-register unit metrics with the registry.

    Usage:
        @unit_metric("precision")
        class PrecisionMetric(BaseUnitMetric):
            def calculate(self, results):
                # Implementation
                pass

    Args:
        name: Unique name for the metric (used for registry lookup)

    Returns:
        Decorator function that registers the class
    """

    def decorator(cls):
        # Import at runtime when decorator is applied (not at module load time)
        # Metrics use this decorator, so they import this registry file.
        # If we imported BaseUnitMetric at the top, we'd have:
        # metric.py -> registry.py -> base.py (circular dependency)
        # By importing here, the import happens when the class is decorated,
        # after all modules have loaded.
        from sygra.core.eval.metrics.unit_metrics.base_unit_metric import (
            BaseUnitMetric,
        )

        # Validate that class inherits from BaseUnitMetric
        if not issubclass(cls, BaseUnitMetric):
            raise TypeError(
                f"{cls.__name__} must inherit from BaseUnitMetric to use @unit_metric decorator"
            )

        UnitMetricRegistry.register(name, cls)
        return cls

    return decorator
