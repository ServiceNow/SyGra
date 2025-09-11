from typing import Any

from pydantic import BaseModel, Field, model_validator, root_validator


class SimpleResponse(BaseModel):
    """Simple response with just text and status"""

    message: str = Field(description="Response message")
    success: bool = Field(default=True, description="Operation success status")
