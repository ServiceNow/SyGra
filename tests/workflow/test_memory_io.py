"""Tests for in-memory sources, stable record ids and runs without output files."""

import hashlib
import json
import sys
from pathlib import Path

import pytest

sys.path.append(str(Path(__file__).parent.parent.parent))

from sygra import Workflow, record_id
from sygra.core.base_task_executor import DefaultTaskExecutor
from sygra.core.dataset.dataset_config import DataSourceConfig, DataSourceType
from sygra.core.dataset.memory_handler import MemoryHandler
from sygra.data import DataSource
from sygra.exceptions import ConfigurationError


def shout(lambda_node_dict, state):
    state["out"] = state["text"].upper()
    return state


def _workflow(rows, name="mem"):
    return Workflow(name).source(rows).lambda_func(shout, output="out")


def test_list_source_stays_in_memory_and_input_is_not_modified(tmp_path):
    rows = [{"id": "a", "text": "x"}, {"id": "b", "text": "y", "meta": {"k": [1]}}]
    snapshot = json.loads(json.dumps(rows))
    workflow = _workflow(rows)

    source = workflow._config.to_dict()["data_config"]["source"]
    assert source["type"] == "memory"
    assert "file_path" not in source

    result = workflow.run(num_records=2, output_dir=str(tmp_path))

    assert sorted(r["out"] for r in result) == ["X", "Y"]
    assert rows == snapshot  # no ids or outputs written into the caller's dicts


def test_data_source_memory_has_no_temp_file():
    config = DataSource.memory([{"text": "x"}]).to_config()
    assert config == {"type": "memory", "records": [{"text": "x"}]}


def test_memory_handler_rejects_non_dict_records():
    handler = MemoryHandler(DataSourceConfig(type=DataSourceType.MEMORY, records=[{"a": 1}, 2]))
    with pytest.raises(ValueError, match="record 1 is int"):
        handler.read()


def test_every_record_gets_an_id_and_output_keeps_it(tmp_path):
    # Only the first row has an id; later rows get the content hash.
    rows = [{"id": "first", "text": "a"}, {"text": "b"}, {"text": "c"}]
    workflow = _workflow(rows, "mem_ids")
    # The output map doesn't include id; library runs add it back.
    workflow.override("output_config.output_map", {"out": {"from": "out"}})

    result = workflow.run(num_records=3, output_dir=str(tmp_path))

    by_id = {r["id"]: r["out"] for r in result}
    assert by_id == {
        "first": "A",
        record_id({"text": "b"}): "B",
        record_id({"text": "c"}): "C",
    }


def test_write_output_false_keeps_records_in_memory(tmp_path):
    rows = [{"id": "1", "text": "a"}, {"id": "2", "text": "b"}]

    result = _workflow(rows, "mem_nofile").run(
        num_records=2, output_dir=str(tmp_path), write_output=False
    )

    assert sorted((r["id"], r["out"]) for r in result) == [("1", "A"), ("2", "B")]
    assert result.output_file is None
    assert not list(tmp_path.glob("*output*"))


@pytest.mark.asyncio
async def test_arun_write_output_false(tmp_path):
    result = await _workflow([{"id": "1", "text": "a"}], "mem_nofile_async").arun(
        num_records=1, output_dir=str(tmp_path), write_output=False
    )
    assert [r["out"] for r in result] == ["A"]
    assert not list(tmp_path.glob("*output*"))


@pytest.mark.parametrize(
    "setup, kwargs, message",
    [
        (lambda w: w.override("graph_post_process", ["x.y.Z"]), {}, "graph_post_process"),
        (lambda w: w.sink(str(Path("/tmp/out.json"))), {}, "sink"),
        (lambda w: w, {"quality": True}, "data quality"),
        (lambda w: w, {"resume": True}, "resumable"),
    ],
)
def test_write_output_false_rejects_features_that_read_the_file(setup, kwargs, message, tmp_path):
    workflow = setup(_workflow([{"id": "1", "text": "a"}], "mem_reject"))
    with pytest.raises(ConfigurationError, match=message):
        workflow.run(num_records=1, output_dir=str(tmp_path), write_output=False, **kwargs)


def test_memory_source_cannot_be_resumed(tmp_path):
    with pytest.raises(ConfigurationError, match="memory source can't be resumed"):
        _workflow([{"id": "1", "text": "a"}], "mem_resume").run(
            num_records=1, output_dir=str(tmp_path), resume=True
        )


def test_record_id_matches_the_cli_hash():
    row = {"text": "b", "n": 1}
    expected = hashlib.sha256(json.dumps(row, sort_keys=True).encode()).hexdigest()
    assert record_id(row) == expected
    assert record_id(row, strict=True) == expected


def test_record_id_strict_raises_on_non_json_values():
    row = {"when": Path("/x")}
    assert record_id(row) == record_id({"when": "/x"})
    with pytest.raises(TypeError):
        record_id(row, strict=True)


def test_cli_keeps_first_record_id_check():
    # Without a run context (the CLI), ids are only assigned when the first record lacks one.
    executor = object.__new__(DefaultTaskExecutor)
    executor.id_column = None
    data = [{"id": "a"}, {"text": "b"}]
    assert executor.assign_ids(data) == [{"id": "a"}, {"text": "b"}]
