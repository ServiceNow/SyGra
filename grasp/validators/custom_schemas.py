from datetime import datetime, timezone
from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator, model_validator, root_validator, validator


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
    def check_non_empty_lists(cls, values):
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
    quality: dict[str, float] = Field(
        default_factory=lambda: {"__default__": True}, validate_default=True
    )
    safety: dict[str, Any] = Field(
        default_factory=lambda: {"__default__": True}, validate_default=True
    )
    length: dict[str, Any] = Field(default=dict)
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
    def set_data_characteristics(cls, data_characteristics):
        if data_characteristics is None or (
            isinstance(data_characteristics, dict) and len(data_characteristics) == 0
        ):
            return {"__default__": True}
        return data_characteristics

    @field_validator("quality", mode="before")
    def set_quality(cls, quality):
        if quality is None or (isinstance(quality, dict) and len(quality) == 0):
            return {"__default__": True}
        return quality

    @field_validator("safety", mode="before")
    def set_safety(cls, safety):
        if safety is None or (isinstance(safety, dict) and len(safety) == 0):
            return {"__default__": True}
        return safety

    @field_validator("categories", mode="before")
    def set_categories(cls, categories):
        if categories is None:
            return []
        elif isinstance(categories, str):
            return [categories]
        return categories

    @field_validator("instruction_tags", mode="before")
    def set_instruction_tags(cls, instruction_tags):
        if instruction_tags is None:
            return []
        elif isinstance(instruction_tags, str):
            return [instruction_tags]
        return instruction_tags

    @field_validator("subcategories", mode="before")
    def set_subcategories(cls, subcategories):
        if subcategories is None:
            return []
        elif isinstance(subcategories, str):
            return [subcategories]
        return subcategories

    @field_validator("parent_id")
    def validate_parent_child(cls, v, values):
        if "message_level" in values:
            if values["message_level"] == 1 and v is not None:
                raise ValueError("First message (level=1) cannot have a parent_id")
            if values["message_level"] > 1 and v is None:
                raise ValueError("Non-first messages must have a parent_id")
        return v


class PipelineStep(BaseModel):
    name: str
    old_key: Optional[str] = None
    new_key: Optional[str] = None
