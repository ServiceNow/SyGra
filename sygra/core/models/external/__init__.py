"""Pluggable LLM providers.

Lets a host application route SyGra's LLM calls through its own client — a
corporate gateway, an in-house SDK, a caching or recording layer, or a test
double — instead of SyGra's built-in HTTP/LiteLLM clients.

Usage::

    from sygra.core.models.external import FakeProvider, LLMRequest, use_llm_providers

    class MyProvider:
        async def generate(self, request: LLMRequest) -> ModelResponse:
            ...

    # model config for a node:
    #   model: {name: my_model, model_type: external, provider: my_gateway}
    with use_llm_providers({"my_gateway": MyProvider()}):
        workflow.run(...)

The provider owns transport, authentication, retries and concurrency limits.
"""

from sygra.core.models.external.provider import (
    DEFAULT_PROVIDER_NAME,
    FakeProvider,
    LLMProvider,
    LLMRequest,
    get_llm_provider,
    register_llm_provider,
    unregister_llm_provider,
    use_llm_providers,
)

__all__ = [
    "DEFAULT_PROVIDER_NAME",
    "FakeProvider",
    "LLMProvider",
    "LLMRequest",
    "get_llm_provider",
    "register_llm_provider",
    "unregister_llm_provider",
    "use_llm_providers",
]
