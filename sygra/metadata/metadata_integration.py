import copy
import time
from functools import wraps
from typing import Callable

from sygra.core.models.model_response import ModelResponse
from sygra.metadata.langchain_callback import calculate_cost
from sygra.metadata.metadata_collector import get_metadata_collector


def track_model_request(func: Callable) -> Callable:
    """
    Decorator to track model requests automatically.

    This decorator can be applied to model request methods to automatically
    collect timing and token usage information.

    Usage:
        @track_model_request
        async def _generate_response(self, input, model_params):
            # ... existing code ...
            return response, status_code
    """

    @wraps(func)
    async def async_wrapper(self, *args, **kwargs):
        start_time = time.time()

        try:
            # Call original function
            model_response: ModelResponse = await func(self, *args, **kwargs)
            latency = time.time() - start_time

            # Extract model name and config
            model_name = getattr(self, "name", lambda: "unknown")()
            model_config = getattr(self, "model_config", None) or getattr(self, "_config", None)

            # Enhance model config with additional metadata (use deep copy to avoid modifying original)
            if model_config:
                model_config = copy.deepcopy(model_config) if isinstance(model_config, dict) else {}

                # Add model type if available
                if hasattr(self, "model_type"):
                    if callable(self.model_type):
                        model_config["type"] = self.model_type()
                    else:
                        model_config["type"] = self.model_type

                # Ensure api_version is in parameters if it exists in config
                if "api_version" in model_config:
                    if "parameters" not in model_config:
                        model_config["parameters"] = {}
                    if "api_version" not in model_config["parameters"]:
                        model_config["parameters"]["api_version"] = model_config["api_version"]

            # Extract token usage from model instance if available
            last_usage = getattr(self, "_last_request_usage", None)
            prompt_tokens = 0
            completion_tokens = 0
            total_tokens = 0

            if last_usage:
                prompt_tokens = last_usage.get("prompt_tokens", 0)
                completion_tokens = last_usage.get("completion_tokens", 0)
                total_tokens = last_usage.get("total_tokens", 0)

            # Calculate cost
            cost_usd = calculate_cost(model_name, prompt_tokens, completion_tokens)

            # Record the request with token usage
            collector = get_metadata_collector()
            collector.record_model_request(
                model_name=model_name,
                latency=latency,
                response_code=model_response.response_code,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total_tokens,
                is_retry=False,
                model_config=model_config,
                cost_usd=cost_usd,
            )

            return model_response

        except Exception:
            latency = time.time() - start_time

            # Record failed request
            model_name = getattr(self, "name", lambda: "unknown")()
            collector = get_metadata_collector()
            collector.record_model_request(
                model_name=model_name,
                latency=latency,
                response_code=999,  # Error code
            )

            raise

    @wraps(func)
    def sync_wrapper(self, *args, **kwargs):
        start_time = time.time()

        try:
            # Call original function
            model_response: ModelResponse = func(self, *args, **kwargs)
            latency = time.time() - start_time

            # Extract model name and config
            model_name = getattr(self, "name", lambda: "unknown")()
            model_config = getattr(self, "model_config", None) or getattr(self, "_config", None)

            # Enhance model config with additional metadata (use deep copy to avoid modifying original)
            if model_config:
                model_config = copy.deepcopy(model_config) if isinstance(model_config, dict) else {}

                # Add model type if available
                if hasattr(self, "model_type"):
                    if callable(self.model_type):
                        model_config["type"] = self.model_type()
                    else:
                        model_config["type"] = self.model_type

                # Ensure api_version is in parameters if it exists in config
                if "api_version" in model_config:
                    if "parameters" not in model_config:
                        model_config["parameters"] = {}
                    if "api_version" not in model_config["parameters"]:
                        model_config["parameters"]["api_version"] = model_config["api_version"]

            # Extract token usage from model instance if available
            last_usage = getattr(self, "_last_request_usage", None)
            prompt_tokens = 0
            completion_tokens = 0
            total_tokens = 0

            if last_usage:
                prompt_tokens = last_usage.get("prompt_tokens", 0)
                completion_tokens = last_usage.get("completion_tokens", 0)
                total_tokens = last_usage.get("total_tokens", 0)

            # Calculate cost
            cost_usd = calculate_cost(model_name, prompt_tokens, completion_tokens)

            # Record the request with token usage
            collector = get_metadata_collector()
            collector.record_model_request(
                model_name=model_name,
                latency=latency,
                response_code=model_response.response_code,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total_tokens,
                is_retry=False,
                model_config=model_config,
                cost_usd=cost_usd,
            )

            return model_response

        except Exception:
            latency = time.time() - start_time

            # Record failed request
            model_name = getattr(self, "name", lambda: "unknown")()
            collector = get_metadata_collector()
            collector.record_model_request(
                model_name=model_name,
                latency=latency,
                response_code=999,
            )

            raise

    # Return appropriate wrapper based on whether function is async
    import asyncio

    if asyncio.iscoroutinefunction(func):
        return async_wrapper
    else:
        return sync_wrapper
