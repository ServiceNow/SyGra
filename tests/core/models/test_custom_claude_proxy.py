import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

# Add the parent directory to sys.path to import the necessary modules
sys.path.append(str(Path(__file__).parent.parent.parent.parent))


from sygra.core.models.custom_models import CustomClaudeProxy


class TestCustomClaudeProxy(unittest.TestCase):
    """Unit tests for CustomClaudeProxy model"""

    def setUp(self):
        """Set up test fixtures before each test method"""
        self.base_config = {
            "name": "claude_large",
            "model_type": "claude_proxy",
            "url": "http://claude-proxy.com",
            "parameters": {"maxTokens": 2500, "temperature": 0},
        }

    def test_init_with_url_only(self):
        """Test CustomClaudeProxy initialization with URL only (no auth_token)"""
        model_config = {**self.base_config}
        model = CustomClaudeProxy(model_config)

        self.assertEqual(model.name(), "claude_large")
        self.assertIsNone(model.auth_token)
        self.assertEqual(model.model_config["url"], "http://claude-proxy.com")

    def test_init_missing_url_raises_error(self):
        """Test that missing URL raises validation error"""
        model_config = {
            "name": "claude_large",
            "model_type": "claude_proxy",
            "parameters": {},
        }

        with self.assertRaises(ValueError) as context:
            CustomClaudeProxy(model_config)

        self.assertIn("url", str(context.exception).lower())

    @patch("sygra.core.models.custom_models.convert_to_openai_tool")
    def test_convert_tools_to_bedrock_format(self, mock_convert):
        """Test tool conversion from OpenAI to Bedrock format"""
        model = CustomClaudeProxy(self.base_config)

        # Mock OpenAI tool format
        mock_convert.return_value = {
            "type": "function",
            "function": {
                "name": "get_weather",
                "description": "Get weather information",
                "parameters": {
                    "type": "object",
                    "properties": {"location": {"type": "string", "description": "City name"}},
                    "required": ["location"],
                },
            },
        }

        tools = [{"name": "get_weather"}]
        formatted = model._convert_tools_to_model_format(tools=tools)

        self.assertEqual(len(formatted), 1)
        self.assertIn("toolSpec", formatted[0])
        self.assertEqual(formatted[0]["toolSpec"]["name"], "get_weather")
        self.assertEqual(formatted[0]["toolSpec"]["description"], "Get weather information")
        self.assertEqual(formatted[0]["toolSpec"]["type"], "function")
        self.assertIn("inputSchema", formatted[0]["toolSpec"])

    def test_convert_tools_empty_list(self):
        """Test tool conversion with empty tools list"""
        model = CustomClaudeProxy(self.base_config)

        formatted = model._convert_tools_to_model_format(tools=[])

        self.assertEqual(formatted, [])

    def test_convert_tools_no_tools_kwarg(self):
        """Test tool conversion when tools kwarg is not provided"""
        model = CustomClaudeProxy(self.base_config)

        formatted = model._convert_tools_to_model_format()

        self.assertEqual(formatted, [])

    def test_convert_content_type_string_to_list(self):
        """Test content conversion from string to list format"""
        model = CustomClaudeProxy(self.base_config)

        msg = {"role": "user", "content": "Hello, how are you?"}
        converted = model._convert_content_type(msg)

        self.assertIsInstance(converted["content"], list)
        self.assertEqual(len(converted["content"]), 1)
        self.assertEqual(converted["content"][0]["text"], "Hello, how are you?")

    def test_convert_content_type_already_list(self):
        """Test content conversion when content is already a list"""
        model = CustomClaudeProxy(self.base_config)

        msg = {"role": "user", "content": [{"type": "text", "text": "Hello"}]}
        converted = model._convert_content_type(msg)

        self.assertIsInstance(converted["content"], list)
        # Type key should be removed
        self.assertNotIn("type", converted["content"][0])

    def test_convert_image_url_to_bedrock_format(self):
        """Test image URL conversion to Bedrock format"""
        model = CustomClaudeProxy(self.base_config)

        msg = {
            "role": "user",
            "content": [
                {
                    "type": "image_url",
                    "image_url": {"url": "data:image/png;base64,iVBORw0KGgoAAAANS"},
                }
            ],
        }
        converted = model._convert_content_type(msg)

        self.assertEqual(len(converted["content"]), 1)
        self.assertIn("image", converted["content"][0])
        self.assertEqual(converted["content"][0]["image"]["format"], "png")
        self.assertIn("source", converted["content"][0]["image"])
        self.assertIn("bytes", converted["content"][0]["image"]["source"])
        # image_url and type keys should be removed
        self.assertNotIn("image_url", converted["content"][0])
        self.assertNotIn("type", converted["content"][0])

    def test_convert_tool_calls_to_bedrock_format(self):
        """Test OpenAI tool_calls conversion to Bedrock format"""
        model = CustomClaudeProxy(self.base_config)

        messages = [
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {
                        "id": "call_123",
                        "type": "function",
                        "function": {"name": "get_weather", "arguments": '{"location": "NYC"}'},
                    }
                ],
            }
        ]

        converted = model._convert_openai_tool_call_to_model_format(messages)

        self.assertEqual(len(converted), 1)
        self.assertEqual(converted[0]["role"], "assistant")
        # tool_calls should be removed
        self.assertNotIn("tool_calls", converted[0])
        # content should have text (from empty string) and toolUse
        self.assertEqual(len(converted[0]["content"]), 2)  # [{"text": ""}, {"toolUse": ...}]
        self.assertIn("text", converted[0]["content"][0])
        self.assertIn("toolUse", converted[0]["content"][1])
        self.assertEqual(converted[0]["content"][1]["toolUse"]["name"], "get_weather")
        self.assertEqual(converted[0]["content"][1]["toolUse"]["toolUseId"], "call_123")
        self.assertEqual(converted[0]["content"][1]["toolUse"]["input"]["location"], "NYC")

    def test_convert_tool_calls_with_multiple_tools(self):
        """Test conversion with multiple tool calls"""
        model = CustomClaudeProxy(self.base_config)

        messages = [
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {
                        "id": "call_1",
                        "type": "function",
                        "function": {"name": "tool1", "arguments": '{"arg": "val1"}'},
                    },
                    {
                        "id": "call_2",
                        "type": "function",
                        "function": {"name": "tool2", "arguments": '{"arg": "val2"}'},
                    },
                ],
            }
        ]

        converted = model._convert_openai_tool_call_to_model_format(messages)

        # content has: [{"text": ""}, {"toolUse": tool1}, {"toolUse": tool2}]
        self.assertEqual(len(converted[0]["content"]), 3)
        self.assertEqual(converted[0]["content"][1]["toolUse"]["name"], "tool1")
        self.assertEqual(converted[0]["content"][2]["toolUse"]["name"], "tool2")

    def test_convert_tool_role_dropped(self):
        """Test that tool role messages are dropped"""
        model = CustomClaudeProxy(self.base_config)

        messages = [
            {"role": "user", "content": "Hello"},
            {"role": "tool", "content": "Tool result", "tool_call_id": "call_123"},
        ]

        converted = model._convert_openai_tool_call_to_model_format(messages)

        # Only user message should remain, tool message dropped
        self.assertEqual(len(converted), 1)
        self.assertEqual(converted[0]["role"], "user")

    def test_convert_tool_use_to_openai(self):
        """Test conversion of Bedrock tool use to OpenAI format"""
        model = CustomClaudeProxy(self.base_config)

        tool_use = {"name": "search", "toolUseId": "tool_123", "input": {"query": "test"}}

        converted = model._convert_tool_use_to_openai(tool_use)

        self.assertEqual(converted["id"], "tool_123")
        self.assertEqual(converted["type"], "function")
        self.assertEqual(converted["function"]["name"], "search")
        self.assertEqual(json.loads(converted["function"]["arguments"])["query"], "test")

    def test_convert_tool_use_empty_dict(self):
        """Test conversion of empty tool use dict"""
        model = CustomClaudeProxy(self.base_config)

        converted = model._convert_tool_use_to_openai({})

        self.assertEqual(converted, {})

    def test_model_name_method(self):
        """Test that name() method returns correct model name"""
        model = CustomClaudeProxy(self.base_config)

        self.assertEqual(model.name(), "claude_large")


if __name__ == "__main__":
    unittest.main()
