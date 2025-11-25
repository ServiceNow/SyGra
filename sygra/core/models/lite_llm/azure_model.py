from typing import Any

from langchain_core.prompt_values import ChatPromptValue
from openai import APIError, BadRequestError, RateLimitError

from sygra.core.models.custom_models import ModelParams
from sygra.core.models.lite_llm.base import LiteLLMBase
from sygra.core.models.model_response import ModelResponse
from sygra.logger.logger_config import logger
from sygra.metadata.metadata_integration import track_model_request
from sygra.utils import constants, utils


class CustomAzure(LiteLLMBase):
    def __init__(self, model_config: dict[str, Any]) -> None:
        super().__init__(model_config)
        utils.validate_required_keys(["url", "auth_token"], model_config, "model")
        self.model_config = model_config
        self.model_name = self.model_config.get("model", self.name())

    @track_model_request
    async def _generate_response(
        self, input: ChatPromptValue, model_params: ModelParams, **kwargs: Any
    ) -> ModelResponse:
        self._apply_tools(**kwargs)
        result = await self._request_text(input, model_params)
        if getattr(result, "finish_reason", None) == "content_filter":

            logger.error(
                f"[{self.name()}] Azure request failed with code: 400 and error: {constants.ERROR_PREFIX} Blocked by azure content filter"
            )
        return result

    # Provider hooks
    def _get_model_prefix(self) -> str:
        return "azure_ai"

    def _base_url_param(self) -> str:
        return "api_base"

    def _provider_label(self) -> str:
        return "Azure"

    def _check_content_filter_finish_reason(self) -> bool:
        return True

    def _map_exception(self, e: Exception, context: str) -> ModelResponse:
        # Import locally to avoid binding at module import time

        if isinstance(e, RateLimitError):
            logger.warning(
                f"[{self.name()}] Azure API request exceeded rate limit: {getattr(e, 'message', e)}"
            )
            ctx = "Azure API"
        elif isinstance(e, BadRequestError):
            logger.error(f"[{self.name()}] Azure API bad request: {getattr(e, 'message', e)}")
            ctx = "Azure API"
        elif isinstance(e, APIError):
            logger.error(f"[{self.name()}] Azure API error: {getattr(e, 'message', e)}")
            ctx = "Azure API"
        else:
            logger.error(f"[{self.name()}] Azure text generation failed: {e}")
            ctx = "Azure API"
        return super()._map_exception(e, ctx)
