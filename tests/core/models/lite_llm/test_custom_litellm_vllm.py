import asyncio
import json
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
from pydantic import BaseModel

from sygra.core.models.custom_models import ModelParams
from sygra.core.models.lite_llm.vllm_model import CustomVLLM as LiteLLMVLLM
from sygra.utils import constants


class TestLiteLLMVLLM(unittest.TestCase):
    def setUp(self):
        # Base model configuration
        self.base_config = {
            "name": "vllm_model",
            "parameters": {"temperature": 0.7, "max_tokens": 100},
            "url": "http://vllm-test.com",
            "auth_token": "Bearer test_token_123",
        }

        # Configuration with completions API
        self.completions_config = {
            **self.base_config,
            "completions_api": True,
            "hf_chat_template_model_id": "meta-llama/Llama-2-7b-chat-hf",
        }

        # Configuration with model serving name
        self.serving_name_config = {
            **self.base_config,
            "model_serving_name": "custom_serving_name",
        }

        # Mock messages
        self.messages = [
            SystemMessage(content="You are a helpful assistant"),
            HumanMessage(content="Hello, how are you?"),
        ]
        self.chat_input = ChatPromptValue(messages=self.messages)

    def test_init(self):
        model = LiteLLMVLLM(self.base_config)
        self.assertEqual(model.model_config, self.base_config)
        self.assertEqual(model.generation_params, self.base_config["parameters"])
        self.assertEqual(model.name(), "vllm_model")
        self.assertEqual(model.auth_token, "test_token_123")
        self.assertEqual(model.model_serving_name, "vllm_model")

    def test_init_with_custom_serving_name(self):
        model = LiteLLMVLLM(self.serving_name_config)
        self.assertEqual(model.model_serving_name, "custom_serving_name")

    @patch("sygra.core.models.lite_llm.vllm_model.logger")
    def test_init_with_completions_api(self, mock_logger):
        with patch("sygra.core.models.custom_models.AutoTokenizer"):
            model = LiteLLMVLLM(self.completions_config)
            self.assertTrue(model.model_config.get("completions_api"))
            mock_logger.info.assert_any_call("Model vllm_model supports completion API.")

    def _get_model_params(self):
        return ModelParams(url="http://vllm-test.com", auth_token="test_token")

    async def _run_generate_response_chat_api_success(self):
        with patch(
            "sygra.core.models.lite_llm.vllm_model.acompletion", new_callable=AsyncMock
        ) as mock_acomp:
            mock_choice = MagicMock()
            mock_choice.model_dump.return_value = {
                "message": {"content": "Hello! I'm doing well, thank you!", "tool_calls": []}
            }
            mock_completion = MagicMock()
            mock_completion.choices = [mock_choice]
            mock_acomp.return_value = mock_completion

            model = LiteLLMVLLM(self.base_config)
            params = self._get_model_params()
            resp = await model._generate_response(self.chat_input, params)

            self.assertEqual(resp.llm_response, "Hello! I'm doing well, thank you!")
            self.assertEqual(resp.response_code, 200)
            called = mock_acomp.call_args.kwargs
            self.assertEqual(called["model"], "hosted_vllm/vllm_model")
            self.assertEqual(called["api_base"], self.base_config["url"])
            self.assertEqual(called["api_key"], "test_token")

    def test_generate_response_chat_api_success(self):
        asyncio.run(self._run_generate_response_chat_api_success())

    async def _run_generate_response_chat_api_with_tools_success(self):
        with patch(
            "sygra.core.models.lite_llm.vllm_model.acompletion", new_callable=AsyncMock
        ) as mock_acomp:
            tool_call = {
                "id": "call_12xyz",
                "function": {"arguments": '{"query":"Latest business news"}', "name": "new_search"},
                "type": "function",
            }
            mock_choice = MagicMock()
            mock_choice.model_dump.return_value = {
                "message": {"content": None, "tool_calls": [tool_call]}
            }
            mock_completion = MagicMock()
            mock_completion.choices = [mock_choice]
            mock_acomp.return_value = mock_completion

            model = LiteLLMVLLM(self.base_config)
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
            "sygra.core.models.lite_llm.vllm_model.atext_completion", new_callable=AsyncMock
        ) as mock_atext:
            mock_choice = MagicMock()
            mock_choice.model_dump.return_value = {"text": "Response text"}
            mock_completion = MagicMock()
            mock_completion.choices = [mock_choice]
            mock_atext.return_value = mock_completion

            model = LiteLLMVLLM(self.completions_config)
            model.get_chat_formatted_text = MagicMock(return_value="Formatted prompt text")
            params = self._get_model_params()
            resp = await model._generate_response(self.chat_input, params)

            self.assertEqual(resp.llm_response, "Response text")
            self.assertEqual(resp.response_code, 200)
            model.get_chat_formatted_text.assert_called_once()
            called = mock_atext.call_args.kwargs
            self.assertEqual(called["prompt"], "Formatted prompt text")
            self.assertEqual(called["model"], "hosted_vllm/vllm_model")

    def test_generate_response_completions_api_success(self):
        asyncio.run(self._run_generate_response_completions_api_success())

    async def _run_generate_response_rate_limit_error(self):
        with (
            patch(
                "sygra.core.models.lite_llm.vllm_model.acompletion", new_callable=AsyncMock
            ) as mock_acomp,
            patch("sygra.core.models.lite_llm.vllm_model.logger") as mock_logger,
        ):
            mock_acomp.side_effect = openai.RateLimitError(
                "Rate limit exceeded", response=MagicMock(), body=None
            )
            model = LiteLLMVLLM(self.base_config)
            params = self._get_model_params()
            resp = await model._generate_response(self.chat_input, params)
            self.assertIn(constants.ERROR_PREFIX, resp.llm_response)
            self.assertIn("vLLM request failed", resp.llm_response)
            self.assertEqual(resp.response_code, 429)
            mock_logger.warn.assert_called()

    def test_generate_response_rate_limit_error(self):
        asyncio.run(self._run_generate_response_rate_limit_error())

    async def _run_generate_response_server_down(self):
        with patch(
            "sygra.core.models.lite_llm.vllm_model.acompletion", new_callable=AsyncMock
        ) as mock_acomp:
            mock_acomp.side_effect = Exception(f"Connection failed: {constants.ELEMAI_JOB_DOWN}")
            model = LiteLLMVLLM(self.base_config)
            params = self._get_model_params()
            resp = await model._generate_response(self.chat_input, params)
            self.assertIn(constants.ERROR_PREFIX, resp.llm_response)
            self.assertIn(constants.ELEMAI_JOB_DOWN, resp.llm_response)
            self.assertEqual(resp.response_code, 503)

    def test_generate_response_server_down(self):
        asyncio.run(self._run_generate_response_server_down())

    async def _run_generate_response_connection_error(self):
        with patch(
            "sygra.core.models.lite_llm.vllm_model.acompletion", new_callable=AsyncMock
        ) as mock_acomp:
            mock_acomp.side_effect = Exception(constants.CONNECTION_ERROR)
            model = LiteLLMVLLM(self.base_config)
            params = self._get_model_params()
            resp = await model._generate_response(self.chat_input, params)
            self.assertEqual(resp.response_code, 503)

    def test_generate_response_connection_error(self):
        asyncio.run(self._run_generate_response_connection_error())

    async def _run_generate_response_generic_exception(self):
        with (
            patch(
                "sygra.core.models.lite_llm.vllm_model.acompletion", new_callable=AsyncMock
            ) as mock_acomp,
            patch("sygra.core.models.lite_llm.vllm_model.logger") as mock_logger,
        ):
            mock_acomp.side_effect = Exception("Network timeout")
            model = LiteLLMVLLM(self.base_config)
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
                "sygra.core.models.lite_llm.vllm_model.acompletion", new_callable=AsyncMock
            ) as mock_acomp,
            patch("sygra.core.models.lite_llm.vllm_model.logger") as mock_logger,
        ):
            mock_acomp.side_effect = BadRequestError(
                "Bad Request", llm_provider="vllm_hosted", model="qwen3_32b"
            )
            model = LiteLLMVLLM(self.base_config)
            model._get_status_from_body = MagicMock(return_value=None)
            params = self._get_model_params()
            resp = await model._generate_response(self.chat_input, params)
            self.assertIn(constants.ERROR_PREFIX, resp.llm_response)
            self.assertIn("Bad Request", resp.llm_response)
            mock_logger.error.assert_called()

    def test_generate_response_bad_request_exception(self):
        asyncio.run(self._run_generate_response_bad_request_exception())

    async def _run_generate_response_with_extracted_status_code(self):
        with patch(
            "sygra.core.models.lite_llm.vllm_model.acompletion", new_callable=AsyncMock
        ) as mock_acomp:
            mock_acomp.side_effect = Exception("Service unavailable")
            model = LiteLLMVLLM(self.base_config)
            model._get_status_from_body = MagicMock(return_value=503)
            params = self._get_model_params()
            resp = await model._generate_response(self.chat_input, params)
            self.assertEqual(resp.response_code, 503)

    def test_generate_response_with_extracted_status_code(self):
        asyncio.run(self._run_generate_response_with_extracted_status_code())

    async def _run_generate_response_with_custom_serving_name(self):
        with patch(
            "sygra.core.models.lite_llm.vllm_model.acompletion", new_callable=AsyncMock
        ) as mock_acomp:
            mock_choice = MagicMock()
            mock_choice.model_dump.return_value = {"message": {"content": "Response"}}
            mock_completion = MagicMock()
            mock_completion.choices = [mock_choice]
            mock_acomp.return_value = mock_completion

            model = LiteLLMVLLM(self.serving_name_config)
            params = self._get_model_params()
            await model._generate_response(self.chat_input, params)

            called = mock_acomp.call_args.kwargs
            self.assertEqual(called["model"], "hosted_vllm/vllm_model")

    def test_generate_response_with_custom_serving_name(self):
        asyncio.run(self._run_generate_response_with_custom_serving_name())

    async def _run_generate_response_passes_generation_params(self):
        with patch(
            "sygra.core.models.lite_llm.vllm_model.acompletion", new_callable=AsyncMock
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
            model = LiteLLMVLLM(config)
            params = self._get_model_params()
            await model._generate_response(self.chat_input, params)

            called = mock_acomp.call_args.kwargs
            self.assertEqual(called["temperature"], 0.9)
            self.assertEqual(called["max_tokens"], 500)
            self.assertEqual(called["top_p"], 0.95)

    def test_generate_response_passes_generation_params(self):
        asyncio.run(self._run_generate_response_passes_generation_params())

    async def _run_native_structured_output_chat_success(self):
        class Item(BaseModel):
            name: str

        with patch(
            "sygra.core.models.lite_llm.vllm_model.acompletion", new_callable=AsyncMock
        ) as mock_acomp:
            mock_choice = MagicMock()
            mock_choice.model_dump.return_value = {
                "message": {"content": json.dumps({"name": "ok"}), "tool_calls": None}
            }
            mock_completion = MagicMock()
            mock_completion.choices = [mock_choice]
            mock_acomp.return_value = mock_completion

            model = LiteLLMVLLM(self.base_config)
            params = self._get_model_params()
            resp = await model._generate_native_structured_output(self.chat_input, params, Item)
            self.assertEqual(resp.response_code, 200)
            self.assertIn("name", resp.llm_response)

    def test_native_structured_output_chat_success(self):
        asyncio.run(self._run_native_structured_output_chat_success())

    @patch("sygra.core.models.custom_models.AutoTokenizer")
    async def _run_native_structured_output_completions_success(self, mock_tokenizer):
        class Item(BaseModel):
            name: str

        with patch(
            "sygra.core.models.lite_llm.vllm_model.atext_completion", new_callable=AsyncMock
        ) as mock_atext:
            mock_choice = MagicMock()
            mock_choice.model_dump.return_value = {"text": json.dumps({"name": "ok"})}
            mock_completion = MagicMock()
            mock_completion.choices = [mock_choice]
            mock_atext.return_value = mock_completion

            model = LiteLLMVLLM(self.completions_config)
            model.get_chat_formatted_text = MagicMock(return_value="Formatted prompt text")
            params = self._get_model_params()
            resp = await model._generate_native_structured_output(self.chat_input, params, Item)
            self.assertEqual(resp.response_code, 200)
            self.assertIn("name", resp.llm_response)

    def test_native_structured_output_completions_success(self):
        asyncio.run(self._run_native_structured_output_completions_success())

    async def _run_native_structured_output_validation_fallback(self):
        class Item(BaseModel):
            name: str

        with patch(
            "sygra.core.models.lite_llm.vllm_model.acompletion", new_callable=AsyncMock
        ) as mock_acomp:
            mock_choice = MagicMock()
            mock_choice.model_dump.return_value = {
                "message": {"content": "not_json", "tool_calls": None}
            }
            mock_completion = MagicMock()
            mock_completion.choices = [mock_choice]
            mock_acomp.return_value = mock_completion

            model = LiteLLMVLLM(self.base_config)
            fallback_resp = MagicMock()
            fallback_resp.llm_response = "fallback"
            fallback_resp.response_code = 200
            model._generate_fallback_structured_output = AsyncMock(return_value=fallback_resp)

            params = self._get_model_params()
            resp = await model._generate_native_structured_output(self.chat_input, params, Item)
            self.assertEqual(resp.response_code, 200)
            self.assertEqual(resp.llm_response, "fallback")

    def test_native_structured_output_validation_fallback(self):
        asyncio.run(self._run_native_structured_output_validation_fallback())


if __name__ == "__main__":
    unittest.main()
