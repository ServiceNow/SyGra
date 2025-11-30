from __future__ import annotations

import logging
from typing import Any

from langchain_core.prompt_values import ChatPromptValue
from openai import APIError, BadRequestError, RateLimitError

from sygra.core.models.custom_models import ModelParams
from sygra.core.models.lite_llm.base import LiteLLMBase
from sygra.core.models.model_response import ModelResponse
from sygra.logger.logger_config import logger
from sygra.metadata.metadata_integration import track_model_request
from sygra.utils import utils
from sygra.utils.model_utils import is_gpt4o_audio_model, should_route_to_transcription, should_route_to_speech, \
    should_route_to_image

logging.getLogger("LiteLLM").setLevel(logging.WARNING)


class CustomAzureOpenAI(LiteLLMBase):

    def __init__(self, model_config: dict[str, Any]) -> None:
        super().__init__(model_config)
        utils.validate_required_keys(["url", "auth_token", "api_version"], model_config, "model")
        self.model_config = model_config
        self.model_name = self.model_config.get("model", self.name())
        self.api_version = self.model_config.get("api_version")

    def _get_model_prefix(self) -> str:
        return "azure"

    def _extra_call_params(self) -> dict[str, Any]:
        return {"api_version": self.api_version}

    def _provider_label(self) -> str:
        return "Azure OpenAI"

    def _native_structured_output_spec(self):
        return ("response_format", "pydantic")

    # Ensure module-level logger is used for tests expecting per-module logging
    def _map_exception(self, e: Exception, context: str) -> ModelResponse:
        if isinstance(e, RateLimitError):
            logger.warning(
                f"[{self.name()}] {context} request exceeded rate limit: {getattr(e, 'message', e)}"
            )
        elif isinstance(e, BadRequestError):
            logger.error(f"[{self.name()}] {context} bad request: {getattr(e, 'message', e)}")
        elif isinstance(e, APIError):
            logger.error(f"[{self.name()}] {context} error: {getattr(e, 'message', e)}")
        else:
            logger.error(f"[{self.name()}] {context} request failed: {e}")
        return super()._map_exception(e, context)

    @track_model_request
    async def _generate_response(
        self, input: ChatPromptValue, model_params: ModelParams, **kwargs: Any
    ) -> ModelResponse:
        # Check the output type and route to appropriate method
        self._apply_tools(**kwargs)
        if is_gpt4o_audio_model(self.model_config):
            return await self._generate_audio_chat_completion(input, model_params)
        # Auto-detect audio input for transcription (audio-to-text)
        if should_route_to_transcription(input, self.model_config):
            return await self._generate_transcription(input, model_params)
        elif should_route_to_speech(self.model_config):
            return await self._generate_speech(input, model_params)
        elif should_route_to_image(self.model_config):
            return await self._generate_image(input, model_params)
        else:
            return await self._generate_text(input, model_params, **kwargs)

    async def _generate_speech(
        self, input: ChatPromptValue, model_params: ModelParams, **kwargs: Any
    ) -> ModelResponse:
        # Pre-log warning at module logger for overly long text, as tests expect warn to be called here
        text_to_speak = " ".join([str(getattr(m, "content", "")) for m in input.messages]).strip()
        if len(text_to_speak) > 4096:
            logger.warn(
                f"[{self.name()}] Text exceeds 4096 character limit: {len(text_to_speak)} characters"
            )
        return await super()._generate_speech(input, model_params)

    async def _generate_transcription(
        self, input: ChatPromptValue, model_params: ModelParams, **kwargs: Any
    ) -> ModelResponse:
        """
        Transcribe audio to text using Azure OpenAI Transcription API via LiteLLM.
        This method is called when input_type is 'audio' in model config.

        Args:
            input: ChatPromptValue containing audio data URLs to transcribe
            model_params: Model parameters including URL and auth token

        Returns:
            Model Response
        """
        ret_code = 200

        try:
            # Extract audio data URLs from messages using utility function
            from sygra.utils.audio_utils import extract_audio_urls_from_messages

            audio_data_urls, text_prompt = extract_audio_urls_from_messages(list(input.messages))

            if not audio_data_urls:
                logger.error(f"[{self.name()}] No audio data provided for transcription")
                return ModelResponse(
                    llm_response=f"{constants.ERROR_PREFIX} No audio data provided for transcription",
                    response_code=400,
                )

            # Process only the first audio file (most transcription APIs handle one file at a time)
            if len(audio_data_urls) > 1:
                logger.warning(
                    f"[{self.name()}] Multiple audio files provided. Using first audio only. "
                    f"Additional {len(audio_data_urls) - 1} file(s) will be ignored."
                )

            audio_data_url = audio_data_urls[0]

            # Create file-like object from audio data URL using utility function
            from sygra.utils.audio_utils import create_audio_file_from_data_url

            audio_file = create_audio_file_from_data_url(audio_data_url)

            # Get transcription-specific parameters from generation_params or model_config
            language = self.generation_params.get("language", self.model_config.get("language"))
            response_format = self.generation_params.get(
                "response_format", self.model_config.get("response_format", "json")
            )
            temperature = self.generation_params.get(
                "temperature", self.model_config.get("temperature", 0)
            )
            timestamp_granularities = self.generation_params.get(
                "timestamp_granularities", self.model_config.get("timestamp_granularities")
            )

            # Build transcription parameters
            transcription_params: dict[str, Any] = {
                "file": audio_file,
            }

            if language:
                transcription_params["language"] = language
            if text_prompt:
                transcription_params["prompt"] = text_prompt
            if response_format:
                transcription_params["response_format"] = response_format
            if temperature is not None:
                transcription_params["temperature"] = temperature
            if timestamp_granularities:
                transcription_params["timestamp_granularities"] = timestamp_granularities

            logger.debug(
                f"[{self.name()}] Transcription parameters - language: {language}, "
                f"format: {response_format}, temperature: {temperature}"
            )

            # Make the transcription API call using LiteLLM with Azure
            transcription_response = await atranscription(
                model=self._get_lite_llm_model_name(),
                api_base=model_params.url,
                api_key=model_params.auth_token,
                api_version=self.api_version,
                **transcription_params,
            )

            # Handle different response formats
            if response_format == "json" or response_format == "verbose_json":
                # Response is an object with 'text' field and possibly other fields
                if hasattr(transcription_response, "text"):
                    resp_text = transcription_response.text
                elif isinstance(transcription_response, dict):
                    resp_text = transcription_response.get("text", str(transcription_response))
                else:
                    resp_text = str(transcription_response)
            else:
                # For 'text', 'srt', 'vtt' formats, response is plain text
                resp_text = str(transcription_response)

        except Exception as e:
            return self._map_exception(e, f"{self._provider_label()} OpenAI Transcription API")

        return ModelResponse(llm_response=resp_text, response_code=ret_code)