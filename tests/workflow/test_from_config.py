"""Tests for Workflow.from_config: workflows built from a config dict or YAML file."""

import copy
import json
import sys
from pathlib import Path

import pytest
import yaml

sys.path.append(str(Path(__file__).parent.parent.parent))

from sygra import ConfigLoader, LLMRequest, ModelResponse, Workflow
from sygra.core.run_context import RunContext, run_context
from sygra.exceptions import ConfigurationError
from sygra.utils import utils


class _RecordingProvider:
    """Echoes the user message and remembers every request's messages."""

    def __init__(self):
        self.messages: list[list[dict]] = []

    async def generate(self, request: LLMRequest) -> ModelResponse:
        self.messages.append(request.messages)
        return ModelResponse(
            llm_response=request.messages[-1]["content"].upper(), response_code=200
        )


def _config(file_path: str, system_prompt, **source_extra) -> dict:
    return {
        "data_config": {
            "source": {
                "type": "disk",
                "file_path": file_path,
                "file_format": "json",
                **source_extra,
            }
        },
        "graph_config": {
            "nodes": {
                "gen": {
                    "node_type": "llm",
                    "model": {"name": "gen", "model_type": "external"},
                    "prompt": [{"system": system_prompt}, {"user": "{text}"}],
                    "output_keys": "answer",
                }
            },
            "edges": [{"from": "START", "to": "gen"}, {"from": "gen", "to": "END"}],
        },
        "output_config": {"output_map": {"id": {"from": "id"}, "answer": {"from": "answer"}}},
    }


def _write_rows(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(rows))


def test_dict_config_runs_without_a_task_directory(tmp_path, monkeypatch):
    data = tmp_path / "data" / "input.json"
    _write_rows(data, [{"id": "1", "text": "hi"}, {"id": "2", "text": "yo"}])
    cwd = tmp_path / "cwd"
    cwd.mkdir()
    monkeypatch.chdir(cwd)
    provider = _RecordingProvider()

    result = (
        Workflow.from_config(_config(str(data), "Be brief."))
        .llm_provider(provider)
        .run(num_records=2)
    )

    assert sorted(r["answer"] for r in result) == ["HI", "YO"]
    assert all(m[0] == {"role": "system", "content": "Be brief."} for m in provider.messages)
    assert list(cwd.iterdir()) == []


def test_prompt_files_and_data_paths_resolve_against_base_dir(tmp_path, monkeypatch):
    base = tmp_path / "flow"
    (base / "prompts").mkdir(parents=True)
    (base / "prompts" / "system.txt").write_text("System from file.")
    _write_rows(base / "data" / "input.json", [{"id": "1", "text": "abc"}])
    monkeypatch.chdir(tmp_path)
    provider = _RecordingProvider()
    config = _config("data/input.json", {"file": "prompts/system.txt"})

    result = (
        Workflow.from_config(config, base_dir=base)
        .llm_provider(provider)
        .run(num_records=1, output_dir=str(tmp_path / "out"))
    )

    assert [r["answer"] for r in result] == ["ABC"]
    assert provider.messages[0][0] == {"role": "system", "content": "System from file."}


def test_yaml_prompt_files_resolve_against_yaml_directory(tmp_path):
    flow = tmp_path / "my_flow"
    flow.mkdir()
    (flow / "system.txt").write_text("From YAML dir.")
    data = tmp_path / "input.json"
    _write_rows(data, [{"id": "1", "text": "x"}])
    (flow / "graph_config.yaml").write_text(
        yaml.safe_dump(_config(str(data), {"file": "system.txt"}))
    )

    workflow = Workflow.from_config(flow / "graph_config.yaml")

    assert workflow.name == "my_flow"
    prompt = workflow._config.to_dict()["graph_config"]["nodes"]["gen"]["prompt"]
    assert prompt[0] == {"system": "From YAML dir."}
    # Without base_dir, data paths are left as written.
    assert workflow._config.to_dict()["data_config"]["source"]["file_path"] == str(data)


def test_relative_prompt_file_needs_base_dir():
    with pytest.raises(ConfigurationError, match="pass base_dir"):
        Workflow.from_config(_config("/abs/input.json", {"file": "system.txt"}))


def test_missing_prompt_file_is_reported(tmp_path):
    with pytest.raises(ConfigurationError, match="not found"):
        Workflow.from_config(_config("/abs/input.json", {"file": "nope.txt"}), base_dir=tmp_path)


def test_absolute_paths_are_kept(tmp_path):
    prompt = tmp_path / "system.txt"
    prompt.write_text("Absolute.")
    config = _config("/data/input.json", {"file": str(prompt)})

    workflow = Workflow.from_config(config, base_dir=tmp_path / "elsewhere")

    resolved = workflow._config.to_dict()
    assert resolved["graph_config"]["nodes"]["gen"]["prompt"][0] == {"system": "Absolute."}
    assert resolved["data_config"]["source"]["file_path"] == "/data/input.json"


def test_config_dict_is_not_modified(tmp_path):
    (tmp_path / "system.txt").write_text("text")
    config = _config("input.json", {"file": "system.txt"})
    original = copy.deepcopy(config)

    Workflow.from_config(config, base_dir=tmp_path)

    assert config == original


def test_name_defaults(tmp_path):
    config = _config("/abs/input.json", "s")
    assert Workflow.from_config(config, name="explicit").name == "explicit"
    assert Workflow.from_config({**config, "task_name": "from_task"}).name == "from_task"
    assert Workflow.from_config(config).name.startswith("workflow_")


def test_source_transformations_are_kept(tmp_path):
    data = tmp_path / "input.json"
    _write_rows(data, [{"id": "1", "body": "hey"}])
    transformations = [
        {
            "transform": "sygra.processors.data_transform.RenameFieldsTransform",
            "params": {"mapping": {"body": "text"}, "overwrite": False},
        }
    ]
    config = _config(str(data), "s", transformations=transformations)

    result = (
        Workflow.from_config(config)
        .llm_provider(_RecordingProvider())
        .run(num_records=1, output_dir=str(tmp_path / "out"))
    )

    assert [r["answer"] for r in result] == ["HEY"]


def test_graph_properties_come_from_the_run_context(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    props = {"chat_conversation": "multiturn", "chat_history_window_size": 3}

    with run_context(RunContext(task_name="cfg_task", graph_properties=props)):
        assert utils.get_graph_properties() == props
        assert utils.get_graph_property("chat_history_window_size", 5) == 3
        # Another task name still reads that task's YAML.
        assert utils.get_graph_properties("other_task") == {}

    # Outside a run (CLI), properties come from the task's graph_config.yaml.
    task_dir = tmp_path / "yaml_task"
    task_dir.mkdir()
    (task_dir / "graph_config.yaml").write_text(
        yaml.safe_dump({"graph_config": {"graph_properties": {"chat_history_window_size": 7}}})
    )
    assert utils.get_graph_properties("yaml_task") == {"chat_history_window_size": 7}


def test_config_loader_load_and_create_uses_from_config(tmp_path):
    (tmp_path / "system.txt").write_text("loaded")
    flow = tmp_path / "graph_config.yaml"
    flow.write_text(yaml.safe_dump(_config("/abs/input.json", {"file": "system.txt"})))

    workflow = ConfigLoader().load_and_create(flow)

    assert isinstance(workflow, Workflow) and workflow._from_config
    assert workflow.name == tmp_path.name
    prompt = workflow._config.to_dict()["graph_config"]["nodes"]["gen"]["prompt"]
    assert prompt[0] == {"system": "loaded"}
