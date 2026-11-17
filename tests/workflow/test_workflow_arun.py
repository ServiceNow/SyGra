"""Tests for async execution: Workflow.arun() and BaseTaskExecutor.aexecute()."""

import asyncio
import sys
import threading
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

sys.path.append(str(Path(__file__).parent.parent.parent))

from sygra import FakeProvider, LLMRequest, ModelResponse, Workflow
from sygra.core.base_task_executor import DefaultTaskExecutor
from sygra.core.models.external import get_llm_provider
from sygra.core.models.server_down import resolve_server_down_action


def _workflow(name: str, provider, n: int = 3) -> Workflow:
    return (
        Workflow(name)
        .source([{"id": str(i), "text": f"t{i}"} for i in range(n)])
        .llm({"name": "gen", "model_type": "external"}, "{text}", output="answer")
        .llm_provider(provider)
    )


@pytest.mark.asyncio
async def test_arun_inside_running_loop(tmp_path):
    provider = FakeProvider(lambda req: req.messages[-1]["content"].upper())

    records = await _workflow("arun_basic", provider).arun(num_records=3, output_dir=str(tmp_path))

    assert sorted(r["answer"] for r in records) == ["T0", "T1", "T2"]
    assert len(provider.requests) == 3
    with pytest.raises(LookupError):
        get_llm_provider()
    assert resolve_server_down_action() == "exit"


@pytest.mark.asyncio
async def test_provider_runs_on_the_callers_loop(tmp_path):
    caller_loop = asyncio.get_running_loop()
    seen_loops = []

    class _LoopBoundProvider:
        async def generate(self, request: LLMRequest) -> ModelResponse:
            seen_loops.append(asyncio.get_running_loop())
            await asyncio.sleep(0)
            return ModelResponse(llm_response="ok", response_code=200)

    await _workflow("arun_loop", _LoopBoundProvider()).arun(num_records=3, output_dir=str(tmp_path))

    assert len(seen_loops) == 3
    assert all(loop is caller_loop for loop in seen_loops)


@pytest.mark.asyncio
async def test_arun_does_not_block_the_loop(tmp_path):
    ticks = 0
    stop = asyncio.Event()

    async def ticker():
        nonlocal ticks
        while not stop.is_set():
            ticks += 1
            await asyncio.sleep(0.001)

    async def slow(request):
        await asyncio.sleep(0.02)
        return ModelResponse(llm_response="ok", response_code=200)

    class _SlowProvider:
        generate = staticmethod(slow)

    task = asyncio.create_task(ticker())
    await _workflow("arun_ticks", _SlowProvider()).arun(num_records=3, output_dir=str(tmp_path))
    stop.set()
    await task

    assert ticks > 5


def test_run_still_works_synchronously(tmp_path):
    records = _workflow("run_sync", FakeProvider("ok")).run(num_records=2, output_dir=str(tmp_path))
    assert [r["answer"] for r in records] == ["ok", "ok"]


@pytest.mark.asyncio
async def test_aexecute_runs_blocking_steps_off_the_loop():
    loop_thread = threading.get_ident()
    threads = {}
    processor = MagicMock()
    processor.aprocess_and_store_results = AsyncMock()

    executor = DefaultTaskExecutor.__new__(DefaultTaskExecutor)

    def prepare(callbacks=None):
        threads["prepare"] = threading.get_ident()
        return processor, "out.json", "json"

    def finalize(dataset_processor, out_file, out_file_type):
        threads["finalize"] = threading.get_ident()
        assert (dataset_processor, out_file, out_file_type) == (processor, "out.json", "json")

    executor._prepare_execution = prepare  # type: ignore[method-assign]
    executor._finalize_execution = finalize  # type: ignore[method-assign]

    await executor.aexecute()

    processor.aprocess_and_store_results.assert_awaited_once()
    processor.process_and_store_results.assert_not_called()
    assert threads["prepare"] != loop_thread
    assert threads["finalize"] != loop_thread
