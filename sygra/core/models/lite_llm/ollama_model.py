import json
from typing import Any, Type

from langchain_core.prompt_values import ChatPromptValue
from litellm import acompletion, atext_completion
from openai import APIError, BadRequestError, RateLimitError
from pydantic import BaseModel, ValidationError

from sygra.core.models.custom_models import BaseCustomModel, ModelParams
from sygra.core.models.model_response import ModelResponse
from sygra.logger.logger_config import logger
from sygra.metadata.metadata_integration import track_model_request
from sygra.utils import constants


class CustomOllama(BaseCustomModel):
    def __init__(self, model_config: dict[str, Any]) -> None:
        super().__init__(model_config)
        self.model_config = model_config

    def _validate_completions_api_model_support(self) -> None:
        logger.info(f"Model {self.name()} supports completion API.")

    def _get_model_prefix(self) -> str:
        return "ollama_chat" if not self.model_config.get("completions_api", False) else "ollama"

    @track_model_request
    async def _generate_native_structured_output(
        self,
        input: ChatPromptValue,
        model_params: ModelParams,
        pydantic_model: Type[BaseModel],
        **kwargs: Any,
    ) -> ModelResponse:
        """Generate structured output using Ollama's format parameter"""
        logger.info(f"[{self.name()}] Attempting native structured output generation")
        model_url = model_params.url
        try:
            tool_calls = None
            # Convert to model format tools
            formatted_tools = self._convert_tools_to_model_format(**kwargs)
            if formatted_tools:
                self.generation_params.update(
                    {"tools": formatted_tools, "tool_choice": kwargs.get("tool_choice", "auto")}
                )
            # Create JSON schema for guided generation
            json_schema = pydantic_model.model_json_schema()

            # Use Ollama's native structured output using format parameter
            extra_params = {**(self.generation_params or {}), "format": json_schema}

            if self.model_config.get("completions_api", False):
                formatted_prompt = self.get_chat_formatted_text(
                    input.messages, **(self.chat_template_params or {})
                )
                # Send the request using the litellm
                completion = await atext_completion(
                    model=self._get_lite_llm_model_name(),
                    prompt=formatted_prompt,
                    api_base=model_url,
                    **extra_params,
                )
                self._extract_token_usage(completion)
                resp_text = completion.choices[0].model_dump()["text"]
            else:
                # Convert input to messages
                messages = self._get_messages(input)
                # Send the request using the litellm
                completion = await acompletion(
                    model=self._get_lite_llm_model_name(),
                    messages=messages,
                    api_base=model_url,
                    **extra_params,
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

            # Now validate and format the JSON output
            try:
                parsed_data = json.loads(resp_text)
                # Try to validate with pydantic model
                logger.debug(f"[{self.name()}] Validating response against schema")
                pydantic_model(**parsed_data)
                logger.info(f"[{self.name()}] Native structured output generation succeeded")
                return ModelResponse(
                    llm_response=resp_text, response_code=resp_status, tool_calls=tool_calls
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

            if self.model_config.get("completions_api", False):
                formatted_prompt = self.get_chat_formatted_text(
                    input.messages, **(self.chat_template_params or {})
                )
                # Send the request using the litellm
                completion = await atext_completion(
                    model=self._get_lite_llm_model_name(),
                    prompt=formatted_prompt,
                    api_base=model_url,
                    **self.generation_params,
                )
                self._extract_token_usage(completion)
                resp_text = completion.choices[0].model_dump()["text"]
            else:
                # Convert input to messages
                messages = self._get_messages(input)
                # Send the request using the litellm
                completion = await acompletion(
                    model=self._get_lite_llm_model_name(),
                    messages=messages,
                    api_base=model_url,
                    **self.generation_params,
                )
                self._extract_token_usage(completion)
                resp_text = completion.choices[0].model_dump()["message"]["content"]
                tool_calls = completion.choices[0].model_dump()["message"]["tool_calls"]

        except RateLimitError as e:
            logger.warning(f"[{self.name()}] Ollama API request exceeded rate limit: {e.message}")
            resp_text = (
                f"{constants.ERROR_PREFIX} Ollama API request exceeded rate limit: {e.message}"
            )
            ret_code = getattr(e, "status_code", 429)
        except BadRequestError as e:
            logger.error(f"[{self.name()}] Ollama API bad request: {e.message}")
            resp_text = f"{constants.ERROR_PREFIX} Ollama API bad request: {e.message}"
            ret_code = getattr(e, "status_code", 400)
        except APIError as e:
            logger.error(f"[{self.name()}] Ollama API error: {e.message}")
            resp_text = f"{constants.ERROR_PREFIX} Ollama API error: {e.message}"
            ret_code = getattr(e, "status_code", 500)
        except Exception as e:
            logger.error(f"[{self.name()}] Ollama text generation failed: {e}")
            resp_text = f"{constants.ERROR_PREFIX} Ollama text generation failed: {e}"
            rcode = self._get_status_from_body(e)
            ret_code = rcode if rcode else 999
        return ModelResponse(llm_response=resp_text, response_code=ret_code, tool_calls=tool_calls)
