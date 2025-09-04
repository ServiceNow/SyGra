from typing import Any


try:
    from grasp.core.models.model_factory import ModelFactory
    from grasp.core.models.custom_models import (
        CustomVLLM,
        CustomOpenAI,
        CustomTGI,
        CustomAzure,
        CustomMistralAPI,
    )
    from grasp.utils import utils

    MODELS_AVAILABLE = True
except ImportError:
    MODELS_AVAILABLE = False


class ModelConfigBuilder:
    """Build model configurations using framework's model system."""

    @staticmethod
    def from_name(model_name: str, **kwargs) -> dict[str, Any] | None:
        """Build model configuration from model name using framework's model configs."""

        try:
            # Try to load from framework's model configs first
            model_configs = utils.load_model_config()
            if model_name in model_configs:
                base_config = model_configs[model_name].copy()

                # Ensure required name field
                base_config["name"] = model_name

                # Override with any provided kwargs
                if "parameters" not in base_config:
                    base_config["parameters"] = {}

                base_config["parameters"].update(
                    {
                        "temperature": kwargs.get(
                            "temperature",
                            base_config["parameters"].get("temperature", 0.7),
                        ),
                        "max_tokens": kwargs.get(
                            "max_tokens",
                            base_config["parameters"].get("max_tokens", 1000),
                        ),
                    }
                )

                return base_config
            else:
                raise ValueError(f"Model {model_name} not found in model configs")

        except Exception as e:
            raise ValueError(f"Error loading model config: {e}")

    @staticmethod
    def validate_config(model_config: dict[str, Any]) -> dict[str, Any]:
        """Validate and ensure model config has required fields."""
        config = model_config.copy()

        if "name" not in config:
            if "model" in config:
                config["name"] = config["model"]
            else:
                raise ValueError("Model config must have 'name' or 'model' field")

        return config


__all__ = ["ModelConfigBuilder"]
