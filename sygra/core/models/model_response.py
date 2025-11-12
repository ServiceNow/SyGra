from typing import Optional

from pydantic import BaseModel


class ModelResponse(BaseModel):
    """
    Model response object

    Args:
        llm_response (Optional[str]): The response from the model.
        response_code (int): The response code from the model.
        reasoning_response (Optional[str]): The reasoning response from the model.
        finish_reason (Optional[str]): The finish reason from the model.
        tool_calls (Optional[list]): The tool calls from the model.
    """

    llm_response: Optional[str]
    response_code: int
    reasoning_response: Optional[str] = None
    finish_reason: Optional[str] = None
    tool_calls: Optional[list] = None
