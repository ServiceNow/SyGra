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
from sygra.core.models.lite_llm.vertex_ai_model import CustomVertexAI
from sygra.utils import constants


class TestLiteLLMVertexAI(unittest.TestCase):
    def setUp(self):
        # Base model configuration for text generation
        self.text_config = {
            "name": "vertex_gemini",
            "model": "gemini-1.5-pro",
            "parameters": {"temperature": 0.7, "max_tokens": 100},
            # Vertex specific required fields
            "vertex_project": "my-gcp-project",
            "vertex_location": "us-central1",
            "vertex_credentials": {"type": "service_account", "client_email": "svc@x"},
        }

        # Configuration for Image Generation
        self.image_config = {
            "name": "vertex_image",
            "model": "imagen-3",
            "output_type": "image",
            "parameters": {"size": "1024x1024", "quality": "standard", "style": "vivid"},
            "vertex_project": "my-gcp-project",
            "vertex_location": "us-central1",
            "vertex_credentials": {"type": "service_account", "client_email": "svc@x"},
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
        model = CustomVertexAI(self.text_config)
        self.assertEqual(model.model_config, self.text_config)
        self.assertEqual(model.generation_params, self.text_config["parameters"])
        self.assertEqual(model.name(), "vertex_gemini")

    def test_init_missing_required_keys_raises_error(self):
        config = {
            "name": "vertex_gemini",
            "parameters": {"temperature": 0.7},
            # missing vertex_project/vertex_location/vertex_credentials
        }
        with self.assertRaises(Exception):
            CustomVertexAI(config)

    async def _run_generate_response_chat_success(self):
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
            mock_completion.status_code = 200
            mock_acomp.return_value = mock_completion

            model = CustomVertexAI(self.text_config)
            # Vertex does not require base url/api_key
            params = ModelParams(url="", auth_token="unused")
            resp = await model._generate_response(self.chat_input, params)

            self.assertEqual(resp.llm_response, "Hello! I'm good.")
            self.assertEqual(resp.response_code, 200)
            called_kwargs = mock_acomp.call_args.kwargs
            self.assertEqual(called_kwargs["model"], "vertex_ai/" + self.text_config["model"])
            # api_base should not be present when url is empty
            self.assertNotIn("api_base", called_kwargs)
            # No api_key for Vertex AI
            self.assertNotIn("api_key", called_kwargs)
            # Ensure Vertex specific params are forwarded
            self.assertEqual(called_kwargs["vertex_project"], self.text_config["vertex_project"])
            self.assertEqual(called_kwargs["vertex_location"], self.text_config["vertex_location"])
            self.assertIn("vertex_credentials", called_kwargs)

    def test_generate_response_chat_success(self):
        asyncio.run(self._run_generate_response_chat_success())

    async def _run_generate_response_chat_with_tool_calls(self):
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

            model = CustomVertexAI(self.text_config)
            params = ModelParams(url="", auth_token="unused")
            resp = await model._generate_response(self.chat_input, params)

            self.assertEqual(resp.response_code, 200)
            self.assertIsNone(resp.llm_response)
            self.assertIsInstance(resp.tool_calls, list)
            self.assertEqual(resp.tool_calls[0]["id"], tool_call["id"])

    def test_generate_response_chat_with_tool_calls(self):
        asyncio.run(self._run_generate_response_chat_with_tool_calls())

    async def _run_generate_response_rate_limit_error(self):
        with (
            patch(
                "sygra.core.models.lite_llm.base.acompletion", new_callable=AsyncMock
            ) as mock_acomp,
            patch("sygra.core.models.lite_llm.vertex_ai_model.logger") as mock_logger,
        ):
            api_error = openai.RateLimitError(
                "Rate limit exceeded",
                response=MagicMock(),
                body={"error": {"message": "Rate limit exceeded", "type": "rate_limit_error"}},
            )
            api_error.status_code = 429
            mock_acomp.side_effect = api_error

            model = CustomVertexAI(self.text_config)
            params = ModelParams(url="", auth_token="unused")
            resp = await model._generate_response(self.chat_input, params)

            self.assertIn(constants.ERROR_PREFIX, resp.llm_response)
            self.assertEqual(resp.response_code, 429)
            mock_logger.warning.assert_called()

    def test_generate_response_rate_limit_error(self):
        asyncio.run(self._run_generate_response_rate_limit_error())

    async def _run_generate_response_bad_request_error(self):
        with patch(
            "sygra.core.models.lite_llm.base.acompletion", new_callable=AsyncMock
        ) as mock_acomp:
            mock_acomp.side_effect = BadRequestError(
                "Bad Request", llm_provider="vertex_ai", model=self.text_config["model"]
            )

            model = CustomVertexAI(self.text_config)
            model._get_status_from_body = MagicMock(return_value=None)
            params = ModelParams(url="", auth_token="unused")
            resp = await model._generate_response(self.chat_input, params)

            self.assertIn(constants.ERROR_PREFIX, resp.llm_response)
            self.assertIn("Bad Request", resp.llm_response)

    def test_generate_response_bad_request_error(self):
        asyncio.run(self._run_generate_response_bad_request_error())

    async def _run_generate_response_api_error(self):
        with (
            patch(
                "sygra.core.models.lite_llm.base.acompletion", new_callable=AsyncMock
            ) as mock_acomp,
            patch("sygra.core.models.lite_llm.vertex_ai_model.logger") as mock_logger,
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

            model = CustomVertexAI(self.text_config)
            params = ModelParams(url="", auth_token="unused")
            resp = await model._generate_response(self.chat_input, params)

            self.assertIn(constants.ERROR_PREFIX, resp.llm_response)
            self.assertIn("Vertex AI API error", resp.llm_response)
            self.assertEqual(resp.response_code, 500)
            mock_logger.error.assert_called()

    def test_generate_response_api_error(self):
        asyncio.run(self._run_generate_response_api_error())

    async def _run_generate_image_success_single(self):
        with patch(
            "sygra.core.models.lite_llm.base.aimage_generation",
            new_callable=AsyncMock,
        ) as mock_img_gen:
            mock_img_gen.return_value = MagicMock()
            model = CustomVertexAI(self.image_config)
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
            model = CustomVertexAI(self.image_config)
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
        model = CustomVertexAI(self.image_config)
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
            model = CustomVertexAI(self.image_config)
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
            model = CustomVertexAI(self.image_config)
            params = ModelParams(url="", auth_token="unused")
            resp = await model._generate_response(self.image_input, params)
            self.assertIn("Vertex AI Image API bad request", resp.llm_response)
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
            model = CustomVertexAI(self.image_config)
            params = ModelParams(url="", auth_token="unused")
            resp = await model._generate_response(self.image_input, params)
            self.assertIn("API error", resp.llm_response)
            self.assertEqual(resp.response_code, 500)

    def test_generate_image_api_error(self):
        asyncio.run(self._run_generate_image_api_error())

    async def _run_generate_image_edit_with_input_image_not_supported(self):
        # Vertex AI should not support image editing; expect 400 error
        model = CustomVertexAI(self.image_config)
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
            self.assertIn("Image editing is not supported by Vertex AI", resp.llm_response)
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

            model = CustomVertexAI(self.text_config)
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

            model = CustomVertexAI(self.text_config)
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
