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

from sygra.core.run_result import FailedRecord, RunUsage

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
        usage: Model and node usage collected during the run.
        failed_records: Records that failed during the run.
        output_file: Output file of the run, once known.
        graph_properties: The workflow's ``graph_properties``. Read by
            ``utils.get_graph_properties()`` instead of the task's YAML file, so
            workflows that have no task directory still get them.
        write_output: Whether output records are written to the output file. When
            ``False``, they're only kept in ``output_records``.
        output_records: Output records of this run, in the order they were written.
    """

    task_name: Optional[str] = None
    metadata_collector: Optional["MetadataCollector"] = None
    sampler_cache: dict[str, tuple[Any, int]] = field(default_factory=dict)
    install_signal_handlers: bool = True
    usage: RunUsage = field(default_factory=RunUsage)
    failed_records: list[FailedRecord] = field(default_factory=list)
    output_file: Optional[str] = None
    graph_properties: Optional[dict[str, Any]] = None
    write_output: bool = True
    output_records: list[Any] = field(default_factory=list)


_RUN_CONTEXT: contextvars.ContextVar[Optional[RunContext]] = contextvars.ContextVar(
    "sygra_run_context", default=None
)

# ``id`` of the record being processed; each record runs in its own asyncio task.
current_record_id: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "sygra_current_record_id", default=None
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
