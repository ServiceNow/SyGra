from __future__ import annotations

import json
import logging
import os
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


class CustomVertexAI(LiteLLMBase):
    def __init__(self, model_config: dict[str, Any]) -> None:
        super().__init__(model_config)
        # Vertex AI via LiteLLM doesn't require url/api_key; credentials are passed explicitly
        utils.validate_required_keys(
            ["vertex_project", "vertex_location", "vertex_credentials"], model_config, "model"
        )
        self.model_config = model_config
        self.model_name = self.model_config.get("model", self.name())

    # Provider hooks
    def _get_model_prefix(self) -> str:
        # Use litellm vertex provider prefix
        return "vertex_ai"

    def _provider_label(self) -> str:
        return "Vertex AI"

    def _requires_api_key(self) -> bool:
        # Credentials provided via vertex_credentials JSON, not api_key
        return False

    def _extra_call_params(self) -> dict[str, Any]:
        extra: dict[str, Any] = {}
        vp = self.model_config.get("vertex_project")
        vl = self.model_config.get("vertex_location")
        vcred = self.model_config.get("vertex_credentials")
        if vp:
            extra["vertex_project"] = vp
        if vl:
            extra["vertex_location"] = vl
        if vcred is not None:
            try:
                if isinstance(vcred, dict):
                    extra["vertex_credentials"] = json.dumps(vcred)
                elif isinstance(vcred, str):
                    path_candidate = os.path.expanduser(os.path.expandvars(vcred))
                    if os.path.isfile(path_candidate):
                        with open(path_candidate, "r") as f:
                            creds_dict = json.load(f)
                        extra["vertex_credentials"] = json.dumps(creds_dict)
                    else:
                        extra["vertex_credentials"] = vcred
                else:
                    extra["vertex_credentials"] = str(vcred)
            except Exception:
                extra["vertex_credentials"] = vcred
        return extra

    def _build_common_kwargs(self, model_params: ModelParams) -> dict[str, Any]:
        # Start with base construction
        common = super()._build_common_kwargs(model_params)
        # Remove base_url if not set/needed
        base_url_key = self._base_url_param()
        if not model_params.url and base_url_key in common:
            common.pop(base_url_key, None)
        # Ensure api_key is not passed
        common.pop("api_key", None)
        return common

    # Vertex AI does not support image editing
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
        if output_type == "audio":
            result = await self._generate_speech(input, model_params)
        elif output_type == "image":
            result = await self._generate_image(input, model_params)
        else:
            result = await self._generate_text(input, model_params)
        return result

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
