# External LLM Providers

> **Route a model's calls through your own client with `model_type: external`**

## Overview

By default SyGra calls models through its built-in HTTP and LiteLLM clients, configured with `SYGRA_<MODEL>_URL` / `SYGRA_<MODEL>_TOKEN`. An **external provider** lets the application that runs SyGra serve the calls instead.

This is useful when:

- Calls must go through your own gateway, router or in-house SDK, with your own auth.
- You want to add caching, recording, rate limiting or cost tracking around every call.
- You need a deterministic test double, so pipelines can be tested without network access.

A provider is any object with an async `generate` method:

```python
from sygra import LLMRequest, ModelResponse


class MyProvider:
    async def generate(self, request: LLMRequest) -> ModelResponse:
        text = await my_client.complete(request.messages, model=request.model, **request.parameters)
        return ModelResponse(llm_response=text, response_code=200)
```

**The provider owns transport, authentication, retries and concurrency.** SyGra builds the request, calls the provider, and then handles the response as usual: structured-output fallback, post-processors and failure detection.

## Quick Start

```python
from sygra import FakeProvider, Workflow

provider = FakeProvider(lambda req: req.messages[-1]["content"].upper())

records = (
    Workflow("external_demo")
    .source([{"id": "1", "text": "hello"}, {"id": "2", "text": "world"}])
    .llm({"name": "generator", "model_type": "external"}, "{text}", output="answer")
    .llm_provider(provider)  # serves model_type: external for this run only
    .run(num_records=2)
)
# records[i]["answer"] == "HELLO" / "WORLD"
```

## Model configuration

Any model config (in a task's `graph_config.yaml`, in `models.yaml`, or passed in code) can use an external provider:

```yaml
model:
  name: generator            # SyGra model name
  model_type: external
  provider: my_gateway       # registered provider name (default: "default")
  model: acme-large          # identifier passed to the provider (default: name)
  parameters:                # passed through as LLMRequest.parameters
    temperature: 0.7
    max_tokens: 2048
  provider_options:          # free-form, passed through as LLMRequest.provider_options
    route: eu
```

| Key | Default | Meaning |
|---|---|---|
| `provider` | `default` | Name of the registered provider that serves this model. |
| `model` | `name` | Model identifier sent to the provider. |
| `parameters` | `{}` | Generation parameters. If a provider can't apply one, it should ignore it. |
| `provider_options` | `{}` | Provider-specific options. SyGra doesn't interpret them. |
| `retry_attempts` | `1` | SyGra-side attempts. The default `1` means no SyGra retries, because the provider owns retries. |
| `delay` | `0` | Pre-call delay in ms. |

## Registering providers

| API | Scope |
|---|---|
| `Workflow.llm_provider(provider, name="default")` | Only for that workflow's `run()` / `arun()`, in the calling context. |
| `with use_llm_providers({"name": provider}): ...` | Code (and asyncio tasks) started inside the block. Shadows global registrations. |
| `register_llm_provider(provider, name="default")` | Process-wide. |

**Resolution order:** context-scoped registrations first, then process-wide ones. A model whose provider can't be found raises `LookupError` when the graph is built, before any record is processed.

**Concurrency:** scoped registrations are isolated per thread and per context, so two workflows running at the same time can use different providers.

## Request and response

`LLMRequest` fields:

| Field | Type | Description |
|---|---|---|
| `name` | `str` | SyGra model name. |
| `model` | `str` | Model identifier to request. |
| `messages` | `list[dict]` | OpenAI-style chat messages (`role`, `content`, plus `tool_calls` / `tool_call_id` where present). |
| `parameters` | `dict` | Generation parameters. |
| `tools` | `list[dict]` | Node tools in the OpenAI function-tool format; empty if the node has none. |
| `tool_choice` | `Any` | The node's tool choice, when tools are used. |
| `provider_options` | `dict` | Pass-through options from the model config. |

Return a `ModelResponse`:

- `llm_response`: the text reply.
- `response_code`: `200` on success. Any other code marks the call as failed: the node records a failure and the record is handled like any other model error.
- `tool_calls`: tool calls in OpenAI dict format, if any.
- `usage`: optional `TokenUsage(prompt_tokens, completion_tokens, total_tokens, estimated)`. It feeds SyGra's metadata and cost tracking. Set `estimated=True` when your backend doesn't report counts and you computed them yourself.
- `served_model`: optional. The model that actually answered. Set it when your backend can route or fall back to a different model than the one requested.

**Exceptions:** an exception raised by `generate` is caught. It becomes an error response that uses the exception's `status_code` attribute when present, and `999` otherwise.

**Server-down detection:** codes 404, 500, 501, 502 and 503 count toward SyGra's [server-down check](../getting_started/model_configuration.md#server-down-handling), like they do for built-in models. Set `server_down_action: ignore` if your provider handles outages itself.

## Testing with `FakeProvider`

`FakeProvider` returns a fixed string, or the result of a callable, and records every request it receives:

```python
from sygra import FakeProvider, TokenUsage

fake = FakeProvider("ok", usage=TokenUsage(prompt_tokens=10, completion_tokens=2, total_tokens=12))
...
assert fake.requests[0].messages[-1]["content"] == "expected prompt"
```

## Limitations

- Agent nodes (`node_type: agent`) use the LangGraph chat-model backend and do not support `model_type: external` yet.
- Native structured output isn't delegated to the provider. Structured output for external models uses SyGra's instruction-based fallback: it adds format instructions to the prompt and validates the reply.
