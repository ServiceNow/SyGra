"""In-memory result of a workflow run: output records, failures, usage and cost."""

from __future__ import annotations

import threading
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from sygra.core.models.model_response import TokenUsage


@dataclass
class UsageStats:
    """Aggregated model usage for one model, node or record.

    Attributes:
        requests: Model requests made (each retry attempt counts).
        failed_requests: Requests that didn't return status 200 or raised.
        prompt_tokens / completion_tokens / total_tokens: Token totals.
        estimated: True if any counted request reported estimated usage.
        latency_seconds: Sum of request (or node) latencies.
        served_models: How often each model actually served a request, when the
            backend reports it (``ModelResponse.served_model``).
        cost_usd: Set only when a ``cost_fn`` is supplied to the run.
    """

    requests: int = 0
    failed_requests: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    estimated: bool = False
    latency_seconds: float = 0.0
    served_models: dict[str, int] = field(default_factory=dict)
    cost_usd: Optional[float] = None

    def _add(
        self,
        usage: Optional[TokenUsage],
        latency: float,
        success: bool,
        served_model: Optional[str] = None,
    ) -> None:
        self.requests += 1
        if not success:
            self.failed_requests += 1
        if usage is not None:
            self.prompt_tokens += usage.prompt_tokens
            self.completion_tokens += usage.completion_tokens
            self.total_tokens += usage.total_tokens
            self.estimated = self.estimated or usage.estimated
        self.latency_seconds += latency
        if served_model:
            self.served_models[served_model] = self.served_models.get(served_model, 0) + 1

    def _merge(self, other: "UsageStats") -> None:
        self.requests += other.requests
        self.failed_requests += other.failed_requests
        self.prompt_tokens += other.prompt_tokens
        self.completion_tokens += other.completion_tokens
        self.total_tokens += other.total_tokens
        self.estimated = self.estimated or other.estimated
        self.latency_seconds += other.latency_seconds
        for name, count in other.served_models.items():
            self.served_models[name] = self.served_models.get(name, 0) + count


@dataclass
class FailedRecord:
    """A record that failed during the run.

    Attributes:
        id: The input record's ``id`` (``None`` if it had none).
        kind: ``"model_error"`` (a node got an error response), ``"exception"``
            (graph execution raised) or ``"schema_validation"`` (output rejected).
        error: Error message.
    """

    id: Optional[str]
    kind: str
    error: str


class RunUsage:
    """Thread-safe accumulator of usage per model, node and record for one run."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.by_model: dict[str, UsageStats] = {}
        self.by_node: dict[str, UsageStats] = {}
        self.by_record: dict[str, UsageStats] = {}

    def record_model_request(
        self,
        model_name: str,
        usage: Optional[TokenUsage],
        latency: float,
        success: bool,
        served_model: Optional[str] = None,
        record_id: Optional[str] = None,
    ) -> None:
        with self._lock:
            self.by_model.setdefault(model_name, UsageStats())._add(
                usage, latency, success, served_model
            )
            if record_id is not None:
                self.by_record.setdefault(record_id, UsageStats())._add(
                    usage, latency, success, served_model
                )

    def record_node_execution(
        self,
        node_name: str,
        usage: Optional[TokenUsage],
        latency: float,
        success: bool,
    ) -> None:
        with self._lock:
            self.by_node.setdefault(node_name, UsageStats())._add(usage, latency, success)

    def total(self) -> UsageStats:
        """Usage summed over all models."""
        total = UsageStats()
        with self._lock:
            for stats in self.by_model.values():
                total._merge(stats)
        return total


CostFn = Callable[[str, UsageStats], float]


class RunResult(list):
    """Result of :meth:`Workflow.run` / :meth:`Workflow.arun`.

    It *is* the list of output records (same content as the output file), so code
    that treats the result as a list keeps working. It also carries:

    Attributes:
        failed_records: Records that failed, with the reason.
        usage_by_model: Usage per model (keyed by the model identifier).
        usage_by_node: Usage per graph node.
        usage_by_record: Usage per input record ``id``.
        total_usage: Usage over all models.
        cost_usd: Total cost, if a ``cost_fn`` was supplied; otherwise ``None``.
        output_file: Path of the output file, or ``None`` if it was temporary.
    """

    def __init__(
        self,
        records: Iterable[Any] = (),
        *,
        failed_records: Optional[list[FailedRecord]] = None,
        usage: Optional[RunUsage] = None,
        output_file: Optional[str] = None,
        cost_fn: Optional[CostFn] = None,
    ) -> None:
        super().__init__(records)
        run_usage = usage or RunUsage()
        self.failed_records: list[FailedRecord] = list(failed_records or [])
        self.usage_by_model: dict[str, UsageStats] = dict(run_usage.by_model)
        self.usage_by_node: dict[str, UsageStats] = dict(run_usage.by_node)
        self.usage_by_record: dict[str, UsageStats] = dict(run_usage.by_record)
        self.total_usage: UsageStats = run_usage.total()
        self.output_file = output_file
        self.cost_usd: Optional[float] = None
        if cost_fn is not None:
            for model_name, stats in self.usage_by_model.items():
                stats.cost_usd = float(cost_fn(model_name, stats))
            self.cost_usd = sum(s.cost_usd or 0.0 for s in self.usage_by_model.values())
            self.total_usage.cost_usd = self.cost_usd

    @property
    def records(self) -> list[Any]:
        """The output records as a plain list."""
        return list(self)
