from __future__ import annotations

import base64
import json
import logging
from typing import Any, Type

import litellm
import openai
from langchain_core.prompt_values import ChatPromptValue
from litellm import BadRequestError, aimage_edit, aimage_generation, aspeech
from pydantic import BaseModel, ValidationError

import sygra.utils.constants as constants
from sygra.core.models.custom_models import BaseCustomModel, ModelParams
from sygra.core.models.model_response import ModelResponse
from sygra.logger.logger_config import logger
from sygra.metadata.metadata_integration import track_model_request
from sygra.utils import utils

logging.getLogger("LiteLLM").setLevel(logging.WARNING)


class CustomOpenAI(BaseCustomModel):

    def __init__(self, model_config: dict[str, Any]) -> None:
        super().__init__(model_config)
        utils.validate_required_keys(["url", "auth_token"], model_config, "model")
        self.model_config = model_config
        self.model_name = self.model_config.get("model", self.name())

    @track_model_request
    async def _generate_native_structured_output(
        self,
        input: ChatPromptValue,
        model_params: ModelParams,
        pydantic_model: Type[BaseModel],
        **kwargs: Any,
    ) -> ModelResponse:
        """Generate structured output using OpenAI's native support"""
        logger.info(f"[{self.name()}] Attempting native structured output generation")
        model_url = model_params.url
        try:
            # Convert to model format tools
            formatted_tools = self._convert_tools_to_model_format(**kwargs)
            if formatted_tools:
                self.generation_params.update(
                    {"tools": formatted_tools, "tool_choice": kwargs.get("tool_choice", "auto")}
                )

            # Add pydantic_model to generation params
            all_params = {
                **(self.generation_params or {}),
                "response_format": pydantic_model,
            }

            # Convert input to messages
            messages = self._get_messages(input)
            # Send the request using the litellm
            completion = await litellm.acompletion(
                model=self._get_lite_llm_model_name(),
                messages=messages,
                base_url=model_url,
                api_key=model_params.auth_token,
                **all_params,
            )
            self._extract_token_usage(completion)
            resp_text = completion.choices[0].model_dump()["message"]["content"]
            tool_calls = completion.choices[0].model_dump()["message"]["tool_calls"]
            # Check if the request was successful based on the response status
            resp_status = getattr(completion, "status_code", 200)  # Default to 200 if not present

            if resp_status != 200:
                logger.error(
                    f"[{self.name()}] Native structured output request failed with code: {resp_status}"
                )
                # Fall back to instruction-based approach
                logger.info(f"[{self.name()}] Falling back to instruction-based structured output")
                return await self._generate_fallback_structured_output(
                    input, model_params, pydantic_model, **kwargs
                )

            logger.info(f"[{self.name()}][{model_url}] RESPONSE: Native support call successful")
            logger.debug(f"[{self.name()}] Native structured output response: {resp_text}")

            # Try to parse and validate the response
            try:
                json_data = json.loads(resp_text or "")
                # Try to validate with pydantic model
                logger.debug(f"[{self.name()}] Validating response against schema")
                pydantic_model.model_validate(json_data)
                logger.info(f"[{self.name()}] Native structured output generation succeeded")
                return ModelResponse(
                    llm_response=resp_text,
                    response_code=resp_status,
                    tool_calls=tool_calls,
                )
            except (json.JSONDecodeError, ValidationError) as e:
                logger.error(f"[{self.name()}] Native structured output validation failed: {e}")
                logger.info(f"[{self.name()}] Falling back to instruction-based structured output")
                # Fall back to instruction-based approach
                return await self._generate_fallback_structured_output(
                    input, model_params, pydantic_model, **kwargs
                )

        except Exception as e:
            logger.error(f"[{self.name()}] Native structured output generation failed: {e}")
            logger.info(f"[{self.name()}] Falling back to instruction-based structured output")
            # Fall back to instruction-based approach
            return await self._generate_fallback_structured_output(
                input, model_params, pydantic_model, **kwargs
            )

    @track_model_request
    async def _generate_response(
        self, input: ChatPromptValue, model_params: ModelParams, **kwargs: Any
    ) -> ModelResponse:
        # Check the output type and route to appropriate method
        output_type = self.model_config.get("output_type")
        if output_type == "audio":
            return await self._generate_speech(input, model_params)
        elif output_type == "image":
            return await self._generate_image(input, model_params)
        else:
            return await self._generate_text(input, model_params, **kwargs)

    async def _generate_text(
        self, input: ChatPromptValue, model_params: ModelParams, **kwargs: Any
    ) -> ModelResponse:
        """
        Generate text using OpenAI/Azure OpenAI Chat or Completions API.
        This method is called when output_type is 'text' or not specified in model config.
        Args:
            input: ChatPromptValue containing the messages for chat completion
            model_params: Model parameters including URL and auth token
        Returns:
            Model Response
        """
        ret_code = 200
        tool_calls = None
        try:
            # Convert to model format tools
            formatted_tools = self._convert_tools_to_model_format(**kwargs)
            if formatted_tools:
                self.generation_params.update(
                    {"tools": formatted_tools, "tool_choice": kwargs.get("tool_choice", "auto")}
                )
            # Convert input to messages
            messages = self._get_messages(input)
            # Send the request using the litellm
            completion = await litellm.acompletion(
                model=self._get_lite_llm_model_name(),
                messages=messages,
                base_url=model_params.url,
                api_key=model_params.auth_token,
                **self.generation_params,
            )
            self._extract_token_usage(completion)
            resp_text = completion.choices[0].model_dump()["message"]["content"]
            tool_calls = completion.choices[0].model_dump()["message"]["tool_calls"]
        except openai.RateLimitError as e:
            logger.warn(f"OpenAI api request exceeded rate limit: {e}")
            resp_text = f"{constants.ERROR_PREFIX} OpenAI request failed {e}"
            ret_code = 429
        except BadRequestError as e:
            resp_text = f"{constants.ERROR_PREFIX} OpenAI request failed with error: {e.message}"
            logger.error(f"OpenAI request failed with error: {e.message}")
            ret_code = e.status_code
        except Exception as x:
            resp_text = f"{constants.ERROR_PREFIX} OpenAI request failed {x}"
            logger.error(resp_text)
            rcode = self._get_status_from_body(x)
            ret_code = rcode if rcode else 999
        return ModelResponse(llm_response=resp_text, response_code=ret_code, tool_calls=tool_calls)

    async def _generate_speech(
        self, input: ChatPromptValue, model_params: ModelParams, **kwargs: Any
    ) -> ModelResponse:
        """
        Generate speech from text using OpenAI/Azure OpenAI TTS API.
        This method is called when output_type is 'audio' in model config.

        Args:
            input: ChatPromptValue containing the text to convert to speech
            model_params: Model parameters including URL and auth token

        Returns:
            Model Response
        """
        ret_code = 200

        try:
            # Extract text from messages
            text_to_speak = ""
            for message in input.messages:
                if hasattr(message, "content"):
                    text_to_speak += str(message.content) + " "
            text_to_speak = text_to_speak.strip()

            if not text_to_speak:
                logger.error(f"[{self.name()}] No text provided for TTS conversion")
                return ModelResponse(
                    llm_response=f"{constants.ERROR_PREFIX} No text provided for TTS conversion",
                    response_code=400,
                )

            # Validate text length (OpenAI TTS limit is 4096 characters)
            if len(text_to_speak) > 4096:
                logger.warn(
                    f"[{self.name()}] Text exceeds 4096 character limit: {len(text_to_speak)} characters"
                )

            # Get TTS-specific parameters from generation_params or model_config
            voice = self.generation_params.get("voice", self.model_config.get("voice", None))
            response_format = self.generation_params.get(
                "response_format", self.model_config.get("response_format", "wav")
            )
            speed = self.generation_params.get("speed", self.model_config.get("speed", 1.0))

            # Validate speed
            speed = max(0.25, min(4.0, float(speed)))

            logger.debug(
                f"[{self.name()}] TTS parameters - voice: {voice}, format: {response_format}, speed: {speed}"
            )

            # Prepare TTS request parameters
            tts_params = {
                "input": text_to_speak,
                "voice": voice,
                "response_format": response_format,
                "speed": speed,
            }

            # Make the TTS API call
            audio_response = await aspeech(
                model=self._get_lite_llm_model_name(),
                base_url=model_params.url,
                api_key=model_params.auth_token,
                **tts_params,
            )

            # Map response format to MIME type
            mime_types = {
                "mp3": "audio/mpeg",
                "opus": "audio/opus",
                "aac": "audio/aac",
                "flac": "audio/flac",
                "wav": "audio/wav",
                "pcm": "audio/pcm",
            }
            mime_type = mime_types.get(response_format, "audio/wav")

            # Create base64 encoded data URL
            audio_base64 = base64.b64encode(audio_response.content).decode("utf-8")
            data_url = f"data:{mime_type};base64,{audio_base64}"
            resp_text = data_url

        except openai.RateLimitError as e:
            logger.warning(f"[{self.name()}] OpenAI TTS API request exceeded rate limit: {e}")
            resp_text = f"{constants.ERROR_PREFIX} Rate limit exceeded: {e}"
            ret_code = 429
        except openai.APIError as e:
            logger.error(f"[{self.name()}] OpenAI TTS API error: {e}")
            resp_text = f"{constants.ERROR_PREFIX} API error: {e}"
            ret_code = getattr(e, "status_code", 500)
        except Exception as x:
            resp_text = f"{constants.ERROR_PREFIX} TTS request failed: {x}"
            logger.error(f"[{self.name()}] {resp_text}")
            rcode = self._get_status_from_body(x)
            ret_code = rcode if rcode else 999

        return ModelResponse(llm_response=resp_text, response_code=ret_code)

    async def _generate_image(
        self, input: ChatPromptValue, model_params: ModelParams
    ) -> ModelResponse:
        """
        Generate or edit images using OpenAI/Azure OpenAI Image API.
        Auto-detects whether to use generation or editing based on input content:
        - If input contains images: uses edit_image() API (text+image-to-image)
        - If input is text only: uses create_image() API (text-to-image)

        Args:
            input: ChatPromptValue containing text prompt and optionally images
            model_params: Model parameters including URL and auth token

        Returns:
            Model Response
        """
        ret_code = 200
        model_url = model_params.url

        try:

            # Extract text and images from messages
            prompt_text = ""
            image_data_urls = []

            for message in input.messages:
                if hasattr(message, "content"):
                    if isinstance(message.content, str):
                        content = message.content
                        if content.startswith("data:image/"):
                            image_data_urls.append(content)
                        else:
                            prompt_text += content + " "
                    elif isinstance(message.content, list):
                        for item in message.content:
                            if isinstance(item, dict):
                                if item.get("type") == "text":
                                    prompt_text += item.get("text", "") + " "
                                elif item.get("type") == "image_url":
                                    url = item.get("image_url", "")
                                    if isinstance(url, dict):
                                        url = url.get("url", "")
                                    if url.startswith("data:image/"):
                                        image_data_urls.append(url)

            prompt_text = prompt_text.strip()
            if not prompt_text:
                logger.error(f"[{self.name()}] No prompt provided for image generation")
                return ModelResponse(
                    llm_response=f"{constants.ERROR_PREFIX} No prompt provided for image generation",
                    response_code=400,
                )

            if len(prompt_text) < 1000:
                pass
            elif self.model_config.get("model") == "dall-e-2" and len(prompt_text) > 1000:
                logger.warn(
                    f"[{self.name()}] Prompt exceeds 1000 character limit: {len(prompt_text)} characters"
                )
            elif self.model_config.get("model") == "dall-e-3" and len(prompt_text) > 4000:
                logger.warn(
                    f"[{self.name()}] Prompt exceeds 4000 character limit: {len(prompt_text)} characters"
                )
            elif self.model_config.get("model") == "gpt-image-1" and len(prompt_text) > 32000:
                logger.warn(
                    f"[Model {self.name()}] Prompt exceeds 32000 character limit: {len(prompt_text)} characters"
                )

            has_images = len(image_data_urls) > 0

            if has_images:
                # Image editing
                logger.debug(
                    f"[{self.name()}] Detected {len(image_data_urls)} image(s) in input, using image edit API"
                )
                return await self._edit_image_with_data_urls(
                    image_data_urls, prompt_text, model_url, model_params
                )
            else:
                # Text-to-image generation
                logger.debug(
                    f"[{self.name()}] No input images detected, using text-to-image generation API"
                )
                return await self._generate_image_from_text(prompt_text, model_url, model_params)

        except ValueError as e:
            logger.error(f"[{self.name()}] Invalid image data URL: {e}")
            resp_text = f"{constants.ERROR_PREFIX} Invalid image data: {e}"
            ret_code = 400
        except openai.RateLimitError as e:
            logger.warning(f"[{self.name()}] OpenAI Image API rate limit: {e}")
            resp_text = f"{constants.ERROR_PREFIX} Rate limit exceeded: {e}"
            ret_code = 429
        except openai.BadRequestError as e:
            logger.error(f"[{self.name()}] OpenAI Image API bad request: {e}")
            resp_text = f"{constants.ERROR_PREFIX} Bad request: {e}"
            ret_code = 400
        except openai.APIError as e:
            logger.error(f"[{self.name()}] OpenAI Image API error: {e}")
            resp_text = f"{constants.ERROR_PREFIX} API error: {e}"
            ret_code = getattr(e, "status_code", 500)
        except Exception as x:
            resp_text = f"{constants.ERROR_PREFIX} Image operation failed: {x}"
            logger.error(f"[{self.name()}] {resp_text}")
            rcode = self._get_status_from_body(x)
            ret_code = rcode if rcode else 999

        return ModelResponse(llm_response=resp_text, response_code=ret_code)

    async def _generate_image_from_text(
        self, prompt_text: str, model_url: str, model_params: ModelParams
    ) -> ModelResponse:
        """
        Generate images from text prompts (text-to-image).

        Args:
            prompt_text: Text prompt for image generation
            model_url: Model URL
            model_params: Model parameters

        Returns:
            Model Response object
        """
        params = self.generation_params

        # Check if streaming is enabled
        is_streaming = params.get("stream", False)

        logger.debug(
            f"[{self.name()}] Image generation parameters - {params}, streaming: {is_streaming}"
        )

        image_response = await aimage_generation(
            model=self._get_lite_llm_model_name(),
            base_url=model_params.url,
            api_key=model_params.auth_token,
            prompt=prompt_text,
            **params,
        )

        if is_streaming:
            images_data = await self._process_streaming_image_response(image_response)
        else:
            images_data = await self._process_image_response(image_response)

        if len(images_data) == 1:
            return ModelResponse(llm_response=images_data[0], response_code=200)
        else:
            return ModelResponse(llm_response=json.dumps(images_data), response_code=200)

    async def _process_streaming_image_response(self, stream_response):
        """
        Process streaming image generation response.
        Delegates to image_utils for processing.
        """
        from sygra.utils.image_utils import process_streaming_image_response

        return await process_streaming_image_response(stream_response, self.name())

    async def _process_image_response(self, image_response):
        """
        Process regular (non-streaming) image response.
        Delegates to image_utils for processing.
        """
        from sygra.utils.image_utils import process_image_response

        return await process_image_response(image_response, self.name())

    async def _url_to_data_url(self, url: str) -> str:
        """
        Fetch an image from URL and convert to base64 data URL.
        Delegates to image_utils for processing.
        """
        from sygra.utils.image_utils import url_to_data_url

        return await url_to_data_url(url, self.name())

    async def _edit_image_with_data_urls(
        self, image_data_urls: list, prompt_text: str, model_url: str, model_params: ModelParams
    ) -> ModelResponse:
        """
        Edit images using data URLs.
        - GPT-Image-1: Supports up to 16 images
        - DALL-E-2: Supports only 1 image

        Args:
            image_data_urls: List of image data URLs
            prompt_text: Edit instruction
            model_url: Model URL
            model_params: Model parameters

        Returns:
            Model Response object
        """
        import io

        from sygra.utils.image_utils import parse_image_data_url

        if not prompt_text:
            logger.error(f"[{self.name()}] No prompt provided for image editing")
            return ModelResponse(
                llm_response=f"{constants.ERROR_PREFIX} No prompt provided for image editing",
                response_code=400,
            )

        model_name = str(self.model_config.get("model", "")).lower()
        # only gpt-image-1 supports multiple images for editing
        supports_multiple_images = "gpt-image-1" == model_name

        num_images = len(image_data_urls)
        if not supports_multiple_images and num_images > 1:
            logger.warning(
                f"[{self.name()}] Model {model_name} only supports single image editing. "
                f"Using first image only. Additional {num_images - 1} image(s) will be ignored."
            )
        elif supports_multiple_images and num_images > 16:
            logger.warning(
                f"[{self.name()}] Model {model_name} supports max 16 images. "
                f"Using first 16 images only. {num_images - 16} image(s) will be ignored."
            )
            image_data_urls = image_data_urls[:16]

        params = self.generation_params

        # Check if streaming is enabled
        is_streaming = params.get("stream", False)

        logger.debug(
            f"[{self.name()}] Image edit parameters - images: {num_images}, params: {params}, streaming: {is_streaming}"
        )

        # Decode images
        if supports_multiple_images and num_images > 1:
            # Multiple images for GPT-Image-1
            image_files = []
            for idx, data_url in enumerate(image_data_urls):
                _, _, img_bytes = parse_image_data_url(data_url)
                img_file = io.BytesIO(img_bytes)
                img_file.name = f"image_{idx}.png"
                image_files.append(img_file)

            image_param = image_files
        else:
            # Single image for DALL-E-2 or single image input
            _, _, image_bytes = parse_image_data_url(image_data_urls[0])
            image_file = io.BytesIO(image_bytes)
            image_file.name = "image.png"

            image_param = [image_file]

        # Call the image edit API
        image_response = await aimage_edit(
            model=self._get_lite_llm_model_name(),
            base_url=model_params.url,
            api_key=model_params.auth_token,
            image=image_param,
            prompt=prompt_text,
            **params,
        )

        # Handle streaming response
        if is_streaming:
            images_data = await self._process_streaming_image_response(image_response)
        else:
            # Process regular response - convert URLs to data URLs
            images_data = await self._process_image_response(image_response)

        if len(images_data) == 1:
            return ModelResponse(llm_response=images_data[0], response_code=200)
        else:
            return ModelResponse(llm_response=json.dumps(images_data), response_code=200)
