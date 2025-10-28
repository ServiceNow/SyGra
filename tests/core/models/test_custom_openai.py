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
            "parameters": {},
            "url": "https://api.openai.com/v1",
            "auth_token": "Bearer sk-test_key_123",
            "api_version": "2023-05-15",
            "voice": "alloy",
            "response_format": "mp3",
            "speed": 1.0,
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
        config_low = {**self.tts_config, "speed": 0.1}
        custom_openai_low = CustomOpenAI(config_low)
        custom_openai_low._client = mock_client

        model_params = ModelParams(url="https://api.openai.com/v1", auth_token="sk-test")
        await custom_openai_low._generate_speech(self.tts_input, model_params)

        # Verify speed was clamped to 0.25
        call_args = mock_client.create_speech.call_args
        self.assertEqual(call_args.kwargs["speed"], 0.25)

        # Test speed too high
        config_high = {**self.tts_config, "speed": 5.0}
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

    @patch("sygra.core.models.custom_models.BaseCustomModel._set_client")
    def test_generate_response_routes_to_speech(self, mock_set_client):
        asyncio.run(self._run_generate_response_routes_to_speech(mock_set_client))


if __name__ == "__main__":
    unittest.main()
