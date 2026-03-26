import sys
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

sys.path.append(str(Path(__file__).parent.parent.parent.parent))


def _make_processor(**kwargs):
    """Helper to create a DatasetProcessor with all heavy deps mocked."""
    defaults = dict(
        input_dataset=[{"id": "1"}],
        graph=MagicMock(),
        graph_config=MagicMock(),
        output_file="/tmp/tasks/my_task/output.jsonl",
        num_records_total=10,
        batch_size=10,
        checkpoint_interval=10,
    )
    defaults.update(kwargs)

    graph_config = defaults["graph_config"]
    graph_config.config = {"task_name": "test_task"}
    graph_config.oasst_mapper = None

    with patch("sygra.core.dataset.dataset_processor.tqdm") as mock_tqdm, \
         patch("sygra.core.dataset.dataset_processor.ResumableExecutionManager"):
        mock_tqdm.tqdm.return_value = MagicMock()
        from sygra.core.dataset.dataset_processor import DatasetProcessor
        processor = DatasetProcessor(**defaults)
    return processor


class TestDatasetProcessorInit(unittest.TestCase):
    def test_raises_when_checkpoint_not_multiple_of_batch(self):
        with patch("sygra.core.dataset.dataset_processor.tqdm"), \
             patch("sygra.core.dataset.dataset_processor.ResumableExecutionManager"):
            from sygra.core.dataset.dataset_processor import DatasetProcessor
            with self.assertRaises(AssertionError):
                DatasetProcessor(
                    input_dataset=[{"id": "1"}],
                    graph=MagicMock(),
                    graph_config=MagicMock(),
                    output_file="/tmp/output.jsonl",
                    num_records_total=10,
                    batch_size=30,
                    checkpoint_interval=100,
                )

    def test_valid_checkpoint_multiple_of_batch(self):
        proc = _make_processor(batch_size=10, checkpoint_interval=100)
        self.assertEqual(proc.batch_size, 10)
        self.assertEqual(proc.checkpoint_interval, 100)


class TestDetermineDatasetType(unittest.TestCase):
    def setUp(self):
        from sygra.core.dataset.dataset_processor import DatasetProcessor
        self.DatasetProcessor = DatasetProcessor

    def test_list_returns_in_memory(self):
        result = self.DatasetProcessor._determine_dataset_type([{"a": 1}])
        self.assertEqual(result, "in_memory")

    def test_streaming_attribute_true_returns_streaming(self):
        mock_ds = MagicMock()
        mock_ds.is_streaming = True
        result = self.DatasetProcessor._determine_dataset_type(mock_ds)
        self.assertEqual(result, "streaming")

    def test_iterable_dataset_returns_streaming(self):
        import datasets
        mock_ds = MagicMock(spec=datasets.IterableDataset)
        result = self.DatasetProcessor._determine_dataset_type(mock_ds)
        self.assertEqual(result, "streaming")

    def test_default_returns_in_memory(self):
        mock_ds = MagicMock(spec=object)
        del mock_ds.is_streaming
        result = self.DatasetProcessor._determine_dataset_type(mock_ds)
        self.assertEqual(result, "in_memory")


class TestExtractTaskName(unittest.TestCase):
    def test_extracts_from_tasks_path(self):
        proc = _make_processor(output_file="/data/tasks/my_task/output.jsonl")
        result = proc._extract_task_name()
        self.assertEqual(result, "my_task")

    def test_fallback_when_no_tasks_segment(self):
        proc = _make_processor(output_file="/data/output/result.jsonl")
        result = proc._extract_task_name()
        self.assertIn("task_", result)


class TestIsErrorCodeInOutput(unittest.TestCase):
    def setUp(self):
        from sygra.core.dataset.dataset_processor import DatasetProcessor
        self.DatasetProcessor = DatasetProcessor

    def test_returns_true_when_error_prefix_found(self):
        output = {"key": "###SERVER_ERROR### something bad happened"}
        self.assertTrue(self.DatasetProcessor.is_error_code_in_output(output))

    def test_returns_false_when_no_error_prefix(self):
        output = {"key": "all good", "count": 5}
        self.assertFalse(self.DatasetProcessor.is_error_code_in_output(output))

    def test_returns_false_for_non_string_values(self):
        output = {"count": 42, "data": [1, 2, 3]}
        self.assertFalse(self.DatasetProcessor.is_error_code_in_output(output))

    def test_returns_false_for_empty_output(self):
        self.assertFalse(self.DatasetProcessor.is_error_code_in_output({}))


class TestGetRecord(unittest.TestCase):
    def test_assigns_uuid_when_record_has_no_id(self):
        proc = _make_processor(input_dataset=[{"value": "hello"}])
        proc.resumable = False
        record = proc._get_record()
        self.assertIn("id", record)
        self.assertTrue(len(record["id"]) > 0)

    def test_keeps_existing_id(self):
        proc = _make_processor(input_dataset=[{"id": "existing-id", "value": "hello"}])
        proc.resumable = False
        record = proc._get_record()
        self.assertEqual(record["id"], "existing-id")

    def test_raises_stop_iteration_when_exhausted(self):
        proc = _make_processor(input_dataset=[])
        proc.resumable = False
        with self.assertRaises(StopIteration):
            proc._get_record()


if __name__ == "__main__":
    unittest.main()
