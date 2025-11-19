from __future__ import annotations

import json
import logging
from typing import Any, Type

import openai
from langchain_core.prompt_values import ChatPromptValue
from litellm import BadRequestError, acompletion, atext_completion
from pydantic import BaseModel, ValidationError

import sygra.utils.constants as constants
from sygra.core.models.custom_models import BaseCustomModel, ModelParams
from sygra.core.models.model_response import ModelResponse
from sygra.logger.logger_config import logger
from sygra.metadata.metadata_integration import track_model_request
from sygra.utils import utils

logging.getLogger("LiteLLM").setLevel(logging.WARNING)


class CustomVLLM(BaseCustomModel):
    def __init__(self, model_config: dict[str, Any]) -> None:
        super().__init__(model_config)
        utils.validate_required_keys(["url", "auth_token"], model_config, "model")
        self.model_config = model_config
        self.auth_token = str(model_config.get("auth_token")).replace("Bearer ", "")
        self.model_serving_name = model_config.get("model_serving_name", self.name())

    def _validate_completions_api_model_support(self) -> None:
        logger.info(f"Model {self.name()} supports completion API.")

    def _get_lite_llm_model_name(self) -> str:
        return f"hosted_vllm/{self.model_serving_name}"

    async def _generate_native_structured_output(
        self,
        input: ChatPromptValue,
        model_params: ModelParams,
        pydantic_model: Type[BaseModel],
        **kwargs: Any,
    ) -> ModelResponse:
        """Generate structured output using vLLM's guided generation"""
        logger.info(f"[{self.name()}] Attempting native structured output generation")
        model_url = model_params.url
        try:
            tool_calls = None

            # Create JSON schema for guided generation
            json_schema = pydantic_model.model_json_schema()

            # Convert to model format tools
            formatted_tools = self._convert_tools_to_model_format(**kwargs)
            if formatted_tools:
                self.generation_params.update(
                    {"tools": formatted_tools, "tool_choice": kwargs.get("tool_choice", "auto")}
                )

            # Use vLLM's native guided generation
            extra_params = {**(self.generation_params or {}), "guided_json": json_schema}

            # Construct payload based on API type
            if self.model_config.get("completions_api", False):
                formatted_prompt = self.get_chat_formatted_text(
                    input.messages, **(self.chat_template_params or {})
                )
                # Send the request using the litellm
                completion = await atext_completion(
                    model=self._get_lite_llm_model_name(),
                    prompt=formatted_prompt,
                    api_base=model_url,
                    api_key=model_params.auth_token,
                    **extra_params,
                )
                resp_text = completion.choices[0].model_dump()["text"]
            else:
                # Convert input to messages
                messages = self._get_messages(input)
                # Send the request using the litellm
                completion = await acompletion(
                    model=self._get_lite_llm_model_name(),
                    messages=messages,
                    api_base=model_url,
                    api_key=model_params.auth_token,
                    **extra_params,
                )
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

            # Now validate and format the JSON output
            try:
                parsed_data = json.loads(resp_text)
                # Validate with pydantic model
                pydantic_model(**parsed_data)
                # Return JSON string representation
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
        ret_code = 200
        model_url = model_params.url
        tool_calls = None
        try:
            # Convert to model format tools
            formatted_tools = self._convert_tools_to_model_format(**kwargs)
            if formatted_tools:
                self.generation_params.update(
                    {"tools": formatted_tools, "tool_choice": kwargs.get("tool_choice", "auto")}
                )
            # Construct payload based on API type
            if self.model_config.get("completions_api", False):
                formatted_prompt = self.get_chat_formatted_text(
                    input.messages, **(self.chat_template_params or {})
                )
                # Send the request using the litellm
                completion = await atext_completion(
                    model=self._get_lite_llm_model_name(),
                    prompt=formatted_prompt,
                    api_base=model_url,
                    api_key=model_params.auth_token,
                    **self.generation_params,
                )
                resp_text = completion.choices[0].model_dump()["text"]
            else:
                # Convert input to messages
                messages = self._get_messages(input)
                # Send the request using the litellm
                completion = await acompletion(
                    model=self._get_lite_llm_model_name(),
                    messages=messages,
                    api_base=model_url,
                    api_key=model_params.auth_token,
                    **self.generation_params,
                )
                resp_text = completion.choices[0].model_dump()["message"]["content"]
                tool_calls = completion.choices[0].model_dump()["message"]["tool_calls"]
            # TODO: Test rate limit handling for vllm
        except openai.RateLimitError as e:
            logger.warn(f"vLLM api request exceeded rate limit: {e}")
            resp_text = f"{constants.ERROR_PREFIX} vLLM request failed {e}"
            ret_code = 429
        except BadRequestError as e:
            resp_text = f"{constants.ERROR_PREFIX} vLLM request failed with error: {e.message}"
            logger.error(f"vLLM request failed with error: {e.message}")
            ret_code = e.status_code
        except Exception as x:
            resp_text = f"{constants.ERROR_PREFIX} Http request failed {x}"
            logger.error(resp_text)
            rcode = self._get_status_from_body(x)
            if constants.ELEMAI_JOB_DOWN in resp_text or constants.CONNECTION_ERROR in resp_text:
                # inference server is down
                ret_code = 503
            elif rcode is not None:
                ret_code = rcode
            else:
                # for other cases, return 999, dont retry
                ret_code = 999
        return ModelResponse(llm_response=resp_text, response_code=ret_code, tool_calls=tool_calls)
