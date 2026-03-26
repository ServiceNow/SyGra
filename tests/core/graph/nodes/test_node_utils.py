import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.append(str(Path(__file__).parent.parent.parent.parent.parent))

from sygra.core.graph.nodes.node_utils import get_node, get_node_config


class TestGetNode(unittest.TestCase):
    def test_raises_assertion_when_node_type_missing(self):
        with self.assertRaises(AssertionError):
            get_node("my_node", {})

    def test_raises_not_implemented_for_unknown_type(self):
        with self.assertRaises(NotImplementedError):
            get_node("my_node", {"node_type": "nonexistent_type"})

    def test_returns_special_node_for_special_type(self):
        from sygra.core.graph.nodes.special_node import SpecialNode
        node = get_node("START", {"node_type": "special"})
        self.assertIsInstance(node, SpecialNode)
        self.assertEqual(node.name, "START")

    @patch("sygra.core.graph.nodes.node_utils.ConnectorNode")
    def test_returns_connector_node_for_connector_type(self, mock_cls):
        mock_instance = MagicMock()
        mock_cls.return_value = mock_instance
        result = get_node("conn_node", {"node_type": "connector"})
        mock_cls.assert_called_once_with("conn_node")
        self.assertEqual(result, mock_instance)

    @patch("sygra.core.graph.nodes.node_utils.LLMNode")
    def test_returns_llm_node_for_llm_type(self, mock_cls):
        mock_instance = MagicMock()
        mock_cls.return_value = mock_instance
        config = {"node_type": "llm", "model": {}, "prompt": []}
        result = get_node("llm_node", config)
        mock_cls.assert_called_once_with("llm_node", config)
        self.assertEqual(result, mock_instance)

    @patch("sygra.core.graph.nodes.node_utils.LambdaNode")
    def test_returns_lambda_node_for_lambda_type(self, mock_cls):
        mock_instance = MagicMock()
        mock_cls.return_value = mock_instance
        config = {"node_type": "lambda", "lambda": "some.module.func"}
        result = get_node("lambda_node", config)
        mock_cls.assert_called_once_with("lambda_node", config)
        self.assertEqual(result, mock_instance)

    @patch("sygra.core.graph.nodes.node_utils.MultiLLMNode")
    def test_returns_multi_llm_node_for_multi_llm_type(self, mock_cls):
        mock_instance = MagicMock()
        mock_cls.return_value = mock_instance
        config = {"node_type": "multi_llm", "models": {}, "prompt": []}
        result = get_node("multi_node", config)
        mock_cls.assert_called_once_with("multi_node", config)
        self.assertEqual(result, mock_instance)


class TestGetNodeConfig(unittest.TestCase):
    def test_raises_assertion_when_node_not_in_config(self):
        with self.assertRaises(AssertionError):
            get_node_config("missing_node", {"nodes": {"other_node": {}}})

    def test_returns_correct_config(self):
        node_cfg = {"node_type": "llm", "prompt": [], "model": {}}
        result = get_node_config("my_node", {"nodes": {"my_node": node_cfg}})
        self.assertEqual(result, node_cfg)

    def test_raises_assertion_when_nodes_key_absent(self):
        with self.assertRaises(AssertionError):
            get_node_config("my_node", {})

    def test_returns_config_among_multiple_nodes(self):
        target_cfg = {"node_type": "lambda", "lambda": "my.func"}
        graph_config = {
            "nodes": {
                "node_a": {"node_type": "llm"},
                "node_b": target_cfg,
                "node_c": {"node_type": "special"},
            }
        }
        result = get_node_config("node_b", graph_config)
        self.assertEqual(result, target_cfg)


if __name__ == "__main__":
    unittest.main()
