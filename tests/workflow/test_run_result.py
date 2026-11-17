"""Tests for RunResult: records plus failures, usage per model/node/record, and cost."""

import json
import sys
from pathlib import Path

import pytest
import yaml

sys.path.append(str(Path(__file__).parent.parent.parent))

from sygra import FakeProvider, LLMRequest, ModelResponse, RunResult, TokenUsage, Workflow
from sygra.core.graph.functions.lambda_function import LambdaFunction
from sygra.core.run_result import UsageStats


def _usage(n: int, estimated: bool = False) -> TokenUsage:
    return TokenUsage(prompt_tokens=n, completion_tokens=1, total_tokens=n + 1, estimated=estimated)


class _Provider:
    """Usage depends on the record text; record 'bad' gets an error response."""

    async def generate(self, request: LLMRequest) -> ModelResponse:
        text = request.messages[-1]["content"]
        if text == "bad":
            return ModelResponse(llm_response="backend refused", response_code=400)
        return ModelResponse(
            llm_response=text.upper(),
            response_code=200,
            usage=_usage(len(text), estimated=True),
            served_model="acme-small",
        )


def _workflow(name: str, rows, provider) -> Workflow:
    return (
        Workflow(name)
        .source(rows)
        .llm(
            {"name": "gen", "model_type": "external", "model": "acme-large"},
            "{text}",
            output="answer",
        )
        .llm_provider(provider)
    )


def test_result_is_a_list_with_usage_and_cost(tmp_path):
    rows = [{"id": "r1", "text": "ab"}, {"id": "r2", "text": "abcd"}]
    prices: list[str] = []

    def cost_fn(model: str, stats: UsageStats) -> float:
        prices.append(model)
        return stats.prompt_tokens * 0.5

    result = _workflow("rr_usage", rows, _Provider()).run(
        num_records=2, output_dir=str(tmp_path), cost_fn=cost_fn
    )

    assert isinstance(result, RunResult) and isinstance(result, list)
    assert sorted(r["answer"] for r in result) == ["AB", "ABCD"]
    assert result.records == list(result)
    assert result.failed_records == []

    model = result.usage_by_model["acme-large"]
    assert (model.requests, model.prompt_tokens, model.total_tokens) == (2, 6, 8)
    assert model.estimated is True
    assert model.served_models == {"acme-small": 2}
    assert model.cost_usd == 3.0 and result.cost_usd == 3.0 and prices == ["acme-large"]

    assert result.usage_by_record["r1"].prompt_tokens == 2
    assert result.usage_by_record["r2"].prompt_tokens == 4
    (node_stats,) = result.usage_by_node.values()
    assert node_stats.total_tokens == 8
    assert result.total_usage.total_tokens == 8
    assert result.output_file is not None and Path(result.output_file).exists()


def test_failed_records_are_reported(tmp_path):
    # The failing record finishes last; earlier successes must still be written.
    rows = [{"id": "ok", "text": "fine"}, {"id": "nope", "text": "bad"}]

    result = _workflow("rr_failed", rows, _Provider()).run(num_records=2, output_dir=str(tmp_path))

    assert [r["id"] for r in result] == ["ok"]
    (failure,) = result.failed_records
    assert failure.id == "nope" and failure.kind == "model_error"
    assert "backend refused" in failure.error
    model = result.usage_by_model["acme-large"]
    assert (model.requests, model.failed_requests) == (2, 1)
    assert result.cost_usd is None


class _Explode(LambdaFunction):
    @staticmethod
    def apply(lambda_node_dict, state):
        if state["id"] == "boom":
            raise RuntimeError("lambda exploded")
        state["out"] = state["text"]
        return state


def test_exceptions_are_reported(tmp_path):
    rows = [{"id": "fine", "text": "x"}, {"id": "boom", "text": "y"}]
    workflow = Workflow("rr_exception").source(rows).lambda_func(_Explode, output="out")

    result = workflow.run(num_records=2, output_dir=str(tmp_path))

    failures = {f.id: f for f in result.failed_records}
    assert failures["boom"].kind == "exception"
    assert "lambda exploded" in failures["boom"].error
    assert "fine" not in failures


def test_yaml_task_returns_records_from_output_file(tmp_path):
    task_dir = tmp_path / "yaml_task"
    task_dir.mkdir()
    (task_dir / "input.json").write_text(json.dumps([{"id": "1", "text": "hi"}]))
    config = {
        "data_config": {
            "source": {
                "type": "disk",
                "file_path": str(task_dir / "input.json"),
                "file_format": "json",
            }
        },
        "graph_config": {
            "nodes": {
                "gen": {
                    "node_type": "llm",
                    "model": {"name": "gen", "model_type": "external"},
                    "prompt": [{"user": "{text}"}],
                    "output_keys": "answer",
                }
            },
            "edges": [{"from": "START", "to": "gen"}, {"from": "gen", "to": "END"}],
        },
        "output_config": {"output_map": {"id": {"from": "id"}, "answer": {"from": "answer"}}},
    }
    (task_dir / "graph_config.yaml").write_text(yaml.safe_dump(config))

    result = (
        Workflow(str(task_dir))
        .llm_provider(FakeProvider("yaml ok"))
        .run(num_records=1, output_dir=str(tmp_path / "out"))
    )

    assert [r["answer"] for r in result] == ["yaml ok"]
    assert result.output_file is not None
    assert result.usage_by_model["gen"].requests == 1


@pytest.mark.asyncio
async def test_arun_returns_run_result(tmp_path):
    result = await _workflow("rr_async", [{"id": "a", "text": "xyz"}], _Provider()).arun(
        num_records=1, output_dir=str(tmp_path)
    )
    assert isinstance(result, RunResult)
    assert result.usage_by_record["a"].prompt_tokens == 3
