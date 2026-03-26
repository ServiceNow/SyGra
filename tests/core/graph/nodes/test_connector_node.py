import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.append(str(Path(__file__).parent.parent.parent.parent.parent))

from sygra.core.graph.nodes.base_node import NodeState, NodeType
from sygra.core.graph.nodes.connector_node import ConnectorNode


class TestConnectorNodeInit(unittest.TestCase):
    @patch("sygra.core.graph.nodes.connector_node.utils")
    def test_init_sets_node_state_active(self, mock_utils):
        mock_utils.backend_factory = MagicMock()
        node = ConnectorNode("connector_1")
        self.assertEqual(node.node_state, NodeState.ACTIVE.value)

    @patch("sygra.core.graph.nodes.connector_node.utils")
    def test_init_sets_node_type_connector(self, mock_utils):
        mock_utils.backend_factory = MagicMock()
        node = ConnectorNode("connector_1")
        self.assertEqual(node.node_type, NodeType.CONNECTOR.value)

    @patch("sygra.core.graph.nodes.connector_node.utils")
    def test_init_stores_node_name(self, mock_utils):
        mock_utils.backend_factory = MagicMock()
        node = ConnectorNode("my_connector")
        self.assertEqual(node.name, "my_connector")


class TestConnectorNodeIsValid(unittest.TestCase):
    @patch("sygra.core.graph.nodes.connector_node.utils")
    def test_is_valid_returns_true(self, mock_utils):
        mock_utils.backend_factory = MagicMock()
        node = ConnectorNode("connector_1")
        self.assertTrue(node.is_valid())


class TestConnectorNodeIsActive(unittest.TestCase):
    @patch("sygra.core.graph.nodes.connector_node.utils")
    def test_is_active_returns_true(self, mock_utils):
        mock_utils.backend_factory = MagicMock()
        node = ConnectorNode("connector_1")
        self.assertTrue(node.is_active())


class TestConnectorNodeToBackend(unittest.TestCase):
    @patch("sygra.core.graph.nodes.connector_node.utils")
    def test_to_backend_calls_create_connector_runnable(self, mock_utils):
        mock_utils.backend_factory = MagicMock()
        expected = MagicMock()
        mock_utils.backend_factory.create_connector_runnable.return_value = expected

        node = ConnectorNode("connector_1")
        result = node.to_backend()

        mock_utils.backend_factory.create_connector_runnable.assert_called_once_with()
        self.assertEqual(result, expected)


if __name__ == "__main__":
    unittest.main()
