"""Tests for model_type: external (pluggable LLMProvider)."""

import asyncio
import sys
import threading
from pathlib import Path
from unittest.mock import patch

import pytest
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.prompt_values import ChatPromptValue
from langchain_core.tools import tool

sys.path.append(str(Path(__file__).parent.parent.parent.parent))

import sygra.utils.constants as constants
from sygra.core.models.external import (
    FakeProvider,
    LLMRequest,
    get_llm_provider,
    register_llm_provider,
    unregister_llm_provider,
    use_llm_providers,
)
from sygra.core.models.external.external_model import ExternalModel
from sygra.core.models.model_factory import ModelFactory
from sygra.core.models.model_response import ModelResponse, TokenUsage


def _prompt(text: str = "hello") -> ChatPromptValue:
    return ChatPromptValue(messages=[SystemMessage(content="be terse"), HumanMessage(content=text)])


def _config(**overrides):
    cfg = {"name": "ext_model", "model_type": "external"}
    cfg.update(overrides)
    return cfg


@pytest.fixture(autouse=True)
def _no_global_providers():
    yield
    unregister_llm_provider("default")
    unregister_llm_provider("other")


# ── Registry ──────────────────────────────────────────────────────────────


def test_missing_provider_fails_at_model_creation():
    with pytest.raises(LookupError, match="No LLM provider registered under 'default'"):
        ModelFactory.create_model(_config())


def test_register_rejects_objects_without_generate():
    with pytest.raises(TypeError):
        register_llm_provider(object())  # type: ignore[arg-type]


def test_scoped_providers_shadow_global_and_reset():
    global_p, scoped_p = FakeProvider("g"), FakeProvider("s")
    register_llm_provider(global_p)
    with use_llm_providers({"default": scoped_p}):
        assert get_llm_provider() is scoped_p
    assert get_llm_provider() is global_p


def test_scoped_providers_are_isolated_per_thread():
    seen = {}

    def worker(name: str, provider: FakeProvider) -> None:
        with use_llm_providers({"default": provider}):
            seen[name] = get_llm_provider()

    p1, p2 = FakeProvider("1"), FakeProvider("2")
    t1 = threading.Thread(target=worker, args=("t1", p1))
    t2 = threading.Thread(target=worker, args=("t2", p2))
    t1.start(), t2.start(), t1.join(), t2.join()
    assert seen == {"t1": p1, "t2": p2}
    with pytest.raises(LookupError):
        get_llm_provider()


def test_scoped_providers_visible_inside_asyncio_run():
    """Workflow.run executes graphs via asyncio.run; the scope must carry over."""
    provider = FakeProvider("x")

    async def resolve():
        return get_llm_provider()

    with use_llm_providers({"default": provider}):
        assert asyncio.run(resolve()) is provider


# ── ExternalModel request/response mapping ────────────────────────────────


@pytest.mark.asyncio
async def test_request_carries_messages_params_and_options():
    provider = FakeProvider("ok")
    register_llm_provider(provider)
    model = ModelFactory.create_model(
        _config(
            model="acme-large",
            parameters={"temperature": 0.2, "max_tokens": 64},
            provider_options={"route": "eu", "tier": 2},
        )
    )
    assert isinstance(model, ExternalModel)

    response = await model(_prompt("hi there"))

    assert response.response_code == 200
    assert response.llm_response == "ok"
    (request,) = provider.requests
    assert isinstance(request, LLMRequest)
    assert request.name == "ext_model"
    assert request.model == "acme-large"
    assert [m["role"] for m in request.messages] == ["system", "user"]
    assert request.messages[-1]["content"] == "hi there"
    assert request.parameters == {"temperature": 0.2, "max_tokens": 64}
    assert request.provider_options == {"route": "eu", "tier": 2}
    assert request.tools == [] and request.tool_choice is None


@pytest.mark.asyncio
async def test_model_defaults_to_name_and_named_provider_is_used():
    default_p, other_p = FakeProvider("d"), FakeProvider("o")
    with use_llm_providers({"default": default_p, "other": other_p}):
        model = ModelFactory.create_model(_config(provider="other"))
        response = await model(_prompt())
    assert response.llm_response == "o"
    assert other_p.requests[0].model == "ext_model"
    assert default_p.requests == []


@pytest.mark.asyncio
async def test_usage_and_served_model_are_propagated():
    usage = TokenUsage(prompt_tokens=11, completion_tokens=5, total_tokens=16, estimated=True)
    provider = FakeProvider(
        lambda req: ModelResponse(
            llm_response="r", response_code=200, usage=usage, served_model="acme-small"
        )
    )
    register_llm_provider(provider)
    model = ModelFactory.create_model(_config(model="acme-large"))

    response = await model(_prompt())

    assert response.served_model == "acme-small"
    assert response.usage == usage
    assert model._last_request_usage == {
        "prompt_tokens": 11,
        "completion_tokens": 5,
        "total_tokens": 16,
    }


