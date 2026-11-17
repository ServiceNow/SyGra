"""Tests for passing hooks (processors, lambdas, conditions, transforms...) as Python objects."""

import json
import sys
import threading
from pathlib import Path

import pytest

sys.path.append(str(Path(__file__).parent.parent.parent))

import sygra
from sygra import LLMRequest, ModelResponse, Workflow
from sygra.hooks import (
    HOOKS_API_VERSION,
    BaseOutputGenerator,
    DataTransform,
    EdgeCondition,
    GraphPostProcessor,
    LambdaFunction,
    NodePostProcessorWithState,
    NodePreProcessor,
)
from sygra.utils import constants, utils


class _Echo:
    """Replies with the last user message, upper-cased."""

    async def generate(self, request: LLMRequest) -> ModelResponse:
        return ModelResponse(
            llm_response=request.messages[-1]["content"].upper(), response_code=200
        )


def module_level_lambda(lambda_node_dict, state):
    state["out"] = state["text"] + "!"
    return state


class _Upper(NodePreProcessor):
    def apply(self, state):
        state["text"] = state["text"].upper()
        return state


class _Tag(NodePostProcessorWithState):
    """Configured instance: the label is constructor state, and a lock isn't deep-copyable."""

    def __init__(self, label: str):
        self.label = label
        self.lock = threading.Lock()
        self.calls = 0

    def apply(self, resp, state):
        with self.lock:
            self.calls += 1
        state["answer"] = f"{self.label}:{resp.message.content}"
        return state


def _llm_model() -> dict:
    return {"name": "gen", "model_type": "external"}


def test_configured_post_processor_instance_keeps_its_state(tmp_path):
    tag = _Tag("v1")
    rows = [{"id": "1", "text": "a"}, {"id": "2", "text": "b"}]

    result = (
        Workflow("hooks_instance")
        .source(rows)
        .llm(_llm_model(), "{text}", output="answer", post_process=tag)
        .llm_provider(_Echo())
        .run(num_records=2, output_dir=str(tmp_path))
    )

    assert sorted(r["answer"] for r in result) == ["v1:A", "v1:B"]
    assert tag.calls == 2  # the same instance was used, not a copy


def test_local_functions_and_classes(tmp_path):
    suffix = "?"

    def add_suffix(state):  # closure: not importable by dotted path
        state["text"] = state["text"] + suffix
        return state

    class Shout(NodePreProcessor):
        def apply(self, state):
            state["text"] = state["text"] + "!"
            return state

    class Double(LambdaFunction):
        @staticmethod
        def apply(lambda_node_dict, state):
            state["out"] = state["answer"] * 2
            return state

    result = (
        Workflow("hooks_local")
        .source([{"id": "1", "text": "x"}])
        .llm(_llm_model(), "{text}", output="answer", pre_process=add_suffix)
        .llm(_llm_model(), "{text}", output="answer2", pre_process=Shout)
        .lambda_func(Double, output="out")
        .llm_provider(_Echo())
        .run(num_records=1, output_dir=str(tmp_path))
    )

    # A pre-processor changes the state its own node renders the prompt from.
    (record,) = result
    assert record["answer"] == "X?"
    assert record["answer2"] == "X!"
    assert record["out"] == "X?X?"


