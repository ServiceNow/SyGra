"""Per-call state for one model request, isolated with contextvars.

A model instance is shared by every record that goes through its node, and records
run concurrently. Values that belong to a single request (its token usage, the tool
parameters for that request) therefore can't live on the instance. They live in a
``ModelCallState`` that ``track_model_request`` opens around each request.
"""

from __future__ import annotations

import contextvars
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class ModelCallState:
    """State of the model request currently in progress.

    Attributes:
        usage: Token usage reported for this request (``prompt_tokens``,
            ``completion_tokens``, ``total_tokens``), if any.
        tool_params: Request parameters derived from the node's tools for this
            request (``tools``, ``tool_choice``, ...). Merged over the model's
            ``generation_params`` without mutating them.
    """

    usage: Optional[dict[str, int]] = None
    tool_params: dict[str, Any] = field(default_factory=dict)


_CURRENT_CALL: contextvars.ContextVar[Optional[ModelCallState]] = contextvars.ContextVar(
    "sygra_model_call", default=None
)


def current_model_call() -> Optional[ModelCallState]:
    """Return the state of the model request in progress, or ``None`` outside one."""
    return _CURRENT_CALL.get()


@contextmanager
def model_call() -> Iterator[ModelCallState]:
    """Open a fresh ``ModelCallState`` for the duration of one model request."""
    state = ModelCallState()
    token = _CURRENT_CALL.set(state)
    try:
        yield state
    finally:
        _CURRENT_CALL.reset(token)
