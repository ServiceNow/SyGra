from typing import Any, Type

from langchain_core.prompt_values import ChatPromptValue
from litellm import BadRequestError, acompletion, atext_completion
from openai import APIError
from openai import BadRequestError as OpenAIBadRequestError
from openai import RateLimitError
from pydantic import BaseModel

from sygra.core.models.custom_models import ModelParams
from sygra.core.models.lite_llm.base import LiteLLMBase
from sygra.core.models.model_response import ModelResponse
from sygra.logger.logger_config import logger
from sygra.metadata.metadata_integration import track_model_request
from sygra.utils import constants


class CustomOllama(LiteLLMBase):
    def __init__(self, model_config: dict[str, Any]) -> None:
        super().__init__(model_config)
        self.model_config = model_config

    def _validate_completions_api_model_support(self) -> None:
        # Ollama supports completions API
        from sygra.logger.logger_config import logger

        logger.info(f"Model {self.name()} supports completion API.")

    def _get_model_prefix(self) -> str:
        return "ollama_chat" if not self.model_config.get("completions_api", False) else "ollama"

    # Provider hooks
    def _requires_api_key(self) -> bool:
        # Ollama typically does not require api_key
        return False

    def _provider_label(self) -> str:
        return "Ollama"

    def _native_structured_output_spec(self):
        # Use JSON schema via `format` param
        return ("format", "schema")

    # Ensure tests patch module-level functions
    def _fn_acompletion(self):
        return acompletion

    def _fn_atext_completion(self):
        return atext_completion

    # Ensure module-level logger is used for tests expecting per-module logging
    def _map_exception(self, e: Exception, context: str) -> ModelResponse:
        if isinstance(e, RateLimitError):
            logger.warning(
                f"[{self.name()}] {context} request exceeded rate limit: {getattr(e, 'message', e)}"
            )
            return super()._map_exception(e, context)
        if isinstance(e, (BadRequestError, OpenAIBadRequestError)):
            msg = getattr(e, "message", e)
            logger.error(f"[{self.name()}] Ollama API bad request: {msg}")
            return ModelResponse(
                llm_response=f"{constants.ERROR_PREFIX} Ollama API bad request: {msg}",
                response_code=getattr(e, "status_code", 400),
            )
        if isinstance(e, APIError):
            logger.error(f"[{self.name()}] {context} error: {getattr(e, 'message', e)}")
            return super()._map_exception(e, context)
        logger.error(f"[{self.name()}] {context} request failed: {e}")
        return super()._map_exception(e, context)

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
