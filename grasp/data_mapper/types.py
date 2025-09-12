from dataclasses import dataclass, field
from typing import Any, Optional, Protocol


@dataclass
class TransformMeta:
    """Metadata about a transform including its requirements"""

    name: str
    requires: list[str] = field(default_factory=list)
    provides: list[str] = field(default_factory=list)


class Transform(Protocol):
    """Protocol defining the interface for transforms"""

    meta: TransformMeta

    def transform(self, value: Any, context: dict[str, Any]) -> Optional[list[dict[str, Any]]]:
        """Transform a value using context, optionally returning rows"""
        pass
