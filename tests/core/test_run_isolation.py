"""Tests for run- and request-scoped state: concurrent runs and requests don't interfere."""

import asyncio
import sys
import threading
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.messages import HumanMessage
from langchain_core.prompt_values import ChatPromptValue
from langchain_core.tools import tool

sys.path.append(str(Path(__file__).parent.parent.parent))

from sygra import LLMRequest, ModelResponse, TokenUsage, Workflow
from sygra.core.dataset.dataset_processor import DatasetProcessor
from sygra.core.models.call_state import current_model_call
from sygra.core.models.custom_models import ModelParams
from sygra.core.models.lite_llm.openai_model import CustomOpenAI as LiteLLMOpenAI
from sygra.core.run_context import RunContext, get_run_context, run_context
from sygra.metadata.metadata_collector import MetadataCollector, get_metadata_collector
from sygra.metadata.metadata_integration import track_model_request
from sygra.utils import utils

# ── Run context ───────────────────────────────────────────────────────────


def test_run_context_scopes_task_sampler_cache_and_collector():
    collector = MetadataCollector.create_isolated()
    assert collector is not MetadataCollector()

    assert get_run_context() is None
    assert utils.get_sampler_cache() is utils.sampler_cache
    with run_context(RunContext(task_name="scoped_task", metadata_collector=collector)) as ctx:
        assert utils.get_current_task() == "scoped_task"
        assert utils.get_sampler_cache() is ctx.sampler_cache
        assert get_metadata_collector() is collector
    assert get_run_context() is None
    assert get_metadata_collector() is MetadataCollector()


def test_signal_handlers_only_on_main_thread_and_when_allowed():
    assert DatasetProcessor._may_install_signal_handlers() is True
    with run_context(RunContext(install_signal_handlers=False)):
        assert DatasetProcessor._may_install_signal_handlers() is False

    seen = []
    thread = threading.Thread(
        target=lambda: seen.append(DatasetProcessor._may_install_signal_handlers())
    )
    thread.start()
    thread.join()
    assert seen == [False]


@pytest.mark.asyncio
async def test_concurrent_aruns_are_isolated(tmp_path):
    def make_provider(tag: str, delay: float):
        seen = {"tasks": set(), "collectors": set()}

        class _Provider:
            async def generate(self, request: LLMRequest) -> ModelResponse:
                seen["tasks"].add(utils.get_current_task())
                seen["collectors"].add(id(get_metadata_collector()))
                await asyncio.sleep(delay)
                return ModelResponse(
                    llm_response=f"{tag}:{request.messages[-1]['content']}", response_code=200
                )

        return _Provider(), seen

    provider_a, seen_a = make_provider("a", 0.01)
    provider_b, seen_b = make_provider("b", 0.002)

    def workflow(name, provider):
        return (
            Workflow(name)
            .source([{"id": str(i), "text": f"t{i}"} for i in range(4)])
            .llm({"name": "gen", "model_type": "external"}, "{text}", output="answer")
            .llm_provider(provider)
        )

    records_a, records_b = await asyncio.gather(
        workflow("iso_a", provider_a).arun(num_records=4, output_dir=str(tmp_path / "a")),
        workflow("iso_b", provider_b).arun(num_records=4, output_dir=str(tmp_path / "b")),
    )

    assert sorted(r["answer"] for r in records_a) == [f"a:t{i}" for i in range(4)]
    assert sorted(r["answer"] for r in records_b) == [f"b:t{i}" for i in range(4)]
    assert seen_a["tasks"] == {"iso_a"} and seen_b["tasks"] == {"iso_b"}
    assert len(seen_a["collectors"]) == 1 and len(seen_b["collectors"]) == 1
    assert seen_a["collectors"] != seen_b["collectors"]
    assert id(get_metadata_collector()) not in seen_a["collectors"] | seen_b["collectors"]


def test_metadata_is_available_after_run(tmp_path):
    usage = TokenUsage(prompt_tokens=3, completion_tokens=2, total_tokens=5)

    class _Provider:
        async def generate(self, request: LLMRequest) -> ModelResponse:
            return ModelResponse(llm_response="ok", response_code=200, usage=usage)

    global_collector = get_metadata_collector()
    was_enabled = global_collector.is_enabled()
    global_collector.set_enabled(True)
    try:
        (
            Workflow("metadata_after_run")
            .source([{"id": "1", "text": "x"}, {"id": "2", "text": "y"}])
            .llm({"name": "gen", "model_type": "external"}, "{text}", output="answer")
            .llm_provider(_Provider())
            .run(num_records=2, output_dir=str(tmp_path))
        )
    finally:
        global_collector.set_enabled(was_enabled)

    metrics = get_metadata_collector().model_metrics["gen"]
    assert metrics.num_requests == 2
    assert metrics.token_stats.total_tokens == 10


# ── Per-request state ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_concurrent_requests_keep_their_own_usage():
    class _Model:
        model_name = "shared"
        model_config = {"parameters": {}}
        _last_request_usage = None

        def name(self):
            return self.model_name

        @track_model_request
        async def generate(self, n: int, delay: float) -> ModelResponse:
            await asyncio.sleep(delay)
            usage = {"prompt_tokens": n, "completion_tokens": n, "total_tokens": 2 * n}
            current_model_call().usage = usage
            self._last_request_usage = usage
            await asyncio.sleep(delay)
            return ModelResponse(llm_response=str(n), response_code=200)

    model = _Model()
    responses = await asyncio.gather(
        *(model.generate(n, delay) for n, delay in [(1, 0.03), (2, 0.0), (3, 0.01), (4, 0.02)])
    )

    assert [r.usage.prompt_tokens for r in responses] == [1, 2, 3, 4]
    assert current_model_call() is None


@pytest.mark.asyncio
async def test_tools_do_not_leak_into_shared_generation_params():
    @tool
    def lookup(key: str) -> str:
        """Look up a key."""
        return key

    config = {
        "name": "oai",
        "model": "gpt-4o",
        "parameters": {"temperature": 0.1},
        "url": "https://example.invalid/v1",
        "auth_token": "sk-test",
    }
    completion = MagicMock()
    choice = MagicMock()
    choice.model_dump.return_value = {"message": {"content": "ok", "tool_calls": None}}
    completion.choices = [choice]
    completion.usage = SimpleNamespace(prompt_tokens=3, completion_tokens=2, total_tokens=5)

    with patch("sygra.core.models.lite_llm.base.acompletion", new_callable=AsyncMock) as acomp:
        acomp.return_value = completion
        model = LiteLLMOpenAI(config)
        params = ModelParams(url=config["url"], auth_token="sk-test")
        prompt = ChatPromptValue(messages=[HumanMessage(content="hi")])

        with_tools = await model._generate_response(prompt, params, tools=[lookup])
        without_tools = await model._generate_response(prompt, params)

    first, second = (call.kwargs for call in acomp.call_args_list)
    assert first["tools"][0]["function"]["name"] == "lookup"
    assert first["tool_choice"] == "auto"
    assert "tools" not in second and "tool_choice" not in second
    assert model.generation_params == {"temperature": 0.1}
    assert config["parameters"] == {"temperature": 0.1}
    expected = TokenUsage(prompt_tokens=3, completion_tokens=2, total_tokens=5)
    assert with_tools.usage == expected and without_tools.usage == expected
