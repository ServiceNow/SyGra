"""Run-scoped state, isolated with contextvars.

SyGra historically kept per-run state in module globals (the current task name, the
metadata collector, the weighted-sampler cache). That is fine for one CLI run per
process, but two workflows running at the same time in one process (for example two
``await workflow.arun()`` calls in a web service) would overwrite each other's state.

A ``RunContext`` holds that state for one run. ``Workflow.run()`` / ``arun()`` open
one per run. Code running outside any run context (the CLI) keeps using the module
globals, so its behaviour is unchanged.
"""

from __future__ import annotations

import contextvars
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:
    from sygra.metadata.metadata_collector import MetadataCollector


@dataclass
class RunContext:
    """State that belongs to one workflow run.

    Attributes:
        task_name: Name of the task being run. Read by ``utils.get_current_task()``.
        metadata_collector: Collector for this run's metadata. Returned by
            ``get_metadata_collector()`` while the run is active.
        sampler_cache: Weighted-sampler data sources and read pointers for this run.
        install_signal_handlers: Whether resumable runs may install SIGINT/SIGTERM
            handlers. Hosts that own signal handling (web servers, workers) should
            leave this ``False``.
    """

    task_name: Optional[str] = None
    metadata_collector: Optional["MetadataCollector"] = None
    sampler_cache: dict[str, tuple[Any, int]] = field(default_factory=dict)
    install_signal_handlers: bool = True


_RUN_CONTEXT: contextvars.ContextVar[Optional[RunContext]] = contextvars.ContextVar(
    "sygra_run_context", default=None
)


def get_run_context() -> Optional[RunContext]:
    """Return the active run context, or ``None`` outside a run (for example in the CLI)."""
    return _RUN_CONTEXT.get()


@contextmanager
def run_context(context: Optional[RunContext] = None) -> Iterator[RunContext]:
    """Make ``context`` (or a new ``RunContext``) active for code started in the block.

    It applies to code, asyncio tasks and ``asyncio.to_thread`` calls started inside
    the ``with`` block.
    """
    ctx = context if context is not None else RunContext()
    token = _RUN_CONTEXT.set(ctx)
    try:
        yield ctx
    finally:
        _RUN_CONTEXT.reset(token)
