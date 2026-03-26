import json
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np

sys.path.append(str(Path(__file__).parent.parent.parent.parent))

from sygra.core.dataset.file_handler import FileHandler


class TestFileHandlerRead(unittest.TestCase):
    def setUp(self):
        self.source_config = MagicMock()
        self.source_config.file_path = "/some/path/data.json"
        self.source_config.encoding = "utf-8"
        self.source_config.shard = None
        self.handler = FileHandler(source_config=self.source_config)

    def test_read_raises_when_no_path_and_no_source_config(self):
        handler = FileHandler(source_config=None)
        with self.assertRaises(ValueError):
            handler.read()

    def test_read_raises_when_source_config_has_no_file_path(self):
        self.source_config.file_path = None
        with self.assertRaises(ValueError):
            self.handler.read()

    def test_read_raises_for_unsupported_extension(self):
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
            f.write(b"hello")
            tmp_path = f.name
        with self.assertRaises(ValueError):
            self.handler.read(tmp_path)

    def test_read_jsonl(self):
        records = [{"a": 1}, {"b": 2}]
        with tempfile.NamedTemporaryFile(suffix=".jsonl", mode="w", delete=False) as f:
            for rec in records:
                f.write(json.dumps(rec) + "\n")
            tmp_path = f.name
        result = self.handler.read(tmp_path)
        self.assertEqual(result, records)

    def test_read_json(self):
        records = [{"x": 10}, {"y": 20}]
        with tempfile.NamedTemporaryFile(suffix=".json", mode="w", delete=False) as f:
            json.dump(records, f)
            tmp_path = f.name
        result = self.handler.read(tmp_path)
        self.assertEqual(result, records)

    def test_read_json_raises_for_non_list(self):
        with tempfile.NamedTemporaryFile(suffix=".json", mode="w", delete=False) as f:
            json.dump({"key": "value"}, f)
            tmp_path = f.name
        with self.assertRaises(ValueError):
            self.handler.read(tmp_path)

    @patch("sygra.core.dataset.file_handler.pd.read_parquet")
    def test_read_parquet(self, mock_read_parquet):
        mock_df = MagicMock()
        mock_df.to_dict.return_value = [{"col": 1}]
        mock_read_parquet.return_value = mock_df
        result = self.handler.read("/some/file.parquet")
        mock_read_parquet.assert_called_once()
        self.assertEqual(result, [{"col": 1}])

    @patch("sygra.core.dataset.file_handler.pd.read_csv")
    def test_read_csv(self, mock_read_csv):
        mock_df = MagicMock()
        mock_df.to_dict.return_value = [{"col": "val"}]
        mock_read_csv.return_value = mock_df
        result = self.handler.read("/some/file.csv")
        mock_read_csv.assert_called_once()
        self.assertEqual(result, [{"col": "val"}])

    def test_read_uses_source_config_path_when_no_arg(self):
        records = [{"z": 99}]
        with tempfile.NamedTemporaryFile(suffix=".json", mode="w", delete=False) as f:
            json.dump(records, f)
            tmp_path = f.name
        self.source_config.file_path = tmp_path
        result = self.handler.read()
        self.assertEqual(result, records)


class TestFileHandlerWrite(unittest.TestCase):
    def setUp(self):
        self.output_config = MagicMock()
        self.output_config.encoding = "utf-8"
        self.handler = FileHandler(source_config=None, output_config=self.output_config)

    def test_write_json(self):
        data = [{"key": "value"}]
        with tempfile.TemporaryDirectory() as tmpdir:
            path = str(Path(tmpdir) / "output.json")
            self.handler.write(data, path)
            with open(path, "r") as f:
                result = json.load(f)
            self.assertEqual(result, data)

    def test_write_jsonl(self):
        data = [{"a": 1}, {"b": 2}]
        with tempfile.TemporaryDirectory() as tmpdir:
            path = str(Path(tmpdir) / "output.jsonl")
            self.handler.write(data, path)
            with open(path, "r") as f:
                lines = [json.loads(l) for l in f]
            self.assertEqual(lines, data)

    @patch("sygra.core.dataset.file_handler.pd.DataFrame")
    def test_write_parquet(self, mock_df_cls):
        mock_df = MagicMock()
        mock_df_cls.return_value = mock_df
        data = [{"col": 1}]
        self.handler.write(data, "/some/file.parquet")
        mock_df.to_parquet.assert_called_once()

    def test_write_creates_parent_directories(self):
        data = [{"val": 1}]
        with tempfile.TemporaryDirectory() as tmpdir:
            path = str(Path(tmpdir) / "nested" / "deep" / "output.json")
            self.handler.write(data, path)
            self.assertTrue(Path(path).exists())

    def test_write_serializes_datetime(self):
        dt = datetime(2024, 1, 15, 12, 0, 0)
        data = [{"ts": dt}]
        with tempfile.TemporaryDirectory() as tmpdir:
            path = str(Path(tmpdir) / "output.json")
            self.handler.write(data, path)
            with open(path, "r") as f:
                result = json.load(f)
            self.assertEqual(result[0]["ts"], dt.isoformat())

    def test_write_serializes_numpy_array(self):
        arr = np.array([1, 2, 3])
        data = [{"arr": arr}]
        with tempfile.TemporaryDirectory() as tmpdir:
            path = str(Path(tmpdir) / "output.json")
            self.handler.write(data, path)
            with open(path, "r") as f:
                result = json.load(f)
            self.assertEqual(result[0]["arr"], [1, 2, 3])


class TestFileHandlerGetFiles(unittest.TestCase):
    def test_get_files_raises_when_no_source_config(self):
        handler = FileHandler(source_config=None)
        with self.assertRaises(ValueError):
            handler.get_files()

    def test_get_files_raises_when_no_file_path(self):
        source_config = MagicMock()
        source_config.file_path = None
        handler = FileHandler(source_config=source_config)
        with self.assertRaises(ValueError):
            handler.get_files()

    def test_get_files_returns_matching_files(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "data.json").write_text("[]")
            (Path(tmpdir) / "data.jsonl").write_text("")
            (Path(tmpdir) / "other.txt").write_text("skip")

            source_config = MagicMock()
            source_config.file_path = str(Path(tmpdir) / "dummy.json")
            source_config.shard = None
            handler = FileHandler(source_config=source_config)

            files = handler.get_files()
            exts = {Path(f).suffix for f in files}
            self.assertTrue(exts.issubset({".json", ".jsonl", ".parquet"}))
            self.assertNotIn(".txt", exts)

    def test_get_files_uses_shard_regex(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "train-001.jsonl").write_text("")
            (Path(tmpdir) / "test-001.jsonl").write_text("")

            source_config = MagicMock()
            source_config.file_path = str(Path(tmpdir) / "dummy.jsonl")
            shard = MagicMock()
            shard.regex = "train-"
            source_config.shard = shard
            handler = FileHandler(source_config=source_config)

            files = handler.get_files()
            self.assertTrue(all("train-" in f for f in files))


if __name__ == "__main__":
    unittest.main()
