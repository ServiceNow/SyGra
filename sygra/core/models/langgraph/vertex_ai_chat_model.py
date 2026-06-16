import warnings
from typing import Any, List, Optional, Tuple

from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatResult
from langchain_openai.chat_models.base import _convert_message_to_dict

from sygra.core.models.custom_models import ModelParams
from sygra.core.models.langgraph.sygra_base_chat_model import SygraBaseChatModel
from sygra.core.models.lite_llm.vertex_ai_model import CustomVertexAI
from sygra.logger.logger_config import logger


class CustomVertexAIChatModel(SygraBaseChatModel):
    """Vertex AI chat model for use in LangGraph agent nodes.

    Delegates the actual LiteLLM/Vertex AI call to :class:`CustomVertexAI` so
    all Vertex-specific logic (model prefix, GCP credentials, tool format,
    etc.) lives in one place.  This class only adds the LangChain
    ``BaseChatModel`` interface required by ``create_react_agent``.

    Gemini thinking-mode models (gemini-3+) return a ``thoughtSignature`` with
    each function-call part.  LiteLLM encodes per-call signatures in the
    tool_call_id and collects all signatures in the message-level
    ``provider_specific_fields``.  ``_convert_message_to_dict`` (langchain-
    openai) strips ``provider_specific_fields``, so we re-attach it here to
    ensure thought_signatures survive the LangGraph message round-trip and are
    sent back in subsequent requests.
    """

    def __init__(self, model_config: dict[str, Any]) -> None:
        super().__init__(model_config)
        self._vertex = CustomVertexAI(model_config)

    @property
    def _llm_type(self) -> str:
        return "custom-vertexai-chatmodel"

    def _get_model_params(self) -> ModelParams:
        # Vertex AI uses GCP credentials, not a URL/auth_token.
        # Return empty params so SygraBaseChatModel._agenerate doesn't crash.
        return ModelParams("", "")

    # ------------------------------------------------------------------
    # thought_signature round-trip helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _build_gemini_messages(messages: List[BaseMessage]) -> List[dict]:
        """Convert LangChain messages to dicts, restoring provider_specific_fields.

        Gemini thinking-mode models require that every assistant message sent
        back in the conversation history includes the original
        ``provider_specific_fields`` (containing ``thought_signatures``).
        ``_convert_message_to_dict`` discards that field, so we re-attach it
        from ``additional_kwargs`` if it was preserved there.
        """
        result = []
        for msg in messages:
            d = _convert_message_to_dict(msg)
            if isinstance(msg, AIMessage):
                # Restore message-level provider_specific_fields (thought_signatures
                # for text parts) if they were saved during _create_chat_result.
                psf = msg.additional_kwargs.get("provider_specific_fields")
                if psf:
                    d["provider_specific_fields"] = psf
                # Restore per-tool-call provider_specific_fields from the raw
                # tool_calls stored by _convert_dict_to_message.
                raw_tcs = msg.additional_kwargs.get("tool_calls", [])
                out_tcs = d.get("tool_calls") or []
                for i, raw_tc in enumerate(raw_tcs):
                    if i >= len(out_tcs):
                        break
                    tc_psf = (
                        raw_tc.get("provider_specific_fields") if isinstance(raw_tc, dict) else None
                    )
                    if tc_psf:
                        out_tcs[i]["provider_specific_fields"] = tc_psf
            result.append(d)
        return result

    def _create_chat_result(
        self,
        response: Any,
        generation_info: Optional[dict] = None,
    ) -> ChatResult:
        """Create ChatResult and preserve provider_specific_fields for Gemini thought_signatures."""
        result = super()._create_chat_result(response, generation_info)

        # Extract provider_specific_fields from the raw response and store in
        # AIMessage.additional_kwargs so _build_gemini_messages can restore them.
        try:
            if isinstance(response, dict):
                response_dict = response
            else:
                with warnings.catch_warnings():
                    warnings.filterwarnings("ignore", category=UserWarning, module="pydantic")
                    response_dict = response.model_dump()

            for i, res in enumerate(response_dict.get("choices", [])):
                if i >= len(result.generations):
                    break
                msg = res.get("message", {})
                psf = msg.get("provider_specific_fields")
                gen_msg = result.generations[i].message
                if psf and isinstance(gen_msg, AIMessage):
                    gen_msg.additional_kwargs["provider_specific_fields"] = psf
        except Exception as exc:
            logger.debug(f"[{self._get_name()}] Could not preserve provider_specific_fields: {exc}")

        return result

    # ------------------------------------------------------------------
    # LiteLLM call wrappers
    # ------------------------------------------------------------------

    async def _generate_response(
        self,
        messages: List[BaseMessage],
        model_params: ModelParams,
        async_client: bool = True,
        **kwargs: Any,
    ) -> Tuple[Any, int]:
        try:
            msgs = self._build_gemini_messages(messages)
            common = self._vertex._build_common_kwargs(model_params)
            params = {**(self._vertex.generation_params or {}), **kwargs}
            completion = await self._vertex._fn_acompletion()(messages=msgs, **common, **params)
            return completion, 200
        except Exception as exc:
            logger.error(f"[{self._get_name()}] Vertex AI async request failed: {exc}")
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
            msgs = self._build_gemini_messages(messages)
            common = self._vertex._build_common_kwargs(model_params)
            params = {**(self._vertex.generation_params or {}), **kwargs}
            completion = litellm.completion(messages=msgs, **common, **params)
            return completion, 200
        except Exception as exc:
            logger.error(f"[{self._get_name()}] Vertex AI sync request failed: {exc}")
            return str(exc), 500
