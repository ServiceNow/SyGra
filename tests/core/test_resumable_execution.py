import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

import json
import tempfile
from unittest.mock import mock_open, patch

import pytest

from grasp.core.resumable_execution import (
    ResumableExecutionManager,
    StreamingPositionTracker,
)


@pytest.fixture
def temp_manager():
    temp_dir = tempfile.TemporaryDirectory()
    output_file = os.path.join(temp_dir.name, "output.json")
    with open(output_file, "w") as f:
        json.dump([], f)
    manager = ResumableExecutionManager("test_task", output_file)
    manager.position_tracker = manager.in_memory_tracker
    yield manager
    temp_dir.cleanup()


def test_get_record_id_hash(temp_manager):
    record = {"name": "Alice", "value": 42}
    hashed = temp_manager.get_record_id(record)
    assert isinstance(hashed, str)
    assert len(hashed) == 64


def test_get_record_id_direct(temp_manager):
    record = {"id": "abc123", "value": 99}
    assert temp_manager.get_record_id(record) == "abc123"


def test_mark_and_check_record_processed(temp_manager):
    record = {"id": "test1"}
    assert not temp_manager.is_record_processed(record)
    temp_manager.mark_record_processed(record, position=5)
    assert temp_manager.is_record_processed(record)


def test_mark_record_processing_and_position(temp_manager):
    record = {"id": "rec2"}
    temp_manager.mark_record_processing(record, position=10)
    assert "rec2" in temp_manager.in_process_records
    assert temp_manager.position_tracker.get_current_position() == 10


def test_save_and_load_state(temp_manager):
    record = {"id": "r-load"}
    temp_manager.mark_record_processed(record, position=2)
    temp_manager.force_save_state()
    # mimicking restarting the job
    new_manager = ResumableExecutionManager("test_task", temp_manager.output_file)
    assert new_manager.load_state()
    assert "r-load" in new_manager.processed_records


def test_no_metadata_file(temp_manager):
    temp_manager.metadata_file = os.path.join(
        os.path.dirname(temp_manager.metadata_file), "missing.json"
    )
    assert not temp_manager.load_state()


def test_corrupted_metadata_file(temp_manager):
    with open(temp_manager.metadata_file, "w") as f:
        f.write("{bad_json")
    assert not temp_manager.load_state()


def test_missing_output_file_reference(temp_manager):
    os.remove(temp_manager.output_file)
    with open(temp_manager.metadata_file, "w") as f:
        json.dump(
            {
                "task_name": "test_task",
                "output_file": temp_manager.output_file,
                "processed_records": [],
                "last_position": 0,
                "dataset_type": "in_memory",
            },
            f,
        )
    assert not temp_manager.load_state()


def test_streaming_tracker_duplicate_detection():
    tracker = StreamingPositionTracker(window_size=2)
    assert not tracker.record_seen("rec1")
    assert tracker.record_seen("rec1")
    assert not tracker.record_seen("rec2")
    assert not tracker.record_seen("rec3")
    assert not tracker.record_seen("rec1")  # evicted


def test_inmemory_advance(temp_manager):
    dataset = list(range(10))
    advanced = temp_manager.in_memory_tracker.advance_to_position(dataset, 5)
    assert advanced == list(range(5, 10))


def test_mark_as_complete_updates_metadata(temp_manager):
    temp_manager.mark_record_processed({"id": "x"}, position=0)
    temp_manager.force_save_state(is_final=True)
    with open(temp_manager.metadata_file) as f:
        meta = json.load(f)
    assert meta["completed"] is True


@patch("os.path.exists", return_value=False)
def test_no_save_if_output_missing(_, temp_manager):
    temp_manager.processed_records.add("x")
    temp_manager.position_tracker.mark_position(0)
    with patch("builtins.open", mock_open()) as m:
        temp_manager._do_save_state()
        m.assert_not_called()


def test_get_metadata_after_save(temp_manager):
    temp_manager.mark_record_processed({"id": "testmeta"}, position=3)
    temp_manager.force_save_state()
    meta = temp_manager.get_metadata()
    assert "testmeta" in meta.get("processed_records", [])


def test_metadata_write_is_atomic(tmp_path):
    output_file = tmp_path / "output.json"
    output_file.write_text("[]")  # simulate a valid output file

    manager = ResumableExecutionManager("test_task", str(output_file))
    manager.position_tracker = manager.in_memory_tracker

    manager.mark_record_processed({"id": "finaltest"}, position=4)
    manager.force_save_state()

    metadata_file = tmp_path / "metadata.json"
    assert metadata_file.exists()

    with open(metadata_file) as f:
        metadata = json.load(f)

    assert metadata["completed"] is False
    assert "finaltest" in metadata["processed_records"]
