import asyncio
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import openai

# Add the parent directory to sys.path to import the necessary modules
sys.path.append(str(Path(__file__).parent.parent.parent.parent))

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.prompt_values import ChatPromptValue
from pydantic import BaseModel

from sygra.core.models.custom_models import ModelParams
from sygra.core.models.lite_llm.bedrock_model import CustomBedrock
from sygra.utils import constants


class TestLiteLLMBedrock(unittest.TestCase):
    def setUp(self):
        # Base model configuration for text generation
        self.text_config = {
            "name": "br_model",
            "model": "us.anthropic.claude-sonnet-4-5-20250929-v1:0",
            "parameters": {"temperature": 0.7, "max_tokens": 100},
            # Bedrock specific required fields
            "aws_access_key_id": "AKIAxxx",
            "aws_secret_access_key": "secret",
            "aws_region_name": "us-east-1",
        }

        # Configuration for Image Generation
        self.image_config = {
            "name": "br_image",
            "model": "stability.sd3",
            "output_type": "image",
            "parameters": {"size": "1024x1024", "quality": "standard", "style": "vivid"},
            "aws_access_key_id": "AKIAxxx",
            "aws_secret_access_key": "secret",
            "aws_region_name": "us-east-1",
        }

        # Messages
        self.messages = [
            SystemMessage(content="You are a helpful assistant"),
            HumanMessage(content="Hello, how are you?"),
        ]
        self.chat_input = ChatPromptValue(messages=self.messages)

        # Image input
        self.image_messages = [HumanMessage(content="A serene mountain landscape at sunset")]
        self.image_input = ChatPromptValue(messages=self.image_messages)

    def test_init(self):
        model = CustomBedrock(self.text_config)
        self.assertEqual(model.model_config, self.text_config)
        self.assertEqual(model.generation_params, self.text_config["parameters"])
        self.assertEqual(model.name(), "br_model")

    def test_init_missing_required_keys_raises_error(self):
        config = {
            "name": "br_model",
            "parameters": {"temperature": 0.7},
            # missing aws_access_key_id/aws_secret_access_key/aws_region_name
        }
        with self.assertRaises(Exception):
            CustomBedrock(config)

    async def _run_generate_text_success(self):
        with patch(
            "sygra.core.models.lite_llm.base.acompletion",
            new_callable=AsyncMock,
        ) as mock_acomp:
            mock_choice = MagicMock()
            mock_choice.model_dump.return_value = {
                "message": {"content": "Hello! I'm good.", "tool_calls": None}
            }
            mock_completion = MagicMock()
            mock_completion.choices = [mock_choice]
            mock_acomp.return_value = mock_completion

            model = CustomBedrock(self.text_config)
            params = ModelParams(url="", auth_token="unused")
            resp = await model._generate_response(self.chat_input, params)

            self.assertEqual(resp.llm_response, "Hello! I'm good.")
            self.assertEqual(resp.response_code, 200)
            called_kwargs = mock_acomp.call_args.kwargs
            self.assertEqual(called_kwargs["model"], "bedrock/" + self.text_config["model"])
            # No base URL or api_key for Bedrock
            self.assertNotIn("api_base", called_kwargs)
            self.assertNotIn("api_key", called_kwargs)
            # Ensure AWS credentials are forwarded
            self.assertEqual(
                called_kwargs["aws_access_key_id"], self.text_config["aws_access_key_id"]
            )
            self.assertEqual(
                called_kwargs["aws_secret_access_key"], self.text_config["aws_secret_access_key"]
            )
            self.assertEqual(called_kwargs["aws_region_name"], self.text_config["aws_region_name"])

    def test_generate_text_success(self):
        asyncio.run(self._run_generate_text_success())

    async def _run_generate_text_with_tool_calls(self):
        with patch(
            "sygra.core.models.lite_llm.base.acompletion", new_callable=AsyncMock
        ) as mock_acomp:
            tool_call = {
                "id": "call_abc",
                "function": {"name": "do_x", "arguments": '{"a":1}'},
                "type": "function",
            }
            mock_choice = MagicMock()
            mock_choice.model_dump.return_value = {
                "message": {"content": None, "tool_calls": [tool_call]}
            }
            mock_completion = MagicMock()
            mock_completion.choices = [mock_choice]
            mock_acomp.return_value = mock_completion

            model = CustomBedrock(self.text_config)
            params = ModelParams(url="", auth_token="unused")
            resp = await model._generate_response(self.chat_input, params)

            self.assertEqual(resp.response_code, 200)
            self.assertIsNone(resp.llm_response)
            self.assertIsInstance(resp.tool_calls, list)
            self.assertEqual(resp.tool_calls[0]["id"], tool_call["id"])

    def test_generate_text_with_tool_calls(self):
        asyncio.run(self._run_generate_text_with_tool_calls())

    async def _run_generate_text_rate_limit_error(self):
        with (
            patch(
                "sygra.core.models.lite_llm.base.acompletion", new_callable=AsyncMock
            ) as mock_acomp,
            patch("sygra.core.models.lite_llm.bedrock_model.logger") as mock_logger,
        ):
            api_error = openai.RateLimitError(
                "Rate limit exceeded",
                response=MagicMock(),
                body={"error": {"message": "Rate limit exceeded", "type": "rate_limit_error"}},
            )
            api_error.status_code = 429
            mock_acomp.side_effect = api_error

            model = CustomBedrock(self.text_config)
            params = ModelParams(url="", auth_token="unused")
            resp = await model._generate_response(self.chat_input, params)

            self.assertIn(constants.ERROR_PREFIX, resp.llm_response)
            self.assertEqual(resp.response_code, 429)
            mock_logger.warning.assert_called()

    def test_generate_text_rate_limit_error(self):
        asyncio.run(self._run_generate_text_rate_limit_error())

    async def _run_generate_text_bad_request_error(self):
        with patch(
            "sygra.core.models.lite_llm.base.acompletion", new_callable=AsyncMock
        ) as mock_acomp:
            mock_acomp.side_effect = openai.BadRequestError(
                "Bad Request", response=MagicMock(status_code=400), body=None
            )

            model = CustomBedrock(self.text_config)
            model._get_status_from_body = MagicMock(return_value=None)
            params = ModelParams(url="", auth_token="unused")
            resp = await model._generate_response(self.chat_input, params)

            self.assertIn(constants.ERROR_PREFIX, resp.llm_response)
            self.assertIn("Bedrock API bad request", resp.llm_response)

    def test_generate_text_bad_request_error(self):
        asyncio.run(self._run_generate_text_bad_request_error())

    async def _run_generate_text_api_error(self):
        with (
            patch(
                "sygra.core.models.lite_llm.base.acompletion", new_callable=AsyncMock
            ) as mock_acomp,
            patch("sygra.core.models.lite_llm.bedrock_model.logger") as mock_logger,
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

            model = CustomBedrock(self.text_config)
            params = ModelParams(url="", auth_token="unused")
            resp = await model._generate_response(self.chat_input, params)

            self.assertIn(constants.ERROR_PREFIX, resp.llm_response)
            self.assertIn("Bedrock API error", resp.llm_response)
            self.assertEqual(resp.response_code, 500)
            mock_logger.error.assert_called()

    def test_generate_text_api_error(self):
        asyncio.run(self._run_generate_text_api_error())

    async def _run_generate_image_success_single(self):
        with patch(
            "sygra.core.models.lite_llm.base.aimage_generation",
            new_callable=AsyncMock,
        ) as mock_img_gen:
            mock_img_gen.return_value = MagicMock()
            model = CustomBedrock(self.image_config)
            model._process_image_response = AsyncMock(return_value=["data:image/png;base64,AAA"])
            params = ModelParams(url="", auth_token="unused")
            resp = await model._generate_response(self.image_input, params)
            self.assertEqual(resp.response_code, 200)
            self.assertEqual(resp.llm_response, "data:image/png;base64,AAA")

    def test_generate_image_success_single(self):
        asyncio.run(self._run_generate_image_success_single())

    async def _run_generate_image_success_multiple(self):
        with patch(
            "sygra.core.models.lite_llm.base.aimage_generation",
            new_callable=AsyncMock,
        ) as mock_img_gen:
            mock_img_gen.return_value = MagicMock()
            model = CustomBedrock(self.image_config)
            model._process_image_response = AsyncMock(
                return_value=["data:image/png;base64,AAA", "data:image/png;base64,BBB"]
            )
            params = ModelParams(url="", auth_token="unused")
            resp = await model._generate_response(self.image_input, params)
            self.assertEqual(resp.response_code, 200)
            data = json.loads(resp.llm_response)
            self.assertEqual(len(data), 2)

    def test_generate_image_success_multiple(self):
        asyncio.run(self._run_generate_image_success_multiple())

    async def _run_generate_image_empty_prompt(self):
        model = CustomBedrock(self.image_config)
        params = ModelParams(url="", auth_token="unused")
        empty_input = ChatPromptValue(messages=[HumanMessage(content="")])
        resp = await model._generate_response(empty_input, params)
        self.assertIn("No prompt provided", resp.llm_response)
        self.assertEqual(resp.response_code, 400)

    def test_generate_image_empty_prompt(self):
        asyncio.run(self._run_generate_image_empty_prompt())

    async def _run_generate_image_rate_limit_error(self):
        with patch(
            "sygra.core.models.lite_llm.base.aimage_generation",
            new_callable=AsyncMock,
        ) as mock_img_gen:
            mock_img_gen.side_effect = openai.RateLimitError(
                "Rate limit exceeded", response=MagicMock(status_code=429), body=None
            )
            model = CustomBedrock(self.image_config)
            params = ModelParams(url="", auth_token="unused")
            resp = await model._generate_response(self.image_input, params)
            self.assertIn("Rate limit exceeded", resp.llm_response)
            self.assertEqual(resp.response_code, 429)

    def test_generate_image_rate_limit_error(self):
        asyncio.run(self._run_generate_image_rate_limit_error())

    async def _run_generate_image_bad_request_error(self):
        with patch(
            "sygra.core.models.lite_llm.base.aimage_generation",
            new_callable=AsyncMock,
        ) as mock_img_gen:
            mock_img_gen.side_effect = openai.BadRequestError(
                "Invalid size parameter", response=MagicMock(status_code=400), body=None
            )
            model = CustomBedrock(self.image_config)
            params = ModelParams(url="", auth_token="unused")
            resp = await model._generate_response(self.image_input, params)
            self.assertIn("Bedrock Image API bad request", resp.llm_response)
            self.assertEqual(resp.response_code, 400)

    def test_generate_image_bad_request_error(self):
        asyncio.run(self._run_generate_image_bad_request_error())

    async def _run_generate_image_api_error(self):
        with patch(
            "sygra.core.models.lite_llm.base.aimage_generation",
            new_callable=AsyncMock,
        ) as mock_img_gen:
            mock_request = MagicMock()
            mock_request.status_code = 500
            api_error = openai.APIError(
                "Internal server error",
                request=mock_request,
                body={"error": {"message": "Internal server error", "type": "api_error"}},
            )
            api_error.status_code = 500
            mock_img_gen.side_effect = api_error
            model = CustomBedrock(self.image_config)
            params = ModelParams(url="", auth_token="unused")
            resp = await model._generate_response(self.image_input, params)
            self.assertIn("API error", resp.llm_response)
            self.assertEqual(resp.response_code, 500)

    def test_generate_image_api_error(self):
        asyncio.run(self._run_generate_image_api_error())

    async def _run_generate_image_edit_with_input_image_not_supported(self):
        # Bedrock should not support image editing; expect 400 error
        model = CustomBedrock(self.image_config)
        params = ModelParams(url="", auth_token="unused")
        # Force image-edit path and avoid real parsing
        with (
            patch.object(
                model, "_extract_prompt_and_images", new_callable=AsyncMock
            ) as mock_extract,
            patch("sygra.utils.image_utils.parse_image_data_url") as mock_parse,
        ):
            mock_extract.return_value = ("Make this brighter", ["data:image/png;base64,AAA"])
            mock_parse.return_value = ("image/png", "png", b"img")
            resp = await model._generate_response(ChatPromptValue(messages=[]), params)
            self.assertIn("Image editing is not supported by Bedrock", resp.llm_response)
            self.assertEqual(resp.response_code, 400)

    def test_generate_image_edit_with_input_image_not_supported(self):
        asyncio.run(self._run_generate_image_edit_with_input_image_not_supported())

    async def _run_native_structured_output_success(self):
        class Item(BaseModel):
            name: str

        with patch(
            "sygra.core.models.lite_llm.base.acompletion",
            new_callable=AsyncMock,
        ) as mock_acomp:
            mock_choice = MagicMock()
            mock_choice.model_dump.return_value = {
                "message": {"content": json.dumps({"name": "ok"}), "tool_calls": None}
            }
            mock_completion = MagicMock()
            mock_completion.choices = [mock_choice]
            mock_completion.status_code = 200
            mock_acomp.return_value = mock_completion

            model = CustomBedrock(self.text_config)
            params = ModelParams(url="", auth_token="unused")
            resp = await model._generate_native_structured_output(self.chat_input, params, Item)
            self.assertEqual(resp.response_code, 200)
            self.assertIn("name", resp.llm_response)

    def test_native_structured_output_success(self):
        asyncio.run(self._run_native_structured_output_success())

    async def _run_native_structured_output_validation_fallback(self):
        class Item(BaseModel):
            name: str

        with patch(
            "sygra.core.models.lite_llm.base.acompletion",
            new_callable=AsyncMock,
        ) as mock_acomp:
            mock_choice = MagicMock()
            # invalid JSON to force fallback
            mock_choice.model_dump.return_value = {
                "message": {"content": "not_json", "tool_calls": None}
            }
            mock_completion = MagicMock()
            mock_completion.choices = [mock_choice]
            mock_acomp.return_value = mock_completion

            model = CustomBedrock(self.text_config)
            # Bypass full fallback execution with a stubbed response
            fallback_resp = MagicMock()
            fallback_resp.llm_response = "fallback"
            fallback_resp.response_code = 200
            model._generate_fallback_structured_output = AsyncMock(return_value=fallback_resp)

            params = ModelParams(url="", auth_token="unused")
            resp = await model._generate_native_structured_output(self.chat_input, params, Item)
            self.assertEqual(resp.response_code, 200)
            self.assertEqual(resp.llm_response, "fallback")

    def test_native_structured_output_validation_fallback(self):
        asyncio.run(self._run_native_structured_output_validation_fallback())


if __name__ == "__main__":
    unittest.main()
