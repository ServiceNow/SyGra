from pydantic import BaseModel, root_validator, model_validator, Field
from typing import Any


class SimpleResponse(BaseModel):
    """Simple response with just text and status"""

    message: str = Field(description="Response message")
    success: bool = Field(default=True, description="Operation success status")
