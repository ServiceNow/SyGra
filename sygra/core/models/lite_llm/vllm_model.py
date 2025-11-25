from __future__ import annotations

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


class CustomVLLM(LiteLLMBase):
    def __init__(self, model_config: dict[str, Any]) -> None:
        super().__init__(model_config)
        utils.validate_required_keys(["url", "auth_token"], model_config, "model")
        self.model_config = model_config
        self.auth_token = str(model_config.get("auth_token")).replace("Bearer ", "")
        self.model_serving_name = model_config.get("model_serving_name", self.name())

    def _validate_completions_api_model_support(self) -> None:
        logger.info(f"Model {self.name()} supports completion API.")

    def _get_model_prefix(self) -> str:
        return "hosted_vllm"

    # Provider hooks
    def _provider_label(self) -> str:
        return "vLLM"

    def _native_structured_output_spec(self):
        # vLLM uses guided_json with JSON schema
        return ("guided_json", "schema")

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
        self._apply_tools(**kwargs)
        return await self._request_text(input, model_params)

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
