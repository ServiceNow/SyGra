from __future__ import annotations

import json
import logging
from typing import Any, Type

from langchain_core.prompt_values import ChatPromptValue
from openai import APIError, BadRequestError, RateLimitError
from pydantic import BaseModel

from sygra.core.models.custom_models import ModelParams
from sygra.core.models.lite_llm.base import LiteLLMBase
from sygra.core.models.model_response import ModelResponse
from sygra.logger.logger_config import logger
from sygra.metadata.metadata_integration import track_model_request
from sygra.utils import utils

logging.getLogger("LiteLLM").setLevel(logging.WARNING)


class CustomOpenAI(LiteLLMBase):

    def __init__(self, model_config: dict[str, Any]) -> None:
        super().__init__(model_config)
        utils.validate_required_keys(["url", "auth_token"], model_config, "model")
        self.model_config = model_config
        self.model_name = self.model_config.get("model", self.name())

    @track_model_request
    async def _generate_native_structured_output(
        self,
        input: ChatPromptValue,
        model_params: ModelParams,
        pydantic_model: Type[BaseModel],
        **kwargs: Any,
    ) -> ModelResponse:
        self._apply_tools(**kwargs)
        return await self._request_native_structured(input, model_params, pydantic_model)

    @track_model_request
    async def _generate_response(
        self, input: ChatPromptValue, model_params: ModelParams, **kwargs: Any
    ) -> ModelResponse:
        # Check the output type and route to appropriate method
        self._apply_tools(**kwargs)
        output_type = self.model_config.get("output_type")
        model_id = str(self.model_config.get("model", "")).lower()
        if "audio" in model_id:
            return await self._generate_audio_chat_completion(input, model_params)
        if output_type == "audio":
            return await self._request_speech(input, model_params)
        elif output_type == "image":
            return await self._request_image(input, model_params)
        else:
            return await self._request_text(input, model_params)

    async def _generate_text(
        self, input: ChatPromptValue, model_params: ModelParams, **kwargs: Any
    ) -> ModelResponse:
        return await self._request_text(input, model_params)

    async def _generate_speech(
        self, input: ChatPromptValue, model_params: ModelParams, **kwargs: Any
    ) -> ModelResponse:
        return await self._request_speech(input, model_params)

    async def _generate_image(
        self, input: ChatPromptValue, model_params: ModelParams
    ) -> ModelResponse:
        return await self._request_image(input, model_params)

    async def _generate_audio_chat_completion(
        self, input: ChatPromptValue, model_params: ModelParams, **kwargs: Any
    ) -> ModelResponse:
        return await self._request_audio_chat_completion(input, model_params)

    async def _generate_image_from_text(
        self, prompt_text: str, model_url: str, model_params: ModelParams
    ) -> ModelResponse:
        params = self.generation_params
        is_streaming = params.get("stream", False)
        image_response = await self._fn_aimage_generation()(
            model=self._get_lite_llm_model_name(),
            base_url=model_params.url,
            api_key=model_params.auth_token,
            prompt=prompt_text,
            **params,
        )
        if is_streaming:
            images_data = await self._process_streaming_image_response(image_response)
        else:
            images_data = await self._process_image_response(image_response)
        if len(images_data) == 1:
            return ModelResponse(llm_response=images_data[0], response_code=200)
        else:
            return ModelResponse(llm_response=json.dumps(images_data), response_code=200)

    async def _process_streaming_image_response(self, stream_response):
        return await super()._process_streaming_image_response(stream_response)

    async def _process_image_response(self, image_response):
        return await super()._process_image_response(image_response)

    async def _url_to_data_url(self, url: str) -> str:
        return await super()._url_to_data_url(url)

    async def _edit_image_with_data_urls(
        self, image_data_urls: list, prompt_text: str, model_url: str, model_params: ModelParams
    ) -> ModelResponse:
        # Delegate to shared image flow
        return await self._request_image(ChatPromptValue(messages=[]), model_params)

    # Provider hooks
    def _get_model_prefix(self) -> str:
        # OpenAI uses direct model names (no prefix)
        return ""

    def _base_url_param(self) -> str:
        return "base_url"

    def _provider_label(self) -> str:
        return "OpenAI"

    def _native_structured_output_spec(self):
        # OpenAI supports pydantic models passed directly
        return ("response_format", "pydantic")

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
