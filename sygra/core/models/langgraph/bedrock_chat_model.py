from typing import Any, List, Tuple

from langchain_core.messages import BaseMessage
from langchain_core.prompt_values import ChatPromptValue

from sygra.core.models.custom_models import ModelParams
from sygra.core.models.langgraph.sygra_base_chat_model import SygraBaseChatModel
from sygra.core.models.lite_llm.bedrock_model import CustomBedrock
from sygra.logger.logger_config import logger


class CustomBedrockChatModel(SygraBaseChatModel):
    """Bedrock chat model for use in LangGraph agent nodes.

    Delegates the actual LiteLLM/Bedrock call to :class:`CustomBedrock` so
    all bedrock-specific logic (model prefix, AWS credentials, tool format,
    etc.) lives in one place.  This class only adds the LangChain
    ``BaseChatModel`` interface required by ``create_react_agent``.
    """

    def __init__(self, model_config: dict[str, Any]) -> None:
        super().__init__(model_config)
        self._bedrock = CustomBedrock(model_config)

    @property
    def _llm_type(self) -> str:
        return "custom-bedrock-chatmodel"

    def _get_model_params(self) -> ModelParams:
        # Bedrock uses AWS credentials, not a URL/auth_token.
        # Return empty params so SygraBaseChatModel._agenerate doesn't crash.
        return ModelParams("", "")

    async def _generate_response(
        self,
        messages: List[BaseMessage],
        model_params: ModelParams,
        async_client: bool = True,
        **kwargs: Any,
    ) -> Tuple[Any, int]:
        try:
            chat_prompt = ChatPromptValue(messages=messages)
            msgs = self._bedrock._get_messages(chat_prompt)
            common = self._bedrock._build_common_kwargs(model_params)
            params = {**(self._bedrock.generation_params or {}), **kwargs}
            completion = await self._bedrock._fn_acompletion()(messages=msgs, **common, **params)
            return completion, 200
        except Exception as exc:
            logger.error(f"[{self._get_name()}] Bedrock async request failed: {exc}")
            return str(exc), 500

    def _sync_generate_response(
        self,
        messages: List[BaseMessage],
        model_params: ModelParams,
        async_client: bool = True,
        **kwargs: Any,
    ) -> Tuple[Any, int]:
        import litellm

        try:
            chat_prompt = ChatPromptValue(messages=messages)
            msgs = self._bedrock._get_messages(chat_prompt)
            common = self._bedrock._build_common_kwargs(model_params)
            params = {**(self._bedrock.generation_params or {}), **kwargs}
            completion = litellm.completion(messages=msgs, **common, **params)
            return completion, 200
        except Exception as exc:
            logger.error(f"[{self._get_name()}] Bedrock sync request failed: {exc}")
            return str(exc), 500
