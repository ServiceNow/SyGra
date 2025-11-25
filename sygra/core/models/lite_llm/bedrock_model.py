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


class CustomBedrock(LiteLLMBase):
    def __init__(self, model_config: dict[str, Any]) -> None:
        super().__init__(model_config)
        # Bedrock via LiteLLM uses AWS credentials (env or explicit params), not url/api_key
        utils.validate_required_keys(
            ["aws_access_key_id", "aws_secret_access_key", "aws_region_name"], model_config, "model"
        )
        self.model_config = model_config
        self.model_name = self.model_config.get("model", self.name())

    # Provider hooks
    def _get_model_prefix(self) -> str:
        # LiteLLM Bedrock provider prefix
        return "bedrock"

    def _provider_label(self) -> str:
        return "Bedrock"

    def _base_url_param(self) -> str:
        # Bedrock does not use base URL
        return "api_base"

    def _requires_api_key(self) -> bool:
        # Credentials are passed via AWS keys or environment, not api_key
        return False

    def _extra_call_params(self) -> dict[str, Any]:
        # Allow passing AWS credentials explicitly via model config, otherwise LiteLLM
        # will read them from the environment.
        cfg = self.model_config
        extra: dict[str, Any] = {}
        for key in (
            "aws_access_key_id",
            "aws_secret_access_key",
            "aws_region_name",
        ):
            val = cfg.get(key)
            if val:
                extra[key] = val
        return extra

    def _build_common_kwargs(self, model_params: ModelParams) -> dict[str, Any]:
        # Start with base construction and remove base_url/api_key as they're not used
        common = super()._build_common_kwargs(model_params)
        base_url_key = self._base_url_param()
        if base_url_key in common:
            common.pop(base_url_key, None)
        common.pop("api_key", None)
        return common

    # Bedrock does not support a generic image edit API across all models
    def _fn_aimage_edit(self):
        raise NotImplementedError(f"Image editing is not supported by {self._provider_label}")

    def _native_structured_output_spec(self):
        return ("response_format", "pydantic")

    @track_model_request
    async def _generate_response(
        self, input: ChatPromptValue, model_params: ModelParams, **kwargs: Any
    ) -> ModelResponse:
        self._apply_tools(**kwargs)
        output_type = self.model_config.get("output_type")
        if output_type == "image":
            return await self._request_image(input, model_params)
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