def test_dict_config_with_hook_objects(tmp_path):
    data = tmp_path / "input.json"
    data.write_text(json.dumps([{"id": "1", "body": "hi"}, {"id": "2", "body": "skip"}]))

    class Rename(DataTransform):
        def __init__(self, src: str):
            self.src = src

        @property
        def name(self) -> str:
            return "rename"

        def transform(self, data, params):
            return [{**r, params["to"]: r[self.src]} for r in data]

    class Route(EdgeCondition):
        def __init__(self, skip_word: str):
            self.skip_word = skip_word

        def apply(self, state):  # instance method: uses constructor state
            return constants.SYGRA_END if state["text"] == self.skip_word else "gen"

    class Prefix(BaseOutputGenerator):
        def generate(self, state):
            record = super().generate(state)
            record["source"] = "hooks"
            return record

    config = {
        "data_config": {
            "source": {
                "type": "disk",
                "file_path": str(data),
                "transformations": [{"transform": Rename("body"), "params": {"to": "text"}}],
            }
        },
        "graph_config": {
            "nodes": {
                "start": {"node_type": "lambda", "lambda": lambda cfg, state: state},
                "gen": {
                    "node_type": "llm",
                    "model": _llm_model(),
                    "prompt": [{"user": "{text}"}],
                    "output_keys": "answer",
                },
            },
            "edges": [
                {"from": "START", "to": "start"},
                {
                    "from": "start",
                    "condition": Route("skip"),
                    "path_map": {"END": "END", "gen": "gen"},
                },
                {"from": "gen", "to": "END"},
            ],
        },
        "output_config": {
            "generator": Prefix(
                {"output_map": {"id": {"from": "id"}, "answer": {"from": "answer"}}}
            ),
        },
    }

    result = (
        Workflow.from_config(config)
        .llm_provider(_Echo())
        .run(num_records=2, output_dir=str(tmp_path / "out"))
    )

    by_id = {r["id"]: r for r in result}
    assert by_id["1"] == {"id": "1", "answer": "HI", "source": "hooks"}
    assert by_id["2"]["answer"] is None and by_id["2"]["source"] == "hooks"


def test_graph_post_processor_instance(tmp_path):
    class CountWords(GraphPostProcessor):
        def __init__(self, field: str):
            self.field = field

        def process(self, data, metadata):
            return [{"id": r["id"], "words": len(r[self.field].split())} for r in data]

    workflow = Workflow("hooks_graph_post").source([{"id": "1", "text": "a b c"}])
    workflow.lambda_func(module_level_lambda, output="out")
    workflow.override("graph_post_process", [CountWords("text")])

    workflow.run(num_records=1, output_dir=str(tmp_path))

    (written,) = tmp_path.glob("CountWords*.json")
    assert json.loads(written.read_text()) == [{"id": "1", "words": 3}]


def test_hook_reference():
    assert utils.hook_reference("a.b.C") == "a.b.C"
    # Importable module-level hooks stay dotted paths, so save_config() still works.
    assert utils.hook_reference(module_level_lambda) == f"{__name__}.module_level_lambda"
    assert utils.hook_reference(_Tag) == f"{__name__}._Tag"

    def local(state):
        return state

    tag = _Tag("x")
    assert utils.hook_reference(local) is local
    assert utils.hook_reference(tag) is tag


def test_dotted_paths_keep_yaml_behavior():
    # Paths resolve to callables, which are never treated as hook instances.
    hook = utils.resolve_hook(f"{__name__}._Upper")
    assert hook is _Upper
    assert isinstance(utils.hook_processor(hook), _Upper)  # new instance per call
    assert utils.hook_apply(_Upper) == _Upper.apply
    tag = _Tag("x")
    assert utils.hook_processor(tag) is tag
    assert utils.hook_processor(module_level_lambda) is None
    assert utils.hook_apply(module_level_lambda) is module_level_lambda


def test_public_hooks_api():
    assert HOOKS_API_VERSION == 1
    for name in (
        "NodePreProcessor",
        "NodePostProcessorWithState",
        "EdgeCondition",
        "DataTransform",
    ):
        assert getattr(sygra, name) is getattr(sygra.hooks, name)


@pytest.mark.parametrize("bad", [42, object()])
def test_invalid_graph_post_process_entry_is_rejected(bad, tmp_path):
    workflow = Workflow("hooks_bad").source([{"id": "1", "text": "a"}])
    workflow.lambda_func(module_level_lambda, output="out")
    workflow.override("graph_post_process", [bad])

    with pytest.raises(Exception, match="graph_post_process"):
        workflow.run(num_records=1, output_dir=str(tmp_path))
