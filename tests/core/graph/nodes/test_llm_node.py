import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

# Ensure project root is on sys.path similar to other tests
sys.path.append(str(Path(__file__).parent.parent.parent.parent))


from sygra.core.graph.nodes.llm_node import LLMNode


class TestLLMNodeToolsInitialization(unittest.TestCase):
    """Unit tests for tools handling in LLMNode.__init__"""

    def setUp(self):
        # Minimal valid node configuration
        self.base_config = {
            "model": {
                "name": "dummy_model",
                "model": "gpt-test",
                "model_type": "openai",
                "url": "https://azure-test.openai.azure.com",
                "auth_token": "test_token_123",
                "api_version": "dummy_api_version",
                "parameters": {},
            },
            "prompt": [
                {"role": "system", "content": "You are a helpful assistant"},
            ],
        }

    @patch("sygra.core.graph.nodes.llm_node.LLMNode._initialize_model")
    @patch("sygra.utils.tool_utils.load_tools")
    @patch("sygra.utils.utils.get_graph_properties")
    def test_init_with_tools_enables_tool_calls_and_loads_tools(
        self, mock_get_graph_properties, mock_load_tools, mock_init_model
    ):
        # Arrange
        tools_config = ["test.tools.weather_tool", "test.tools.search_tool"]
        config = {
            **self.base_config,
            "tools": tools_config,
            # optional: specify tool_choice to ensure it does not affect init
            "tool_choice": "auto",
        }

        fake_tools = [MagicMock(name="weather_tool"), MagicMock(name="search_tool")]
        mock_load_tools.return_value = fake_tools
        mock_get_graph_properties.return_value = {}

        # Initialize LLM Node
        node = LLMNode("llm_node_with_tools", config)

        # Assert
        mock_init_model.assert_called_once()
        mock_load_tools.assert_called_once_with(tools_config)
        self.assertTrue(node.tool_calls_enabled)
        self.assertEqual(node.tools, fake_tools)

    @patch("sygra.core.graph.nodes.llm_node.LLMNode._initialize_model")
    @patch("sygra.utils.utils.get_graph_properties")
    def test_init_without_tools_disables_tool_calls(
        self, mock_get_graph_properties, mock_init_model
    ):
        # Arrange
        config = {**self.base_config}
        mock_get_graph_properties.return_value = {}

        # Act
        node = LLMNode("llm_node_without_tools", config)

        # Assert
        mock_init_model.assert_called_once()
        self.assertFalse(node.tool_calls_enabled)
        self.assertEqual(node.tools, [])


if __name__ == "__main__":
    unittest.main()
