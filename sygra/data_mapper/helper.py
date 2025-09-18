import json
from datetime import datetime
from typing import Any, Optional, Type

import numpy as np
from pydantic import BaseModel, Field

from sygra.data_mapper.transformations import (
    ConversationTransform,
    CopyTransform,
    DPOConversationTransform,
    LengthTransform,
    QualityTransform,
    TaxonomyTransform,
)
from sygra.data_mapper.types import Transform
from sygra.validators.custom_schemas import PipelineStep


class JSONEncoder(json.JSONEncoder):
    """Encodes special objects (datetime, np.ndarray) to JSON-friendly representations."""

    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        return super().default(obj)


class PipelineConfig(BaseModel):
    """Configuration class for the transformation pipeline, using Pydantic for validation and structure."""

    pipeline: list[PipelineStep]
    output: dict[str, Any] = Field(default_factory=dict)


class TransformRegistry:
    """Registry to manage transform classes and their instances."""

    def __init__(self):
        self._registry: dict[str, Transform] = {}

    def register(self, name: Optional[str] = None):
        """
        Decorator for registering a transform class with the registry.

        Args:
            name (str, optional): The name to associate with the transform, if not provided,
                                   the class name is used.

        Returns:
            decorator function for registering the transform class.
        """

        def decorator(transform_class: Type[Transform]) -> Type[Transform]:
            transform_name = name or transform_class.meta.name
            self._registry[transform_name] = transform_class()
            return transform_class

        return decorator

    def register_transforms(self, *transforms: Type[Transform]) -> None:
        """
        Register multiple transform classes at once.

        Args:
            *transforms (Type[Transform]): Transform classes to be registered.
        """
        for transform_class in transforms:
            self._registry[transform_class.meta.name] = transform_class()

    def get(self, name: str) -> Transform:
        """
        Retrieve a transform by its name.

        Args:
            name (str): The name of the transform to retrieve.

        Returns:
            Transform: The transform instance associated with the given name.

        Raises:
            ValueError: If the transform is not found in the registry.
        """
        if name not in self._registry:
            raise ValueError(f"Transform '{name}' not found in registry!")
        return self._registry[name]

    @staticmethod
    def validate_requirements(transform: Transform, context: dict[str, Any]) -> None:
        """
        Check if all required context fields are present for the transform.

        Args:
            transform (Transform): The transform instance to validate.
            context (dict[str, Any]): The context in which the transform is to be applied.

        Raises:
            ValueError: If any required context field is missing.
        """
        for req in transform.meta.requires:
            if req not in context:
                raise ValueError(
                    f"Transform {transform.meta.name} requires '{req}' in context. Please ensure input data is in conversation format. If not, disable OASST mapping accordingly."
                )


transform_registry = TransformRegistry()
transform_registry.register_transforms(
    TaxonomyTransform,
    ConversationTransform,
    QualityTransform,
    LengthTransform,
    CopyTransform,
    DPOConversationTransform,
)
