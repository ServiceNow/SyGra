"""LLMProvider protocol, request type, provider registry and a test FakeProvider."""

from __future__ import annotations

import contextvars
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from typing import Any, Callable, Optional, Protocol, Union, runtime_checkable

from pydantic import BaseModel, Field

from sygra.core.models.model_response import ModelResponse, TokenUsage

DEFAULT_PROVIDER_NAME = "default"


class LLMRequest(BaseModel):
    """Provider-agnostic description of one LLM call.

    Attributes:
        name: SyGra model name (the ``name`` key of the node's model config).
        model: Model identifier to request from the provider (``model`` key of the
            model config, defaulting to ``name``).
        messages: Chat messages as OpenAI-style dicts (``role``/``content``, plus
            ``tool_calls``/``tool_call_id`` where present).
        parameters: Generation parameters from the model config (``temperature``,
            ``max_tokens``, ...). Providers that cannot apply a parameter should
            ignore it rather than fail.
        tools: Tools converted to the OpenAI function-tool format; empty when the
            node does not use tools.
        tool_choice: Tool choice requested by the node, if any.
        provider_options: Free-form, provider-specific options from the model
            config's ``provider_options`` key. SyGra passes them through untouched.
    """

    name: str
    model: str
    messages: list[dict[str, Any]]
    parameters: dict[str, Any] = Field(default_factory=dict)
    tools: list[dict[str, Any]] = Field(default_factory=list)
    tool_choice: Optional[Any] = None
    provider_options: dict[str, Any] = Field(default_factory=dict)


@runtime_checkable
class LLMProvider(Protocol):
    """Anything with an async ``generate(LLMRequest) -> ModelResponse`` method.

    Implementations own transport, authentication, retries and concurrency.
    Errors should be returned as a ``ModelResponse`` with a non-200
    ``response_code``; an exception is also caught and converted by SyGra.
    """

    async def generate(self, request: LLMRequest) -> ModelResponse: ...


# ── Registry ──────────────────────────────────────────────────────────────
# Process-wide registrations, plus a context-scoped overlay set by
# ``use_llm_providers`` (and ``Workflow.llm_provider``). The overlay wins, so
# concurrent runs in different contexts/threads can use different providers.

_GLOBAL_PROVIDERS: dict[str, LLMProvider] = {}
_SCOPED_PROVIDERS: contextvars.ContextVar[Optional[Mapping[str, LLMProvider]]] = (
    contextvars.ContextVar("sygra_scoped_llm_providers", default=None)
)


def _validate(provider: Any) -> LLMProvider:
    if not isinstance(provider, LLMProvider):
        raise TypeError(
            f"LLM provider must define an async 'generate(request)' method; got {type(provider)!r}"
        )
    return provider


def register_llm_provider(provider: LLMProvider, name: str = DEFAULT_PROVIDER_NAME) -> None:
    """Register a provider process-wide under ``name``."""
    _GLOBAL_PROVIDERS[name] = _validate(provider)


def unregister_llm_provider(name: str = DEFAULT_PROVIDER_NAME) -> None:
    """Remove a process-wide provider registration (no-op if absent)."""
    _GLOBAL_PROVIDERS.pop(name, None)


def get_llm_provider(name: str = DEFAULT_PROVIDER_NAME) -> LLMProvider:
    """Resolve a provider: context-scoped registrations first, then process-wide.

    Raises:
        LookupError: if no provider is registered under ``name``.
    """
    scoped = _SCOPED_PROVIDERS.get()
    if scoped and name in scoped:
        return scoped[name]
    if name in _GLOBAL_PROVIDERS:
        return _GLOBAL_PROVIDERS[name]
    raise LookupError(
        f"No LLM provider registered under '{name}'. Register one with "
        f"register_llm_provider(...), use_llm_providers(...) or Workflow.llm_provider(...)."
    )


@contextmanager
def use_llm_providers(providers: Mapping[str, LLMProvider]) -> Iterator[None]:
    """Make ``providers`` resolvable within the current context.

    Scoped registrations shadow process-wide ones with the same name and are
    visible to code (and asyncio tasks) started inside the ``with`` block.
    """
    merged: dict[str, LLMProvider] = dict(_SCOPED_PROVIDERS.get() or {})
    merged.update({name: _validate(p) for name, p in providers.items()})
    token = _SCOPED_PROVIDERS.set(merged)
    try:
        yield
    finally:
        _SCOPED_PROVIDERS.reset(token)


# ── Test double ───────────────────────────────────────────────────────────

FakeResponder = Callable[[LLMRequest], Union[str, ModelResponse]]


class FakeProvider:
    """Deterministic provider for tests and examples. Records every request.

    Args:
        responder: Either a fixed string reply, or a callable mapping an
            ``LLMRequest`` to a reply string or a full ``ModelResponse``.
            Defaults to echoing the last message's content.
        usage: Optional token usage attached to string replies.
    """

    def __init__(
        self,
        responder: Union[str, FakeResponder, None] = None,
        usage: Optional[TokenUsage] = None,
    ) -> None:
        self._responder = responder
        self._usage = usage
        self.requests: list[LLMRequest] = []

    async def generate(self, request: LLMRequest) -> ModelResponse:
        self.requests.append(request)
        if self._responder is None:
            reply: Union[str, ModelResponse] = (
                str(request.messages[-1].get("content", "")) if request.messages else ""
            )
        elif isinstance(self._responder, str):
            reply = self._responder
        else:
            reply = self._responder(request)
        if isinstance(reply, ModelResponse):
            return reply
        return ModelResponse(
            llm_response=reply,
            response_code=200,
            usage=self._usage,
            served_model=request.model,
        )
