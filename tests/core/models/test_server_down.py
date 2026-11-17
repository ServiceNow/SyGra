"""Tests for server-down handling: exit (CLI default), raise (library) or ignore."""

import asyncio
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from langchain_core.messages import HumanMessage
from langchain_core.prompt_values import ChatPromptValue

sys.path.append(str(Path(__file__).parent.parent.parent.parent))

import sygra.utils.constants as constants
from sygra.core.dataset.dataset_processor import DatasetProcessor
from sygra.core.models.external import FakeProvider, register_llm_provider, unregister_llm_provider
from sygra.core.models.model_factory import ModelFactory
from sygra.core.models.model_response import ModelResponse
from sygra.core.models.server_down import resolve_server_down_action, server_down_action
from sygra.exceptions import ModelError, ModelServerDownError

MAX_FAILURES = 3


def _prompt() -> ChatPromptValue:
    return ChatPromptValue(messages=[HumanMessage(content="hi")])


def _down_provider() -> FakeProvider:
    return FakeProvider(lambda req: ModelResponse(llm_response="unavailable", response_code=503))


def _model(**overrides):
    cfg = {"name": "ext_model", "model_type": "external"}
    cfg.update(overrides)
    return ModelFactory.create_model(cfg)


async def _hit(model, times: int = MAX_FAILURES) -> None:
    for _ in range(times):
        await model(_prompt())


@pytest.fixture(autouse=True)
def _setup(monkeypatch):
    monkeypatch.setattr(constants, "HANDLE_SERVER_DOWN", True)
    monkeypatch.setattr(constants, "MAX_FAILED_ERROR", MAX_FAILURES)
    monkeypatch.setattr(constants, "MODEL_FAILURE_WINDOW_IN_SEC", 30)
    register_llm_provider(_down_provider())
    yield
    unregister_llm_provider("default")


# ── Resolution ────────────────────────────────────────────────────────────


def test_resolution_order():
    assert resolve_server_down_action() == "exit"
    with server_down_action("raise"):
        assert resolve_server_down_action() == "raise"
        assert resolve_server_down_action("ignore") == "ignore"
        with server_down_action("ignore"):
            assert resolve_server_down_action() == "ignore"
        assert resolve_server_down_action() == "raise"
    assert resolve_server_down_action() == "exit"


def test_invalid_action_is_rejected():
    with pytest.raises(ValueError, match="Invalid server_down_action"):
        _model(server_down_action="explode")
    with pytest.raises(ValueError, match="Invalid server_down_action"):
        with server_down_action("explode"):  # type: ignore[arg-type]
            pass


# ── Model behaviour ───────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_default_exits_as_before():
    model = _model()
    with pytest.raises(SystemExit):
        await _hit(model)


@pytest.mark.asyncio
async def test_raise_scope_raises_model_server_down_error():
    model = _model()
    with server_down_action("raise"):
        with pytest.raises(ModelServerDownError) as exc_info:
            await _hit(model)
    err = exc_info.value
    assert isinstance(err, ModelError)
    assert err.model_name == "ext_model"
    assert err.failures == MAX_FAILURES
    assert err.window_seconds < 30


@pytest.mark.asyncio
async def test_below_threshold_does_not_raise():
    model = _model()
    with server_down_action("raise"):
        await _hit(model, MAX_FAILURES - 1)
    assert len(model.model_failed_response_timestamp) == MAX_FAILURES - 1


@pytest.mark.asyncio
async def test_model_config_overrides_scope():
    ignoring = _model(server_down_action="ignore")
    exiting = _model(server_down_action="exit")
    with server_down_action("raise"):
        await _hit(ignoring, MAX_FAILURES + 2)
        assert ignoring.model_failed_response_timestamp == []
        with pytest.raises(SystemExit):
            await _hit(exiting)


# ── Propagation ───────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_dataset_processor_aborts_and_cancels_in_flight_records(tmp_path):
    cancelled = asyncio.Event()

    class _Graph:
        async def ainvoke(self, record, debug=False, config=None):
            if record["id"] == "slow":
                try:
                    await asyncio.Event().wait()
                except asyncio.CancelledError:
                    cancelled.set()
                    raise
            await asyncio.sleep(0)
            raise ModelServerDownError("m", MAX_FAILURES, 0.1)

    graph_config = MagicMock()
    graph_config.config = {}
    records = [{"id": "slow"}, {"id": "a"}, {"id": "b"}]
    processor = DatasetProcessor(
        records,
        _Graph(),  # type: ignore[arg-type]
        graph_config,
        str(tmp_path / "output.json"),
        num_records_total=len(records),
        batch_size=10,
        checkpoint_interval=10,
    )

    with pytest.raises(ModelServerDownError):
        await processor._process_and_store_results()
    assert cancelled.is_set()


def test_workflow_run_raises_and_keeps_process_alive(tmp_path):
    from sygra import Workflow

    workflow = (
        Workflow("server_down_e2e")
        .source([{"id": str(i), "text": f"t{i}"} for i in range(MAX_FAILURES + 1)])
        .llm({"name": "gen", "model_type": "external"}, "{text}", output="answer")
    )

    with pytest.raises(ModelServerDownError):
        workflow.run(num_records=MAX_FAILURES + 1, output_dir=str(tmp_path))
    assert resolve_server_down_action() == "exit"
