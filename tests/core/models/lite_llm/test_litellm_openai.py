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
from sygra.core.models.lite_llm.openai_model import CustomOpenAI as LiteLLMOpenAI
from sygra.utils import constants
from sygra.utils.audio_utils import get_audio_url


class TestLiteLLMOpenAI(unittest.TestCase):
    def setUp(self):
        # Base model configuration for text generation
        self.text_config = {
            "name": "oai_gpt4",
            "model": "gpt-4o",
            "parameters": {"temperature": 0.7, "max_tokens": 100},
            "url": "https://api.openai.com/v1",
            "auth_token": "Bearer sk-test_key_123",
        }

        # Configuration for TTS
        self.tts_config = {
            "name": "oai_tts",
            "model": "gpt-4o-mini-tts",
            "output_type": "audio",
            "parameters": {
                "voice": "alloy",
                "response_format": "mp3",
                "speed": 1.0,
            },
            "url": "https://api.openai.com/v1",
            "auth_token": "Bearer sk-test_key_123",
        }

        # Configuration for Image Generation
        self.image_config = {
            "name": "oai_image",
            "model": "dall-e-3",
            "output_type": "image",
            "parameters": {"size": "1024x1024", "quality": "standard", "style": "vivid"},
            "url": "https://api.openai.com/v1",
            "auth_token": "Bearer sk-test_key_123",
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
        model = LiteLLMOpenAI(self.text_config)
        self.assertEqual(model.model_config, self.text_config)
        self.assertEqual(model.generation_params, self.text_config["parameters"])
        self.assertEqual(model.name(), "oai_gpt4")

    def test_init_missing_required_keys_raises_error(self):
        config = {
            "name": "oai_gpt4",
            "parameters": {"temperature": 0.7},
            # missing url/auth_token
        }
        with self.assertRaises(Exception):
            LiteLLMOpenAI(config)

    async def _run_generate_text_success(self):
        # Mock litellm.acompletion
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

            model = LiteLLMOpenAI(self.text_config)
            params = ModelParams(url=self.text_config["url"], auth_token="sk-test")
            resp = await model._generate_text(self.chat_input, params)

            self.assertEqual(resp.llm_response, "Hello! I'm good.")
            self.assertEqual(resp.response_code, 200)
            # Verify litellm call args
            called_kwargs = mock_acomp.call_args.kwargs
            self.assertEqual(called_kwargs["model"], self.text_config["model"])
            self.assertEqual(called_kwargs["base_url"], self.text_config["url"])
            self.assertEqual(called_kwargs["api_key"], "sk-test")
            self.assertNotIn("api_version", called_kwargs)

    def test_generate_text_success(self):
        asyncio.run(self._run_generate_text_success())

    async def _run_generate_text_with_tool_calls(self):
        with patch(
            "sygra.core.models.lite_llm.base.acompletion",
            new_callable=AsyncMock,
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

            model = LiteLLMOpenAI(self.text_config)
            params = ModelParams(url=self.text_config["url"], auth_token="sk-test")
            resp = await model._generate_text(self.chat_input, params)

            self.assertEqual(resp.response_code, 200)
            self.assertIsNone(resp.llm_response)
            self.assertIsInstance(resp.tool_calls, list)
            self.assertEqual(resp.tool_calls[0]["id"], tool_call["id"])

    def test_generate_text_with_tool_calls(self):
        asyncio.run(self._run_generate_text_with_tool_calls())

    async def _run_generate_text_rate_limit_error(self):
        with (
            patch(
                "sygra.core.models.lite_llm.base.acompletion",
                new_callable=AsyncMock,
            ) as mock_acomp,
            patch("sygra.core.models.lite_llm.openai_model.logger") as mock_logger,
        ):
            api_error = openai.RateLimitError(
                "Rate limit exceeded",
                response=MagicMock(),
                body={"error": {"message": "Rate limit exceeded", "type": "rate_limit_error"}},
            )
            api_error.status_code = 429
            mock_acomp.side_effect = api_error

            model = LiteLLMOpenAI(self.text_config)
            params = ModelParams(url=self.text_config["url"], auth_token="sk-test")
            resp = await model._generate_text(self.chat_input, params)

            self.assertIn(constants.ERROR_PREFIX, resp.llm_response)
            self.assertEqual(resp.response_code, 429)
            mock_logger.warning.assert_called()

    def test_generate_text_rate_limit_error(self):
        asyncio.run(self._run_generate_text_rate_limit_error())

    async def _run_generate_text_generic_exception(self):
        with patch(
            "sygra.core.models.lite_llm.base.acompletion",
            new_callable=AsyncMock,
        ) as mock_acomp:
            mock_acomp.side_effect = Exception("Network timeout")

            model = LiteLLMOpenAI(self.text_config)
            model._get_status_from_body = MagicMock(return_value=None)
            params = ModelParams(url=self.text_config["url"], auth_token="sk-test")
            resp = await model._generate_text(self.chat_input, params)

            self.assertIn(constants.ERROR_PREFIX, resp.llm_response)
            self.assertIn("Network timeout", resp.llm_response)
            self.assertEqual(resp.response_code, 999)

    def test_generate_text_generic_exception(self):
        asyncio.run(self._run_generate_text_generic_exception())

    async def _run_generate_text_bad_request_exception(self):
        with patch(
            "sygra.core.models.lite_llm.base.acompletion",
            new_callable=AsyncMock,
        ) as mock_acomp:
            mock_acomp.side_effect = BadRequestError(
                "Bad Request", llm_provider="openai", model="gpt-4o"
            )
            model = LiteLLMOpenAI(self.text_config)
            model._get_status_from_body = MagicMock(return_value=None)
            params = ModelParams(url=self.text_config["url"], auth_token="sk-test")
            resp = await model._generate_text(self.chat_input, params)

            self.assertIn(constants.ERROR_PREFIX, resp.llm_response)
            self.assertIn("Bad Request", resp.llm_response)

    def test_generate_text_bad_request_exception(self):
        asyncio.run(self._run_generate_text_bad_request_exception())

    async def _run_generate_text_api_error(self):
        with (
            patch(
                "sygra.core.models.lite_llm.base.acompletion",
                new_callable=AsyncMock,
            ) as mock_acomp,
            patch("sygra.core.models.lite_llm.openai_model.logger") as mock_logger,
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

            model = LiteLLMOpenAI(self.text_config)
            params = ModelParams(url=self.text_config["url"], auth_token="sk-test")
            resp = await model._generate_text(self.chat_input, params)

            self.assertIn(constants.ERROR_PREFIX, resp.llm_response)
            self.assertIn("OpenAI API error", resp.llm_response)
            self.assertEqual(resp.response_code, 500)
            mock_logger.error.assert_called()

    def test_generate_text_api_error(self):
        asyncio.run(self._run_generate_text_api_error())

    async def _run_generate_speech_success_base64(self):
        with patch(
            "sygra.core.models.lite_llm.base.aspeech", new_callable=AsyncMock
        ) as mock_aspeech:
            mock_resp = MagicMock()
            mock_resp.content = b"fake_audio_data"
            mock_aspeech.return_value = mock_resp

            model = LiteLLMOpenAI(self.tts_config)
            params = ModelParams(url=self.tts_config["url"], auth_token="sk-test")
            tts_input = ChatPromptValue(messages=[HumanMessage(content="Hello TTS")])
            resp = await model._generate_speech(tts_input, params)

            expected = get_audio_url(mock_resp.content, "audio/mpeg")
            self.assertEqual(resp.llm_response, expected)
            self.assertEqual(resp.response_code, 200)

    def test_generate_speech_success_base64(self):
        asyncio.run(self._run_generate_speech_success_base64())

    async def _run_generate_speech_empty_text(self):
        model = LiteLLMOpenAI(self.tts_config)
        params = ModelParams(url=self.tts_config["url"], auth_token="sk-test")
        empty_input = ChatPromptValue(messages=[HumanMessage(content="")])
        resp = await model._generate_speech(empty_input, params)
        self.assertIn("No text provided", resp.llm_response)
        self.assertEqual(resp.response_code, 400)

    def test_generate_speech_empty_text(self):
        asyncio.run(self._run_generate_speech_empty_text())

    async def _run_generate_speech_speed_clamping(self):
        with patch(
            "sygra.core.models.lite_llm.base.aspeech", new_callable=AsyncMock
        ) as mock_aspeech:
            mock_resp = MagicMock()
            mock_resp.content = b"audio_data"
            mock_aspeech.return_value = mock_resp

            # Too low speed -> clamp to 0.25
            low_cfg = {**self.tts_config, "parameters": {"speed": 0.1}}
            model_low = LiteLLMOpenAI(low_cfg)
            params = ModelParams(url=self.tts_config["url"], auth_token="sk-test")
            tts_input = ChatPromptValue(messages=[HumanMessage(content="Hi")])
            await model_low._generate_speech(tts_input, params)
            self.assertEqual(mock_aspeech.call_args.kwargs["speed"], 0.25)

            # Too high speed -> clamp to 4.0
            high_cfg = {**self.tts_config, "parameters": {"speed": 5.0}}
            model_high = LiteLLMOpenAI(high_cfg)
            await model_high._generate_speech(tts_input, params)
            self.assertEqual(mock_aspeech.call_args.kwargs["speed"], 4.0)

    def test_generate_speech_speed_clamping(self):
        asyncio.run(self._run_generate_speech_speed_clamping())

    async def _run_generate_speech_rate_limit_error(self):
        with (
            patch(
                "sygra.core.models.lite_llm.base.aspeech", new_callable=AsyncMock
            ) as mock_aspeech,
            patch("sygra.core.models.lite_llm.openai_model.logger") as mock_logger,
        ):
            api_error = openai.RateLimitError(
                "Rate limit exceeded",
                response=MagicMock(),
                body={"error": {"message": "Rate limit exceeded", "type": "rate_limit_error"}},
            )
            api_error.status_code = 429
            mock_aspeech.side_effect = api_error
            model = LiteLLMOpenAI(self.tts_config)
            params = ModelParams(url=self.tts_config["url"], auth_token="sk-test")
            tts_input = ChatPromptValue(messages=[HumanMessage(content="Hi")])
            resp = await model._generate_speech(tts_input, params)
            self.assertIn(constants.ERROR_PREFIX, resp.llm_response)
            self.assertEqual(resp.response_code, 429)
            mock_logger.warning.assert_called()

    def test_generate_speech_rate_limit_error(self):
        asyncio.run(self._run_generate_speech_rate_limit_error())

    async def _run_generate_speech_bad_request_error(self):
        with patch(
            "sygra.core.models.lite_llm.base.aspeech", new_callable=AsyncMock
        ) as mock_aspeech:
            mock_aspeech.side_effect = BadRequestError(
                "Invalid voice", llm_provider="openai", model="gpt-4o-mini-tts"
            )

            model = LiteLLMOpenAI(self.tts_config)
            params = ModelParams(url=self.tts_config["url"], auth_token="sk-test")
            tts_input = ChatPromptValue(messages=[HumanMessage(content="Hi")])
            resp = await model._generate_speech(tts_input, params)

            self.assertIn(constants.ERROR_PREFIX, resp.llm_response)
            self.assertIn("OpenAI TTS bad request", resp.llm_response)

    def test_generate_speech_bad_request_error(self):
        asyncio.run(self._run_generate_speech_bad_request_error())

    async def _run_generate_speech_api_error(self):
        with (
            patch(
                "sygra.core.models.lite_llm.base.aspeech", new_callable=AsyncMock
            ) as mock_aspeech,
            patch("sygra.core.models.lite_llm.openai_model.logger") as mock_logger,
        ):
            mock_request = MagicMock()
            mock_request.status_code = 500
            api_error = openai.APIError(
                "Internal server error",
                request=mock_request,
                body={"error": {"message": "Internal server error", "type": "api_error"}},
            )
            api_error.status_code = 500
            mock_aspeech.side_effect = api_error

            model = LiteLLMOpenAI(self.tts_config)
            params = ModelParams(url=self.tts_config["url"], auth_token="sk-test")
            tts_input = ChatPromptValue(messages=[HumanMessage(content="Hi")])
            resp = await model._generate_speech(tts_input, params)
            self.assertIn("OpenAI TTS request failed with error", resp.llm_response)
            self.assertEqual(resp.response_code, 500)
            mock_logger.error.assert_called()

    def test_generate_speech_api_error(self):
        asyncio.run(self._run_generate_speech_api_error())

    async def _run_generate_response_routes_to_speech(self):
        with patch(
            "sygra.core.models.lite_llm.base.aspeech", new_callable=AsyncMock
        ) as mock_aspeech:
            mock_resp = MagicMock()
            mock_resp.content = b"audio"
            mock_aspeech.return_value = mock_resp
            model = LiteLLMOpenAI(self.tts_config)
            params = ModelParams(url=self.tts_config["url"], auth_token="sk-test")
            resp = await model._generate_response(
                ChatPromptValue(messages=[HumanMessage(content="Hi")]), params
            )
            self.assertEqual(resp.response_code, 200)
            mock_aspeech.assert_awaited()

    def test_generate_response_routes_to_speech(self):
        asyncio.run(self._run_generate_response_routes_to_speech())

    async def _run_generate_image_success_single(self):
        with patch(
            "sygra.core.models.lite_llm.base.aimage_generation",
            new_callable=AsyncMock,
        ) as mock_img_gen:
            mock_img_gen.return_value = MagicMock()
            model = LiteLLMOpenAI(self.image_config)
            # Patch instance processor to avoid internal imports
            model._process_image_response = AsyncMock(return_value=["data:image/png;base64,AAA"])
            params = ModelParams(url=self.image_config["url"], auth_token="sk-test")
            resp = await model._generate_image(self.image_input, params)
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
            model = LiteLLMOpenAI(self.image_config)
            model._process_image_response = AsyncMock(
                return_value=["data:image/png;base64,AAA", "data:image/png;base64,BBB"]
            )
            params = ModelParams(url=self.image_config["url"], auth_token="sk-test")
            resp = await model._generate_image(self.image_input, params)
            self.assertEqual(resp.response_code, 200)
            data = json.loads(resp.llm_response)
            self.assertEqual(len(data), 2)

    def test_generate_image_success_multiple(self):
        asyncio.run(self._run_generate_image_success_multiple())

    async def _run_generate_image_empty_prompt(self):
        model = LiteLLMOpenAI(self.image_config)
        params = ModelParams(url=self.image_config["url"], auth_token="sk-test")
        empty_input = ChatPromptValue(messages=[HumanMessage(content="")])
        resp = await model._generate_image(empty_input, params)
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
            model = LiteLLMOpenAI(self.image_config)
            params = ModelParams(url=self.image_config["url"], auth_token="sk-test")
            resp = await model._generate_image(self.image_input, params)
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
            model = LiteLLMOpenAI(self.image_config)
            params = ModelParams(url=self.image_config["url"], auth_token="sk-test")
            resp = await model._generate_image(self.image_input, params)
            self.assertIn("OpenAI Image API bad request", resp.llm_response)
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
            model = LiteLLMOpenAI(self.image_config)
            params = ModelParams(url=self.image_config["url"], auth_token="sk-test")
            resp = await model._generate_image(self.image_input, params)
            self.assertIn("API error", resp.llm_response)
            self.assertEqual(resp.response_code, 500)

    def test_generate_image_api_error(self):
        asyncio.run(self._run_generate_image_api_error())

    async def _run_generate_image_edit_with_input_image(self):
        with (
            patch(
                "sygra.core.models.lite_llm.base.aimage_edit", new_callable=AsyncMock
            ) as mock_img_edit,
            patch("sygra.utils.image_utils.parse_image_data_url") as mock_parse,
        ):
            mock_img_edit.return_value = MagicMock()
            mock_parse.return_value = ("image/png", "png", b"img")

            model = LiteLLMOpenAI(self.image_config)
            model._process_image_response = AsyncMock(return_value=["data:image/png;base64,EDIT"])
            params = ModelParams(url=self.image_config["url"], auth_token="sk-test")

            img_data_url = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAUA\nAAAAF..."
            messages = [
                HumanMessage(
                    content=[
                        {"type": "text", "text": "Make this brighter"},
                        {"type": "image_url", "image_url": {"url": img_data_url}},
                    ]
                )
            ]
            edit_input = ChatPromptValue(messages=messages)
            resp = await model._generate_image(edit_input, params)
            self.assertEqual(resp.response_code, 200)
            self.assertEqual(resp.llm_response, "data:image/png;base64,EDIT")

    def test_generate_image_edit_with_input_image(self):
        asyncio.run(self._run_generate_image_edit_with_input_image())

    async def _run_generate_image_invalid_image_data_url(self):
        with (
            patch(
                "sygra.core.models.lite_llm.base.aimage_edit", new_callable=AsyncMock
            ) as mock_img_edit,
            patch("sygra.utils.image_utils.parse_image_data_url") as mock_parse,
        ):
            mock_img_edit.return_value = MagicMock()
            mock_parse.side_effect = ValueError("bad image data")

            model = LiteLLMOpenAI(self.image_config)
            params = ModelParams(url=self.image_config["url"], auth_token="sk-test")

            messages = [
                HumanMessage(
                    content=[
                        {"type": "text", "text": "Edit this"},
                        {
                            "type": "image_url",
                            "image_url": {"url": "data:image/png;base64,INVALID"},
                        },
                    ]
                )
            ]
            edit_input = ChatPromptValue(messages=messages)
            resp = await model._generate_image(edit_input, params)

            self.assertIn("Invalid image data", resp.llm_response)
            self.assertEqual(resp.response_code, 400)

    def test_generate_image_invalid_image_data_url(self):
        asyncio.run(self._run_generate_image_invalid_image_data_url())

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
            mock_acomp.return_value = mock_completion

            model = LiteLLMOpenAI(self.text_config)
            params = ModelParams(url=self.text_config["url"], auth_token="sk-test")
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

            model = LiteLLMOpenAI(self.text_config)
            fallback_resp = MagicMock()
            fallback_resp.llm_response = "fallback"
            fallback_resp.response_code = 200
            model._generate_fallback_structured_output = AsyncMock(return_value=fallback_resp)

            params = ModelParams(url=self.text_config["url"], auth_token="sk-test")
            resp = await model._generate_native_structured_output(self.chat_input, params, Item)
            self.assertEqual(resp.response_code, 200)
            self.assertEqual(resp.llm_response, "fallback")

    def test_native_structured_output_validation_fallback(self):
        asyncio.run(self._run_native_structured_output_validation_fallback())


if __name__ == "__main__":
    unittest.main()
