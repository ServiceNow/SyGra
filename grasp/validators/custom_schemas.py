from datetime import datetime, timezone
from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator, model_validator


class CustomUserSchema(BaseModel):
    """
    This demonstrates an example of a customizable user schema that can be modified or redefined by the end user.
    Below is a sample schema with associated validator methods.
    """

    id: int
    conversation: list[dict[str, Any]]
    taxonomy: list[dict[str, Any]]
    annotation_type: list[str]
    language: list[str]
    tags: list[str]

    @model_validator(mode="before")
    @classmethod
    def check_non_empty_lists(cls, values: dict[str, Any]):
        if not values.get("id"):
            raise ValueError("id cannot be empty")
        return values


class SourceInfo(BaseModel):
    """Source dataset information"""

    name: str
    version: str
    url: Optional[str] = None


class MetaInfo(BaseModel):
    """Enhanced metadata about the source and transformation"""

    source_id: Optional[str]
    source_metadata: dict[str, Any] = Field(default_factory=dict)


class CoreLLMDataFabricFormat(BaseModel):
    """Enhanced schema for transformed message rows"""

    conversation_id: str
    message_id: str
    parent_id: Optional[str]
    root_message_id: str
    message_level: int
    role: str
    content: str
    languages: list[str] = Field(default_factory=list)
    categories: list[str] = Field(default_factory=list)
    subcategories: list[str] = Field(default_factory=list)
    generated_by: str = ""
    quality: dict[str, Any] = Field(
        default_factory=lambda: {"__default__": True}, validate_default=True
    )
    safety: dict[str, Any] = Field(
        default_factory=lambda: {"__default__": True}, validate_default=True
    )
    length: dict[str, Any] = Field(default_factory=dict)
    instruction_tags: list[str] = Field(default_factory=list)
    data_characteristics: dict[str, Any] = Field(
        default_factory=lambda: {"__default__": True}, validate_default=True
    )
    tags: list[str] = Field(default_factory=list)
    metainfo: MetaInfo
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    active: bool = True

    @field_validator("data_characteristics", mode="before")
    @classmethod
    def set_data_characteristics(cls, v):
        if v is None or (isinstance(v, dict) and len(v) == 0):
            return {"__default__": True}
        return v

    @field_validator("quality", mode="before")
    @classmethod
    def set_quality(cls, v):
        if v is None or (isinstance(v, dict) and len(v) == 0):
            return {"__default__": True}
        return v

    @field_validator("safety", mode="before")
    @classmethod
    def set_safety(cls, v):
        if v is None or (isinstance(v, dict) and len(v) == 0):
            return {"__default__": True}
        return v

    @field_validator("categories", mode="before")
    @classmethod
    def set_categories(cls, v):
        if v is None:
            return []
        if isinstance(v, str):
            return [v]
        return v

    @field_validator("instruction_tags", mode="before")
    @classmethod
    def set_instruction_tags(cls, v):
        if v is None:
            return []
        if isinstance(v, str):
            return [v]
        return v

    @field_validator("subcategories", mode="before")
    @classmethod
    def set_subcategories(cls, v):
        if v is None:
            return []
        if isinstance(v, str):
            return [v]
        return v

    # ---------- cross-field validation (v2: model_validator) ----------
    @model_validator(mode="after")
    def validate_parent_child(self):
        if self.message_level == 1 and self.parent_id is not None:
            raise ValueError("First message (level=1) cannot have a parent_id")
        if self.message_level > 1 and self.parent_id is None:
            raise ValueError("Non-first messages must have a parent_id")
        return self


class PipelineStep(BaseModel):
    name: str
    old_key: Optional[str] = None
    new_key: Optional[str] = None
