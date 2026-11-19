from typing import Optional

from pydantic import BaseModel


class TokenUsage(BaseModel):
    """
    Token usage for one model call.

    Args:
        prompt_tokens (int): Input tokens.
        completion_tokens (int): Output tokens.
        total_tokens (int): Total tokens.
        estimated (bool): True when counts were estimated rather than reported by the backend.
    """

    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    estimated: bool = False


class ModelResponse(BaseModel):
    """
    Model response object

    Args:
        llm_response (Optional[str]): The response from the model.
        response_code (int): The response code from the model.
        reasoning_response (Optional[str]): The reasoning response from the model.
        finish_reason (Optional[str]): The finish reason from the model.
        tool_calls (Optional[list]): The tool calls from the model.
        usage (Optional[TokenUsage]): Token usage, when the backend (or provider) reports it.
        served_model (Optional[str]): The model that actually served the call, when known.
            May differ from the requested model if a gateway or router falls back.
    """

    llm_response: Optional[str]
    response_code: int
    reasoning_response: Optional[str] = None
    finish_reason: Optional[str] = None
    tool_calls: Optional[list] = None
    usage: Optional[TokenUsage] = None
    served_model: Optional[str] = None
