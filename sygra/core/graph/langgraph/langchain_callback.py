"""LangChain callback handler for tracking LLM calls in agents."""

from typing import Any, Dict, List, Optional
from uuid import UUID

from langchain_core.callbacks import AsyncCallbackHandler
from langchain_core.outputs import LLMResult

from sygra.logger.logger_config import logger
from sygra.metadata.metadata_collector import get_metadata_collector


def calculate_cost(model_name: str, prompt_tokens: int, completion_tokens: int) -> float:
    """
    Calculate the cost of a model request based on token usage.

    Uses LangChain Community's official pricing data only. Returns 0.0 if pricing
    is not available for the model (no fallback estimates to avoid stale data).

    Supports:
    - OpenAI models (direct API)
    - Azure OpenAI models (same pricing as OpenAI)
    - Anthropic Claude on AWS Bedrock

    Args:
        model_name: Name of the model
        prompt_tokens: Number of prompt tokens
        completion_tokens: Number of completion tokens

    Returns:
        Total cost in USD, or 0.0 if pricing not available
    """
    try:
        # This also works for Azure OpenAI since they use the same model names and pricing
        from langchain_community.callbacks.openai_info import (
            TokenType,
            get_openai_token_cost_for_model,
        )

        try:
            prompt_cost = get_openai_token_cost_for_model(
                model_name, prompt_tokens, token_type=TokenType.PROMPT
            )
            completion_cost = get_openai_token_cost_for_model(
                model_name, completion_tokens, token_type=TokenType.COMPLETION
            )
            return prompt_cost + completion_cost
        except (KeyError, ValueError):
            # Not an OpenAI/Azure model or not in pricing table
            pass

        # Try Bedrock Anthropic models (Claude on AWS)
        from langchain_community.callbacks.bedrock_anthropic_callback import (
            _get_anthropic_claude_token_cost,
        )

        if "claude" in model_name.lower() or "anthropic" in model_name.lower():
            try:
                return _get_anthropic_claude_token_cost(
                    prompt_tokens, completion_tokens, model_name
                )
            except (KeyError, ValueError):
                # Claude model but not in Bedrock pricing table
                pass

    except ImportError:
        logger.warning(
            "langchain-community not available for cost calculation. "
            "Install with: pip install langchain-community"
        )
        return 0.0

    # No pricing available - log and return 0.0
    logger.debug(
        f"No pricing information available for model '{model_name}'. "
        f"Cost will be reported as $0.00. "
        f"Supported models: OpenAI (GPT-4, GPT-3.5, etc.), Azure OpenAI and Anthropic Claude on Bedrock."
    )
    return 0.0


class MetadataTrackingCallback(AsyncCallbackHandler):
    """
    Callback handler to track LLM calls made by LangChain agents.

    This captures token usage and other metrics from agent LLM calls
    that don't go through our custom model wrappers.
    """

    def __init__(self, model_name: str = "unknown"):
        """
        Initialize the callback handler.

        Args:
            model_name: Name of the model being used
        """
        super().__init__()
        self.model_name = model_name
        self.call_start_times: Dict[UUID, float] = {}

    async def on_llm_start(
        self,
        serialized: Dict[str, Any],
        prompts: List[str],
        *,
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> None:
        """Track when an LLM call starts."""
        import time

        self.call_start_times[run_id] = time.time()

    async def on_llm_end(
        self,
        response: LLMResult,
        *,
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        tags: Optional[List[str]] = None,
        **kwargs: Any,
    ) -> None:
        """Track when an LLM call ends and record metrics."""
        import time

        # Calculate latency
        start_time = self.call_start_times.pop(run_id, None)
        latency = time.time() - start_time if start_time else 0.0

        # Extract token usage from response
        prompt_tokens = 0
        completion_tokens = 0
        total_tokens = 0

        if response.llm_output and "token_usage" in response.llm_output:
            token_usage = response.llm_output["token_usage"]
            prompt_tokens = token_usage.get("prompt_tokens", 0)
            completion_tokens = token_usage.get("completion_tokens", 0)
            total_tokens = token_usage.get("total_tokens", 0)

        # Try to extract model info from response metadata
        model_name = self.model_name
        model_type = "unknown"
        model_url = None

        if response.llm_output:
            # Try to get model name from response if not set
            if model_name == "unknown" and "model_name" in response.llm_output:
                model_name = response.llm_output["model_name"]

            # Extract model type and URL if available
            if "system_fingerprint" in response.llm_output:
                model_type = "OpenAI"  # OpenAI models have system_fingerprint

        # Calculate cost
        cost_usd = calculate_cost(model_name, prompt_tokens, completion_tokens)

        # Record in metadata collector
        collector = get_metadata_collector()

        # Create minimal model config for tracking
        model_config = {
            "name": model_name,
            "type": model_type,
        }
        if model_url:
            model_config["url"] = model_url

        collector.record_model_request(
            model_name=model_name,
            latency=latency,
            response_code=200,  # Assume success if we got here
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            is_retry=False,
            model_config=model_config,
            cost_usd=cost_usd,
        )

        logger.debug(
            f"[AGENT_LLM_CALL] {model_name} - "
            f"tokens: {total_tokens}, latency: {latency:.3f}s, cost: ${cost_usd:.6f}"
        )

    async def on_llm_error(
        self,
        error: BaseException,
        *,
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        tags: Optional[List[str]] = None,
        **kwargs: Any,
    ) -> None:
        """Track when an LLM call fails."""
        import time

        # Calculate latency
        start_time = self.call_start_times.pop(run_id, None)
        latency = time.time() - start_time if start_time else 0.0

        # Record failed request
        collector = get_metadata_collector()
        collector.record_model_request(
            model_name=self.model_name,
            latency=latency,
            response_code=999,  # Error code
        )

        logger.debug(f"[AGENT_LLM_ERROR] {self.model_name} - latency: {latency:.3f}s")
