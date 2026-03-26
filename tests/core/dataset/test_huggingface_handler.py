import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.append(str(Path(__file__).parent.parent.parent.parent))

from sygra.core.dataset.huggingface_handler import HuggingFaceHandler
from sygra.core.dataset.dataset_config import DataSourceConfig, OutputConfig


def _make_source_config(**kwargs):
    defaults = dict(
        repo_id="user/dataset",
        config_name="default",
        split="train",
        streaming=False,
        token=None,
        shard=None,
        encoding="utf-8",
    )
    defaults.update(kwargs)
    sc = MagicMock(spec=DataSourceConfig)
    for k, v in defaults.items():
        setattr(sc, k, v)
    return sc


def _make_output_config(**kwargs):
    defaults = dict(
        repo_id="user/output",
        config_name="default",
        split="train",
        private=False,
        token=None,
    )
    defaults.update(kwargs)
    oc = MagicMock(spec=OutputConfig)
    for k, v in defaults.items():
        setattr(oc, k, v)
    return oc


class TestHuggingFaceHandlerInit(unittest.TestCase):
    @patch("sygra.core.dataset.huggingface_handler.HfFileSystem")
    def test_init_stores_configs(self, mock_fs_cls):
        sc = _make_source_config()
        oc = _make_output_config()
        handler = HuggingFaceHandler(source_config=sc, output_config=oc)
        self.assertEqual(handler.source_config, sc)
        self.assertEqual(handler.output_config, oc)

    @patch("sygra.core.dataset.huggingface_handler.HfFileSystem")
    def test_init_creates_hf_filesystem(self, mock_fs_cls):
        sc = _make_source_config(token="my_token")
        handler = HuggingFaceHandler(source_config=sc)
        mock_fs_cls.assert_called_once_with(token="my_token")


class TestHuggingFaceHandlerRead(unittest.TestCase):
    @patch("sygra.core.dataset.huggingface_handler.HfFileSystem")
    def test_read_raises_when_no_source_config(self, mock_fs_cls):
        handler = HuggingFaceHandler(source_config=None)
        with self.assertRaises((ValueError, RuntimeError)):
            handler.read()

    @patch("sygra.core.dataset.huggingface_handler.HfFileSystem")
    def test_read_calls_read_shard_when_path_and_shard_set(self, mock_fs_cls):
        sc = _make_source_config(shard=MagicMock())
        handler = HuggingFaceHandler(source_config=sc)
        with patch.object(handler, "_read_shard", return_value=[]) as mock_shard:
            handler.read(path="some/path")
        mock_shard.assert_called_once_with("some/path")

    @patch("sygra.core.dataset.huggingface_handler.HfFileSystem")
    def test_read_calls_read_dataset_when_no_path(self, mock_fs_cls):
        sc = _make_source_config()
        handler = HuggingFaceHandler(source_config=sc)
        with patch.object(handler, "_read_dataset", return_value=[]) as mock_dataset:
            handler.read()
        mock_dataset.assert_called_once()


class TestHuggingFaceHandlerWrite(unittest.TestCase):
    @patch("sygra.core.dataset.huggingface_handler.HfFileSystem")
    def test_write_raises_when_no_output_config(self, mock_fs_cls):
        sc = _make_source_config()
        handler = HuggingFaceHandler(source_config=sc, output_config=None)
        with self.assertRaises((ValueError, RuntimeError)):
            handler.write([{"a": 1}])

    @patch("sygra.core.dataset.huggingface_handler.HfFileSystem")
    @patch("sygra.core.dataset.huggingface_handler.HfApi")
    def test_create_repo_raises_when_no_output_config(self, mock_api_cls, mock_fs_cls):
        sc = _make_source_config()
        handler = HuggingFaceHandler(source_config=sc, output_config=None)
        with self.assertRaises(ValueError):
            handler._create_repo()

    @patch("sygra.core.dataset.huggingface_handler.HfFileSystem")
    @patch("sygra.core.dataset.huggingface_handler.HfApi")
    def test_create_repo_raises_when_repo_id_empty(self, mock_api_cls, mock_fs_cls):
        sc = _make_source_config()
        oc = _make_output_config(repo_id="")
        handler = HuggingFaceHandler(source_config=sc, output_config=oc)
        with self.assertRaises(ValueError):
            handler._create_repo()


