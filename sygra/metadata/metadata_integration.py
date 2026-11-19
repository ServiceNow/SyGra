import copy
import time
from functools import wraps
from typing import Any, Callable, Optional

from sygra.core.graph.langgraph.langchain_callback import calculate_cost
from sygra.core.models.call_state import ModelCallState, model_call
from sygra.core.models.model_response import ModelResponse, TokenUsage
from sygra.core.run_context import current_record_id, get_run_context
from sygra.metadata.metadata_collector import get_metadata_collector


def _record_run_usage(
    model_name: str, usage: Optional[TokenUsage], latency: float, model_response: Any = None
) -> None:
    """Add one request to the active run's usage (library runs only)."""
    ctx = get_run_context()
    if ctx is None:
        return
    ctx.usage.record_model_request(
        model_name=model_name,
        usage=usage,
        latency=latency,
        success=getattr(model_response, "response_code", 999) == 200,
        served_model=getattr(model_response, "served_model", None),
        record_id=current_record_id.get(),
    )


def _resolve_usage(
    model_response: Any, state: ModelCallState, legacy_usage: Any = None
) -> TokenUsage:
    """Usage for one request: from the response, else what the request reported.

    ``legacy_usage`` is a ``_last_request_usage`` dict that the model set during this
    request; it covers model classes that don't report usage via the call state.
    The resolved usage is attached to the response, so callers get per-request
    usage without reading shared model attributes.
    """
    usage = getattr(model_response, "usage", None)
    if isinstance(usage, TokenUsage):
        return usage
    reported = state.usage or (legacy_usage if isinstance(legacy_usage, dict) else None)
    if not reported:
        return TokenUsage()
    try:
        usage = TokenUsage(
            prompt_tokens=int(reported.get("prompt_tokens") or 0),
            completion_tokens=int(reported.get("completion_tokens") or 0),
            total_tokens=int(reported.get("total_tokens") or 0),
        )
    except (TypeError, ValueError):
        return TokenUsage()
    if isinstance(model_response, ModelResponse):
        model_response.usage = usage
    return usage


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
            usage_before = getattr(self, "_last_request_usage", None)
            with model_call() as state:
                model_response: ModelResponse = await func(self, *args, **kwargs)
            usage_after = getattr(self, "_last_request_usage", None)
            legacy_usage = usage_after if usage_after is not usage_before else None
            latency = time.time() - start_time

            # Extract model name and config
            model_name = getattr(self, "model_name", "unknown")
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

            # Token usage for this request (not the model's last request)
            usage = _resolve_usage(model_response, state, legacy_usage)
            prompt_tokens = usage.prompt_tokens
            completion_tokens = usage.completion_tokens
            total_tokens = usage.total_tokens

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
            _record_run_usage(model_name, usage, latency, model_response)

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
            _record_run_usage(model_name, None, latency)

            raise

    @wraps(func)
    def sync_wrapper(self, *args, **kwargs):
        start_time = time.time()

        try:
            # Call original function
            usage_before = getattr(self, "_last_request_usage", None)
            with model_call() as state:
                model_response: ModelResponse = func(self, *args, **kwargs)
            usage_after = getattr(self, "_last_request_usage", None)
            legacy_usage = usage_after if usage_after is not usage_before else None
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

            # Token usage for this request (not the model's last request)
            usage = _resolve_usage(model_response, state, legacy_usage)
            prompt_tokens = usage.prompt_tokens
            completion_tokens = usage.completion_tokens
            total_tokens = usage.total_tokens

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
            _record_run_usage(model_name, usage, latency, model_response)

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
            _record_run_usage(model_name, None, latency)

            raise

    # Return appropriate wrapper based on whether function is async
    import asyncio

    if asyncio.iscoroutinefunction(func):
        return async_wrapper
    else:
        return sync_wrapper
