import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import yaml

sys.path.append(str(Path(__file__).parent.parent.parent))

from sygra.configuration.loader import ConfigLoader


class TestConfigLoaderLoad(unittest.TestCase):
    def test_load_returns_dict_unchanged_when_given_dict(self):
        loader = ConfigLoader()
        config = {"task_name": "test", "nodes": {}}
        result = loader.load(config)
        self.assertEqual(result, config)

    def test_load_reads_yaml_file(self):
        config_data = {"task_name": "my_task", "nodes": {"n1": {"node_type": "llm"}}}
        with tempfile.NamedTemporaryFile(suffix=".yaml", mode="w", delete=False) as f:
            yaml.dump(config_data, f)
            tmp_path = f.name

        loader = ConfigLoader()
        result = loader.load(tmp_path)
        self.assertEqual(result["task_name"], "my_task")

    def test_load_raises_file_not_found_for_missing_file(self):
        loader = ConfigLoader()
        with self.assertRaises(FileNotFoundError):
            loader.load("/nonexistent/path/config.yaml")

    def test_load_raises_type_error_for_non_dict_yaml(self):
        with tempfile.NamedTemporaryFile(suffix=".yaml", mode="w", delete=False) as f:
            yaml.dump(["item1", "item2"], f)
            tmp_path = f.name

        loader = ConfigLoader()
        with self.assertRaises(TypeError):
            loader.load(tmp_path)

    def test_load_accepts_path_object(self):
        config_data = {"task_name": "path_test"}
        with tempfile.NamedTemporaryFile(suffix=".yaml", mode="w", delete=False) as f:
            yaml.dump(config_data, f)
            tmp_path = Path(f.name)

        loader = ConfigLoader()
        result = loader.load(tmp_path)
        self.assertEqual(result["task_name"], "path_test")


class TestConfigLoaderLoadAndCreate(unittest.TestCase):
    def test_load_and_create_returns_workflow_with_correct_flags(self):
        config_data = {"task_name": "my_workflow", "nodes": {}}
        with tempfile.NamedTemporaryFile(suffix=".yaml", mode="w", delete=False) as f:
            yaml.dump(config_data, f)
            tmp_path = f.name

        loader = ConfigLoader()
        workflow = loader.load_and_create(tmp_path)

        self.assertTrue(workflow._supports_subgraphs)
        self.assertTrue(workflow._supports_multimodal)
        self.assertTrue(workflow._supports_resumable)
        self.assertTrue(workflow._supports_quality)
        self.assertTrue(workflow._supports_oasst)

    def test_load_and_create_sets_name_from_parent_directory(self):
        config_data = {"task_name": "my_workflow"}
        with tempfile.TemporaryDirectory() as tmpdir:
            task_dir = Path(tmpdir) / "my_task_name"
            task_dir.mkdir()
            config_file = task_dir / "graph_config.yaml"
            config_file.write_text(yaml.dump(config_data))

            loader = ConfigLoader()
            workflow = loader.load_and_create(str(config_file))

        self.assertEqual(workflow.name, "my_task_name")

    def test_load_and_create_with_dict_sets_name_from_task_name(self):
        config = {"task_name": "dict_task", "nodes": {}}
        loader = ConfigLoader()
        workflow = loader.load_and_create(config)
        self.assertEqual(workflow.name, "dict_task")

    def test_load_and_create_with_dict_without_task_name_uses_default(self):
        config = {"nodes": {}}
        loader = ConfigLoader()
        workflow = loader.load_and_create(config)
        self.assertEqual(workflow.name, "loaded_workflow")


if __name__ == "__main__":
    unittest.main()
