import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

# Add the parent directory to sys.path to import the necessary modules
sys.path.append(str(Path(__file__).parent.parent.parent.parent))


from sygra.core.models.custom_models import CustomGeminiProxy


class TestCustomGeminiProxy(unittest.TestCase):
    """Unit tests for CustomGeminiProxy model"""

    def setUp(self):
        """Set up test fixtures before each test method"""
        self.base_config = {
            "name": "gemini_2.5_proxy",
            "model_type": "gemini_proxy",
            "url": "http://gemini-proxy.com",
            "parameters": {"maxOutputTokens": 2500, "temperature": 0},
        }

    def test_init_without_auth_token(self):
        """Test CustomGeminiProxy initialization without auth_token"""
        model = CustomGeminiProxy(self.base_config)

        self.assertEqual(model.name(), "gemini_2.5_proxy")
        self.assertIsNone(model.auth_token)

    def test_init_missing_url_raises_error(self):
        """Test that missing URL raises validation error"""
        model_config = {
            "name": "gemini_2.5_proxy",
            "model_type": "gemini_proxy",
            "parameters": {},
        }

        with self.assertRaises(ValueError) as context:
            CustomGeminiProxy(model_config)

        self.assertIn("url", str(context.exception).lower())

    @patch("sygra.core.models.custom_models.convert_to_openai_tool")
    def test_convert_tools_to_gemini_format(self, mock_convert):
        """Test tool conversion from OpenAI to Gemini format"""
        model = CustomGeminiProxy(self.base_config)

        mock_convert.return_value = {
            "type": "function",
            "function": {
                "name": "search",
                "description": "Search the web",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Search query",
                            "examples": ["example"],
                        }
                    },
                },
            },
        }

        tools = [{"name": "search"}]
        formatted = model._convert_tools_to_model_format(tools=tools)

        self.assertEqual(len(formatted), 1)
        self.assertEqual(formatted[0]["name"], "search")
        self.assertEqual(formatted[0]["description"], "Search the web")
        # Gemini format should only have type and description in properties
        self.assertIn("type", formatted[0]["parameters"]["properties"]["query"])
        self.assertIn("description", formatted[0]["parameters"]["properties"]["query"])
        # examples should be removed
        self.assertNotIn("examples", formatted[0]["parameters"]["properties"]["query"])

    def test_convert_tools_empty_list(self):
        """Test tool conversion with empty tools list"""
        model = CustomGeminiProxy(self.base_config)

        formatted = model._convert_tools_to_model_format(tools=[])

        self.assertEqual(formatted, [])

    def test_convert_tools_no_tools_kwarg(self):
        """Test tool conversion when tools kwarg is not provided"""
        model = CustomGeminiProxy(self.base_config)

        formatted = model._convert_tools_to_model_format()

        self.assertEqual(formatted, [])

    @patch("sygra.core.models.custom_models.convert_to_openai_tool")
    def test_convert_tools_without_function_field_skipped(self, mock_convert):
        """Test that tools without function field are skipped"""
        model = CustomGeminiProxy(self.base_config)

        mock_convert.return_value = {"type": "other"}  # No function field

        tools = [{"name": "invalid_tool"}]
        formatted = model._convert_tools_to_model_format(tools=tools)

        # Tool should be skipped
        self.assertEqual(len(formatted), 0)

    @patch("sygra.core.models.custom_models.convert_to_openai_tool")
    def test_convert_tools_without_name_field_skipped(self, mock_convert):
        """Test that tools without name field are skipped"""
        model = CustomGeminiProxy(self.base_config)

        mock_convert.return_value = {
            "type": "function",
            "function": {"description": "No name"},  # Missing name
        }

        tools = [{"name": "invalid_tool"}]
        formatted = model._convert_tools_to_model_format(tools=tools)

        # Tool should be skipped
        self.assertEqual(len(formatted), 0)

    def test_convert_to_parts_with_text(self):
        """Test content conversion to Gemini parts format with text"""
        model = CustomGeminiProxy(self.base_config)

        parts = model._convert_to_parts("Hello world")

        self.assertEqual(parts, [{"text": "Hello world"}])

    def test_convert_to_parts_with_list_content(self):
        """Test content conversion with list of content items"""
        model = CustomGeminiProxy(self.base_config)

        contents = [{"type": "text", "text": "Hello"}, {"type": "text", "text": "World"}]

        parts = model._convert_to_parts(contents)

        self.assertEqual(len(parts), 2)
        self.assertEqual(parts[0]["text"], "Hello")
        self.assertEqual(parts[1]["text"], "World")

    def test_convert_to_parts_with_image(self):
        """Test image conversion to Gemini inline_data format"""
        model = CustomGeminiProxy(self.base_config)

        contents = [
            {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64,/9j/4AAQSkZJRg"}}
        ]

        parts = model._convert_to_parts(contents)

        self.assertEqual(len(parts), 1)
        self.assertIn("inline_data", parts[0])
        self.assertEqual(parts[0]["inline_data"]["mime_type"], "image/jpeg")
        self.assertEqual(parts[0]["inline_data"]["data"], "/9j/4AAQSkZJRg")

    def test_convert_to_parts_with_png_image(self):
        """Test PNG image conversion"""
        model = CustomGeminiProxy(self.base_config)

        contents = [
            {"type": "image_url", "image_url": {"url": "data:image/png;base64,iVBORw0KGgo"}}
        ]

        parts = model._convert_to_parts(contents)

        self.assertEqual(parts[0]["inline_data"]["mime_type"], "image/png")
        self.assertEqual(parts[0]["inline_data"]["data"], "iVBORw0KGgo")

    def test_convert_functions_to_parts(self):
        """Test function call conversion to Gemini format"""
        model = CustomGeminiProxy(self.base_config)

        tool_calls = [
            {
                "id": "call_123",
                "type": "function",
                "function": {"name": "get_weather", "arguments": '{"location": "SF"}'},
            }
        ]

        func_parts, map_id = model._convert_functions_to_parts(tool_calls)

        self.assertEqual(len(func_parts), 1)
        self.assertIn("functionCall", func_parts[0])
        self.assertEqual(func_parts[0]["functionCall"]["name"], "get_weather")
        self.assertEqual(func_parts[0]["functionCall"]["args"]["location"], "SF")
        self.assertEqual(map_id["call_123"], "get_weather")

    def test_convert_functions_with_multiple_calls(self):
        """Test conversion with multiple function calls"""
        model = CustomGeminiProxy(self.base_config)

        tool_calls = [
            {
                "id": "call_1",
                "type": "function",
                "function": {"name": "func1", "arguments": '{"a": 1}'},
            },
            {
                "id": "call_2",
                "type": "function",
                "function": {"name": "func2", "arguments": '{"b": 2}'},
            },
        ]

        func_parts, map_id = model._convert_functions_to_parts(tool_calls)

        self.assertEqual(len(func_parts), 2)
        self.assertEqual(func_parts[0]["functionCall"]["name"], "func1")
        self.assertEqual(func_parts[1]["functionCall"]["name"], "func2")
        self.assertEqual(map_id["call_1"], "func1")
        self.assertEqual(map_id["call_2"], "func2")

    def test_convert_openai_tool_call_to_gemini_format(self):
        """Test full OpenAI tool call conversion to Gemini format"""
        model = CustomGeminiProxy(self.base_config)

        messages = [
            {"role": "user", "content": "What's the weather?"},
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
            },
            {
                "role": "tool",
                "tool_call_id": "call_123",
                "content": "Sunny, 75F",
                "status": "success",
            },
            {"role": "user", "content": "Thanks"},
        ]

        converted = model._convert_openai_tool_call_to_model_format(messages)

        # First user message
        self.assertEqual(converted[0]["role"], "user")
        # Assistant message with function call (role becomes "model")
        self.assertEqual(converted[1]["role"], "model")
        # parts has: [{"text": ""}, {"functionCall": ...}]
        self.assertEqual(len(converted[1]["parts"]), 2)
        self.assertIn("functionCall", converted[1]["parts"][1])
        # Tool result merged with next user message
        self.assertEqual(converted[2]["role"], "user")
        self.assertIn("functionResponse", converted[2]["parts"][0])

    def test_convert_tool_use_to_openai(self):
        """Test conversion of Gemini tool use to OpenAI format"""
        model = CustomGeminiProxy(self.base_config)

        tool_use = {"name": "search", "args": {"query": "test"}}

        converted = model._convert_tool_use_to_openai(tool_use, "toolcall_456")

        self.assertEqual(converted["id"], "toolcall_456")
        self.assertEqual(converted["type"], "function")
        self.assertEqual(converted["function"]["name"], "search")
        self.assertEqual(json.loads(converted["function"]["arguments"])["query"], "test")

    def test_convert_tool_use_empty_dict(self):
        """Test conversion of empty tool use dict"""
        model = CustomGeminiProxy(self.base_config)

        converted = model._convert_tool_use_to_openai({}, "id_123")

        self.assertEqual(converted, {})

    def test_model_name_method(self):
        """Test that name() method returns correct model name"""
        model = CustomGeminiProxy(self.base_config)

        self.assertEqual(model.name(), "gemini_2.5_proxy")


if __name__ == "__main__":
    unittest.main()
