import asyncio
import sys
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import openai

from sygra.utils.audio_utils import get_audio_url

# Add the parent directory to sys.path to import the necessary modules
sys.path.append(str(Path(__file__).parent.parent.parent.parent))

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.prompt_values import ChatPromptValue

from sygra.core.models.custom_models import CustomOpenAI, ModelParams
from sygra.utils import constants


class TestCustomOpenAI(unittest.TestCase):
    """Unit tests for the CustomOpenAI class - model level tests"""

    def setUp(self):
        """Set up test fixtures before each test method"""
        # Base model configuration for text generation
        self.text_config = {
            "name": "gpt4_model",
            "model": "gpt-4",
            "parameters": {"temperature": 0.7, "max_tokens": 100},
            "url": "https://api.openai.com/v1",
            "auth_token": "Bearer sk-test_key_123",
            "api_version": "2023-05-15",
        }

        # Configuration for TTS
        self.tts_config = {
            "name": "tts_model",
            "model": "tts-1",
            "model_type": "openai",
            "output_type": "audio",
            "url": "https://api.openai.com/v1",
            "auth_token": "Bearer sk-test_key_123",
            "api_version": "2023-05-15",
            "parameters": {
                "voice": "alloy",
                "response_format": "mp3",
                "speed": 1.0,
            },
        }

        # Configuration with completions API
        self.completions_config = {
            **self.text_config,
            "completions_api": True,
            "hf_chat_template_model_id": "meta-llama/Llama-2-7b-chat-hf",
        }

        # Mock messages for text generation
        self.messages = [
            SystemMessage(content="You are a helpful assistant"),
            HumanMessage(content="Hello, how are you?"),
        ]
        self.chat_input = ChatPromptValue(messages=self.messages)

        # Mock messages for TTS
        self.tts_messages = [HumanMessage(content="Hello, this is a test of text to speech.")]
        self.tts_input = ChatPromptValue(messages=self.tts_messages)

        # Configuration for Image Generation
        self.image_config = {
            "name": "dalle3_model",
            "model": "dall-e-3",
            "output_type": "image",
            "url": "https://api.openai.com/v1",
            "auth_token": "Bearer sk-test_key_123",
            "api_version": "2023-05-15",
            "parameters": {"size": "1024x1024", "quality": "standard", "style": "vivid"},
        }

        # Mock messages for Image Generation
        self.image_messages = [HumanMessage(content="A serene mountain landscape at sunset")]
        self.image_input = ChatPromptValue(messages=self.image_messages)

    def test_init(self):
        """Test initialization of CustomOpenAI"""
        custom_openai = CustomOpenAI(self.text_config)

        # Verify model was properly initialized
        self.assertEqual(custom_openai.model_config, self.text_config)
        self.assertEqual(custom_openai.generation_params, self.text_config["parameters"])
        self.assertEqual(custom_openai.name(), "gpt4_model")

    def test_init_missing_required_keys_raises_error(self):
        """Test initialization without required keys raises error"""
        config = {
            "name": "gpt4_model",
            "parameters": {"temperature": 0.7},
        }

        with self.assertRaises(Exception):
            CustomOpenAI(config)

    @patch("sygra.core.models.custom_models.logger")
    def test_init_with_completions_api(self, mock_logger):
        """Test initialization with completions API enabled"""
        with patch("sygra.core.models.custom_models.AutoTokenizer"):
            custom_openai = CustomOpenAI(self.completions_config)

            self.assertTrue(custom_openai.model_config.get("completions_api"))
            # Should log that model supports completion API
            mock_logger.info.assert_any_call("Model gpt4_model supports completion API.")

    # ============== _generate_text Tests ==============

    async def _run_generate_text_chat_api_success(self, mock_set_client):
        """Test _generate_text with chat API (non-completions)"""
        # Setup mock client
        mock_client = MagicMock()
        mock_client.build_request.return_value = {
            "messages": [{"role": "user", "content": "Hello"}]
        }

        # Setup mock completion response
        mock_choice = MagicMock()
        mock_choice.model_dump.return_value = {
            "message": {"content": "Hello! I'm doing well, thank you!", "tool_calls": None},
        }
        mock_completion = MagicMock()
        mock_completion.choices = [mock_choice]

        mock_client.send_request = AsyncMock(return_value=mock_completion)

        # Setup custom model
        custom_openai = CustomOpenAI(self.text_config)
        custom_openai._client = mock_client

        # Call _generate_text
        model_params = ModelParams(url="https://api.openai.com/v1", auth_token="sk-test")
        model_response = await custom_openai._generate_text(self.chat_input, model_params)

        # Verify results (text should be stripped)
        self.assertEqual(model_response.llm_response, "Hello! I'm doing well, thank you!")
        self.assertEqual(model_response.response_code, 200)

        # Verify method calls
        mock_set_client.assert_called_once()
        mock_client.build_request.assert_called_once_with(messages=self.messages)
        mock_client.send_request.assert_awaited_once()

    async def _run_generate_text_chat_api_with_tools_success(self, mock_set_client):
        """Test _generate_text with chat API (non-completions)"""
        # Setup mock client
        mock_client = MagicMock()
        mock_client.build_request.return_value = {
            "messages": [{"role": "user", "content": "Get me latest business news"}]
        }

        # Setup mock completion response
        mock_choice = MagicMock()
        sample_tool_call = {
            "id": "call_12xyz",
            "function": {
                "arguments": '{"query":"Latest business news"}',
                # A JSON string of the arguments for the function
                "name": "new_search",  # The name of the function to be called
            },
            "type": "function",
        }
        mock_choice.model_dump.return_value = {
            "message": {"content": None, "tool_calls": [sample_tool_call]},
        }
        mock_completion = MagicMock()
        mock_completion.choices = [mock_choice]

        mock_client.send_request = AsyncMock(return_value=mock_completion)

        # Setup custom model
        custom_openai = CustomOpenAI(self.text_config)
        custom_openai._client = mock_client

        # Call _generate_text
        model_params = ModelParams(url="https://api.openai.com/v1", auth_token="sk-test")
        model_response = await custom_openai._generate_text(self.chat_input, model_params)

        # Verify results (text should be stripped)
        self.assertEqual(model_response.llm_response, None)
        self.assertEqual(model_response.response_code, 200)
        self.assertEqual(model_response.tool_calls[0]["id"], sample_tool_call.get("id"))
        self.assertEqual(
            model_response.tool_calls[0]["function"]["arguments"],
            sample_tool_call.get("function").get("arguments"),
        )
        self.assertEqual(
            model_response.tool_calls[0]["function"]["name"],
            sample_tool_call.get("function").get("name"),
        )
        self.assertEqual(model_response.tool_calls[0]["type"], sample_tool_call.get("type"))

        # Verify method calls
        mock_set_client.assert_called_once()
        mock_client.build_request.assert_called_once_with(messages=self.messages)
        mock_client.send_request.assert_awaited_once()

    @patch("sygra.core.models.custom_models.BaseCustomModel._set_client")
    def test_generate_text_chat_api_with_tools_success(self, mock_set_client):
        asyncio.run(self._run_generate_text_chat_api_with_tools_success(mock_set_client))

    @patch("sygra.core.models.custom_models.BaseCustomModel._set_client")
    def test_generate_text_chat_api_success(self, mock_set_client):
        asyncio.run(self._run_generate_text_chat_api_success(mock_set_client))

    async def _run_generate_text_completions_api_success(self, mock_set_client, mock_tokenizer):
        """Test _generate_text with completions API"""
        # Setup mock client
        mock_client = MagicMock()
        mock_client.build_request.return_value = {"prompt": "Formatted prompt"}

        # Setup mock completion response for completions API
        mock_choice = MagicMock()
        mock_choice.model_dump.return_value = {"text": "Response text"}
        mock_completion = MagicMock()
        mock_completion.choices = [mock_choice]

        mock_client.send_request = AsyncMock(return_value=mock_completion)

        # Setup custom model with completions API
        custom_openai = CustomOpenAI(self.completions_config)
        custom_openai._client = mock_client
        custom_openai.get_chat_formatted_text = MagicMock(return_value="Formatted prompt")

        # Call _generate_text
        model_params = ModelParams(url="https://api.openai.com/v1", auth_token="sk-test")
        model_response = await custom_openai._generate_text(self.chat_input, model_params)

        # Verify results (text should be stripped)
        self.assertEqual(model_response.llm_response, "Response text")
        self.assertEqual(model_response.response_code, 200)

        # Verify completions API path was used
        custom_openai.get_chat_formatted_text.assert_called_once()
        mock_client.build_request.assert_called_once_with(formatted_prompt="Formatted prompt")

    @patch("sygra.core.models.custom_models.AutoTokenizer")
    @patch("sygra.core.models.custom_models.BaseCustomModel._set_client")
    def test_generate_text_completions_api_success(self, mock_set_client, mock_tokenizer):
        asyncio.run(
            self._run_generate_text_completions_api_success(mock_set_client, mock_tokenizer)
        )

    async def _run_generate_text_rate_limit_error(self, mock_set_client, mock_logger):
        """Test _generate_text with rate limit error"""
        # Setup mock client to raise RateLimitError
        mock_client = MagicMock()
        mock_client.build_request.return_value = {"messages": []}
        mock_client.send_request = AsyncMock(
            side_effect=openai.RateLimitError(
                "Rate limit exceeded", response=MagicMock(), body=None
            )
        )

        # Setup custom model
        custom_openai = CustomOpenAI(self.text_config)
        custom_openai._client = mock_client

        # Call _generate_text
        model_params = ModelParams(url="https://api.openai.com/v1", auth_token="sk-test")
        model_response = await custom_openai._generate_text(self.chat_input, model_params)

        # Verify results - should return 429 for rate limit
        self.assertIn(constants.ERROR_PREFIX, model_response.llm_response)
        self.assertEqual(model_response.response_code, 429)

        # Verify warning logging
        mock_logger.warn.assert_called()
        self.assertIn("rate limit", str(mock_logger.warn.call_args))

    @patch("sygra.core.models.custom_models.logger")
    @patch("sygra.core.models.custom_models.BaseCustomModel._set_client")
    def test_generate_text_rate_limit_error(self, mock_set_client, mock_logger):
        asyncio.run(self._run_generate_text_rate_limit_error(mock_set_client, mock_logger))

    async def _run_generate_text_generic_exception(self, mock_set_client, mock_logger):
        """Test _generate_text with generic exception"""
        # Setup mock client to raise generic exception
        mock_client = MagicMock()
        mock_client.build_request.return_value = {"messages": []}
        mock_client.send_request = AsyncMock(side_effect=Exception("Network timeout"))

        # Setup custom model
        custom_openai = CustomOpenAI(self.text_config)
        custom_openai._client = mock_client
        custom_openai._get_status_from_body = MagicMock(return_value=None)

        # Call _generate_text
        model_params = ModelParams(url="https://api.openai.com/v1", auth_token="sk-test")
        model_response = await custom_openai._generate_text(self.chat_input, model_params)

        # Verify results - should return 999 for generic error
        self.assertIn(constants.ERROR_PREFIX, model_response.llm_response)
        self.assertIn("Network timeout", model_response.llm_response)
        self.assertEqual(model_response.response_code, 999)

    @patch("sygra.core.models.custom_models.logger")
    @patch("sygra.core.models.custom_models.BaseCustomModel._set_client")
    def test_generate_text_generic_exception(self, mock_set_client, mock_logger):
        asyncio.run(self._run_generate_text_generic_exception(mock_set_client, mock_logger))

    # ============== _generate_speech Tests ==============

    async def _run_generate_speech_success_base64(self, mock_set_client):
        """Test _generate_speech returns base64 encoded audio when no output_file"""
        # Setup mock client
        mock_client = MagicMock()
        mock_audio_content = b"fake_audio_data"
        mock_response = MagicMock()
        mock_response.content = mock_audio_content

        mock_client.create_speech = AsyncMock(return_value=mock_response)

        # Setup custom model
        custom_openai = CustomOpenAI(self.tts_config)
        custom_openai._client = mock_client

        # Call _generate_speech
        model_params = ModelParams(url="https://api.openai.com/v1", auth_token="sk-test")
        model_response = await custom_openai._generate_speech(self.tts_input, model_params)

        # Verify results
        expected_base64 = get_audio_url(mock_audio_content, "audio/mpeg")
        self.assertEqual(model_response.llm_response, expected_base64)
        self.assertEqual(model_response.response_code, 200)

        # Verify method calls
        mock_set_client.assert_called_once()
        mock_client.create_speech.assert_awaited_once()

    @patch("sygra.core.models.custom_models.BaseCustomModel._set_client")
    def test_generate_speech_success_base64(self, mock_set_client):
        asyncio.run(self._run_generate_speech_success_base64(mock_set_client))

    async def _run_generate_speech_empty_text(self, mock_logger):
        """Test _generate_speech with empty text"""
        # Setup custom model
        custom_openai = CustomOpenAI(self.tts_config)

        # Create empty input
        empty_input = ChatPromptValue(messages=[HumanMessage(content="")])

        # Call _generate_speech
        model_params = ModelParams(url="https://api.openai.com/v1", auth_token="sk-test")
        model_response = await custom_openai._generate_speech(empty_input, model_params)

        # Verify results
        self.assertIn(constants.ERROR_PREFIX, model_response.llm_response)
        self.assertIn("No text provided", model_response.llm_response)
        self.assertEqual(model_response.response_code, 400)

    @patch("sygra.core.models.custom_models.logger")
    # @patch("sygra.core.models.custom_models.BaseCustomModel._set_client")
    def test_generate_speech_empty_text(self, mock_logger):
        asyncio.run(self._run_generate_speech_empty_text(mock_logger))

    async def _run_generate_speech_text_too_long(self, mock_logger):
        """Test _generate_speech with text exceeding 4096 character limit"""
        # Setup custom model
        custom_openai = CustomOpenAI(self.tts_config)

        # Create input with text > 4096 characters
        long_text = "A" * 5000
        long_input = ChatPromptValue(messages=[HumanMessage(content=long_text)])

        # Call _generate_speech
        model_params = ModelParams(url="https://api.openai.com/v1", auth_token="sk-test")
        await custom_openai._generate_speech(long_input, model_params)

        # Verify warning logging
        mock_logger.warn.assert_called()
        self.assertIn("Text exceeds 4096 character limit", str(mock_logger.warn.call_args))

    @patch("sygra.core.models.custom_models.logger")
    def test_generate_speech_text_too_long(self, mock_logger):
        asyncio.run(self._run_generate_speech_text_too_long(mock_logger))

    async def _run_generate_speech_speed_clamping(self, mock_set_client):
        """Test _generate_speech clamps speed to valid range"""
        # Setup mock client
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.content = b"audio_data"
        mock_client.create_speech = AsyncMock(return_value=mock_response)

        # Test speed too low
        config_low = {**self.tts_config, "parameters": {"speed": 0.1}}
        custom_openai_low = CustomOpenAI(config_low)
        custom_openai_low._client = mock_client

        model_params = ModelParams(url="https://api.openai.com/v1", auth_token="sk-test")
        await custom_openai_low._generate_speech(self.tts_input, model_params)

        # Verify speed was clamped to 0.25
        call_args = mock_client.create_speech.call_args
        self.assertEqual(call_args.kwargs["speed"], 0.25)

        # Test speed too high
        config_high = {**self.tts_config, "parameters": {"speed": 5.0}}
        custom_openai_high = CustomOpenAI(config_high)
        custom_openai_high._client = mock_client

        await custom_openai_high._generate_speech(self.tts_input, model_params)

        # Verify speed was clamped to 4.0
        call_args = mock_client.create_speech.call_args
        self.assertEqual(call_args.kwargs["speed"], 4.0)

    @patch("sygra.core.models.custom_models.BaseCustomModel._set_client")
    def test_generate_speech_speed_clamping(self, mock_set_client):
        asyncio.run(self._run_generate_speech_speed_clamping(mock_set_client))

    async def _run_generate_speech_rate_limit_error(self, mock_set_client, mock_logger):
        """Test _generate_speech with rate limit error"""
        # Setup mock client to raise RateLimitError
        mock_client = MagicMock()
        mock_client.create_speech = AsyncMock(
            side_effect=openai.RateLimitError(
                "Rate limit exceeded", response=MagicMock(), body=None
            )
        )

        # Setup custom model
        custom_openai = CustomOpenAI(self.tts_config)
        custom_openai._client = mock_client

        # Call _generate_speech
        model_params = ModelParams(url="https://api.openai.com/v1", auth_token="sk-test")
        model_response = await custom_openai._generate_speech(self.tts_input, model_params)

        # Verify results
        self.assertIn(constants.ERROR_PREFIX, model_response.llm_response)
        self.assertIn("Rate limit exceeded", model_response.llm_response)
        self.assertEqual(model_response.response_code, 429)

    @patch("sygra.core.models.custom_models.logger")
    @patch("sygra.core.models.custom_models.BaseCustomModel._set_client")
    def test_generate_speech_rate_limit_error(self, mock_set_client, mock_logger):
        asyncio.run(self._run_generate_speech_rate_limit_error(mock_set_client, mock_logger))

    async def _run_generate_speech_api_error(self, mock_set_client, mock_logger):
        """Test _generate_speech with API error"""
        # Setup mock client to raise APIError
        mock_request = MagicMock()
        mock_request.status_code = 500
        api_error = openai.APIError(
            "Internal server error",
            request=mock_request,
            body={"error": {"message": "Internal server error", "type": "api_error"}},
        )
        api_error.status_code = 500

        mock_client = MagicMock()
        mock_client.create_speech = AsyncMock(side_effect=api_error)

        # Setup custom model
        custom_openai = CustomOpenAI(self.tts_config)
        custom_openai._client = mock_client

        # Call _generate_speech
        model_params = ModelParams(url="https://api.openai.com/v1", auth_token="sk-test")
        model_response = await custom_openai._generate_speech(self.tts_input, model_params)

        # Verify results
        self.assertIn(constants.ERROR_PREFIX, model_response.llm_response)
        self.assertIn("API error", model_response.llm_response)
        self.assertEqual(model_response.response_code, 500)

    @patch("sygra.core.models.custom_models.logger")
    @patch("sygra.core.models.custom_models.BaseCustomModel._set_client")
    def test_generate_speech_api_error(self, mock_set_client, mock_logger):
        asyncio.run(self._run_generate_speech_api_error(mock_set_client, mock_logger))

    # ============== _generate_response Routing Tests ==============

    async def _run_generate_response_routes_to_speech(self, mock_set_client):
        """Test _generate_response routes to _generate_speech for audio output"""
        # Setup mock client
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.content = b"audio_data"
        mock_client.create_speech = AsyncMock(return_value=mock_response)

        # Setup custom model with audio output type
        custom_openai = CustomOpenAI(self.tts_config)
        custom_openai._client = mock_client

        # Call _generate_response (should route to _generate_speech)
        model_params = ModelParams(url="https://api.openai.com/v1", auth_token="sk-test")
        model_response = await custom_openai._generate_response(self.tts_input, model_params)

        # Verify it called create_speech (TTS path)
        mock_client.create_speech.assert_awaited_once()
        self.assertEqual(model_response.response_code, 200)

    # ===================== Image Generation Tests =====================

    async def _run_generate_image_success_single(self, mock_set_client):
        """Test _generate_image successfully generates a single image"""
        import base64

        # Setup mock client
        mock_client = MagicMock()
        mock_image_data = b"fake_image_data_png"
        mock_b64 = base64.b64encode(mock_image_data).decode("utf-8")

        # Mock the response structure
        mock_img = MagicMock()
        mock_img.b64_json = mock_b64
        mock_response = MagicMock()
        mock_response.data = [mock_img]

        mock_client.create_image = AsyncMock(return_value=mock_response)

        # Setup custom model
        custom_openai = CustomOpenAI(self.image_config)
        custom_openai._client = mock_client

        # Call _generate_image
        model_params = ModelParams(url="https://api.openai.com/v1", auth_token="sk-test")
        model_response = await custom_openai._generate_image(self.image_input, model_params)

        # Verify results
        self.assertIn("data:image/png;base64,", model_response.llm_response)
        self.assertIn(mock_b64, model_response.llm_response)
        self.assertEqual(model_response.response_code, 200)

        # Verify method calls
        mock_set_client.assert_called_once()
        mock_client.create_image.assert_awaited_once()

    @patch("sygra.core.models.custom_models.BaseCustomModel._set_client")
    def test_generate_image_success_single(self, mock_set_client):
        asyncio.run(self._run_generate_image_success_single(mock_set_client))

    async def _run_generate_image_success_multiple(self, mock_set_client):
        """Test _generate_image successfully generates multiple images (DALL-E-2)"""
        import base64
        import json

        # Setup mock client
        mock_client = MagicMock()
        mock_image_data1 = b"fake_image_data_1"
        mock_image_data2 = b"fake_image_data_2"
        mock_b64_1 = base64.b64encode(mock_image_data1).decode("utf-8")
        mock_b64_2 = base64.b64encode(mock_image_data2).decode("utf-8")

        # Mock the response structure with multiple images
        mock_img1 = MagicMock()
        mock_img1.b64_json = mock_b64_1
        mock_img2 = MagicMock()
        mock_img2.b64_json = mock_b64_2
        mock_response = MagicMock()
        mock_response.data = [mock_img1, mock_img2]

        mock_client.create_image = AsyncMock(return_value=mock_response)

        # Setup custom model with n=2
        config = {**self.image_config, "n": 2, "model": "dall-e-2"}
        custom_openai = CustomOpenAI(config)
        custom_openai._client = mock_client

        # Call _generate_image
        model_params = ModelParams(url="https://api.openai.com/v1", auth_token="sk-test")
        model_response = await custom_openai._generate_image(self.image_input, model_params)

        # Verify results
        result = json.loads(model_response.llm_response)
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 2)
        self.assertIn("data:image/png;base64,", result[0])
        self.assertIn("data:image/png;base64,", result[1])
        self.assertEqual(model_response.response_code, 200)

    @patch("sygra.core.models.custom_models.BaseCustomModel._set_client")
    def test_generate_image_success_multiple(self, mock_set_client):
        asyncio.run(self._run_generate_image_success_multiple(mock_set_client))

    async def _run_generate_image_with_different_sizes(self, mock_set_client):
        """Test _generate_image with different size parameters"""
        import base64

        sizes = ["256x256", "512x512", "1024x1024", "1792x1024", "1024x1792"]

        for size in sizes:
            # Setup mock client
            mock_client = MagicMock()
            mock_image_data = b"fake_image_data"
            mock_b64 = base64.b64encode(mock_image_data).decode("utf-8")

            mock_img = MagicMock()
            mock_img.b64_json = mock_b64
            mock_response = MagicMock()
            mock_response.data = [mock_img]

            mock_client.create_image = AsyncMock(return_value=mock_response)

            # Setup custom model with specific size
            config = {**self.image_config, "parameters": {"size": size}}
            custom_openai = CustomOpenAI(config)
            custom_openai._client = mock_client

            # Call _generate_image
            model_params = ModelParams(url="https://api.openai.com/v1", auth_token="sk-test")
            model_response = await custom_openai._generate_image(self.image_input, model_params)

            # Verify results
            self.assertIn("data:image/png;base64,", model_response.llm_response)
            self.assertEqual(model_response.response_code, 200)

            # Verify create_image was called and size was passed via kwargs
            mock_client.create_image.assert_called_once()
            # Size is in generation_params which gets passed via **params
            call_kwargs = mock_client.create_image.call_args.kwargs
            self.assertIn("size", call_kwargs)
            self.assertEqual(call_kwargs["size"], size)

    @patch("sygra.core.models.custom_models.BaseCustomModel._set_client")
    def test_generate_image_with_different_sizes(self, mock_set_client):
        asyncio.run(self._run_generate_image_with_different_sizes(mock_set_client))

    async def _run_generate_image_with_quality_hd(self, mock_set_client):
        """Test _generate_image with HD quality"""
        import base64

        # Setup mock client
        mock_client = MagicMock()
        mock_image_data = b"fake_hd_image_data"
        mock_b64 = base64.b64encode(mock_image_data).decode("utf-8")

        mock_img = MagicMock()
        mock_img.b64_json = mock_b64
        mock_response = MagicMock()
        mock_response.data = [mock_img]

        mock_client.create_image = AsyncMock(return_value=mock_response)

        # Setup custom model with HD quality
        config = {**self.image_config, "parameters": {"quality": "hd"}}
        custom_openai = CustomOpenAI(config)
        custom_openai._client = mock_client

        # Call _generate_image
        model_params = ModelParams(url="https://api.openai.com/v1", auth_token="sk-test")
        model_response = await custom_openai._generate_image(self.image_input, model_params)

        # Verify results
        self.assertEqual(model_response.response_code, 200)

        # Verify create_image was called with HD quality
        mock_client.create_image.assert_called_once()
        call_kwargs = mock_client.create_image.call_args.kwargs
        self.assertIn("quality", call_kwargs)
        self.assertEqual(call_kwargs["quality"], "hd")

    @patch("sygra.core.models.custom_models.BaseCustomModel._set_client")
    def test_generate_image_with_quality_hd(self, mock_set_client):
        asyncio.run(self._run_generate_image_with_quality_hd(mock_set_client))

    async def _run_generate_image_with_different_styles(self, mock_set_client):
        """Test _generate_image with different style parameters"""
        import base64

        styles = ["vivid", "natural"]

        for style in styles:
            # Setup mock client
            mock_client = MagicMock()
            mock_image_data = b"fake_image_data"
            mock_b64 = base64.b64encode(mock_image_data).decode("utf-8")

            mock_img = MagicMock()
            mock_img.b64_json = mock_b64
            mock_response = MagicMock()
            mock_response.data = [mock_img]

            mock_client.create_image = AsyncMock(return_value=mock_response)

            # Setup custom model with specific style
            config = {**self.image_config, "parameters": {"style": style}}
            custom_openai = CustomOpenAI(config)
            custom_openai._client = mock_client

            # Call _generate_image
            model_params = ModelParams(url="https://api.openai.com/v1", auth_token="sk-test")
            model_response = await custom_openai._generate_image(self.image_input, model_params)

            # Verify results
            self.assertEqual(model_response.response_code, 200)

            # Verify create_image was called with the correct style
            mock_client.create_image.assert_called_once()
            call_kwargs = mock_client.create_image.call_args.kwargs
            self.assertIn("style", call_kwargs)
            self.assertEqual(call_kwargs["style"], style)

    @patch("sygra.core.models.custom_models.BaseCustomModel._set_client")
    def test_generate_image_with_different_styles(self, mock_set_client):
        asyncio.run(self._run_generate_image_with_different_styles(mock_set_client))

    async def _run_generate_image_empty_prompt(self, mock_set_client):
        """Test _generate_image with empty prompt returns error"""
        # Setup mock client
        mock_client = MagicMock()

        # Setup custom model
        custom_openai = CustomOpenAI(self.image_config)
        custom_openai._client = mock_client

        # Create empty prompt
        empty_messages = [HumanMessage(content="")]
        empty_input = ChatPromptValue(messages=empty_messages)

        # Call _generate_image
        model_params = ModelParams(url="https://api.openai.com/v1", auth_token="sk-test")
        model_response = await custom_openai._generate_image(empty_input, model_params)

        # Verify error response
        self.assertIn("No prompt provided", model_response.llm_response)
        self.assertEqual(model_response.response_code, 400)

    @patch("sygra.core.models.custom_models.BaseCustomModel._set_client")
    def test_generate_image_empty_prompt(self, mock_set_client):
        asyncio.run(self._run_generate_image_empty_prompt(mock_set_client))

    async def _run_generate_image_rate_limit_error(self, mock_set_client):
        """Test _generate_image handles rate limit errors"""
        # Setup mock client
        mock_client = MagicMock()
        rate_limit_error = openai.RateLimitError(
            "Rate limit exceeded",
            response=MagicMock(status_code=429),
            body=None,
        )
        mock_client.create_image = AsyncMock(side_effect=rate_limit_error)

        # Setup custom model
        custom_openai = CustomOpenAI(self.image_config)
        custom_openai._client = mock_client

        # Call _generate_image
        model_params = ModelParams(url="https://api.openai.com/v1", auth_token="sk-test")
        model_response = await custom_openai._generate_image(self.image_input, model_params)

        # Verify error handling
        self.assertIn("Rate limit exceeded", model_response.llm_response)
        self.assertEqual(model_response.response_code, 429)

    @patch("sygra.core.models.custom_models.BaseCustomModel._set_client")
    def test_generate_image_rate_limit_error(self, mock_set_client):
        asyncio.run(self._run_generate_image_rate_limit_error(mock_set_client))

    async def _run_generate_image_bad_request_error(self, mock_set_client):
        """Test _generate_image handles bad request errors"""
        # Setup mock client
        mock_client = MagicMock()
        bad_request_error = openai.BadRequestError(
            "Invalid size parameter",
            response=MagicMock(status_code=400),
            body=None,
        )
        mock_client.create_image = AsyncMock(side_effect=bad_request_error)

        # Setup custom model
        custom_openai = CustomOpenAI(self.image_config)
        custom_openai._client = mock_client

        # Call _generate_image
        model_params = ModelParams(url="https://api.openai.com/v1", auth_token="sk-test")
        model_response = await custom_openai._generate_image(self.image_input, model_params)

        # Verify error handling
        self.assertIn("Bad request", model_response.llm_response)
        self.assertEqual(model_response.response_code, 400)

    @patch("sygra.core.models.custom_models.BaseCustomModel._set_client")
    def test_generate_image_bad_request_error(self, mock_set_client):
        asyncio.run(self._run_generate_image_bad_request_error(mock_set_client))

    async def _run_generate_image_api_error(self, mock_set_client):
        """Test _generate_image handles API errors"""
        # Setup mock client
        mock_client = MagicMock()
        mock_request = MagicMock()
        mock_request.status_code = 500
        api_error = openai.APIError(
            "Internal server error",
            request=mock_request,
            body={"error": {"message": "Internal server error", "type": "api_error"}},
        )
        api_error.status_code = 500
        mock_client.create_image = AsyncMock(side_effect=api_error)

        # Setup custom model
        custom_openai = CustomOpenAI(self.image_config)
        custom_openai._client = mock_client

        # Call _generate_image
        model_params = ModelParams(url="https://api.openai.com/v1", auth_token="sk-test")
        model_response = await custom_openai._generate_image(self.image_input, model_params)

        # Verify error handling
        self.assertIn("API error", model_response.llm_response)
        self.assertEqual(model_response.response_code, 500)

    @patch("sygra.core.models.custom_models.BaseCustomModel._set_client")
    def test_generate_image_api_error(self, mock_set_client):
        asyncio.run(self._run_generate_image_api_error(mock_set_client))

    async def _run_generate_response_routes_to_image(self, mock_set_client):
        """Test _generate_response correctly routes to _generate_image when output_type is 'image'"""
        import base64

        # Setup mock client
        mock_client = MagicMock()
        mock_image_data = b"fake_image_data"
        mock_b64 = base64.b64encode(mock_image_data).decode("utf-8")

        mock_img = MagicMock()
        mock_img.b64_json = mock_b64
        mock_response = MagicMock()
        mock_response.data = [mock_img]

        mock_client.create_image = AsyncMock(return_value=mock_response)

        # Setup custom model with image output type
        custom_openai = CustomOpenAI(self.image_config)
        custom_openai._client = mock_client

        # Call _generate_response (should route to _generate_image)
        model_params = ModelParams(url="https://api.openai.com/v1", auth_token="sk-test")
        model_response = await custom_openai._generate_response(self.image_input, model_params)

        # Verify it called create_image (image generation path)
        mock_client.create_image.assert_awaited_once()
        self.assertEqual(model_response.response_code, 200)

    @patch("sygra.core.models.custom_models.BaseCustomModel._set_client")
    def test_generate_response_routes_to_image(self, mock_set_client):
        asyncio.run(self._run_generate_response_routes_to_image(mock_set_client))

    @patch("sygra.core.models.custom_models.BaseCustomModel._set_client")
    def test_generate_response_routes_to_speech(self, mock_set_client):
        asyncio.run(self._run_generate_response_routes_to_speech(mock_set_client))

    # ===== Image Editing Tests =====

    async def _run_edit_image_single_dalle2(self, mock_set_client):
        """Test single image editing with DALL-E-2"""
        import base64

        # Sample image data URL
        sample_image = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="

        # Create input with image and text
        from langchain.schema import HumanMessage

        messages_with_image = [
            HumanMessage(
                content=[
                    {"type": "image_url", "image_url": sample_image},
                    {"type": "text", "text": "Remove the background"},
                ]
            )
        ]
        image_edit_input = ChatPromptValue(messages=messages_with_image)

        # Setup mock client
        mock_client = MagicMock()
        mock_image_data = b"fake_edited_image"
        mock_b64 = base64.b64encode(mock_image_data).decode("utf-8")

        mock_img = MagicMock()
        mock_img.b64_json = mock_b64
        mock_response = MagicMock()
        mock_response.data = [mock_img]

        mock_client.edit_image = AsyncMock(return_value=mock_response)

        # Setup custom model for DALL-E-2
        config = {**self.image_config, "model": "dall-e-2"}
        custom_openai = CustomOpenAI(config)
        custom_openai._client = mock_client

        # Call _generate_image (should auto-detect and route to editing)
        model_params = ModelParams(url="https://api.openai.com/v1", auth_token="sk-test")
        model_response = await custom_openai._generate_image(image_edit_input, model_params)

        # Verify results
        self.assertIn("data:image/png;base64,", model_response.llm_response)
        self.assertEqual(model_response.response_code, 200)

        # Verify edit_image was called (not create_image)
        mock_client.edit_image.assert_called_once()

    @patch("sygra.core.models.custom_models.BaseCustomModel._set_client")
    def test_edit_image_single_dalle2(self, mock_set_client):
        asyncio.run(self._run_edit_image_single_dalle2(mock_set_client))

    async def _run_edit_image_multiple_gpt_image_1(self, mock_set_client):
        """Test multi-image editing with GPT-Image-1 (2-16 images)"""
        import base64
        import json

        # Sample image data URLs (3 images)
        sample_image_1 = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
        sample_image_2 = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8/5+hHgAHggJ/PchI7wAAAABJRU5ErkJggg=="
        sample_image_3 = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChAHgFPU/tQAAAABJRU5ErkJggg=="

        # Create input with multiple images and text
        from langchain.schema import HumanMessage

        messages_with_images = [
            HumanMessage(
                content=[
                    {"type": "image_url", "image_url": sample_image_1},
                    {"type": "image_url", "image_url": sample_image_2},
                    {"type": "image_url", "image_url": sample_image_3},
                    {"type": "text", "text": "Combine into a collage"},
                ]
            )
        ]
        image_edit_input = ChatPromptValue(messages=messages_with_images)

        # Setup mock client
        mock_client = MagicMock()
        mock_image_data1 = b"fake_edited_image_1"
        mock_image_data2 = b"fake_edited_image_2"
        mock_b64_1 = base64.b64encode(mock_image_data1).decode("utf-8")
        mock_b64_2 = base64.b64encode(mock_image_data2).decode("utf-8")

        mock_img1 = MagicMock()
        mock_img1.b64_json = mock_b64_1
        mock_img2 = MagicMock()
        mock_img2.b64_json = mock_b64_2
        mock_response = MagicMock()
        mock_response.data = [mock_img1, mock_img2]

        mock_client.edit_image = AsyncMock(return_value=mock_response)

        # Setup custom model for GPT-Image-1
        config = {**self.image_config, "model": "gpt-image-1", "n": 2}
        custom_openai = CustomOpenAI(config)
        custom_openai._client = mock_client

        # Call _generate_image
        model_params = ModelParams(url="https://api.openai.com/v1", auth_token="sk-test")
        model_response = await custom_openai._generate_image(image_edit_input, model_params)

        # Verify results - should return multiple images
        result = json.loads(model_response.llm_response)
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 2)
        self.assertEqual(model_response.response_code, 200)

        # Verify edit_image was called with list of images
        mock_client.edit_image.assert_called_once()
        call_args = mock_client.edit_image.call_args
        self.assertIsInstance(call_args.kwargs["image"], list)
        self.assertEqual(len(call_args.kwargs["image"]), 3)  # 3 input images

    @patch("sygra.core.models.custom_models.BaseCustomModel._set_client")
    def test_edit_image_multiple_gpt_image_1(self, mock_set_client):
        asyncio.run(self._run_edit_image_multiple_gpt_image_1(mock_set_client))

    async def _run_edit_image_more_than_16_images(self, mock_set_client):
        """Test that >16 images are trimmed to 16 for GPT-Image-1"""
        import base64

        # Create 20 image data URLs
        sample_image = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="

        # Create input with 20 images
        from langchain.schema import HumanMessage

        image_items = [{"type": "image_url", "image_url": sample_image} for _ in range(20)]
        image_items.append({"type": "text", "text": "Create a grid"})
        messages_with_many_images = [HumanMessage(content=image_items)]
        image_edit_input = ChatPromptValue(messages=messages_with_many_images)

        # Setup mock client
        mock_client = MagicMock()
        mock_image_data = b"fake_edited_image"
        mock_b64 = base64.b64encode(mock_image_data).decode("utf-8")

        mock_img = MagicMock()
        mock_img.b64_json = mock_b64
        mock_response = MagicMock()
        mock_response.data = [mock_img]

        mock_client.edit_image = AsyncMock(return_value=mock_response)

        # Setup custom model for GPT-Image-1
        config = {**self.image_config, "model": "gpt-image-1"}
        custom_openai = CustomOpenAI(config)
        custom_openai._client = mock_client

        # Call _generate_image
        model_params = ModelParams(url="https://api.openai.com/v1", auth_token="sk-test")

        with patch("sygra.core.models.custom_models.logger") as mock_logger:
            model_response = await custom_openai._generate_image(image_edit_input, model_params)

            # Verify warning was logged
            mock_logger.warning.assert_called_once()
            warning_msg = mock_logger.warning.call_args[0][0]
            self.assertIn("supports max 16 images", warning_msg)
            self.assertIn("4 image(s) will be ignored", warning_msg)

        # Verify only 16 images were passed to API
        call_args = mock_client.edit_image.call_args
        self.assertEqual(len(call_args.kwargs["image"]), 16)
        self.assertEqual(model_response.response_code, 200)

    @patch("sygra.core.models.custom_models.BaseCustomModel._set_client")
    def test_edit_image_more_than_16_images(self, mock_set_client):
        asyncio.run(self._run_edit_image_more_than_16_images(mock_set_client))

    async def _run_edit_image_multiple_with_dalle2_warns(self, mock_set_client):
        """Test that DALL-E-2 warns and uses only first image when given multiple"""
        import base64

        # Create input with 3 images
        sample_image_1 = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
        sample_image_2 = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8/5+hHgAHggJ/PchI7wAAAABJRU5ErkJggg=="
        sample_image_3 = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChAHgFPU/tQAAAABJRU5ErkJggg=="

        from langchain.schema import HumanMessage

        messages_with_images = [
            HumanMessage(
                content=[
                    {"type": "image_url", "image_url": sample_image_1},
                    {"type": "image_url", "image_url": sample_image_2},
                    {"type": "image_url", "image_url": sample_image_3},
                    {"type": "text", "text": "Edit this"},
                ]
            )
        ]
        image_edit_input = ChatPromptValue(messages=messages_with_images)

        # Setup mock client
        mock_client = MagicMock()
        mock_image_data = b"fake_edited_image"
        mock_b64 = base64.b64encode(mock_image_data).decode("utf-8")

        mock_img = MagicMock()
        mock_img.b64_json = mock_b64
        mock_response = MagicMock()
        mock_response.data = [mock_img]

        mock_client.edit_image = AsyncMock(return_value=mock_response)

        # Setup custom model for DALL-E-2 (single image only)
        config = {**self.image_config, "model": "dall-e-2"}
        custom_openai = CustomOpenAI(config)
        custom_openai._client = mock_client

        # Call _generate_image
        model_params = ModelParams(url="https://api.openai.com/v1", auth_token="sk-test")

        with patch("sygra.core.models.custom_models.logger") as mock_logger:
            model_response = await custom_openai._generate_image(image_edit_input, model_params)

            # Verify warning was logged
            mock_logger.warning.assert_called_once()
            warning_msg = mock_logger.warning.call_args[0][0]
            self.assertIn("only supports single image editing", warning_msg)
            self.assertIn("2 image(s) will be ignored", warning_msg)

        self.assertEqual(model_response.response_code, 200)

    @patch("sygra.core.models.custom_models.BaseCustomModel._set_client")
    def test_edit_image_multiple_with_dalle2_warns(self, mock_set_client):
        asyncio.run(self._run_edit_image_multiple_with_dalle2_warns(mock_set_client))

    async def _run_edit_image_empty_prompt(self, mock_set_client):
        """Test error when no edit instruction provided"""
        # Sample image but no text prompt
        sample_image = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="

        from langchain.schema import HumanMessage

        # Only image, no text
        messages_image_only = [
            HumanMessage(content=[{"type": "image_url", "image_url": sample_image}])
        ]
        image_edit_input = ChatPromptValue(messages=messages_image_only)

        # Setup custom model
        config = {**self.image_config, "model": "dall-e-2"}
        custom_openai = CustomOpenAI(config)

        # Call _generate_image
        model_params = ModelParams(url="https://api.openai.com/v1", auth_token="sk-test")
        model_response = await custom_openai._generate_image(image_edit_input, model_params)

        # Verify error response
        self.assertIn("###SERVER_ERROR###", model_response.llm_response)
        self.assertIn("No prompt provided", model_response.llm_response)
        self.assertEqual(model_response.response_code, 400)

    @patch("sygra.core.models.custom_models.BaseCustomModel._set_client")
    def test_edit_image_empty_prompt(self, mock_set_client):
        asyncio.run(self._run_edit_image_empty_prompt(mock_set_client))

    async def _run_edit_image_no_images_routes_to_generation(self, mock_set_client):
        """Test that input without images routes to generation (not editing)"""
        import base64

        # Text prompt only, no images
        from langchain.schema import HumanMessage

        messages_text_only = [HumanMessage(content="Generate a sunset")]
        text_only_input = ChatPromptValue(messages=messages_text_only)

        # Setup mock client
        mock_client = MagicMock()
        mock_image_data = b"fake_generated_image"
        mock_b64 = base64.b64encode(mock_image_data).decode("utf-8")

        mock_img = MagicMock()
        mock_img.b64_json = mock_b64
        mock_response = MagicMock()
        mock_response.data = [mock_img]

        # Mock create_image (generation)
        mock_client.create_image = AsyncMock(return_value=mock_response)
        # Mock edit_image (should NOT be called)
        mock_client.edit_image = AsyncMock(return_value=mock_response)

        # Setup custom model
        config = {**self.image_config, "model": "dall-e-3"}
        custom_openai = CustomOpenAI(config)
        custom_openai._client = mock_client

        # Call _generate_image
        model_params = ModelParams(url="https://api.openai.com/v1", auth_token="sk-test")
        model_response = await custom_openai._generate_image(text_only_input, model_params)

        # Verify create_image was called (generation), NOT edit_image
        mock_client.create_image.assert_called_once()
        mock_client.edit_image.assert_not_called()
        self.assertEqual(model_response.response_code, 200)

    @patch("sygra.core.models.custom_models.BaseCustomModel._set_client")
    def test_edit_image_no_images_routes_to_generation(self, mock_set_client):
        asyncio.run(self._run_edit_image_no_images_routes_to_generation(mock_set_client))

    # ============ GPT-4O-AUDIO TESTS ============

    async def _run_audio_chat_text_to_text(self, mock_set_client):
        """Test gpt-4o-audio with text input, text output"""
        import base64

        # Setup config for gpt-4o-audio
        audio_chat_config = {
            "name": "gpt4o_audio_model",
            "model": "gpt-4o-audio-preview",
            "url": "https://api.openai.com/v1",
            "auth_token": "Bearer sk-test_key_123",
            "api_version": "2023-05-15",
            "parameters": {"temperature": 0.7},
        }

        # Mock messages - text only
        messages = [HumanMessage(content="Hello, how are you?")]
        chat_input = ChatPromptValue(messages=messages)

        # Setup mock client
        mock_client = MagicMock()
        
        # Mock build_request to return properly formatted messages
        mock_client.build_request = MagicMock(return_value={
            "messages": [{"role": "user", "content": "Hello, how are you?"}]
        })
        
        mock_choice = MagicMock()
        mock_choice.model_dump.return_value = {
            "message": {"content": "I'm doing well, thank you!"}
        }
        mock_completion = MagicMock()
        mock_completion.choices = [mock_choice]

        mock_client.send_request = AsyncMock(return_value=mock_completion)

        # Create custom model
        custom_openai = CustomOpenAI(audio_chat_config)
        custom_openai._client = mock_client

        # Call _generate_response
        model_params = ModelParams(url="https://api.openai.com/v1", auth_token="sk-test")
        response = await custom_openai._generate_response(chat_input, model_params)

        # Verify it routed to audio chat completion
        self.assertEqual(response.response_code, 200)
        self.assertEqual(response.llm_response, "I'm doing well, thank you!")
        mock_client.send_request.assert_called_once()

        # Verify payload structure
        call_args = mock_client.send_request.call_args
        payload = call_args[0][0]
        self.assertIn("messages", payload)
        self.assertEqual(len(payload["messages"]), 1)

    @patch("sygra.core.models.custom_models.BaseCustomModel._set_client")
    def test_audio_chat_text_to_text(self, mock_set_client):
        """Test gpt-4o-audio routes correctly and handles text-to-text"""
        asyncio.run(self._run_audio_chat_text_to_text(mock_set_client))

    async def _run_audio_chat_text_to_audio(self, mock_set_client):
        """Test gpt-4o-audio with text input, audio output"""
        import base64

        # Setup config for gpt-4o-audio with audio output
        audio_chat_config = {
            "name": "gpt4o_audio_model",
            "model": "gpt-4o-audio-preview",
            "output_type": "audio",
            "url": "https://api.openai.com/v1",
            "auth_token": "Bearer sk-test_key_123",
            "api_version": "2023-05-15",
            "parameters": {
                "audio": {
                    "voice": "alloy",
                    "format": "wav",
                }
            },
        }

        # Mock messages - text only
        messages = [HumanMessage(content="Say hello")]
        chat_input = ChatPromptValue(messages=messages)

        # Setup mock client with audio response
        mock_client = MagicMock()
        
        # Mock build_request to return properly formatted messages
        mock_client.build_request = MagicMock(return_value={
            "messages": [{"role": "user", "content": "Say hello"}]
        })
        
        fake_audio_data = b"fake_audio_bytes"
        audio_base64 = base64.b64encode(fake_audio_data).decode("utf-8")

        mock_choice = MagicMock()
        mock_choice.model_dump.return_value = {
            "message": {
                "content": "Hello there!",
                "audio": {"data": audio_base64, "format": "wav"},
            }
        }
        mock_completion = MagicMock()
        mock_completion.choices = [mock_choice]

        mock_client.send_request = AsyncMock(return_value=mock_completion)

        # Create custom model
        custom_openai = CustomOpenAI(audio_chat_config)
        custom_openai._client = mock_client

        # Call _generate_response
        model_params = ModelParams(url="https://api.openai.com/v1", auth_token="sk-test")
        response = await custom_openai._generate_response(chat_input, model_params)

        # Verify audio data URL was returned
        self.assertEqual(response.response_code, 200)
        self.assertTrue(response.llm_response.startswith("data:audio/wav;base64,"))
        self.assertIn(audio_base64, response.llm_response)

        # Verify payload included modalities
        call_args = mock_client.send_request.call_args
        payload = call_args[0][0]
        self.assertIn("modalities", payload)
        self.assertIn("audio", payload["modalities"])
        
        # Verify audio params are in gen_params (3rd argument to send_request)
        gen_params = call_args[0][2]
        self.assertIn("audio", gen_params)
        self.assertEqual(gen_params["audio"]["voice"], "alloy")
        self.assertEqual(gen_params["audio"]["format"], "wav")

    @patch("sygra.core.models.custom_models.BaseCustomModel._set_client")
    def test_audio_chat_text_to_audio(self, mock_set_client):
        """Test gpt-4o-audio text-to-audio generation"""
        asyncio.run(self._run_audio_chat_text_to_audio(mock_set_client))

    async def _run_audio_chat_audio_to_text(self, mock_set_client):
        """Test gpt-4o-audio with audio input, text output (transcription)"""
        import base64

        # Setup config for gpt-4o-audio
        audio_chat_config = {
            "name": "gpt4o_audio_model",
            "model": "gpt-4o-audio-preview",
            "input_type": "audio",
            "url": "https://api.openai.com/v1",
            "auth_token": "Bearer sk-test_key_123",
            "api_version": "2023-05-15",
            "parameters": {},
        }

        # Create mock audio data URL
        fake_audio = b"fake_wav_audio_data"
        audio_b64 = base64.b64encode(fake_audio).decode("utf-8")
        audio_data_url = f"data:audio/wav;base64,{audio_b64}"

        # Mock messages with audio input
        messages = [
            HumanMessage(
                content=[
                    {"type": "audio_url", "audio_url": {"url": audio_data_url}},
                    {"type": "text", "text": "Transcribe this audio"},
                ]
            )
        ]
        chat_input = ChatPromptValue(messages=messages)

        # Setup mock client
        mock_client = MagicMock()
        
        # Mock build_request to return properly formatted messages
        mock_client.build_request = MagicMock(return_value={
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "audio_url", "audio_url": {"url": audio_data_url}},
                        {"type": "text", "text": "Transcribe this audio"},
                    ]
                }
            ]
        })
        
        mock_choice = MagicMock()
        mock_choice.model_dump.return_value = {
            "message": {"content": "This is the transcribed text."}
        }
        mock_completion = MagicMock()
        mock_completion.choices = [mock_choice]

        mock_client.send_request = AsyncMock(return_value=mock_completion)

        # Create custom model
        custom_openai = CustomOpenAI(audio_chat_config)
        custom_openai._client = mock_client

        # Call _generate_response
        model_params = ModelParams(url="https://api.openai.com/v1", auth_token="sk-test")
        response = await custom_openai._generate_response(chat_input, model_params)

        # Verify transcription returned
        self.assertEqual(response.response_code, 200)
        self.assertEqual(response.llm_response, "This is the transcribed text.")

        # Verify audio was converted to input_audio format
        call_args = mock_client.send_request.call_args
        payload = call_args[0][0]
        messages_sent = payload["messages"]
        self.assertEqual(len(messages_sent), 1)

        # Check that audio_url was converted to input_audio
        content = messages_sent[0]["content"]
        self.assertTrue(any(item.get("type") == "input_audio" for item in content))

        # Find the input_audio item
        audio_item = next(item for item in content if item.get("type") == "input_audio")
        self.assertIn("input_audio", audio_item)
        self.assertIn("data", audio_item["input_audio"])
        self.assertIn("format", audio_item["input_audio"])
        self.assertEqual(audio_item["input_audio"]["format"], "wav")

    @patch("sygra.core.models.custom_models.BaseCustomModel._set_client")
    def test_audio_chat_audio_to_text(self, mock_set_client):
        """Test gpt-4o-audio audio-to-text (transcription)"""
        asyncio.run(self._run_audio_chat_audio_to_text(mock_set_client))

    async def _run_audio_chat_audio_to_audio(self, mock_set_client):
        """Test gpt-4o-audio with audio input, audio output"""
        import base64

        # Setup config for gpt-4o-audio with audio I/O
        audio_chat_config = {
            "name": "gpt4o_audio_model",
            "model": "gpt-4o-audio-preview",
            "input_type": "audio",
            "output_type": "audio",
            "url": "https://api.openai.com/v1",
            "auth_token": "Bearer sk-test_key_123",
            "api_version": "2023-05-15",
            "parameters": {
                "audio": {
                    "voice": "nova",
                    "format": "mp3",
                }
            },
        }

        # Create mock audio input
        fake_input_audio = b"fake_input_wav"
        input_audio_b64 = base64.b64encode(fake_input_audio).decode("utf-8")
        input_audio_url = f"data:audio/wav;base64,{input_audio_b64}"

        # Mock messages with audio input
        messages = [
            HumanMessage(
                content=[
                    {"type": "audio_url", "audio_url": {"url": input_audio_url}},
                    {"type": "text", "text": "Translate this to English"},
                ]
            )
        ]
        chat_input = ChatPromptValue(messages=messages)

        # Setup mock client with audio response
        mock_client = MagicMock()
        
        # Mock build_request to return properly formatted messages
        mock_client.build_request = MagicMock(return_value={
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "audio_url", "audio_url": {"url": input_audio_url}},
                        {"type": "text", "text": "Translate this to English"},
                    ]
                }
            ]
        })
        
        fake_output_audio = b"fake_output_mp3"
        output_audio_b64 = base64.b64encode(fake_output_audio).decode("utf-8")

        mock_choice = MagicMock()
        mock_choice.model_dump.return_value = {
            "message": {
                "content": "Translated text",
                "audio": {"data": output_audio_b64, "format": "mp3"},
            }
        }
        mock_completion = MagicMock()
        mock_completion.choices = [mock_choice]

        mock_client.send_request = AsyncMock(return_value=mock_completion)

        # Create custom model
        custom_openai = CustomOpenAI(audio_chat_config)
        custom_openai._client = mock_client

        # Call _generate_response
        model_params = ModelParams(url="https://api.openai.com/v1", auth_token="sk-test")
        response = await custom_openai._generate_response(chat_input, model_params)

        # Verify audio output returned
        self.assertEqual(response.response_code, 200)
        # MP3 format uses audio/mpeg MIME type
        self.assertTrue(response.llm_response.startswith("data:audio/mpeg;base64,"))
        self.assertIn(output_audio_b64, response.llm_response)

        # Verify payload included modalities for audio output
        call_args = mock_client.send_request.call_args
        payload = call_args[0][0]
        self.assertIn("modalities", payload)
        self.assertIn("audio", payload["modalities"])

    @patch("sygra.core.models.custom_models.BaseCustomModel._set_client")
    def test_audio_chat_audio_to_audio(self, mock_set_client):
        """Test gpt-4o-audio audio-to-audio (translation/transformation)"""
        asyncio.run(self._run_audio_chat_audio_to_audio(mock_set_client))

    async def _run_audio_chat_rate_limit_error(self, mock_set_client):
        """Test gpt-4o-audio handles rate limit errors"""
        # Setup config
        audio_chat_config = {
            "name": "gpt4o_audio_model",
            "model": "gpt-4o-audio-preview",
            "url": "https://api.openai.com/v1",
            "auth_token": "Bearer sk-test_key_123",
            "api_version": "2023-05-15",
            "parameters": {},
        }

        messages = [HumanMessage(content="Test message")]
        chat_input = ChatPromptValue(messages=messages)

        # Setup mock client to raise rate limit error
        mock_client = MagicMock()
        
        # Mock build_request to return properly formatted messages
        mock_client.build_request = MagicMock(return_value={
            "messages": [{"role": "user", "content": "Test message"}]
        })
        
        rate_limit_error = openai.RateLimitError(
            "Rate limit exceeded",
            response=MagicMock(status_code=429),
            body=None,
        )
        mock_client.send_request = AsyncMock(side_effect=rate_limit_error)

        custom_openai = CustomOpenAI(audio_chat_config)
        custom_openai._client = mock_client

        model_params = ModelParams(url="https://api.openai.com/v1", auth_token="sk-test")
        response = await custom_openai._generate_response(chat_input, model_params)

        # Verify error handling
        self.assertEqual(response.response_code, 429)
        self.assertIn("###SERVER_ERROR###", response.llm_response)
        self.assertIn("Rate limit exceeded", response.llm_response)

    @patch("sygra.core.models.custom_models.BaseCustomModel._set_client")
    def test_audio_chat_rate_limit_error(self, mock_set_client):
        """Test gpt-4o-audio rate limit error handling"""
        asyncio.run(self._run_audio_chat_rate_limit_error(mock_set_client))

    async def _run_audio_chat_bad_request_error(self, mock_set_client):
        """Test gpt-4o-audio handles bad request errors"""
        audio_chat_config = {
            "name": "gpt4o_audio_model",
            "model": "gpt-4o-audio-preview",
            "url": "https://api.openai.com/v1",
            "auth_token": "Bearer sk-test_key_123",
            "api_version": "2023-05-15",
            "parameters": {},
        }

        messages = [HumanMessage(content="Test")]
        chat_input = ChatPromptValue(messages=messages)

        # Setup mock client to raise bad request error
        mock_client = MagicMock()
        
        # Mock build_request to return properly formatted messages
        mock_client.build_request = MagicMock(return_value={
            "messages": [{"role": "user", "content": "Test"}]
        })
        
        bad_request_error = openai.BadRequestError(
            "Invalid audio format",
            response=MagicMock(status_code=400),
            body=None,
        )
        mock_client.send_request = AsyncMock(side_effect=bad_request_error)

        custom_openai = CustomOpenAI(audio_chat_config)
        custom_openai._client = mock_client

        model_params = ModelParams(url="https://api.openai.com/v1", auth_token="sk-test")
        response = await custom_openai._generate_response(chat_input, model_params)

        # Verify error handling
        self.assertEqual(response.response_code, 400)
        self.assertIn("###SERVER_ERROR###", response.llm_response)
        self.assertIn("Bad request", response.llm_response)

    @patch("sygra.core.models.custom_models.BaseCustomModel._set_client")
    def test_audio_chat_bad_request_error(self, mock_set_client):
        """Test gpt-4o-audio bad request error handling"""
        asyncio.run(self._run_audio_chat_bad_request_error(mock_set_client))

    async def _run_audio_chat_model_detection(self, mock_set_client):
        """Test that gpt-4o-audio model is correctly detected and routed"""
        # Test various model name variations
        model_names = [
            "gpt-4o-audio-preview",
            "gpt-4o-audio-preview-2024-10-01",
            "GPT-4O-AUDIO-PREVIEW",  # Case insensitive
        ]

        for model_name in model_names:
            audio_chat_config = {
                "name": "test_model",
                "model": model_name,
                "url": "https://api.openai.com/v1",
                "auth_token": "Bearer sk-test_key_123",
                "api_version": "2023-05-15",
                "parameters": {},
            }

            messages = [HumanMessage(content="Test")]
            chat_input = ChatPromptValue(messages=messages)

            # Setup mock client
            mock_client = MagicMock()
            
            # Mock build_request to return properly formatted messages
            mock_client.build_request = MagicMock(return_value={
                "messages": [{"role": "user", "content": "Test"}]
            })
            
            mock_choice = MagicMock()
            mock_choice.model_dump.return_value = {"message": {"content": "Response"}}
            mock_completion = MagicMock()
            mock_completion.choices = [mock_choice]
            mock_client.send_request = AsyncMock(return_value=mock_completion)

            custom_openai = CustomOpenAI(audio_chat_config)
            custom_openai._client = mock_client

            model_params = ModelParams(url="https://api.openai.com/v1", auth_token="sk-test")
            response = await custom_openai._generate_response(
                chat_input, model_params
            )

            # Verify it was routed to audio chat completion
            self.assertEqual(response.response_code, 200, f"Failed for model: {model_name}")
            mock_client.send_request.assert_called()

    @patch("sygra.core.models.custom_models.BaseCustomModel._set_client")
    def test_audio_chat_model_detection(self, mock_set_client):
        """Test gpt-4o-audio model name detection (case insensitive)"""
        asyncio.run(self._run_audio_chat_model_detection(mock_set_client))

    async def _run_audio_chat_role_mapping(self, mock_set_client):
        """Test that LangChain message types are correctly mapped to OpenAI roles"""
        audio_chat_config = {
            "name": "gpt4o_audio_model",
            "model": "gpt-4o-audio-preview",
            "url": "https://api.openai.com/v1",
            "auth_token": "Bearer sk-test_key_123",
            "api_version": "2023-05-15",
            "parameters": {},
        }

        # Create messages with different LangChain types
        from langchain_core.messages import AIMessage

        messages = [
            SystemMessage(content="You are helpful"),  # type='system'
            HumanMessage(content="Hello"),  # type='human'
            AIMessage(content="Hi there"),  # type='ai'
        ]
        chat_input = ChatPromptValue(messages=messages)

        # Setup mock client
        mock_client = MagicMock()
        
        # Mock build_request to return properly formatted messages with correct role mapping
        mock_client.build_request = MagicMock(return_value={
            "messages": [
                {"role": "system", "content": "You are helpful"},
                {"role": "user", "content": "Hello"},
                {"role": "assistant", "content": "Hi there"},
            ]
        })
        
        mock_choice = MagicMock()
        mock_choice.model_dump.return_value = {"message": {"content": "Response"}}
        mock_completion = MagicMock()
        mock_completion.choices = [mock_choice]
        mock_client.send_request = AsyncMock(return_value=mock_completion)

        custom_openai = CustomOpenAI(audio_chat_config)
        custom_openai._client = mock_client

        model_params = ModelParams(url="https://api.openai.com/v1", auth_token="sk-test")
        response = await custom_openai._generate_response(chat_input, model_params)

        # Verify the call was made
        self.assertEqual(response.response_code, 200)
        mock_client.send_request.assert_called_once()

        # Verify role mapping in the payload
        call_args = mock_client.send_request.call_args
        payload = call_args[0][0]
        messages_sent = payload["messages"]

        # Check that roles are correctly mapped
        self.assertEqual(len(messages_sent), 3)
        self.assertEqual(messages_sent[0]["role"], "system")  # system -> system
        self.assertEqual(messages_sent[1]["role"], "user")  # human -> user
        self.assertEqual(messages_sent[2]["role"], "assistant")  # ai -> assistant

    @patch("sygra.core.models.custom_models.BaseCustomModel._set_client")
    def test_audio_chat_role_mapping(self, mock_set_client):
        """Test LangChain to OpenAI role mapping"""
        asyncio.run(self._run_audio_chat_role_mapping(mock_set_client))


if __name__ == "__main__":
    unittest.main()
