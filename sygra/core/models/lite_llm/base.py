from __future__ import annotations

import base64
import json
from typing import Any, Optional, Tuple, Type, cast

from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompt_values import ChatPromptValue
from litellm import acompletion, aimage_edit, aimage_generation, aspeech, atext_completion
from openai import APIError, BadRequestError, RateLimitError
from pydantic import BaseModel

import sygra.utils.constants as constants
from sygra.core.models.custom_models import BaseCustomModel, ModelParams
from sygra.core.models.model_response import ModelResponse
from sygra.logger.logger_config import logger
from sygra.metadata.metadata_integration import track_model_request


class LiteLLMBase(BaseCustomModel):
    """
    An intermediate base for LiteLLM-backed models that centralizes the common
    request patterns (chat vs completions), structured output, image and speech
    generation, response parsing, and exception mapping.

    Subclasses should override the provider hooks below to adapt parameter names
    and capabilities without duplicating logic in each model class.
    """

    # ----------------------- Provider hooks (override in subclasses) -----------------------
    def _base_url_param(self) -> str:
        """Return the name of the parameter used by LiteLLM for the base URL.
        Common values are 'api_base' (default) or 'base_url' (OpenAI)."""
        return "api_base"

    def _requires_api_key(self) -> bool:
        """Whether this provider requires an api_key parameter."""
        return True

    def _extra_call_params(self) -> dict[str, Any]:
        """Provider-specific extra params to pass to LiteLLM calls (e.g., api_version)."""
        return {}

    def _provider_label(self) -> str:
        """Human-readable provider label used in error messages (e.g., 'OpenAI', 'Azure OpenAI')."""
        return self.name()

    def _native_structured_output_spec(self) -> Optional[Tuple[str, str]]:
        """
        If provider supports native structured output, return a tuple of
        (param_name, value_kind), where value_kind is either:
        - 'pydantic' -> pass the pydantic model class directly
        - 'schema'   -> pass pydantic_model.model_json_schema()
        Return None if not supported.
        """
        return None

    def _check_content_filter_finish_reason(self) -> bool:
        """Whether to convert finish_reason == 'content_filter' to a 400 error (Azure AI)."""
        return False

    # ----- Async call providers (override to return provider-module functions so tests can patch there) -----
    def _fn_acompletion(self):
        return acompletion

    def _fn_atext_completion(self):
        return atext_completion

    def _fn_aspeech(self):
        return aspeech

    def _fn_aimage_generation(self):
        return aimage_generation

    def _fn_aimage_edit(self):
        return aimage_edit

    # ----------------------- Common helpers -----------------------
    def _apply_tools(self, **kwargs: Any) -> None:
        formatted_tools = self._convert_tools_to_model_format(**kwargs)
        if formatted_tools:
            update = {"tools": formatted_tools, "tool_choice": kwargs.get("tool_choice", "auto")}
            # Azure AI needs allow-list for tool_choice propagation
            if self._get_model_prefix() == "azure_ai":
                update["allowed_openai_params"] = ["tool_choice"]
            self.generation_params.update(update)

    def _build_common_kwargs(self, model_params: ModelParams) -> dict[str, Any]:
        base_url_key = self._base_url_param()
        common: dict[str, Any] = {
            "model": self._get_lite_llm_model_name(),
            base_url_key: model_params.url,
        }
        if self._requires_api_key():
            common["api_key"] = model_params.auth_token
        common.update(self._extra_call_params())
        return common

    def _parse_chat_choice(self, completion: Any) -> Tuple[str, Optional[list]]:
        md = completion.choices[0].model_dump()
        message = md.get("message", {})
        return message.get("content"), message.get("tool_calls")

    def _parse_completions_choice(self, completion: Any) -> Tuple[str, None]:
        md = completion.choices[0].model_dump()
        return md.get("text"), None

    def _status_code_of(self, completion: Any) -> int:
        code = getattr(completion, "status_code", None)
        return code if isinstance(code, int) else 200

    def _map_exception(self, e: Exception, context: str) -> ModelResponse:
        if isinstance(e, RateLimitError):
            logger.warning(
                f"[{self.name()}] {context} request exceeded rate limit: {getattr(e, 'message', e)}"
            )
            return ModelResponse(
                llm_response=f"{constants.ERROR_PREFIX} {context} request exceeded rate limit: {getattr(e, 'message', e)}",
                response_code=getattr(e, "status_code", 429),
            )
        if isinstance(e, BadRequestError):
            logger.error(f"[{self.name()}] {context} bad request: {getattr(e, 'message', e)}")
            return ModelResponse(
                llm_response=f"{constants.ERROR_PREFIX} {context} bad request: {getattr(e, 'message', e)}",
                response_code=getattr(e, "status_code", 400),
            )
        if isinstance(e, APIError):
            msg = getattr(e, "message", e)
            logger.error(f"[{self.name()}] {context} error: {msg}")
            # Match expected phrasing for TTS tests
            if "TTS" in context:
                err_text = f"{constants.ERROR_PREFIX} {context} request failed with error: {msg}"
            else:
                err_text = f"{constants.ERROR_PREFIX} {context} error: {msg}"
            return ModelResponse(
                llm_response=err_text,
                response_code=getattr(e, "status_code", 500),
            )
        logger.error(f"[{self.name()}] {context} request failed: {e}")
        # Try to infer status from body
        rcode = self._get_status_from_body(e)
        return ModelResponse(
            llm_response=f"{constants.ERROR_PREFIX} {context} request failed: {e}",
            response_code=rcode if rcode else 999,
        )

    # ----------------------- Text (chat or completions) -----------------------
    async def _generate_text(
        self, input: ChatPromptValue, model_params: ModelParams
    ) -> ModelResponse:
        common = self._build_common_kwargs(model_params)
        tool_calls = None
        try:
            if self.model_config.get("completions_api", False):
                prompt = self.get_chat_formatted_text(
                    input.messages, **(self.chat_template_params or {})
                )
                completion = await self._fn_atext_completion()(
                    prompt=prompt, **common, **self.generation_params
                )
                self._extract_token_usage(completion)
                resp_text, tool_calls = self._parse_completions_choice(completion)
            else:
                messages = self._get_messages(input)
                completion = await self._fn_acompletion()(
                    messages=messages, **common, **self.generation_params
                )
                self._extract_token_usage(completion)
                resp_text, tool_calls = self._parse_chat_choice(completion)
                # Content filter handling
                if self._check_content_filter_finish_reason():
                    finish_reason = completion.choices[0].model_dump().get("finish_reason")
                    if finish_reason == "content_filter":
                        logger.error(
                            f"[{self.name()}] Azure request failed with code: 400 and error: {constants.ERROR_PREFIX} Blocked by azure content filter"
                        )
                        return ModelResponse(
                            llm_response=f"{constants.ERROR_PREFIX} Blocked by azure content filter",
                            response_code=400,
                            finish_reason=finish_reason,
                        )
            return ModelResponse(
                llm_response=resp_text,
                response_code=self._status_code_of(completion),
                tool_calls=tool_calls,
            )
        except Exception as e:
            return self._map_exception(e, f"{self._provider_label()} API")

    # ----------------------- Native structured output -----------------------

    @track_model_request
    async def _generate_native_structured_output(
        self,
        input: ChatPromptValue,
        model_params: ModelParams,
        pydantic_model: Type[BaseModel],
        **kwargs: Any,
    ) -> ModelResponse:
        self._apply_tools(**kwargs)
        spec = self._native_structured_output_spec()
        if not spec:
            logger.info(
                f"[{self.name()}] Native structured output not supported; using fallback instructions"
            )
            return cast(
                ModelResponse,
                await self._generate_fallback_structured_output(
                    input, model_params, pydantic_model
                ),
            )
        param_name, value_kind = spec
        common = self._build_common_kwargs(model_params)
        try:
            # Construct provider-specific param
            extra: dict[str, Any] = {}
            if value_kind == "pydantic":
                extra[param_name] = pydantic_model
            else:
                extra[param_name] = pydantic_model.model_json_schema()

            all_params = {**(self.generation_params or {}), **extra}

            if self.model_config.get("completions_api", False):
                prompt = self.get_chat_formatted_text(
                    input.messages, **(self.chat_template_params or {})
                )
                completion = await self._fn_atext_completion()(
                    prompt=prompt, **common, **all_params
                )
                self._extract_token_usage(completion)
                resp_text, tool_calls = self._parse_completions_choice(completion)
            else:
                messages = self._get_messages(input)
                completion = await self._fn_acompletion()(messages=messages, **common, **all_params)
                self._extract_token_usage(completion)
                resp_text, tool_calls = self._parse_chat_choice(completion)

            status = self._status_code_of(completion)
            if status != 200:
                logger.error(
                    f"[{self.name()}] Native structured output request failed with code: {status}"
                )
                # Fall back to instruction-based approach
                return cast(
                    ModelResponse,
                    await self._generate_fallback_structured_output(
                        input, model_params, pydantic_model
                    ),
                )

            # Validate result; on failure, fall back
            try:
                if value_kind == "pydantic":
                    json_data = json.loads(resp_text or "")
                    pydantic_model.model_validate(json_data)
                else:
                    parsed_data = json.loads(resp_text or "{}")
                    pydantic_model(**parsed_data)
                return ModelResponse(
                    llm_response=resp_text, response_code=status, tool_calls=tool_calls
                )
            except Exception as ve:
                logger.error(f"[{self.name()}] Native structured output validation failed: {ve}")
                # Fall back to instruction-based approach
                return cast(
                    ModelResponse,
                    await self._generate_fallback_structured_output(
                        input, model_params, pydantic_model
                    ),
                )
        except Exception as e:
            return self._map_exception(e, f"{self._provider_label()} API")

    @track_model_request
    async def _generate_fallback_structured_output(
        self,
        input: ChatPromptValue,
        model_params: ModelParams,
        pydantic_model: Type[BaseModel],
        **kwargs: Any,
    ) -> ModelResponse:
        try:
            logger.info("Generating fallback structured output (LiteLLM)")
            self._apply_tools(**kwargs)

            parser = PydanticOutputParser(pydantic_object=pydantic_model)
            format_instructions = parser.get_format_instructions()

            modified_messages = list(input.messages)
            if modified_messages and getattr(modified_messages[-1], "content", None):
                modified_messages[-1].content = (
                    str(modified_messages[-1].content) + f"\n\n{format_instructions}"
                )

            modified_input = ChatPromptValue(messages=modified_messages)

            model_response: ModelResponse = await self._generate_text(modified_input, model_params)

            if model_response.response_code != 200:
                logger.error(
                    f"[{self.name()}] Fallback structured output failed with code: {model_response.response_code}"
                )
                return model_response

            try:
                parsed_output = parser.parse(model_response.llm_response or "")
                logger.info(f"[{self.name()}] Fallback structured output parsed successfully")
                return ModelResponse(
                    llm_response=parsed_output.model_dump_json(),
                    response_code=200,
                    tool_calls=model_response.tool_calls,
                )
            except Exception as ve:
                logger.warning(f"[{self.name()}] Failed to parse fallback structured output: {ve}")
                return model_response
        except Exception as e:
            return self._map_exception(e, f"{self._provider_label()} API")

    # ----------------------- Speech -----------------------
    async def _generate_speech(
        self, input: ChatPromptValue, model_params: ModelParams
    ) -> ModelResponse:
        common = self._build_common_kwargs(model_params)
        ret_code = 200
        try:
            text_to_speak = " ".join(
                [str(getattr(m, "content", "")) for m in input.messages]
            ).strip()
            if not text_to_speak:
                return ModelResponse(
                    llm_response=f"{constants.ERROR_PREFIX} No text provided for TTS conversion",
                    response_code=400,
                )

            voice = self.generation_params.get("voice", self.model_config.get("voice", None))
            response_format = self.generation_params.get(
                "response_format", self.model_config.get("response_format", "wav")
            )
            speed = max(
                0.25,
                min(
                    4.0,
                    float(self.generation_params.get("speed", self.model_config.get("speed", 1.0))),
                ),
            )

            tts_params = {
                "input": text_to_speak,
                "voice": voice,
                "response_format": response_format,
                "speed": speed,
            }
            audio_response = await self._fn_aspeech()(**common, **tts_params)

            mime_types = {
                "mp3": "audio/mpeg",
                "opus": "audio/opus",
                "aac": "audio/aac",
                "flac": "audio/flac",
                "wav": "audio/wav",
                "pcm": "audio/pcm",
            }
            mime_type = mime_types.get(response_format, "audio/wav")
            audio_base64 = base64.b64encode(audio_response.content).decode("utf-8")
            data_url = f"data:{mime_type};base64,{audio_base64}"
            return ModelResponse(llm_response=data_url, response_code=ret_code)
        except Exception as e:
            return self._map_exception(e, f"{self._provider_label()} TTS")

    async def _generate_audio_chat_completion(
        self, input: ChatPromptValue, model_params: ModelParams
    ) -> ModelResponse:
        try:
            messages = self._get_messages(input)
            processed_messages: list[dict[str, Any]] = []
            for m in messages:
                content = m.get("content")
                if isinstance(content, list):
                    new_content = []
                    for item in content:
                        if isinstance(item, dict) and item.get("type") == "audio_url":
                            audio_url = item.get("audio_url", {})
                            if isinstance(audio_url, dict):
                                data_url = audio_url.get("url", "")
                            else:
                                data_url = audio_url
                            if isinstance(data_url, str) and data_url.startswith("data:audio/"):
                                parts = data_url.split(";base64,")
                                if len(parts) == 2:
                                    mime_header = parts[0]
                                    base64_data = parts[1]
                                    mime_parts = mime_header.split(":")
                                    if len(mime_parts) == 2:
                                        format_part = mime_parts[1].replace("audio/", "")
                                        if format_part == "mpeg":
                                            format_part = "mp3"
                                        new_content.append(
                                            {
                                                "type": "input_audio",
                                                "input_audio": {
                                                    "data": base64_data,
                                                    "format": format_part,
                                                },
                                            }
                                        )
                                    else:
                                        new_content.append(item)
                                else:
                                    new_content.append(item)
                            else:
                                new_content.append(item)
                        else:
                            new_content.append(item)
                    m = {**m, "content": new_content}
                processed_messages.append(m)

            output_type = self.model_config.get("output_type")
            has_audio_output = output_type == "audio"
            has_audio_input = any(
                isinstance(m.get("content"), list)
                and any(it.get("type") == "input_audio" for it in m.get("content", []))
                for m in processed_messages
            )
            modalities = ["text"]
            if has_audio_output:
                if "audio" not in modalities:
                    modalities.append("audio")
            if not has_audio_input:
                has_audio_output = True
                modalities = ["text", "audio"]

            audio_params: dict[str, Any] = {}
            if has_audio_output:
                ap = self.generation_params.get("audio")
                if isinstance(ap, dict):
                    audio_params = ap
                else:
                    audio_params = {"voice": "alloy", "format": "wav"}
                    self.generation_params["audio"] = audio_params

            common = self._build_common_kwargs(model_params)
            all_params = {**self.generation_params}
            if "audio" in modalities:
                all_params["modalities"] = modalities

            completion = await self._fn_acompletion()(
                messages=processed_messages, **common, **all_params
            )
            self._extract_token_usage(completion)
            msg = completion.choices[0].model_dump().get("message", {})
            if "audio" in modalities and isinstance(msg.get("audio"), dict):
                audio_base64 = msg["audio"].get("data", "")
                fmt = audio_params.get("format", "wav")
                mime_types = {
                    "mp3": "audio/mpeg",
                    "opus": "audio/opus",
                    "aac": "audio/aac",
                    "flac": "audio/flac",
                    "wav": "audio/wav",
                    "pcm": "audio/pcm",
                }
                mime_type = mime_types.get(fmt, "audio/wav")
                data_url = f"data:{mime_type};base64,{audio_base64}"
                return ModelResponse(
                    llm_response=data_url, response_code=self._status_code_of(completion)
                )
            else:
                resp_text = msg.get("content", "") or None
                return ModelResponse(
                    llm_response=resp_text, response_code=self._status_code_of(completion)
                )
        except Exception as e:
            return self._map_exception(e, f"{self._provider_label()} API")

    # ----------------------- Image -----------------------
    async def _extract_prompt_and_images(self, input: ChatPromptValue) -> tuple[str, list[str]]:
        prompt_text = ""
        image_data_urls: list[str] = []
        for message in input.messages:
            if hasattr(message, "content"):
                content = getattr(message, "content")
                if isinstance(content, str):
                    if content.startswith("data:image/"):
                        image_data_urls.append(content)
                    else:
                        prompt_text += f"{content} "
                elif isinstance(content, list):
                    for item in content:
                        if isinstance(item, dict):
                            if item.get("type") == "text":
                                prompt_text += f"{item.get('text', '')} "
                            elif item.get("type") == "image_url":
                                url = item.get("image_url", "")
                                if isinstance(url, dict):
                                    url = url.get("url", "")
                                if isinstance(url, str) and url.startswith("data:image/"):
                                    image_data_urls.append(url)
        return prompt_text.strip(), image_data_urls

    def _image_capabilities(self) -> dict[str, Any]:
        caps = self.model_config.get("image_capabilities")
        out: dict[str, Any] = {}
        if isinstance(caps, dict):
            prompt_limit = caps.get("prompt_char_limit")
            max_edit_images = caps.get("max_edit_images")
            if isinstance(prompt_limit, int) and prompt_limit > 0:
                out["prompt_char_limit"] = prompt_limit
            if isinstance(max_edit_images, int) and max_edit_images > 0:
                out["max_edit_images"] = max_edit_images
        return out

    async def _generate_image(
        self, input: ChatPromptValue, model_params: ModelParams
    ) -> ModelResponse:
        common = self._build_common_kwargs(model_params)
        try:
            prompt_text, image_data_urls = await self._extract_prompt_and_images(input)
            if not prompt_text:
                return ModelResponse(
                    llm_response=f"{constants.ERROR_PREFIX} No prompt provided for image generation",
                    response_code=400,
                )

            caps = self._image_capabilities()
            limit = caps.get("prompt_char_limit")
            if isinstance(limit, int) and limit > 0 and len(prompt_text) > limit:
                logger.warning(
                    f"[{self.name()}] Prompt exceeds {limit} character limit: {len(prompt_text)} characters"
                )

            has_images = len(image_data_urls) > 0
            params = self.generation_params
            is_streaming = params.get("stream", False)

            if has_images:
                # Image editing path
                # Validate provider supports image editing before proceeding
                fn_edit = getattr(self, "_fn_aimage_edit", None)
                if not callable(fn_edit):
                    logger.error(
                        f"[{self.name()}] Image editing not supported by {self._provider_label()}"
                    )
                    return ModelResponse(
                        llm_response=f"{constants.ERROR_PREFIX} Image editing is not supported by {self._provider_label()}",
                        response_code=400,
                    )
                import io

                from sygra.utils.image_utils import parse_image_data_url

                max_imgs = caps.get("max_edit_images")
                if isinstance(max_imgs, int) and max_imgs > 0:
                    num_images = len(image_data_urls)
                    if num_images > max_imgs:
                        logger.warning(
                            f"[{self.name()}] Only {max_imgs} input image(s) supported for editing. Using first {max_imgs} image(s). {num_images - max_imgs} image(s) will be ignored."
                        )
                        image_data_urls = image_data_urls[:max_imgs]

                image_param: list[Any]
                if len(image_data_urls) > 1:
                    image_files = []
                    for idx, data_url in enumerate(image_data_urls):
                        _, _, img_bytes = parse_image_data_url(data_url)
                        img_file = io.BytesIO(img_bytes)
                        img_file.name = f"image_{idx}.png"
                        image_files.append(img_file)
                    image_param = image_files
                else:
                    _, _, image_bytes = parse_image_data_url(image_data_urls[0])
                    image_file = io.BytesIO(image_bytes)
                    image_file.name = "image.png"
                    image_param = [image_file]
                try:
                    image_response = await self._fn_aimage_edit()(
                        image=image_param, prompt=prompt_text, **common, **params
                    )
                except NotImplementedError:
                    logger.error(
                        f"[{self.name()}] Image editing not supported by {self._provider_label()}"
                    )
                    return ModelResponse(
                        llm_response=f"{constants.ERROR_PREFIX} Image editing is not supported by {self._provider_label()}",
                        response_code=400,
                    )
                if is_streaming:
                    images_data = await self._process_streaming_image_response(image_response)
                else:
                    images_data = await self._process_image_response(image_response)
            else:
                # Text-to-image path
                image_response = await self._fn_aimage_generation()(
                    prompt=prompt_text, **common, **params
                )
                if is_streaming:
                    images_data = await self._process_streaming_image_response(image_response)
                else:
                    images_data = await self._process_image_response(image_response)

            if len(images_data) == 1:
                return ModelResponse(llm_response=images_data[0], response_code=200)
            else:
                return ModelResponse(llm_response=json.dumps(images_data), response_code=200)
        except ValueError as e:
            # Malformed image data (e.g., bad data URL)
            logger.error(f"[{self.name()}] Invalid image data URL: {e}")
            return ModelResponse(
                llm_response=f"{constants.ERROR_PREFIX} Invalid image data: {e}",
                response_code=400,
            )
        except Exception as e:
            return self._map_exception(e, f"{self._provider_label()} Image API")

    # ----------------------- Image helpers (overridable for tests) -----------------------
    async def _process_streaming_image_response(self, stream_response):
        from sygra.utils.image_utils import process_streaming_image_response

        return await process_streaming_image_response(stream_response, self.name())

    async def _process_image_response(self, image_response):
        from sygra.utils.image_utils import process_image_response

        return await process_image_response(image_response, self.name())

    async def _url_to_data_url(self, url: str) -> str:
        from sygra.utils.image_utils import url_to_data_url

        return await url_to_data_url(url, self.name())
