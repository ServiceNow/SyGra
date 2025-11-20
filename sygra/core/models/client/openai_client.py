from typing import Any, Dict, List, Optional, Sequence, Union, cast

import httpx
from langchain_core.messages import BaseMessage
from langchain_openai.chat_models.base import _convert_message_to_dict
from openai import AsyncOpenAI, OpenAI
from pydantic import BaseModel, ConfigDict, Field

from sygra.core.models.client.base_client import BaseClient
from sygra.logger.logger_config import logger
from sygra.utils import constants


class OpenAIClientConfig(BaseModel):
    base_url: str = Field(..., description="Base URL for the OpenAI API")
    api_key: str = Field(..., description="API key for authentication")
    http_client: Union[httpx.AsyncClient, httpx.Client] = Field(
        ..., description="HTTP client to use"
    )
    # default_headers: Dict[str, str] = Field(default={"Connection": "close"},
    #                                         description="Default headers for API requests")
    timeout: int = Field(
        default=constants.DEFAULT_TIMEOUT, description="Request timeout in seconds"
    )
    max_retries: int = Field(default=3, description="Maximum number of retries for failed requests")

    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        extra="allow",
    )


class OpenAIClient(BaseClient):
    def __init__(
        self,
        async_client=True,
        chat_completions_api=True,
        stop: Optional[List[str]] = None,
        **client_kwargs,
    ):
        """
        Initialize a OpenAI client.

        Args:
        - async_client (bool, optional): Whether to use an async client. Defaults to False.
        - chat_completions_api (bool, optional): Whether to use the chat completions API. Defaults to True.
        - stop (Optional[List[str]], optional): List of strings indicating when to stop generating text. Defaults to None.
        - **client_kwargs: Additional keyword arguments to pass to the OpenAI or AsyncOpenAI constructor.
        """
        super().__init__(**client_kwargs)

        # Validate client_kwargs using Pydantic model
        validated_config = OpenAIClientConfig(**client_kwargs)
        validated_client_kwargs = validated_config.model_dump()

        self.client: Any = (
            AsyncOpenAI(**validated_client_kwargs)
            if async_client
            else OpenAI(**validated_client_kwargs)
        )
        self.async_client = async_client
        self.chat_completions_api = chat_completions_api
        self.stop = stop

    def build_request(
        self,
        messages: Optional[Sequence[BaseMessage]] = None,
        formatted_prompt: Optional[str] = None,
        stop: Optional[List[str]] = None,
        **kwargs: Any,
    ) -> Any:
        """
        Build a request payload for the model.

        If the model is using the chat completions API, the messages will be converted to a list of dictionaries
        and added to the payload under the key "messages". If the model is using the completions API, the formatted
        prompt will be added to the payload under the key "prompt". If the messages or formatted prompt are invalid,
        a ValueError will be raised.

        Args:
            messages (List[BaseMessage]): The messages to pass to the model. This is necessary for chat completions API.
            formatted_prompt (str): The formatted prompt to pass to the model. This is necessary for completions API.
            stop (Optional[List[str]], optional): List of stop sequences that indicate when text generation should halt. If None, the client-level default set during initialization will be used.
            **kwargs: Additional keyword arguments to include in the payload.

        Returns:
            dict: The request payload.

        Raises:
            ValueError: If the messages or formatted prompt are invalid.
        """
        # Prefer explicit stop passed to this call; otherwise use client default
        effective_stop = stop if stop is not None else self.stop
        if effective_stop is not None:
            kwargs["stop"] = effective_stop
        payload = {**kwargs}
        if self.chat_completions_api:
            if messages is not None and len(messages) > 0:
                messages = self._convert_input(messages).to_messages()
                payload["messages"] = [_convert_message_to_dict(m) for m in messages]
                return payload
            else:
                logger.error(
                    "messages passed is None or empty. Please provide valid messages to build request with chat completions API."
                )
                raise ValueError(
                    "messages passed is None or empty. Please provide valid messages to build request with chat completions API."
                )
        else:
            if formatted_prompt is not None and len(formatted_prompt) > 0:
                payload["prompt"] = formatted_prompt
                return payload
            else:
                logger.error(
                    "formatted_prompt passed is None. Please provide a valid formatted prompt to build request with completion API."
                )
                raise ValueError(
                    "formatted_prompt passed is None. Please provide a valid formatted prompt to build request with completion API."
                )

    def send_request(
        self,
        payload: Any,
        model_name: str,
        generation_params: Optional[Dict[str, Any]] = None,
    ):
        """
        Send a request to the Vllm hosted model.

        This method takes in a payload dictionary, a model name, and generation parameters.
        It sends a request to the Vllm hosted model with the given payload and generation parameters.
        If the chat completions API is being used, it will call the `chat.completions.create` method.
        Otherwise, it will call the `completions.create` method.

        Args:
            payload (dict): The payload to send to the model.
            model_name (str): The name of the model to send the request to.
            generation_params (Optional[Dict[str, Any]], optional): Additional generation parameters to pass to the model. Defaults to None.

        Returns:
            Any: The response from the model.
        """
        generation_params = generation_params or {}

        # Check for vLLM-specific parameters
        additional_extensions = {
            "guided_json",
            "guided_regex",
            "guided_choice",
            "guided_grammar",
        }

        additional_params = {
            k: v for k, v in generation_params.items() if k in additional_extensions
        }
        standard_params = {
            k: v for k, v in generation_params.items() if k not in additional_extensions
        }

        client = cast(Any, self.client)
        if not additional_params:
            if self.chat_completions_api:
                return client.chat.completions.create(
                    **payload, model=model_name, **generation_params
                )
            else:
                return client.completions.create(**payload, model=model_name, **generation_params)
        else:
            logger.info(f"Detected vLLM-specific parameters: {additional_params}")
            # Use extra_body to pass vLLM-specific parameters
            if self.chat_completions_api:
                return client.chat.completions.create(
                    **payload,
                    model=model_name,
                    extra_body=additional_params,
                    **standard_params,
                )
            else:
                return client.completions.create(
                    **payload,
                    model=model_name,
                    extra_body=additional_params,
                    **standard_params,
                )

    async def create_speech(
        self,
        model: str,
        input: str,
        voice: str,
        response_format: str = "mp3",
        speed: float = 1.0,
    ) -> Any:
        """
        Create speech audio from text using OpenAI's text-to-speech API.

        Args:
            model (str): The TTS model to use (e.g., 'tts-1', 'tts-1-hd')
            input (str): The text to convert to speech
            voice (str): The voice to use like alloy, echo, fable, onyx, nova, shimmer etc.
            response_format (str, optional): The audio formats like mp3, opus, aac, flac, wav, pcm etc. Defaults to 'wav'
            speed (float, optional): The speed of the audio (0.25 to 4.0). Defaults to 1.0

        Returns:
            Any: The audio response from the API

        Raises:
            ValueError: If async_client is False (TTS requires async client)
        """
        if not self.async_client:
            raise ValueError(
                "TTS API requires async client. Please initialize with async_client=True"
            )

        client = cast(Any, self.client)
        return await client.audio.speech.create(
            model=model,
            input=input,
            voice=voice,
            response_format=response_format,
            speed=speed,
        )

    async def create_transcription(
        self,
        file: Any,
        model: str,
        **kwargs: Any,
    ) -> Any:
        """
        Transcribe audio to text using OpenAI's audio transcription API.

        Args:
            file: The audio file to transcribe. Can be a file path (str) or file-like object.
                  Supported formats: mp3, mp4, mpeg, mpga, m4a, wav, webm, flac, ogg
            model (str): The transcription model to use (e.g., 'whisper-1', 'gpt-4o-transcribe')
            **kwargs: Additional parameters supported by the API:
                - language (str): Language of the input audio in ISO-639-1 format (e.g., 'en', 'es')
                - prompt (str): Optional text to guide the model's style
                - response_format (str): Format of the transcript output
                  Options: 'json', 'text', 'srt', 'verbose_json', 'vtt'. Defaults to 'json'
                - temperature (float): Sampling temperature between 0 and 1. Defaults to 0
                - timestamp_granularities (list): Timestamp granularities for segments
                  Options: ['word', 'segment']. Only for verbose_json format

        Returns:
            Any: The transcription response from the API

        Raises:
            ValueError: If async_client is False (Transcription requires async client)
        """
        if not self.async_client:
            raise ValueError(
                "Transcription API requires async client. Please initialize with async_client=True"
            )

        client = cast(Any, self.client)

        # Build the request parameters with all provided kwargs
        params: Dict[str, Any] = {
            "file": file,
            "model": model,
            **kwargs,  # Pass all additional parameters
        }

        return await client.audio.transcriptions.create(**params)

    async def create_image(
        self,
        model: str,
        prompt: str,
        **kwargs: Any,
    ) -> Any:
        """
        Generate images from text prompts using OpenAI's image generation API.

        Args:
            model (str): The image model to use (e.g., 'dall-e-2', 'dall-e-3', 'gpt-image-1')
            prompt (str): The text description of the desired image(s)
            **kwargs: Additional parameters supported by the API:
                - size (str): Image size (e.g., "1024x1024", "1792x1024")
                - quality (str): "standard" or "hd"
                - n (int): Number of images to generate
                - response_format (str): "url" or "b64_json"
                - style (str): "vivid" or "natural"
                - stream (bool): Enable streaming responses
                - Any other parameters supported by OpenAI API

        Returns:
            Any: The image generation response from the API

        Raises:
            ValueError: If async_client is False (Image generation requires async client)
        """
        if not self.async_client:
            raise ValueError(
                "Image generation API requires async client. Please initialize with async_client=True"
            )

        client = cast(Any, self.client)

        # Build the request parameters with all provided kwargs
        params: Dict[str, Any] = {
            "model": model,
            "prompt": prompt,
            **kwargs,  # Pass all additional parameters
        }

        return await client.images.generate(**params)

    async def edit_image(
        self,
        image: Union[Any, List[Any]],
        prompt: str,
        **kwargs: Any,
    ) -> Any:
        """
        Edit existing image(s) based on a text prompt.

        Args:
            image: The image(s) to edit. Can be:
                   - Single image: file path (str) or file-like object
                   - Multiple images (gpt-image-1 only): list of file paths or file-like objects
                   For gpt-image-1: png, webp, or jpg < 50MB each, up to 16 images
                   For dall-e-2: single square png < 4MB
            prompt (str): A text description of the desired edits
            **kwargs: Additional parameters supported by the API:
                - model (str): Model to use (e.g., 'dall-e-2', 'gpt-image-1')
                - n (int): Number of images to generate
                - size (str): Size of generated images
                - response_format (str): "url" or "b64_json"
                - stream (bool): Enable streaming responses
                - Any other parameters supported by OpenAI API

        Returns:
            Any: The image edit response from the API

        Raises:
            ValueError: If async_client is False
        """
        if not self.async_client:
            raise ValueError(
                "Image edit API requires async client. Please initialize with async_client=True"
            )

        client = cast(Any, self.client)

        # Build the request parameters with all provided kwargs
        params: Dict[str, Any] = {
            "image": image,
            "prompt": prompt,
            **kwargs,  # Pass all additional parameters
        }

        return await client.images.edit(**params)

    async def create_image_variation(
        self,
        image: Any,
        model: Optional[str] = None,
        n: int = 1,
        size: Optional[str] = None,
        response_format: Optional[str] = None,
    ) -> Any:
        """
        Create a variation of a given image.

        Args:
            image: The image to use as the basis for variation(s). Must be a valid PNG file,
                   less than 4MB, and square. Can be a file path (str) or file-like object.
            model (str, optional): The model to use (e.g., 'dall-e-2')
            n (int, optional): Number of variations to generate (1-10). Defaults to 1
            size (str, optional): Size of generated images: "256x256", "512x512", or "1024x1024"
            response_format (str, optional): "url" or "b64_json"

        Returns:
            Any: The image variation response from the API

        Raises:
            ValueError: If async_client is False
        """
        if not self.async_client:
            raise ValueError(
                "Image variation API requires async client. Please initialize with async_client=True"
            )

        client = cast(Any, self.client)

        # Build the request parameters
        params: Dict[str, Any] = {
            "image": image,
            "n": n,
        }

        # Add optional parameters if provided
        if model is not None:
            params["model"] = model
        if size is not None:
            params["size"] = size
        if response_format is not None:
            params["response_format"] = response_format

        return await client.images.create_variation(**params)
