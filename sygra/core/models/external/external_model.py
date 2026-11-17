"""``model_type: external`` — delegate generation to a registered LLMProvider."""

from __future__ import annotations

from typing import Any

from langchain_core.prompt_values import ChatPromptValue

import sygra.utils.constants as constants
from sygra.core.models.custom_models import BaseCustomModel, ModelParams
from sygra.core.models.external.provider import (
    DEFAULT_PROVIDER_NAME,
    LLMProvider,
    LLMRequest,
    get_llm_provider,
)
from sygra.core.models.model_response import ModelResponse
from sygra.logger.logger_config import logger
from sygra.metadata.metadata_integration import track_model_request


class ExternalModel(BaseCustomModel):
    """Model whose calls are served by a host-supplied ``LLMProvider``.

    Model config keys:
        provider: name of the registered provider (default ``"default"``).
        model: model identifier passed to the provider (defaults to ``name``).
        parameters: generation parameters, passed through as ``LLMRequest.parameters``.
        provider_options: free-form dict passed through as ``LLMRequest.provider_options``.

    The provider owns transport, retries and concurrency, so by default SyGra does
    not retry (``retry_attempts: 1``) and adds no pre-call delay (``delay: 0``).
    Both can still be set in the model config.
    """

    def __init__(self, model_config: dict[str, Any]) -> None:
        model_config = dict(model_config)
        model_config.setdefault("parameters", {})
        model_config.setdefault("retry_attempts", 1)
        model_config.setdefault("delay", 0)
        super().__init__(model_config)
        self.provider_name: str = str(model_config.get("provider") or DEFAULT_PROVIDER_NAME)
        # Resolve eagerly so a missing provider fails at graph build, not mid-run.
        self._provider: LLMProvider = get_llm_provider(self.provider_name)

    def _build_request(self, input: ChatPromptValue, **kwargs: Any) -> LLMRequest:
        return LLMRequest(
            name=self.name(),
            model=self.model_name,
            messages=self._get_messages(input),
            parameters=dict(self.generation_params),
            tools=self._convert_tools_to_model_format(**kwargs),
            tool_choice=kwargs.get("tool_choice") if kwargs.get("tools") else None,
            provider_options=dict(self.model_config.get("provider_options") or {}),
        )

    @track_model_request
    async def _generate_response(
        self, input: ChatPromptValue, model_params: ModelParams, **kwargs: Any
    ) -> ModelResponse:
        self._last_request_usage = None
        try:
            request = self._build_request(input, **kwargs)
            response = await self._provider.generate(request)
        except Exception as exc:  # provider bugs must not crash the run
            logger.error(f"[{self.name()}] External provider '{self.provider_name}' failed: {exc}")
            return ModelResponse(
                llm_response=f"{constants.ERROR_PREFIX} External provider error: {exc}",
                response_code=getattr(exc, "status_code", None) or 999,
            )

        if not isinstance(response, ModelResponse):
            return ModelResponse(
                llm_response=(
                    f"{constants.ERROR_PREFIX} External provider '{self.provider_name}' returned "
                    f"{type(response).__name__}, expected ModelResponse"
                ),
                response_code=999,
            )

        if response.response_code != 200 and constants.ERROR_PREFIX not in (
            response.llm_response or ""
        ):
            # Make failures visible to nodes, which detect errors by ERROR_PREFIX.
            response.llm_response = f"{constants.ERROR_PREFIX} {response.llm_response or ''}"

        if response.usage is not None:
            self._last_request_usage = {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens,
            }
        return response