class TestHuggingFaceHandlerGetFiles(unittest.TestCase):
    @patch("sygra.core.dataset.huggingface_handler.HfFileSystem")
    def test_get_files_raises_when_no_source_config(self, mock_fs_cls):
        handler = HuggingFaceHandler(source_config=None)
        with self.assertRaises((ValueError, RuntimeError)):
            handler.get_files()

    @patch("sygra.core.dataset.huggingface_handler.HfFileSystem")
    def test_get_files_returns_all_files_when_no_shard(self, mock_fs_cls):
        sc = _make_source_config(shard=None)
        handler = HuggingFaceHandler(source_config=sc)
        handler.fs.glob.return_value = ["file1.parquet", "file2.parquet"]
        result = handler.get_files()
        self.assertEqual(result, ["file1.parquet", "file2.parquet"])

    @patch("sygra.core.dataset.huggingface_handler.HfFileSystem")
    def test_get_files_filters_by_shard_index(self, mock_fs_cls):
        shard = MagicMock()
        shard.regex = "/*.parquet"
        shard.index = {0, 2}
        sc = _make_source_config(shard=shard)
        handler = HuggingFaceHandler(source_config=sc)
        handler.fs.glob.return_value = ["file0.parquet", "file1.parquet", "file2.parquet"]
        result = handler.get_files()
        self.assertEqual(len(result), 2)
        self.assertIn("file0.parquet", result)
        self.assertIn("file2.parquet", result)


class TestHuggingFaceHandlerDecodeBase64Media(unittest.TestCase):
    @patch("sygra.core.dataset.huggingface_handler.HfFileSystem")
    def test_decodes_valid_data_url(self, mock_fs_cls):
        import base64
        sc = _make_source_config()
        handler = HuggingFaceHandler(source_config=sc)
        data = b"hello bytes"
        encoded = base64.b64encode(data).decode("utf-8")
        data_url = f"data:image/png;base64,{encoded}"
        result = handler._decode_base64_media(data_url)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["bytes"], data)

    @patch("sygra.core.dataset.huggingface_handler.HfFileSystem")
    def test_returns_none_for_invalid_item(self, mock_fs_cls):
        sc = _make_source_config()
        handler = HuggingFaceHandler(source_config=sc)
        result = handler._decode_base64_media(["not_a_data_url"])
        self.assertEqual(len(result), 1)
        self.assertIsNone(result[0])


class TestHuggingFaceHandlerDetectMediaColumns(unittest.TestCase):
    @patch("sygra.core.dataset.huggingface_handler.HfFileSystem")
    @patch("sygra.core.dataset.huggingface_handler.image_utils")
    @patch("sygra.core.dataset.huggingface_handler.audio_utils")
    def test_detects_image_str_column(self, mock_audio, mock_image, mock_fs_cls):
        import pandas as pd
        mock_image.is_data_url.return_value = True
        mock_image.is_image_file_path.return_value = False
        mock_audio.is_data_url.return_value = False
        mock_audio.is_audio_file_path.return_value = False

        sc = _make_source_config()
        handler = HuggingFaceHandler(source_config=sc)
        df = pd.DataFrame({"img": ["data:image/png;base64,abc"]})
        result = handler._detect_media_columns(df)
        self.assertEqual(len(result["image_str"]), 1)

    @patch("sygra.core.dataset.huggingface_handler.HfFileSystem")
    @patch("sygra.core.dataset.huggingface_handler.image_utils")
    @patch("sygra.core.dataset.huggingface_handler.audio_utils")
    def test_detects_no_media_for_text_column(self, mock_audio, mock_image, mock_fs_cls):
        import pandas as pd
        mock_image.is_data_url.return_value = False
        mock_image.is_image_file_path.return_value = False
        mock_audio.is_data_url.return_value = False
        mock_audio.is_audio_file_path.return_value = False

        sc = _make_source_config()
        handler = HuggingFaceHandler(source_config=sc)
        df = pd.DataFrame({"text": ["hello world"]})
        result = handler._detect_media_columns(df)
        self.assertEqual(result["image_str"], [])
        self.assertEqual(result["audio_str"], [])


class TestHuggingFaceHandlerStoreDatasetMetadata(unittest.TestCase):
    @patch("sygra.core.dataset.huggingface_handler.HfFileSystem")
    def test_stores_fingerprint_when_available(self, mock_fs_cls):
        sc = _make_source_config()
        handler = HuggingFaceHandler(source_config=sc)
        mock_ds = MagicMock()
        mock_ds._fingerprint = "abc123"
        mock_ds.info = None
        handler._store_dataset_metadata(mock_ds)
        self.assertEqual(handler.dataset_hash, "abc123")

    @patch("sygra.core.dataset.huggingface_handler.HfFileSystem")
    def test_handles_dataset_without_fingerprint(self, mock_fs_cls):
        sc = _make_source_config()
        handler = HuggingFaceHandler(source_config=sc)
        mock_ds = MagicMock(spec=[])
        # No _fingerprint attribute
        handler._store_dataset_metadata(mock_ds)
        self.assertIsNone(handler.dataset_hash)


if __name__ == "__main__":
    unittest.main()