@pytest.mark.asyncio
async def test_tools_are_converted_to_openai_format():
    @tool
    def lookup(ticket_id: str) -> str:
        """Look up a ticket."""
        return ticket_id

    provider = FakeProvider("ok")
    register_llm_provider(provider)
    model = ModelFactory.create_model(_config())

    await model(_prompt(), tools=[lookup], tool_choice="auto")

    (request,) = provider.requests
    assert request.tool_choice == "auto"
    assert request.tools[0]["type"] == "function"
    assert request.tools[0]["function"]["name"] == "lookup"


# ── Failure handling ──────────────────────────────────────────────────────


class _Boom(Exception):
    status_code = 503


class _RaisingProvider:
    def __init__(self, exc: Exception):
        self.exc, self.calls = exc, 0

    async def generate(self, request: LLMRequest) -> ModelResponse:
        self.calls += 1
        raise self.exc


@pytest.mark.asyncio
async def test_provider_exception_becomes_error_response():
    provider = _RaisingProvider(_Boom("gateway down"))
    register_llm_provider(provider)
    model = ModelFactory.create_model(_config())

    response = await model(_prompt())

    assert response.response_code == 503
    assert constants.ERROR_PREFIX in (response.llm_response or "")
    assert "gateway down" in (response.llm_response or "")


@pytest.mark.asyncio
async def test_non_200_response_is_marked_as_error():
    provider = FakeProvider(lambda req: ModelResponse(llm_response="nope", response_code=400))
    register_llm_provider(provider)
    model = ModelFactory.create_model(_config())

    response = await model(_prompt())

    assert response.response_code == 400
    assert response.llm_response.startswith(constants.ERROR_PREFIX)


@pytest.mark.asyncio
async def test_no_sygra_retries_by_default():
    provider = FakeProvider(lambda req: ModelResponse(llm_response="slow down", response_code=429))
    register_llm_provider(provider)
    model = ModelFactory.create_model(_config())

    await model(_prompt())

    assert len(provider.requests) == 1


@pytest.mark.asyncio
async def test_retries_can_be_enabled_in_config():
    replies = iter(
        [
            ModelResponse(llm_response="slow down", response_code=429),
            ModelResponse(llm_response="ok", response_code=200),
        ]
    )
    provider = FakeProvider(lambda req: next(replies))
    register_llm_provider(provider)
    model = ModelFactory.create_model(_config(retry_attempts=2))

    with patch(
        "sygra.core.models.custom_models.wait_random_exponential", return_value=lambda rs: 0
    ):
        response = await model(_prompt())

    assert response.llm_response == "ok"
    assert len(provider.requests) == 2


@pytest.mark.asyncio
async def test_wrong_return_type_becomes_error_response():
    class _BadProvider:
        async def generate(self, request):
            return "not a ModelResponse"

    register_llm_provider(_BadProvider())
    model = ModelFactory.create_model(_config())

    response = await model(_prompt())

    assert response.response_code == 999
    assert constants.ERROR_PREFIX in (response.llm_response or "")


# ── ModelFactory.register_model_type ──────────────────────────────────────


def test_register_model_type_adds_and_guards_existing():
    class MyModel:
        def __init__(self, model_config):
            self.model_config = model_config

    try:
        ModelFactory.register_model_type("my_custom_type", MyModel)
        created = ModelFactory.create_model({"name": "m", "model_type": "my_custom_type"})
        assert isinstance(created, MyModel)
        with pytest.raises(ValueError, match="already registered"):
            ModelFactory.register_model_type("my_custom_type", MyModel)
        ModelFactory.register_model_type("my_custom_type", MyModel, override=True)
    finally:
        ModelFactory.MODEL_TYPE_MAP[constants.MODEL_BACKEND_CUSTOM].pop("my_custom_type", None)


# ── Workflow integration ──────────────────────────────────────────────────


def test_workflow_runs_end_to_end_with_scoped_provider(tmp_path):
    from sygra import Workflow

    provider = FakeProvider(lambda req: req.messages[-1]["content"].upper())
    workflow = (
        Workflow("external_provider_e2e")
        .source([{"id": "1", "text": "hello"}, {"id": "2", "text": "world"}])
        .llm({"name": "gen", "model_type": "external"}, "{text}", output="answer")
        .llm_provider(provider)
    )

    records = workflow.run(num_records=2, output_dir=str(tmp_path))

    assert sorted(r["answer"] for r in records) == ["HELLO", "WORLD"]
    assert len(provider.requests) == 2
    # the provider was scoped to the run only
    with pytest.raises(LookupError):
        get_llm_provider()
