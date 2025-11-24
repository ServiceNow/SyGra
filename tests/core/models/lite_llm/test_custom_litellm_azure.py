import asyncio
import sys
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import openai
from litellm import BadRequestError

sys.path.append(str(Path(__file__).parent.parent.parent.parent))

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.prompt_values import ChatPromptValue

from sygra.core.models.custom_models import ModelParams
from sygra.core.models.lite_llm.azure_model import CustomAzure
from sygra.utils import constants


class TestLiteLLMAzure(unittest.TestCase):
    def setUp(self):
        self.base_config = {
            "name": "azure_model",
            "parameters": {"temperature": 0.7, "max_tokens": 100},
            "url": "https://azure.example.com",
            "auth_token": "Bearer sk-test_key_123",
        }

        self.messages = [
            SystemMessage(content="You are a helpful assistant"),
            HumanMessage(content="Hello, how are you?"),
        ]
        self.chat_input = ChatPromptValue(messages=self.messages)

    def test_init(self):
        model = CustomAzure(self.base_config)
        self.assertEqual(model.model_config, self.base_config)
        self.assertEqual(model.generation_params, self.base_config["parameters"])
        self.assertEqual(model.name(), "azure_model")

    def test_init_missing_required_keys_raises_error(self):
        config = {
            "name": "azure_model",
            "parameters": {"temperature": 0.7},
        }
        with self.assertRaises(Exception):
            CustomAzure(config)

    async def _run_generate_response_success(self):
        with patch(
            "sygra.core.models.lite_llm.azure_model.acompletion", new_callable=AsyncMock
        ) as mock_acomp:
            mock_choice = MagicMock()
            mock_choice.model_dump.return_value = {
                "message": {"content": "Hello! I'm good.", "tool_calls": None},
                "finish_reason": "stop",
            }
            mock_completion = MagicMock()
            mock_completion.choices = [mock_choice]
            mock_acomp.return_value = mock_completion
            mock_completion.status_code = 200

            model = CustomAzure(self.base_config)
            params = ModelParams(url=self.base_config["url"], auth_token="sk-test")
            resp = await model._generate_response(self.chat_input, params)

            self.assertEqual(resp.llm_response, "Hello! I'm good.")
            self.assertEqual(resp.response_code, 200)
            called_kwargs = mock_acomp.call_args.kwargs
            self.assertEqual(called_kwargs["model"], "azure_ai/azure_model")
            self.assertEqual(called_kwargs["api_base"], self.base_config["url"])
            self.assertEqual(called_kwargs["api_key"], "sk-test")

    def test_generate_response_success(self):
        asyncio.run(self._run_generate_response_success())

    async def _run_generate_response_with_tool_calls(self):
        with patch(
            "sygra.core.models.lite_llm.azure_model.acompletion", new_callable=AsyncMock
        ) as mock_acomp:
            tool_call = {
                "id": "call_abc",
                "function": {"name": "do_x", "arguments": '{"a":1}'},
                "type": "function",
            }
            mock_choice = MagicMock()
            mock_choice.model_dump.return_value = {
                "message": {"content": None, "tool_calls": [tool_call]},
                "finish_reason": "tool_calls",
            }
            mock_completion = MagicMock()
            mock_completion.choices = [mock_choice]
            mock_acomp.return_value = mock_completion
            mock_completion.status_code = 200

            model = CustomAzure(self.base_config)
            params = ModelParams(url=self.base_config["url"], auth_token="sk-test")
            resp = await model._generate_response(self.chat_input, params)

            self.assertEqual(resp.response_code, 200)
            self.assertIsNone(resp.llm_response)
            self.assertIsInstance(resp.tool_calls, list)
            self.assertEqual(resp.tool_calls[0]["id"], tool_call["id"])

    def test_generate_response_with_tool_calls(self):
        asyncio.run(self._run_generate_response_with_tool_calls())

    async def _run_generate_response_content_filter(self):
        with (
            patch(
                "sygra.core.models.lite_llm.azure_model.acompletion", new_callable=AsyncMock
            ) as mock_acomp,
            patch("sygra.core.models.lite_llm.azure_model.logger") as mock_logger,
        ):
            mock_choice = MagicMock()
            mock_choice.model_dump.return_value = {
                "message": {"content": "blocked", "tool_calls": None},
                "finish_reason": "content_filter",
            }
            mock_completion = MagicMock()
            mock_completion.choices = [mock_choice]
            mock_acomp.return_value = mock_completion

            model = CustomAzure(self.base_config)
            params = ModelParams(url=self.base_config["url"], auth_token="sk-test")
            resp = await model._generate_response(self.chat_input, params)

            self.assertIn(constants.ERROR_PREFIX, resp.llm_response)
            self.assertIn("Blocked by azure content filter", resp.llm_response)
            self.assertEqual(resp.response_code, 400)
            self.assertEqual(resp.finish_reason, "content_filter")
            mock_logger.error.assert_called()

    def test_generate_response_content_filter(self):
        asyncio.run(self._run_generate_response_content_filter())

    async def _run_generate_response_rate_limit_error(self):
        with (
            patch(
                "sygra.core.models.lite_llm.azure_model.acompletion", new_callable=AsyncMock
            ) as mock_acomp,
            patch("sygra.core.models.lite_llm.azure_model.logger") as mock_logger,
        ):
            api_error = openai.RateLimitError(
                "Rate limit exceeded",
                response=MagicMock(),
                body={"error": {"message": "Rate limit exceeded", "type": "rate_limit_error"}},
            )
            api_error.status_code = 429
            mock_acomp.side_effect = api_error

            model = CustomAzure(self.base_config)
            params = ModelParams(url=self.base_config["url"], auth_token="sk-test")
            resp = await model._generate_response(self.chat_input, params)

            self.assertIn(constants.ERROR_PREFIX, resp.llm_response)
            self.assertIn("Azure API request exceeded rate limit", resp.llm_response)
            self.assertEqual(resp.response_code, 429)
            mock_logger.warning.assert_called()

    def test_generate_response_rate_limit_error(self):
        asyncio.run(self._run_generate_response_rate_limit_error())

    async def _run_generate_response_bad_request_exception(self):
        with (
            patch(
                "sygra.core.models.lite_llm.azure_model.acompletion", new_callable=AsyncMock
            ) as mock_acomp,
            patch("sygra.core.models.lite_llm.azure_model.logger") as mock_logger,
        ):
            mock_acomp.side_effect = BadRequestError(
                "Bad Request", llm_provider="azure_ai", model="gpt-4o"
            )
            model = CustomAzure(self.base_config)
            model._get_status_from_body = MagicMock(return_value=None)
            params = ModelParams(url=self.base_config["url"], auth_token="sk-test")
            resp = await model._generate_response(self.chat_input, params)
            self.assertIn(constants.ERROR_PREFIX, resp.llm_response)
            self.assertIn("Bad Request", resp.llm_response)
            mock_logger.error.assert_called()

    def test_generate_response_bad_request_exception(self):
        asyncio.run(self._run_generate_response_bad_request_exception())

    async def _run_generate_response_api_error(self):
        with (
            patch(
                "sygra.core.models.lite_llm.azure_model.acompletion", new_callable=AsyncMock
            ) as mock_acomp,
            patch("sygra.core.models.lite_llm.azure_model.logger") as mock_logger,
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

            model = CustomAzure(self.base_config)
            params = ModelParams(url=self.base_config["url"], auth_token="sk-test")
            resp = await model._generate_response(self.chat_input, params)
            self.assertIn(constants.ERROR_PREFIX, resp.llm_response)
            self.assertIn("Azure API error", resp.llm_response)
            self.assertEqual(resp.response_code, 500)
            mock_logger.error.assert_called()

    def test_generate_response_api_error(self):
        asyncio.run(self._run_generate_response_api_error())

    async def _run_generate_response_generic_exception(self):
        with (
            patch(
                "sygra.core.models.lite_llm.azure_model.acompletion", new_callable=AsyncMock
            ) as mock_acomp,
            patch("sygra.core.models.lite_llm.azure_model.logger") as mock_logger,
        ):
            mock_acomp.side_effect = Exception("Network timeout")
            model = CustomAzure(self.base_config)
            model._get_status_from_body = MagicMock(return_value=None)
            params = ModelParams(url=self.base_config["url"], auth_token="sk-test")
            resp = await model._generate_response(self.chat_input, params)
            self.assertIn(constants.ERROR_PREFIX, resp.llm_response)
            self.assertIn("Network timeout", resp.llm_response)
            self.assertEqual(resp.response_code, 999)
            mock_logger.error.assert_called()

    def test_generate_response_generic_exception(self):
        asyncio.run(self._run_generate_response_generic_exception())

    async def _run_generate_response_with_extracted_status_code(self):
        with patch(
            "sygra.core.models.lite_llm.azure_model.acompletion", new_callable=AsyncMock
        ) as mock_acomp:
            mock_acomp.side_effect = Exception("Service unavailable")
            model = CustomAzure(self.base_config)
            model._get_status_from_body = MagicMock(return_value=503)
            params = ModelParams(url=self.base_config["url"], auth_token="sk-test")
            resp = await model._generate_response(self.chat_input, params)
            self.assertEqual(resp.response_code, 503)

    def test_generate_response_with_extracted_status_code(self):
        asyncio.run(self._run_generate_response_with_extracted_status_code())

    async def _run_generate_response_passes_generation_params(self):
        with patch(
            "sygra.core.models.lite_llm.azure_model.acompletion", new_callable=AsyncMock
        ) as mock_acomp:
            mock_choice = MagicMock()
            mock_choice.model_dump.return_value = {
                "message": {"content": "Response", "tool_calls": None},
                "finish_reason": "stop",
            }
            mock_completion = MagicMock()
            mock_completion.choices = [mock_choice]
            mock_acomp.return_value = mock_completion

            config = {
                **self.base_config,
                "parameters": {"temperature": 0.9, "max_tokens": 500, "top_p": 0.95},
            }
            model = CustomAzure(config)
            params = ModelParams(url=self.base_config["url"], auth_token="sk-test")
            await model._generate_response(self.chat_input, params)

            called = mock_acomp.call_args.kwargs
            self.assertEqual(called["temperature"], 0.9)
            self.assertEqual(called["max_tokens"], 500)
            self.assertEqual(called["top_p"], 0.95)

    def test_generate_response_passes_generation_params(self):
        asyncio.run(self._run_generate_response_passes_generation_params())


if __name__ == "__main__":
    unittest.main()
