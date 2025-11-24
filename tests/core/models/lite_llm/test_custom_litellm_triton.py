import asyncio
import sys
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import openai
from litellm import BadRequestError

# Add the parent directory to sys.path to import the necessary modules
sys.path.append(str(Path(__file__).parent.parent.parent.parent))

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.prompt_values import ChatPromptValue

from sygra.core.models.custom_models import ModelParams
from sygra.core.models.lite_llm.triton_model import CustomTriton as LiteLLMTriton
from sygra.utils import constants


class TestLiteLLMTriton(unittest.TestCase):
    def setUp(self):
        # Base model configuration
        self.base_config = {
            "name": "triton_model",
            "parameters": {"temperature": 0.7, "max_tokens": 100},
            "url": "http://triton-test.com",
            "auth_token": "Bearer test_token_123",
        }

        # Configuration with completions API
        self.completions_config = {
            **self.base_config,
            "completions_api": True,
            "hf_chat_template_model_id": "meta-llama/Llama-2-7b-chat-hf",
        }

        # Mock messages
        self.messages = [
            SystemMessage(content="You are a helpful assistant"),
            HumanMessage(content="Hello, how are you?"),
        ]
        self.chat_input = ChatPromptValue(messages=self.messages)

    def _get_model_params(self):
        return ModelParams(url=self.base_config["url"], auth_token="test_token")

    def test_init(self):
        model = LiteLLMTriton(self.base_config)
        self.assertEqual(model.model_config, self.base_config)
        self.assertEqual(model.generation_params, self.base_config["parameters"])
        self.assertEqual(model.name(), "triton_model")

    @patch("sygra.core.models.lite_llm.triton_model.logger")
    def test_init_with_completions_api(self, mock_logger):
        with patch("sygra.core.models.custom_models.AutoTokenizer"):
            model = LiteLLMTriton(self.completions_config)
            self.assertTrue(model.model_config.get("completions_api"))
            mock_logger.info.assert_any_call("Model triton_model supports completion API.")

    async def _run_generate_response_chat_api_success(self):
        with patch(
            "sygra.core.models.lite_llm.triton_model.acompletion", new_callable=AsyncMock
        ) as mock_acomp:
            mock_choice = MagicMock()
            mock_choice.model_dump.return_value = {
                "message": {"content": "Hello! I'm doing well, thank you!", "tool_calls": []}
            }
            mock_completion = MagicMock()
            mock_completion.choices = [mock_choice]
            mock_acomp.return_value = mock_completion

            model = LiteLLMTriton(self.base_config)
            params = self._get_model_params()
            resp = await model._generate_response(self.chat_input, params)

            self.assertEqual(resp.llm_response, "Hello! I'm doing well, thank you!")
            self.assertEqual(resp.response_code, 200)
            called = mock_acomp.call_args.kwargs
            self.assertEqual(called["model"], "triton/triton_model")
            self.assertEqual(called["api_base"], self.base_config["url"])
            self.assertEqual(called["api_key"], "test_token")

    def test_generate_response_chat_api_success(self):
        asyncio.run(self._run_generate_response_chat_api_success())

    async def _run_generate_response_chat_api_with_tools_success(self):
        with patch(
            "sygra.core.models.lite_llm.triton_model.acompletion", new_callable=AsyncMock
        ) as mock_acomp:
            tool_call = {
                "id": "call_12xyz",
                "function": {
                    "arguments": '{"query":"Latest business news"}',
                    "name": "news_search",
                },
                "type": "function",
            }
            mock_choice = MagicMock()
            mock_choice.model_dump.return_value = {
                "message": {"content": None, "tool_calls": [tool_call]}
            }
            mock_completion = MagicMock()
            mock_completion.choices = [mock_choice]
            mock_acomp.return_value = mock_completion

            model = LiteLLMTriton(self.base_config)
            params = self._get_model_params()
            resp = await model._generate_response(self.chat_input, params)

            self.assertEqual(resp.response_code, 200)
            self.assertIsNone(resp.llm_response)
            self.assertEqual(resp.tool_calls[0]["id"], tool_call["id"])

    def test_generate_response_chat_api_with_tools_success(self):
        asyncio.run(self._run_generate_response_chat_api_with_tools_success())

    @patch("sygra.core.models.custom_models.AutoTokenizer")
    async def _run_generate_response_completions_api_success(self, mock_tokenizer):
        with patch(
            "sygra.core.models.lite_llm.triton_model.atext_completion", new_callable=AsyncMock
        ) as mock_atext:
            mock_choice = MagicMock()
            mock_choice.model_dump.return_value = {"text": "Response text"}
            mock_completion = MagicMock()
            mock_completion.choices = [mock_choice]
            mock_atext.return_value = mock_completion

            model = LiteLLMTriton(self.completions_config)
            model.get_chat_formatted_text = MagicMock(return_value="Formatted prompt text")
            params = self._get_model_params()
            resp = await model._generate_response(self.chat_input, params)

            self.assertEqual(resp.llm_response, "Response text")
            self.assertEqual(resp.response_code, 200)
            model.get_chat_formatted_text.assert_called_once()
            called = mock_atext.call_args.kwargs
            self.assertEqual(called["prompt"], "Formatted prompt text")
            self.assertEqual(called["model"], "triton/triton_model")

    def test_generate_response_completions_api_success(self):
        asyncio.run(self._run_generate_response_completions_api_success())

    async def _run_generate_response_rate_limit_error(self):
        with (
            patch(
                "sygra.core.models.lite_llm.triton_model.acompletion", new_callable=AsyncMock
            ) as mock_acomp,
            patch("sygra.core.models.lite_llm.triton_model.logger") as mock_logger,
        ):
            api_error = openai.RateLimitError(
                "Rate limit exceeded",
                response=MagicMock(),
                body={"error": {"message": "Rate limit exceeded", "type": "rate_limit_error"}},
            )
            api_error.status_code = 429
            mock_acomp.side_effect = api_error
            model = LiteLLMTriton(self.base_config)
            params = self._get_model_params()
            resp = await model._generate_response(self.chat_input, params)
            self.assertIn(constants.ERROR_PREFIX, resp.llm_response)
            self.assertIn("Triton API request exceeded rate limit", resp.llm_response)
            self.assertEqual(resp.response_code, 429)
            mock_logger.warning.assert_called()

    def test_generate_response_rate_limit_error(self):
        asyncio.run(self._run_generate_response_rate_limit_error())

    async def _run_generate_response_connection_error(self):
        with patch(
            "sygra.core.models.lite_llm.triton_model.acompletion", new_callable=AsyncMock
        ) as mock_acomp:
            mock_acomp.side_effect = Exception(constants.CONNECTION_ERROR)
            model = LiteLLMTriton(self.base_config)
            params = self._get_model_params()
            resp = await model._generate_response(self.chat_input, params)
            self.assertEqual(resp.response_code, 999)

    def test_generate_response_connection_error(self):
        asyncio.run(self._run_generate_response_connection_error())

    async def _run_generate_response_generic_exception(self):
        with (
            patch(
                "sygra.core.models.lite_llm.triton_model.acompletion", new_callable=AsyncMock
            ) as mock_acomp,
            patch("sygra.core.models.lite_llm.triton_model.logger") as mock_logger,
        ):
            mock_acomp.side_effect = Exception("Network timeout")
            model = LiteLLMTriton(self.base_config)
            model._get_status_from_body = MagicMock(return_value=None)
            params = self._get_model_params()
            resp = await model._generate_response(self.chat_input, params)
            self.assertIn(constants.ERROR_PREFIX, resp.llm_response)
            self.assertIn("Network timeout", resp.llm_response)
            self.assertEqual(resp.response_code, 999)
            mock_logger.error.assert_called()

    def test_generate_response_generic_exception(self):
        asyncio.run(self._run_generate_response_generic_exception())

    async def _run_generate_response_bad_request_exception(self):
        with (
            patch(
                "sygra.core.models.lite_llm.triton_model.acompletion", new_callable=AsyncMock
            ) as mock_acomp,
            patch("sygra.core.models.lite_llm.triton_model.logger") as mock_logger,
        ):
            mock_acomp.side_effect = BadRequestError(
                "Bad Request", llm_provider="triton", model="some_model"
            )
            model = LiteLLMTriton(self.base_config)
            model._get_status_from_body = MagicMock(return_value=None)
            params = self._get_model_params()
            resp = await model._generate_response(self.chat_input, params)
            self.assertIn(constants.ERROR_PREFIX, resp.llm_response)
            self.assertIn("Bad Request", resp.llm_response)
            mock_logger.error.assert_called()

    def test_generate_response_bad_request_exception(self):
        asyncio.run(self._run_generate_response_bad_request_exception())

    async def _run_generate_response_api_error_chat_api(self):
        with (
            patch(
                "sygra.core.models.lite_llm.triton_model.acompletion", new_callable=AsyncMock
            ) as mock_acomp,
            patch("sygra.core.models.lite_llm.triton_model.logger") as mock_logger,
        ):
            mock_request = MagicMock()
            mock_request.status_code = 500
            api_error = openai.APIError(
                "Internal server error",
                request=mock_request,
                body={"error": {"message": "Internal server error", "type": "api_error"}},
            )
            api_error.status_code = 500
            mock_acomp.side_effect = api_error

            model = LiteLLMTriton(self.base_config)
            params = self._get_model_params()
            resp = await model._generate_response(self.chat_input, params)
            self.assertIn(constants.ERROR_PREFIX, resp.llm_response)
            self.assertIn("Triton API error", resp.llm_response)
            self.assertEqual(resp.response_code, 500)
            mock_logger.error.assert_called()

    def test_generate_response_api_error_chat_api(self):
        asyncio.run(self._run_generate_response_api_error_chat_api())

    async def _run_generate_response_with_extracted_status_code(self):
        with patch(
            "sygra.core.models.lite_llm.triton_model.acompletion", new_callable=AsyncMock
        ) as mock_acomp:
            mock_acomp.side_effect = Exception("Service unavailable")
            model = LiteLLMTriton(self.base_config)
            model._get_status_from_body = MagicMock(return_value=503)
            params = self._get_model_params()
            resp = await model._generate_response(self.chat_input, params)
            self.assertEqual(resp.response_code, 503)

    def test_generate_response_with_extracted_status_code(self):
        asyncio.run(self._run_generate_response_with_extracted_status_code())

    async def _run_generate_response_passes_generation_params(self):
        with patch(
            "sygra.core.models.lite_llm.triton_model.acompletion", new_callable=AsyncMock
        ) as mock_acomp:
            mock_choice = MagicMock()
            mock_choice.model_dump.return_value = {"message": {"content": "Response"}}
            mock_completion = MagicMock()
            mock_completion.choices = [mock_choice]
            mock_acomp.return_value = mock_completion

            config = {
                **self.base_config,
                "parameters": {"temperature": 0.9, "max_tokens": 500, "top_p": 0.95},
            }
            model = LiteLLMTriton(config)
            params = self._get_model_params()
            await model._generate_response(self.chat_input, params)

            called = mock_acomp.call_args.kwargs
            self.assertEqual(called["temperature"], 0.9)
            self.assertEqual(called["max_tokens"], 500)
            self.assertEqual(called["top_p"], 0.95)

    def test_generate_response_passes_generation_params(self):
        asyncio.run(self._run_generate_response_passes_generation_params())


if __name__ == "__main__":
    unittest.main()
