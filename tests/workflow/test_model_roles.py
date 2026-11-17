"""Tests for model roles: nodes name a role, and each run maps roles to models."""

import sys
from pathlib import Path

import pytest

sys.path.append(str(Path(__file__).parent.parent.parent))

from sygra import LLMRequest, ModelResponse, Workflow
from sygra.core.models.model_factory import ModelFactory
from sygra.core.run_context import RunContext, run_context
from sygra.exceptions import ConfigurationError


class _WhoAmI:
    """Replies with the model that served the request and its temperature."""

    async def generate(self, request: LLMRequest) -> ModelResponse:
        temperature = request.parameters.get("temperature")
        return ModelResponse(llm_response=f"{request.model}@{temperature}", response_code=200)


def _ext(name, **params):
    config = {"name": name, "model_type": "external"}
    if params:
        config["parameters"] = params
    return config


def _workflow(name="roles"):
    return (
        Workflow(name)
        .source([{"id": "1", "q": "hi"}])
        .llm({"role": "generator"}, "{q}", output="answer")
        .llm({"role": "reviewer", "parameters": {"temperature": 0.1}}, "{answer}", output="review")
        .llm_provider(_WhoAmI())
    )


def test_same_graph_runs_against_different_model_mixes(tmp_path):
    workflow = _workflow().model_roles(
        {"generator": _ext("gen-a", temperature=0.9), "reviewer": _ext("rev-a")}
    )

    first = workflow.run(num_records=1, output_dir=str(tmp_path / "a"))
    second = workflow.run(
        num_records=1,
        output_dir=str(tmp_path / "b"),
        model_roles={"generator": _ext("gen-b", temperature=0.5)},
    )

    assert (first[0]["answer"], first[0]["review"]) == ("gen-a@0.9", "rev-a@0.1")
    # The per-run map overrides one role; the workflow default keeps the other.
    assert (second[0]["answer"], second[0]["review"]) == ("gen-b@0.5", "rev-a@0.1")
    assert set(second.usage_by_model) == {"gen-b", "rev-a"}


def test_node_parameters_override_role_parameters(tmp_path):
    result = _workflow("roles_params").run(
        num_records=1,
        output_dir=str(tmp_path),
        model_roles={"generator": _ext("g"), "reviewer": _ext("r", temperature=0.7)},
    )
    assert result[0]["review"] == "r@0.1"


def test_unknown_role_is_a_clear_error(tmp_path):
    with pytest.raises(ConfigurationError, match="No model for role 'reviewer'.*generator"):
        _workflow("roles_missing").run(
            num_records=1, output_dir=str(tmp_path), model_roles={"generator": _ext("g")}
        )


def test_from_config_model_roles_key(tmp_path):
    config = {
        "data_config": {"source": {"type": "memory", "records": [{"id": "1", "q": "x"}]}},
        "graph_config": {
            "nodes": {
                "gen": {
                    "node_type": "llm",
                    "model": {"role": "generator"},
                    "prompt": [{"user": "{q}"}],
                    "output_keys": "answer",
                }
            },
            "edges": [{"from": "START", "to": "gen"}, {"from": "gen", "to": "END"}],
        },
        "model_roles": {"generator": _ext("cfg-gen")},
    }

    result = Workflow.from_config(config).llm_provider(_WhoAmI()).run(output_dir=str(tmp_path))

    assert result[0]["answer"] == "cfg-gen@None"
    assert "model_roles" in config  # the caller's dict isn't modified


def test_resolve_model_role_rules():
    with run_context(RunContext(model_roles={"generator": "gpt-x"})):
        assert ModelFactory._resolve_model_role({"role": "generator"}) == {"name": "gpt-x"}
        with pytest.raises(ConfigurationError, match="both 'name' and 'role'"):
            ModelFactory._resolve_model_role({"role": "generator", "name": "other"})
    with run_context(RunContext(model_roles={"generator": {"model_type": "external"}})):
        with pytest.raises(ConfigurationError, match="must be a model name"):
            ModelFactory._resolve_model_role({"role": "generator"})


def test_no_run_context_leaves_model_config_unchanged():
    # The CLI has no run context: role configs are left as they are.
    config = {"role": "generator"}
    assert ModelFactory._resolve_model_role(config) is config
