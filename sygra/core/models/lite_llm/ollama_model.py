from typing import Any

from langchain_core.prompt_values import ChatPromptValue
from openai import APIError, BadRequestError, RateLimitError

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

    # Ensure module-level logger is used for tests expecting per-module logging
    def _map_exception(self, e: Exception, context: str) -> ModelResponse:
        if isinstance(e, RateLimitError):
            logger.warning(
                f"[{self.name()}] {context} request exceeded rate limit: {getattr(e, 'message', e)}"
            )
            return super()._map_exception(e, context)
        if isinstance(e, BadRequestError):
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
    async def _generate_response(
        self, input: ChatPromptValue, model_params: ModelParams, **kwargs: Any
    ) -> ModelResponse:
        self._apply_tools(**kwargs)
        output_type = self.model_config.get("output_type")
        if output_type in ("audio", "image"):
            logger.error(
                f"[{self.name()}] {self._provider_label()} does not support output_type '{output_type}'"
            )
            raise ValueError(
                f"[{self.name()}] {self._provider_label()} does not support output_type '{output_type}'"
            )
        return await self._generate_text(input, model_params)
