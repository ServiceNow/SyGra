import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.append(str(Path(__file__).parent.parent.parent.parent.parent))

from sygra.core.graph.nodes.multi_llm_node import MultiLLMNode


def _make_config(models=None, extra=None):
    config = {
        "node_type": "multi_llm",
        "prompt": [{"role": "system", "content": "You are helpful."}],
        "models": models or {
            "model_a": {"name": "a", "model": "gpt-a", "model_type": "openai"},
            "model_b": {"name": "b", "model": "gpt-b", "model_type": "openai"},
        },
    }
    if extra:
        config.update(extra)
    return config


class TestMultiLLMNodeInit(unittest.TestCase):
    @patch("sygra.core.graph.nodes.multi_llm_node.LLMNode")
    @patch("sygra.core.graph.nodes.multi_llm_node.utils")
    def test_init_creates_llm_node_per_model(self, mock_utils, mock_llm_node_cls):
        mock_utils.backend_factory = MagicMock()
        mock_llm_node_cls.return_value = MagicMock()

        node = MultiLLMNode("multi_node", _make_config())

        self.assertEqual(mock_llm_node_cls.call_count, 2)
        self.assertIn("model_a", node.llm_dict)
        self.assertIn("model_b", node.llm_dict)

    @patch("sygra.core.graph.nodes.multi_llm_node.LLMNode")
    @patch("sygra.core.graph.nodes.multi_llm_node.utils")
    def test_init_uses_default_post_process_when_not_in_config(self, mock_utils, mock_llm_node_cls):
        mock_utils.backend_factory = MagicMock()
        mock_llm_node_cls.return_value = MagicMock()

        node = MultiLLMNode("multi_node", _make_config())

        self.assertEqual(node.multi_llm_post_process, node._default_multi_llm_post_process)

    @patch("sygra.core.graph.nodes.multi_llm_node.LLMNode")
    @patch("sygra.core.graph.nodes.multi_llm_node.utils")
    def test_init_with_custom_post_process_function(self, mock_utils, mock_llm_node_cls):
        mock_utils.backend_factory = MagicMock()
        mock_llm_node_cls.return_value = MagicMock()
        custom_func = MagicMock()
        mock_utils.get_func_from_str.return_value = custom_func

        config = _make_config(extra={"multi_llm_post_process": "some.module.custom_func"})
        node = MultiLLMNode("multi_node", config)

        self.assertEqual(node.multi_llm_post_process, custom_func)

    @patch("sygra.core.graph.nodes.multi_llm_node.LLMNode")
    @patch("sygra.core.graph.nodes.multi_llm_node.utils")
    def test_init_with_post_process_class_uses_instance_apply(self, mock_utils, mock_llm_node_cls):
        mock_utils.backend_factory = MagicMock()
        mock_llm_node_cls.return_value = MagicMock()

        class MyPostProcess:
            def apply(self, model_outputs):
                return model_outputs

        mock_utils.get_func_from_str.return_value = MyPostProcess

        config = _make_config(extra={"multi_llm_post_process": "some.module.MyPostProcess"})
        node = MultiLLMNode("multi_node", config)

        self.assertEqual(node.multi_llm_post_process.__name__, "apply")


class TestDefaultMultiLLMPostProcess(unittest.TestCase):
    @patch("sygra.core.graph.nodes.multi_llm_node.LLMNode")
    @patch("sygra.core.graph.nodes.multi_llm_node.utils")
    def test_default_post_process_aggregates_outputs(self, mock_utils, mock_llm_node_cls):
        mock_utils.backend_factory = MagicMock()
        mock_llm_node_cls.return_value = MagicMock()

        config = _make_config(models={"m1": {"name": "m1", "model": "gpt", "model_type": "openai"}})
        node = MultiLLMNode("multi_node", config)
        node.output_key = "messages"

        result = node._default_multi_llm_post_process({
            "m1": {"messages": ["response from m1"]},
        })

        self.assertIn("messages", result)
        self.assertEqual(result["messages"][0]["m1"], ["response from m1"])


class TestMultiLLMNodeValidate(unittest.TestCase):
    @patch("sygra.core.graph.nodes.multi_llm_node.LLMNode")
    @patch("sygra.core.graph.nodes.multi_llm_node.utils")
    def test_validate_raises_when_models_missing(self, mock_utils, mock_llm_node_cls):
        mock_utils.validate_required_keys.side_effect = ValueError("Missing key: models")
        mock_utils.backend_factory = MagicMock()

        with self.assertRaises((ValueError, Exception)):
            MultiLLMNode("multi_node", {"node_type": "multi_llm", "prompt": []})

    @patch("sygra.core.graph.nodes.multi_llm_node.LLMNode")
    @patch("sygra.core.graph.nodes.multi_llm_node.utils")
    def test_validate_raises_when_prompt_missing(self, mock_utils, mock_llm_node_cls):
        mock_utils.validate_required_keys.side_effect = ValueError("Missing key: prompt")
        mock_utils.backend_factory = MagicMock()

        with self.assertRaises((ValueError, Exception)):
            MultiLLMNode("multi_node", {"node_type": "multi_llm", "models": {}})


class TestMultiLLMNodeToBackend(unittest.TestCase):
    @patch("sygra.core.graph.nodes.multi_llm_node.LLMNode")
    @patch("sygra.core.graph.nodes.multi_llm_node.utils")
    def test_to_backend_calls_backend_factory(self, mock_utils, mock_llm_node_cls):
        mock_utils.backend_factory = MagicMock()
        mock_llm_node_cls.return_value = MagicMock()
        expected = MagicMock()
        mock_utils.backend_factory.create_multi_llm_runnable.return_value = expected

        node = MultiLLMNode("multi_node", _make_config())
        result = node.to_backend()

        mock_utils.backend_factory.create_multi_llm_runnable.assert_called_once_with(
            node.llm_dict, node.multi_llm_post_process
        )
        self.assertEqual(result, expected)


class TestMultiLLMNodeExecWrapper(unittest.IsolatedAsyncioTestCase):
    @patch("sygra.core.graph.nodes.multi_llm_node.LLMNode")
    @patch("sygra.core.graph.nodes.multi_llm_node.utils")
    async def test_exec_wrapper_calls_llm_nodes_and_post_process(self, mock_utils, mock_llm_node_cls):
        mock_utils.backend_factory = MagicMock()

        fake_llm_a = MagicMock()
        fake_llm_a._exec_wrapper = MagicMock(return_value={"messages": ["output_a"]})
        fake_llm_b = MagicMock()
        fake_llm_b._exec_wrapper = MagicMock(return_value={"messages": ["output_b"]})
        mock_llm_node_cls.side_effect = [fake_llm_a, fake_llm_b]

        node = MultiLLMNode("multi_node", _make_config())
        post_process_mock = MagicMock(return_value={"messages": ["aggregated"]})
        node.multi_llm_post_process = post_process_mock

        with patch.object(node, "_record_execution_metadata"):
            result = await node._exec_wrapper({"input": "hello"})

        post_process_mock.assert_called_once()
        self.assertEqual(result, {"messages": ["aggregated"]})


if __name__ == "__main__":
    unittest.main()
