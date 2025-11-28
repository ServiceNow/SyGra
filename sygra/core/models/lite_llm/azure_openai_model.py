from __future__ import annotations

import logging
from typing import Any

from langchain_core.prompt_values import ChatPromptValue
from openai import APIError, BadRequestError, RateLimitError

from sygra.core.models.custom_models import ModelParams
from sygra.core.models.lite_llm.base import LiteLLMBase
from sygra.core.models.model_response import ModelResponse
from sygra.logger.logger_config import logger
from sygra.metadata.metadata_integration import track_model_request
from sygra.utils import utils

logging.getLogger("LiteLLM").setLevel(logging.WARNING)


class CustomAzureOpenAI(LiteLLMBase):

    def __init__(self, model_config: dict[str, Any]) -> None:
        super().__init__(model_config)
        utils.validate_required_keys(["url", "auth_token", "api_version"], model_config, "model")
        self.model_config = model_config
        self.model_name = self.model_config.get("model", self.name())
        self.api_version = self.model_config.get("api_version")

    def _get_model_prefix(self) -> str:
        return "azure"

    def _extra_call_params(self) -> dict[str, Any]:
        return {"api_version": self.api_version}

    def _provider_label(self) -> str:
        return "Azure OpenAI"

    def _native_structured_output_spec(self):
        return ("response_format", "pydantic")

    @track_model_request
    async def _generate_response(
        self, input: ChatPromptValue, model_params: ModelParams, **kwargs: Any
    ) -> ModelResponse:
        self._apply_tools(**kwargs)
        output_type = self.model_config.get("output_type")
        model_id = str(self.model_config.get("model", "")).lower()
        if "audio" in model_id:
            return await self._generate_audio_chat_completion(input, model_params)
        if output_type == "audio":
            return await self._generate_speech(input, model_params)
        elif output_type == "image":
            return await self._generate_image(input, model_params)
        else:
            return await self._generate_text(input, model_params)

    async def _generate_speech(
        self, input: ChatPromptValue, model_params: ModelParams, **kwargs: Any
    ) -> ModelResponse:
        # Pre-log warning at module logger for overly long text, as tests expect warn to be called here
        text_to_speak = " ".join([str(getattr(m, "content", "")) for m in input.messages]).strip()
        if len(text_to_speak) > 4096:
            logger.warn(
                f"[{self.name()}] Text exceeds 4096 character limit: {len(text_to_speak)} characters"
            )
        return await super()._generate_speech(input, model_params)

    # Ensure module-level logger is used for tests expecting per-module logging
    def _map_exception(self, e: Exception, context: str) -> ModelResponse:
        if isinstance(e, RateLimitError):
            logger.warning(
                f"[{self.name()}] {context} request exceeded rate limit: {getattr(e, 'message', e)}"
            )
        elif isinstance(e, BadRequestError):
            logger.error(f"[{self.name()}] {context} bad request: {getattr(e, 'message', e)}")
        elif isinstance(e, APIError):
            logger.error(f"[{self.name()}] {context} error: {getattr(e, 'message', e)}")
        else:
            logger.error(f"[{self.name()}] {context} request failed: {e}")
        return super()._map_exception(e, context)
