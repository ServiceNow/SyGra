"""What to do when a model looks down (repeated 404/5xx responses in a short window).

Actions:
    ``"exit"``: log and call ``sys.exit()``. The default, and the CLI behaviour.
    ``"raise"``: raise :class:`sygra.exceptions.ModelServerDownError`, so the host decides.
    ``"ignore"``: don't track server-down responses for this model.

Resolution order: the model config's ``server_down_action`` key, then the action set
for the current context with :func:`server_down_action` (``Workflow.run`` sets
``"raise"``), then ``"exit"``.
"""

from __future__ import annotations

import contextvars
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any, Literal, Optional, cast

ServerDownAction = Literal["exit", "raise", "ignore"]
SERVER_DOWN_ACTIONS: tuple[str, ...] = ("exit", "raise", "ignore")
DEFAULT_SERVER_DOWN_ACTION: ServerDownAction = "exit"

_SCOPED_ACTION: contextvars.ContextVar[Optional[ServerDownAction]] = contextvars.ContextVar(
    "sygra_server_down_action", default=None
)


def validate_server_down_action(action: Any) -> Optional[ServerDownAction]:
    """Return ``action`` if it is a valid action or ``None``; raise ``ValueError`` otherwise."""
    if action is None:
        return None
    if action not in SERVER_DOWN_ACTIONS:
        raise ValueError(
            f"Invalid server_down_action {action!r}; expected one of {list(SERVER_DOWN_ACTIONS)}"
        )
    return cast(ServerDownAction, action)


def resolve_server_down_action(configured: Optional[ServerDownAction] = None) -> ServerDownAction:
    """Return the effective action: ``configured`` (from model config), then scope, then default."""
    if configured is not None:
        return configured
    return _SCOPED_ACTION.get() or DEFAULT_SERVER_DOWN_ACTION


@contextmanager
def server_down_action(action: ServerDownAction) -> Iterator[None]:
    """Set the server-down action for models used within the current context.

    Applies to code, asyncio tasks and context-copying executors started inside the
    ``with`` block. A model's own ``server_down_action`` config key still wins.
    """
    token = _SCOPED_ACTION.set(validate_server_down_action(action))
    try:
        yield
    finally:
        _SCOPED_ACTION.reset(token)
