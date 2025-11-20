from __future__ import annotations

import asyncio
import base64
import collections
import json
import os
import random
import re
import sys
import time
from abc import ABC, abstractmethod
from typing import (
    Any,
    DefaultDict,
    Dict,
    Optional,
    Sequence,
    Type,
    cast,
)

import openai
from langchain_core.language_models import LanguageModelInput
from langchain_core.messages import BaseMessage, convert_to_messages
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompt_values import ChatPromptValue, PromptValue, StringPromptValue
from langchain_core.utils.function_calling import convert_to_openai_tool
from langchain_openai.chat_models.base import _convert_message_to_dict
from pydantic import BaseModel, ValidationError
from tenacity import (
    AsyncRetrying,
    RetryError,
    retry_if_result,
    stop_after_attempt,
    wait_random_exponential,
)
from transformers import AutoTokenizer

import sygra.utils.constants as constants
from sygra.core.models.client.base_client import BaseClient
from sygra.core.models.client.client_factory import ClientFactory
from sygra.core.models.client.http_client import HttpClient
from sygra.core.models.client.openai_client import OpenAIClient
from sygra.core.models.model_response import ModelResponse
from sygra.core.models.structured_output.structured_output_config import StructuredOutputConfig
from sygra.logger.logger_config import logger
from sygra.metadata.metadata_integration import track_model_request
from sygra.utils import utils
from sygra.utils.model_utils import (
    is_gpt4o_audio_model,
    should_route_to_image,
    should_route_to_speech,
    should_route_to_transcription,
)


class ModelParams:
    def __init__(self, url: str, auth_token: str):
        self.url = url
        self.auth_token = auth_token


class BaseCustomModel(ABC):
    def __init__(self, model_config: dict[str, Any]) -> None:
        utils.validate_required_keys(["name", "parameters"], model_config, "model")
        self.model_config = model_config
        self._structured_output_lock: Optional[asyncio.Lock] = None
        # Store last request token usage for metadata collection
        self._last_request_usage: Optional[dict[str, int]] = None

        # Initialize structured output configuration
        structured_output_raw = model_config.get("structured_output")
        if structured_output_raw is None:
            self.structured_output_config: Dict[str, Any] = {}
            key_present = False
        else:
            self.structured_output_config = structured_output_raw or {}
            key_present = True

        self.structured_output = StructuredOutputConfig(self.structured_output_config, key_present)

        # sleep before every call - in ms
        self.delay = model_config.get("delay", 100)
        # max_wait for 8 attempts = 2^(8-1) = 128 secs
        self.retry_attempts = model_config.get("retry_attempts", 8)
        self.generation_params: dict[Any, Any] = model_config.get("parameters") or {}
        self.chat_template_params: dict[Any, Any] = model_config.get("chat_template_params") or {}
        self.hf_chat_template_model_id = model_config.get("hf_chat_template_model_id")
        self._validate_completions_api_support()
        self.model_stats: Dict[str, Any] = {"resp_code_dist": {}, "errors": {}}
        # track total count for round_robin load balancing; see "_get_model_url"
        self.call_count = 0
        # track the number of requests per url for least_requests load balancing; see "_get_model_url"
        self.url_reqs_count: DefaultDict[str, int] = collections.defaultdict(int)
        # store the timestamps to check if server is down
        self.model_failed_response_timestamp: list[float] = []
        self._client: BaseClient

    def _set_client(self, url: str, auth_token: Optional[str] = None, async_client: bool = True):
        """Get or create the client instance on demand."""
        self._client = ClientFactory.create_client(self.model_config, url, auth_token, async_client)

    def _validate_completions_api_model_support(self) -> None:
        """Validates that if completions_api is set to True, raises an error that model does not support completion API.

        Raises
        ------
        ValueError
            Model does not support completion API.
        """
        raise ValueError(
            f"Model {self.name()} does not support completion API. "
            f"Please set completions_api to False or remove completions_api from {self.name()} config in models.yaml"
        )

    def _validate_completions_api_support(self) -> None:
        """
        Validates that if completions_api is set to True and hf_chat_template_model_id is set,
        Fetches the tokenizer for the model and sets the chat template.
        Raises a warning if Tokenizer cannot be fetched or chat template is not set.

        Raises
        ------
        Warning
            Model does not support completion API.
        """

        completions_api_enabled = self.model_config.get("completions_api", False)
        if completions_api_enabled:
            self._validate_completions_api_model_support()
            if self.hf_chat_template_model_id:
                try:
                    self.tokenizer = AutoTokenizer.from_pretrained(
                        self.hf_chat_template_model_id, token=os.environ.get(constants.HF_TOKEN)
                    )
                    if self.model_config.get("modify_tokenizer", False):
                        self._set_chat_template()
                except Exception:
                    logger.warn(
                        f"Tokenizer for {self.name()} cannot be fetched."
                        f"Setting completions_api to False."
                    )
                    self.model_config["completions_api"] = False
            else:
                logger.warn(
                    f"Completions API is enabled for {self.name()} but hf_chat_template_model_id is not set."
                    f"Setting completions_api to False."
                )
                self.model_config["completions_api"] = False

    def _extract_token_usage(self, response: Any) -> None:
        """
        Extract and store token usage from API response for metadata collection.
        """
        if hasattr(response, "usage") and response.usage:
            usage_dict = {
                "prompt_tokens": getattr(response.usage, "prompt_tokens", 0),
                "completion_tokens": getattr(response.usage, "completion_tokens", 0),
                "total_tokens": getattr(response.usage, "total_tokens", 0),
            }

            self._last_request_usage = usage_dict

    def _set_chat_template(self):
        """
        Set the chat template for the tokenizer from the environment variable.
        Raises
        -------
        EnvironmentError
            If the environment variable for the chat template is not set and override_tokenizer is True.
        """
        env_name = utils.get_env_name(self.name())
        env_var = f"SYGRA_{env_name}_CHAT_TEMPLATE"

        template = os.environ.get(env_var)
        if template:
            self.tokenizer.chat_template = template
        else:
            raise EnvironmentError(
                f"Environment variable {env_var} not set, but override_tokenizer is True."
            )

    async def __call__(self, input: ChatPromptValue, **kwargs: Any) -> Any:
        # model_url = self._get_model_url()
        model_params = self._get_model_params()
        model_url = model_params.url

        # Handle structured output
        use_structured_output = (
            self.structured_output_config is not None and self.structured_output.enabled
        )

        logger.debug(
            f"[{self.name()}][{model_url}] REQUEST: {utils.convert_messages_from_langchain_to_chat_format(input.messages)}"
        )
        model_response: ModelResponse = await self._call_with_retry(
            input, model_params, use_structured_output, **kwargs
        )

        # Apply common finalization logic
        return self._finalize_response(model_response, model_url)

    def _finalize_response(self, model_response: ModelResponse, model_url: str) -> ModelResponse:
        """Common response finalization logic"""
        self._update_model_stats(model_response.llm_response, model_response.response_code)
        self._handle_server_down(model_response.response_code)
        # reduce the count of requests for the url to handle least_requests load balancing
        self.url_reqs_count[model_url] -= 1
        logger.debug(f"[{self.name()}][{model_url}] RESPONSE: {model_response.llm_response}")
        model_response.llm_response = self._replace_special_tokens(model_response.llm_response)
        model_response.llm_response = self._post_process_for_model(model_response.llm_response)
        return model_response

    async def _get_lock(self) -> asyncio.Lock:
        if self._structured_output_lock is None:
            self._structured_output_lock = asyncio.Lock()
        return self._structured_output_lock

    async def _handle_structured_output(
        self, input: ChatPromptValue, model_params: ModelParams, **kwargs: Any
    ) -> Optional[ModelResponse]:
        """Handle structured output generation"""
        lock = await self._get_lock()
        # Re-entry prevention using asyncio locking
        async with lock:
            pydantic_model = self.structured_output.get_pydantic_model()
            if not pydantic_model:
                logger.warning(
                    "Structured output enabled but no valid schema found, falling back to regular generation"
                )
                # Return a flag to signal that regular generation should be used
                return None

            # Check if model supports native structured output
            if self._supports_native_structured_output():
                logger.info(f"Using native structured output for {self.name()}")
                return await self._generate_native_structured_output(
                    input, model_params, pydantic_model, **kwargs
                )
            else:
                logger.info(f"Using fallback structured output for {self.name()}")
                # Get response from fallback method
                model_response: ModelResponse = await self._generate_fallback_structured_output(
                    input, model_params, pydantic_model, **kwargs
                )
                return model_response

    def _supports_native_structured_output(self) -> bool:
        """Check if the model supports native structured output"""
        return (
            type(self)._generate_native_structured_output
            is not BaseCustomModel._generate_native_structured_output
        )

    async def _generate_native_structured_output(
        self,
        input: ChatPromptValue,
        model_params: ModelParams,
        pydantic_model: Type[BaseModel],
        **kwargs: Any,
    ) -> ModelResponse:
        """Generate structured output using native model support"""
        # This will be implemented in specific model classes
        raise NotImplementedError("Native structured output not implemented for this model")

    async def _generate_fallback_structured_output(
        self,
        input: ChatPromptValue,
        model_params: ModelParams,
        pydantic_model: Type[BaseModel],
        **kwargs: Any,
    ) -> ModelResponse:
        """Generate structured output using instruction-based fallback"""
        logger.info("Generating fallback structured output")
        parser = PydanticOutputParser(pydantic_object=pydantic_model)
        format_instructions = parser.get_format_instructions()

        # Modify the prompt to include format instructions
        modified_messages = list(input.messages)
        if modified_messages and modified_messages[-1].content:
            modified_messages[-1].content = (
                str(modified_messages[-1].content) + f"\n\n{format_instructions}"
            )

        modified_input = ChatPromptValue(messages=modified_messages)

        # Generate the text with retry (uses our centralized retry logic)
        model_response: ModelResponse = await self._generate_response_with_retry(
            modified_input, model_params, **kwargs
        )

        if model_response.response_code != 200:
            logger.error(
                f"[{self.name()}] Failed to generate fallback structured output: Status {model_response.response_code}"
            )
            return model_response

        # Try to parse the response to validate it's proper JSON
        try:
            parsed_output = parser.parse(model_response.llm_response or "")
            logger.info(f"[{self.name()}] Structured output parsed successfully")
            # Return the validated JSON string
            return ModelResponse(
                llm_response=parsed_output.model_dump_json(),
                response_code=200,
                tool_calls=model_response.tool_calls,
            )
        except Exception as e:
            logger.warning(f"[{self.name()}] Failed to parse structured output: {e}")
            logger.error(f"[{self.name()}] Returning unparsed response")
            # Return the original response text with status code 200
            return model_response

    def name(self) -> str:
        return cast(str, self.model_config["name"])

    def model_type(self) -> str:
        """Return the model type based on the class name."""
        class_name = self.__class__.__name__
        # Remove 'Custom' prefix if present
        if class_name.startswith("Custom"):
            return class_name[6:]  # Remove 'Custom' prefix
        return class_name

    def _get_model_params(self) -> ModelParams:
        url = self.model_config.get("url", "")
        auth_token = self.model_config.get("auth_token", "")

        return_url = None
        return_auth_token = None
        if isinstance(url, str):
            return_url = url
            return_auth_token = auth_token
        elif isinstance(url, list):
            load_balancing = self.model_config.get("load_balancing", "least_requests")
            if load_balancing == "round_robin":
                idx = self.call_count % len(url)
                return_url = url[idx]
                return_auth_token = auth_token[idx] if isinstance(auth_token, list) else auth_token
            elif load_balancing == "least_requests":
                # initialize the count for each url if it is not already done
                if not self.url_reqs_count:
                    self.url_reqs_count = collections.defaultdict(int, {u: 0 for u in url})
                # find the url with least requests
                min_value = min(self.url_reqs_count.values())
                min_keys = [k for k, v in self.url_reqs_count.items() if v == min_value]
                # get random url if all have same number of requests
                return_url = random.choice(min_keys)
                return_auth_token = (
                    auth_token[url.index(return_url)]
                    if isinstance(auth_token, list)
                    else auth_token
                )
                self.url_reqs_count[return_url] += 1
            else:
                raise ValueError(
                    f"Invalid load balancing type: {load_balancing}. Supported types are round_robin and least_requests"
                )
        else:
            raise ValueError("Model URL should be a string or a list of strings")

        self.call_count += 1
        return ModelParams(return_url, return_auth_token)

    # return the configured url if it is a string or
    # return the url based on the call count if it is a list to distribute the load
    def _get_model_url(self) -> str:
        url = self.model_config["url"]
        return_url = None
        if isinstance(url, str):
            return_url = url
        elif isinstance(url, list):
            load_balancing = self.model_config.get("load_balancing", "least_requests")
            if load_balancing == "round_robin":
                return_url = url[self.call_count % len(url)]
            elif load_balancing == "least_requests":
                # initialize the count for each url if it is not already done
                if not self.url_reqs_count:
                    self.url_reqs_count = collections.defaultdict(int, {u: 0 for u in url})
                # find the url with the least requests
                min_value = min(self.url_reqs_count.values())
                min_keys = [k for k, v in self.url_reqs_count.items() if v == min_value]
                # get random url if all have same number of requests
                return_url = random.choice(min_keys)
                self.url_reqs_count[return_url] += 1
            else:
                raise ValueError(
                    f"Invalid load balancing type: {load_balancing}. Supported types are round_robin and least_requests"
                )
        else:
            raise ValueError("Model URL should be a string or a list of strings")

        self.call_count += 1
        return return_url

    def _update_model_stats(self, resp_text: Optional[str], resp_status: int) -> None:
        code_count = self.model_stats["resp_code_dist"].get(resp_status, 0)
        self.model_stats["resp_code_dist"][resp_status] = code_count + 1
        if resp_status != 200:
            # TODO: Right now the error messages are based on vllm; need to generalize for all models
            if not resp_text:
                resp_text = ""
            resp_text = resp_text.lower()
            if "timed out" in resp_text:
                error_type = "timeout"
            elif "maximum context length is" in resp_text:
                error_type = "tokens_exceeded"
            elif "connection error" in resp_text:
                error_type = "connection_error"
            else:
                error_type = "other"
            error_count = self.model_stats["errors"].get(error_type, 0)
            self.model_stats["errors"][error_type] = error_count + 1

        # log model stats after every model_stats_interval
        total_requests = sum(self.model_stats["resp_code_dist"].values())
        model_stats_interval = self.model_config.get("stats_interval", 10000)
        if total_requests % model_stats_interval == 0:
            # convert stats to percentage
            temp_model_stats = {"total_requests": total_requests}
            for key_for_percent in ["resp_code_dist", "errors"]:
                temp_model_stats[key_for_percent] = {
                    k: f"{(v / total_requests): 0.3f}"
                    for k, v in self.model_stats[key_for_percent].items()
                }

            logger.info(f"[{self.name()}] Model Stats: {temp_model_stats}")

    @abstractmethod
    @track_model_request
    async def _generate_response(
        self, input: ChatPromptValue, model_params: ModelParams, **kwargs: Any
    ) -> ModelResponse:
        pass

    def _ping_model(self, url: str, auth_token: str) -> int:
        """
        Ping a single model
        Args:
            url: single url to ping
            auth_token: auth token for the url
        """
        # hello message
        is_multi_modal = self.model_config.get("multi_modal", True)
        msg = utils.backend_factory.get_test_message(is_multi_modal=is_multi_modal)
        # build parameters
        model_param = ModelParams(url=url, auth_token=auth_token)
        model_response: ModelResponse = asyncio.run(self._generate_response(msg, model_param))
        return model_response.response_code

    def ping(self) -> int:
        """
        Ping the model with a hello message and return http code
        if returns 200, its success
        """
        url_obj = self.model_config.get("url")
        auth_token = self.model_config.get("auth_token")
        if isinstance(url_obj, list):
            for i, url in enumerate(url_obj):
                token = auth_token[i] if isinstance(auth_token, list) else auth_token
                status = self._ping_model(url=str(url), auth_token=str(token))
                if status != 200:
                    logger.error(f"Server({url}) responded with {status}")
                    return status
            return 200
        else:
            return self._ping_model(url=str(url_obj), auth_token=str(auth_token))

    def get_chat_formatted_text(
        self, chat_format_object: Sequence[BaseMessage], **chat_template_params
    ) -> str:
        chat_formatted_text = str(
            self.tokenizer.apply_chat_template(
                utils.convert_messages_from_langchain_to_chat_format(chat_format_object),
                tokenize=False,
                add_generation_prompt=True,
                **chat_template_params,
            )
        )
        logger.debug(f"Chat formatted text: {chat_formatted_text}")
        return chat_formatted_text

    def _replace_special_tokens(self, text: Optional[str]) -> str:
        if not text:
            return ""
        for token in self.model_config.get("special_tokens", []):
            text = text.replace(token, "")
        return text.strip()

    def _post_process_for_model(self, text: str) -> str:
        if self.name() == "mixtral8x7b":
            # handle 8x7b generation of underscore with backslash
            text = text.replace("\\_", "_")
        elif self.name() == "mixtral_instruct_8x22b":
            # very specific pattern observed in 8x22b. The value within the details tag is what we need
            pattern1 = re.compile("<details><summary>.*?</summary>(.*?)</details>", re.DOTALL)
            res = re.findall(pattern1, text)
            if len(res) == 1:
                text = res[0]

            # to handle cases where mixtral adds additional tags around the text. e.g. [ANS]....[/ANS].
            # we are currently handling only cases where we observe one occurrence of the tag to reduce false positives
            pattern2 = re.compile(r"^\[([A-Z]+)\](.*?)\[/\1\]", re.DOTALL)
            res = re.findall(pattern2, text)
            if len(res) == 1:
                text = res[0][1]
            # 8x22b adds intermittently adds begin{align*} and end{align*} tags. Probably coming from latex training
            # data.
            text = text.replace("begin{align*}", "").replace("end{align*}", "").strip()
        return text

    def _is_retryable_error(self, result: ModelResponse):
        """check if the error is a rate limit error by checking response code"""
        # currently retrying for too many requests error(429)
        # and APIConnectionError(599) returned by OpenAI intermittently
        # and 444 = Blocked by azure content filter
        return result.response_code in constants.RETRYABLE_HTTP_ERROR

    def _log_before_retry(self, retry_state):
        """log retry attempt"""
        resp_code = retry_state.outcome.result().response_code
        logger.warning(
            f"[{self.name()}] Retrying the request in {retry_state.next_action.sleep} seconds as it returned"
            f" {resp_code} code"
        )

    async def _call_with_retry(
        self,
        input: ChatPromptValue,
        model_params: ModelParams,
        use_structured_output: bool = False,
        **kwargs: Any,
    ) -> ModelResponse:
        """
        Centralized retry method that delegates to either regular text generation
        or structured output handling based on the flag.
        """
        result: ModelResponse = ModelResponse(
            llm_response=f"{constants.ERROR_PREFIX} All retry attempts failed", response_code=999
        )
        try:
            async for attempt in AsyncRetrying(
                retry=retry_if_result(self._is_retryable_error),
                wait=wait_random_exponential(multiplier=1),
                stop=stop_after_attempt(self.retry_attempts),
                before_sleep=self._log_before_retry,
            ):
                with attempt:
                    # initial delay for each call (in ms)
                    await asyncio.sleep(self.delay / 1000)

                    # Call the appropriate method based on the flag
                    if use_structured_output:
                        # Call the structured output handling
                        so_result = await self._handle_structured_output(
                            input, model_params, **kwargs
                        )

                        # If _handle_structured_output returns None, it means we should fall back to regular generation
                        if so_result is None:
                            logger.info(
                                "Structured output not configured, falling back to regular generation"
                            )
                            result = await self._generate_response(input, model_params, **kwargs)
                        else:
                            result = so_result
                    else:
                        # Regular text generation
                        result = await self._generate_response(input, model_params, **kwargs)

                    # Apply post-processing if defined
                    post_proc = self._get_post_processor()
                    if post_proc is not None:
                        result.llm_response = post_proc().apply(result.llm_response)
                if (
                    attempt.retry_state.outcome is not None
                    and not attempt.retry_state.outcome.failed
                ):
                    attempt.retry_state.set_result(result)
        except RetryError:
            logger.error(f"[{self.name()}] Request failed after {self.retry_attempts} attempts")
            # Return a default error response if all retries failed
            result = ModelResponse(
                llm_response=f"{constants.ERROR_PREFIX} All retry attempts failed",
                response_code=999,
            )
        return result

    async def _generate_response_with_retry(
        self, input: ChatPromptValue, model_params: ModelParams, **kwargs: Any
    ) -> ModelResponse:
        """
        Backward compatibility method that uses the centralized _call_with_retry.
        Retry text generation with model with exponential backoff and random jitter.
        Total number of retry attempts and delay between each attempt can be configured
        via "retry_attempts" and "delay" properties in eval/config/models.json
        """
        return await self._call_with_retry(
            input, model_params, use_structured_output=False, **kwargs
        )

    # get post processor if available, returns none if not defined
    def _get_post_processor(self):
        post_proc = self.model_config.get("post_process")
        return utils.get_func_from_str(post_proc) if post_proc else None

    def _handle_server_down(self, resp_status: int):
        """
        When the server is down, we check if we receive server down status(404, 500-503)
        if the failure count is 10(MAX_FAILED_ERROR) within 30(MODEL_FAILURE_WINDOW_IN_SEC) seconds
        shutdown the process, we need to fix the model first
        """
        if not constants.HANDLE_SERVER_DOWN:
            # no need to handle this, user has disabled the feature
            return
        if resp_status in constants.SERVER_DOWN_ERROR_CODE:
            # append the current timestamp for this error
            self.model_failed_response_timestamp.append(time.time())
            # if storage is full, pop the first in
            if len(self.model_failed_response_timestamp) > constants.MAX_FAILED_ERROR:
                self.model_failed_response_timestamp.pop(0)

            total_in_queue = len(self.model_failed_response_timestamp)
            # if total count is more than maximum error to handle, than only do the validation
            if total_in_queue >= constants.MAX_FAILED_ERROR:
                # when MAX_FAILED_ERROR = 10
                # if 100 in total, check time diff of 91st(old) and 100th(new)
                # if 10 in total, check time diff of 1st(old) and 10th(new)
                oldest_timestamp = self.model_failed_response_timestamp[
                    total_in_queue - constants.MAX_FAILED_ERROR
                ]
                newest_timestamp = self.model_failed_response_timestamp[total_in_queue - 1]
                time_gap_in_sec = newest_timestamp - oldest_timestamp
                logger.warning(
                    f"Server failure count: {constants.MAX_FAILED_ERROR} in {time_gap_in_sec} seconds."
                )
                # last n(MAX_FAILED_ERROR) failures within t(MODEL_FAILURE_WINDOW_IN_SEC) seconds
                if time_gap_in_sec < constants.MODEL_FAILURE_WINDOW_IN_SEC:
                    logger.error(
                        f"SYSTEM EXITING as the dependant model({self.name()}) is down for longer period."
                    )
                    sys.exit()

    def _get_status_from_body(self, response: Any) -> Optional[int]:
        """
        Extract http error status code from body
        """
        try:
            # Attempt to normalize to a dict body
            body: Optional[dict[str, Any]] = None
            # Some SDK exceptions have a `.body` attribute (object with dict or JSON string)
            if hasattr(response, "body"):
                resp_body = getattr(response, "body")
                if isinstance(resp_body, dict):
                    body = resp_body
                elif isinstance(resp_body, str):
                    body = json.loads(resp_body)
            # If not found via attribute, the response itself might be a dict or JSON string
            if body is None:
                if isinstance(response, dict):
                    body = response
                elif isinstance(response, str):
                    # Try load as JSON string
                    body = json.loads(response)
                else:
                    return None

            status_code = body.get("statusCode")
            # for openai api it is in code
            if status_code is None:
                code = body.get("code")
                if code is not None:
                    return int(code)
                return None
            else:
                return int(status_code)
        except Exception:
            return None

    def _convert_tools_to_model_format(self, **kwargs):
        formatted_tools = []
        if kwargs.get("tools"):
            tools = kwargs.get("tools", [])
            formatted_tools = [convert_to_openai_tool(tool, strict=True) for tool in tools]
        return formatted_tools

    @staticmethod
    def _convert_input(model_input: LanguageModelInput) -> PromptValue:
        """
        Convert the input to a PromptValue.

        This method takes in a LanguageModelInput, which can be a PromptValue,
        a str, or a list of BaseMessages, and returns a PromptValue.

        If the input is already a PromptValue, it is simply returned.
        If the input is a str, it is converted to a StringPromptValue.
        If the input is a list of BaseMessages, it is converted to a ChatPromptValue.
        Otherwise, a ValueError is raised.

        Args:
            model_input (LanguageModelInput): The input to convert.

        Returns:
            PromptValue: The converted input.

        Raises:
            ValueError: If the input is not a PromptValue, str, or list of BaseMessages.
        """
        if isinstance(model_input, PromptValue):
            return model_input
        if isinstance(model_input, str):
            return StringPromptValue(text=model_input)
        if isinstance(model_input, Sequence):
            return ChatPromptValue(messages=convert_to_messages(model_input))
        msg = (
            f"Invalid input type {type(model_input)}. "
            "Must be a PromptValue, str, or list of BaseMessages."
        )
        raise ValueError(msg)

    def _get_messages(self, input: ChatPromptValue) -> list[dict[str, Any]]:
        prompt_value: PromptValue = self._convert_input(input.messages)
        langchain_messages: list[BaseMessage] = prompt_value.to_messages()
        messages: list[dict[str, Any]] = [_convert_message_to_dict(m) for m in langchain_messages]
        return messages


class CustomTGI(BaseCustomModel):
    def __init__(self, model_config: dict[str, Any]) -> None:
        super().__init__(model_config)
        utils.validate_required_keys(["url", "auth_token"], model_config, "model")
        self.model_config = model_config
        self.auth_token = cast(str, model_config.get("auth_token")).replace("Bearer ", "")

    def _validate_completions_api_model_support(self) -> None:
        logger.info(f"Model {self.name()} supports completion API.")

    def _validate_completions_api_support(self) -> None:
        """
        Validates that if completions_api is set to True and hf_chat_template_model_id is set,
        Fetches the tokenizer for the model and sets the chat template.
        Raises a warning if Tokenizer cannot be fetched or chat template is not set.

        Raises
        ------
        Warning
            Model does not support completion API.
        """
        self.model_config["completions_api"] = True
        self._validate_completions_api_model_support()
        if self.hf_chat_template_model_id:
            try:
                self.tokenizer = AutoTokenizer.from_pretrained(
                    self.hf_chat_template_model_id, token=os.environ.get(constants.HF_TOKEN)
                )
                if self.model_config.get("modify_tokenizer", False):
                    self._set_chat_template()
            except Exception:
                raise ValueError(f"Tokenizer for {self.name()} cannot be fetched.")
        else:
            raise ValueError(f"Please set hf_chat_template_model_id for TGI Model {self.name()}.")

    async def _generate_native_structured_output(
        self,
        input: ChatPromptValue,
        model_params: ModelParams,
        pydantic_model: Type[BaseModel],
        **kwargs: Any,
    ) -> ModelResponse:
        """Generate structured output using TGI's native support"""
        logger.info(f"[{self.name()}] Attempting native structured output generation")
        model_url = model_params.url
        try:
            # Set Client
            self._set_client(model_params.url, model_params.auth_token)
            client = cast(HttpClient, self._client)

            # Get JSON schema from the Pydantic model
            json_schema = pydantic_model.model_json_schema()

            # Build Request
            payload = {
                "inputs": self.get_chat_formatted_text(
                    input.messages, **(self.chat_template_params or {})
                )
            }

            # Prepare generation parameters with guidance
            generation_params_with_guidance = {
                **(self.generation_params or {}),
                "parameters": {"grammar": {"type": "json", "value": json_schema}},
            }

            payload = client.build_request_with_payload(payload=payload)

            # Send Request with guidance parameters
            resp = await client.async_send_request(
                payload, generation_params=generation_params_with_guidance
            )

            resp_text = resp.text
            resp_status = resp.status_code
            logger.info(f"[{self.name()}][{model_url}] RESPONSE: Native support call successful")
            logger.debug(f"[{self.name()}] Native structured output response: {resp_text}")

            if resp_status != 200:
                logger.error(
                    f"[{self.name()}] Native structured output HTTP request failed with code: {resp_status}"
                )
                # Fall back to instruction-based approach
                logger.info(f"[{self.name()}] Falling back to instruction-based structured output")
                return await self._generate_fallback_structured_output(
                    input, model_params, pydantic_model, **kwargs
                )

            # Parse the response text - TGI returns the guided JSON directly
            resp_text = json.loads(resp_text)["generated_text"]

            # Validate the response against the schema
            try:
                resp_text = json.loads(resp_text) if isinstance(resp_text, str) else resp_text
                # Attempt to parse with the pydantic model to validate
                logger.debug(f"[{self.name()}] Validating response against schema")
                pydantic_model.model_validate(resp_text)
                # If validation succeeds, return the validated JSON
                logger.info(f"[{self.name()}] Native structured output generation succeeded")
                return ModelResponse(llm_response=json.dumps(resp_text), response_code=resp_status)
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

    def _extract_tgi_token_usage(self, response_data: dict) -> None:
        """
        Extract token usage from TGI response details.

        TGI returns token statistics in the 'details' field when details=true:
        - details.generated_tokens: completion tokens
        - len(details.prefill): prompt tokens (if available)

        Args:
            response_data: Parsed JSON response from TGI
        """
        if "details" in response_data and response_data["details"]:
            details = response_data["details"]

            # Get completion tokens
            completion_tokens = details.get("generated_tokens", 0)

            # Get prompt tokens from prefill length
            prompt_tokens = 0
            if "prefill" in details and details["prefill"]:
                prompt_tokens = len(details["prefill"])

            # Calculate total
            total_tokens = prompt_tokens + completion_tokens

            # Store in the standard format
            self._last_request_usage = {
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": total_tokens,
            }

            logger.debug(
                f"[{self.name()}] Extracted token usage from TGI: "
                f"prompt={prompt_tokens}, completion={completion_tokens}, total={total_tokens}"
            )

    @track_model_request
    async def _generate_response(
        self, input: ChatPromptValue, model_params: ModelParams, **kwargs: Any
    ) -> ModelResponse:
        try:
            # Set Client
            self._set_client(model_params.url, model_params.auth_token)
            client = cast(HttpClient, self._client)
            # Build Request
            payload = {
                "inputs": self.get_chat_formatted_text(
                    input.messages, **(self.chat_template_params or {})
                )
            }
            payload = client.build_request_with_payload(payload=payload)

            # Merge generation params with details=true for token statistics
            generation_params = {**(self.generation_params or {})}
            if "parameters" not in generation_params:
                generation_params["parameters"] = {}
            # Enable details to get token statistics
            generation_params["parameters"]["details"] = True

            # Send Request
            resp = await client.async_send_request(payload, generation_params=generation_params)

            resp_text = resp.text
            ret_code = resp.status_code
            if ret_code != 200:
                logger.error(
                    f"HTTP request failed with code: {resp.status_code} and error: {resp_text}"
                )
                resp_text = f"{constants.ERROR_PREFIX} {resp_text}"
                if (
                    constants.ELEMAI_JOB_DOWN in resp_text
                    or constants.CONNECTION_ERROR in resp_text
                ):
                    # server down
                    ret_code = 503
                else:
                    ret_code = resp.status_code
            else:
                # Parse response to extract both text and token statistics
                response_data = json.loads(resp_text)

                # Extract token usage from details
                self._extract_tgi_token_usage(response_data)

                # Get generated text
                resp_text = response_data["generated_text"]
        except Exception as x:
            resp_text = f"{constants.ERROR_PREFIX} Http request failed {x}"
            logger.error(resp_text)
            rcode = self._get_status_from_body(x)
            ret_code = rcode if rcode else 999
            return ModelResponse(llm_response=resp_text, response_code=ret_code)
        return ModelResponse(llm_response=resp_text, response_code=ret_code)


class CustomAzure(BaseCustomModel):
    def __init__(self, model_config: dict[str, Any]) -> None:
        super().__init__(model_config)
        utils.validate_required_keys(["url", "auth_token"], model_config, "model")
        self.model_config = model_config
        auth_token_value = model_config["auth_token"]  # already validated key exists

        if isinstance(auth_token_value, str):
            self.auth_token = auth_token_value.replace("Bearer ", "")
        elif isinstance(auth_token_value, list) and auth_token_value:
            # take first element if non-empty list
            first_item = auth_token_value[0]
            if not isinstance(first_item, str):
                raise TypeError("auth_token list must contain strings")
            self.auth_token = first_item.replace("Bearer ", "")
        else:
            raise ValueError("auth_token must be a string or non-empty list of strings")

    @track_model_request
    async def _generate_response(
        self, input: ChatPromptValue, model_params: ModelParams, **kwargs: Any
    ) -> ModelResponse:
        model_url = model_params.url
        try:
            # Set Client
            self._set_client(model_url, model_params.auth_token)
            # Build Request
            payload = {
                "messages": utils.convert_messages_from_langchain_to_chat_format(input.messages)
            }
            payload = self._client.build_request_with_payload(payload=payload)
            # Send Request
            resp = await self._client.async_send_request(
                payload, generation_params=self.generation_params
            )

            logger.debug(f"[{self.name()}]\n[{model_url}] \n REQUEST DATA: {payload}")

            resp_text = resp.text
            ret_code = resp.status_code
            if ret_code != 200:
                logger.error(
                    f"[{self.name()}] HTTP request failed with code: {ret_code} and error: {resp_text}"
                )
                resp_text = ""
            else:
                result = json.loads(resp_text)
                if result["choices"][0]["finish_reason"] == "content_filter":
                    return ModelResponse(
                        llm_response="Blocked by azure content filter", response_code=444
                    )
                resp_text = result["choices"][0]["message"]["content"]
        except Exception as x:
            resp_text = f"Http request failed {x}"
            logger.error(resp_text)
            rcode = self._get_status_from_body(x)
            ret_code = rcode if rcode else 999
            return ModelResponse(llm_response=resp_text, response_code=ret_code)
        return ModelResponse(llm_response=resp_text, response_code=ret_code)


class CustomMistralAPI(BaseCustomModel):
    def __init__(self, model_config: dict[str, Any]) -> None:
        super().__init__(model_config)

    @track_model_request
    async def _generate_response(
        self, input: ChatPromptValue, model_params: ModelParams, **kwargs: Any
    ) -> ModelResponse:
        ret_code = 200
        model_url = model_params.url
        try:
            chat_format_messages = utils.convert_messages_from_langchain_to_chat_format(
                input.messages
            )
            messages = [{"role": m["role"], "content": m["content"]} for m in chat_format_messages]
            self._set_client(model_url, model_params.auth_token)
            chat_response = await self._client.chat.complete_async(  # type: ignore
                model=self.model_config.get("model"),
                messages=messages,
                **self.generation_params,
            )

            self._extract_token_usage(chat_response)
            resp_text = chat_response.choices[0].message.content
        except Exception as x:
            resp_text = f"{constants.ERROR_PREFIX} Http request failed {x}"
            logger.error(resp_text)
            lower_resp_text = resp_text.lower()
            rcode = self._get_status_from_body(x)
            if (
                constants.MIXTRAL_API_RATE_LIMIT_ERROR.lower() in lower_resp_text
                or constants.MIXTRAL_API_MODEL_OVERLOAD_ERROR.lower() in lower_resp_text
            ):
                ret_code = 429
            elif rcode is not None:
                ret_code = rcode
            else:
                # for other cases, return 999, dont retry
                ret_code = 999
        return ModelResponse(llm_response=resp_text, response_code=ret_code)


class CustomVLLM(BaseCustomModel):
    def __init__(self, model_config: dict[str, Any]) -> None:
        super().__init__(model_config)
        utils.validate_required_keys(["url", "auth_token"], model_config, "model")
        self.model_config = model_config
        self.auth_token = str(model_config.get("auth_token")).replace("Bearer ", "")
        self.model_serving_name = model_config.get("model_serving_name", self.name())

    def _validate_completions_api_model_support(self) -> None:
        logger.info(f"Model {self.name()} supports completion API.")

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
            self._set_client(model_url, model_params.auth_token)
            client = cast(OpenAIClient, self._client)
            tool_calls = []

            # Create JSON schema for guided generation
            json_schema = pydantic_model.model_json_schema()

            # Prepare payload using the client
            if self.model_config.get("completions_api", False):
                formatted_prompt = self.get_chat_formatted_text(
                    input.messages, **(self.chat_template_params or {})
                )
                payload = client.build_request(formatted_prompt=formatted_prompt)
            else:
                payload = client.build_request(messages=input.messages)

            # Convert to model format tools
            formatted_tools = self._convert_tools_to_model_format(**kwargs)
            if formatted_tools:
                self.generation_params.update(
                    {"tools": formatted_tools, "tool_choice": kwargs.get("tool_choice", "auto")}
                )

            # Use vLLM's native guided generation
            extra_params = {**(self.generation_params or {}), "guided_json": json_schema}

            # Send the request using the client
            completion = await client.send_request(payload, self.model_serving_name, extra_params)

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

            # Extract response text based on API type
            if self.model_config.get("completions_api", False):
                resp_text = completion.choices[0].model_dump()["text"]
            else:
                resp_text = completion.choices[0].model_dump()["message"]["content"]
                tool_calls = completion.choices[0].model_dump()["message"]["tool_calls"]
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
                    llm_response=json.dumps(parsed_data),
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
            # create vllm client for every request otherwise it starts failing set header to close connection
            # otherwise spurious event loop errors show up -
            # https://github.com/encode/httpx/discussions/2959#discussioncomment-7665278
            self._set_client(model_url, model_params.auth_token)
            if self.model_config.get("completions_api", False):
                formatted_prompt = self.get_chat_formatted_text(
                    input.messages, **(self.chat_template_params or {})
                )
                payload = self._client.build_request(formatted_prompt=formatted_prompt)
            else:
                payload = self._client.build_request(messages=input.messages)

            # Convert to model format tools
            formatted_tools = self._convert_tools_to_model_format(**kwargs)
            if formatted_tools:
                self.generation_params.update(
                    {"tools": formatted_tools, "tool_choice": kwargs.get("tool_choice", "auto")}
                )

            completion = await self._client.send_request(
                payload, self.model_serving_name, self.generation_params
            )

            self._extract_token_usage(completion)

            if self.model_config.get("completions_api", False):
                resp_text = completion.choices[0].model_dump()["text"]
            else:
                resp_text = completion.choices[0].model_dump()["message"]["content"]
                tool_calls = completion.choices[0].model_dump()["message"]["tool_calls"]
            # TODO: Test rate limit handling for vllm
        except openai.RateLimitError as e:
            logger.warn(f"vLLM api request exceeded rate limit: {e}")
            resp_text = f"{constants.ERROR_PREFIX} Http request failed {e}"
            ret_code = 429
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


class CustomOpenAI(BaseCustomModel):

    def __init__(self, model_config: dict[str, Any]) -> None:
        super().__init__(model_config)
        utils.validate_required_keys(
            ["url", "auth_token", "api_version", "model"], model_config, "model"
        )
        self.model_config = model_config

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
            self._set_client(model_url, model_params.auth_token)

            # Prepare payload using the client
            if self.model_config.get("completions_api", False):
                formatted_prompt = self.get_chat_formatted_text(
                    input.messages, **(self.chat_template_params or {})
                )
                payload = self._client.build_request(formatted_prompt=formatted_prompt)
            else:
                payload = self._client.build_request(messages=input.messages)

            # Convert to model format tools
            formatted_tools = self._convert_tools_to_model_format(**kwargs)
            if formatted_tools:
                self.generation_params.update(
                    {"tools": formatted_tools, "tool_choice": kwargs.get("tool_choice", "auto")}
                )

            # Add pydantic_model to generation params
            all_params = {
                **(self.generation_params or {}),
                "pydantic_model": pydantic_model,
            }
            # Send the request using the client
            completion = await self._client.send_request(
                payload, str(self.model_config.get("model")), all_params
            )

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

            # Extract response text based on API type
            if self.model_config.get("completions_api", False):
                model_response: ModelResponse = ModelResponse(
                    llm_response=completion.choices[0].model_dump()["text"],
                    response_code=resp_status,
                )
            else:
                model_response = ModelResponse(
                    llm_response=completion.choices[0].model_dump()["message"]["content"],
                    response_code=resp_status,
                    tool_calls=completion.choices[0].model_dump()["message"]["tool_calls"],
                )
            logger.info(f"[{self.name()}][{model_url}] RESPONSE: Native support call successful")
            logger.debug(
                f"[{self.name()}] Native structured output response: {model_response.llm_response}"
            )

            # Try to parse and validate the response
            try:
                json_data = json.loads(model_response.llm_response or "")
                # Try to validate with pydantic model
                logger.debug(f"[{self.name()}] Validating response against schema")
                pydantic_model.model_validate(json_data)
                logger.info(f"[{self.name()}] Native structured output generation succeeded")
                return model_response
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
        # Check if this is gpt-4o-audio model which uses chat completions with audio
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
        model_url = model_params.url
        tool_calls = None
        try:
            # create azure openai client for every request otherwise it starts failing
            # set header to close connection otherwise spurious event loop errors show up - https://github.com/encode/httpx/discussions/2959#discussioncomment-7665278
            self._set_client(model_url, model_params.auth_token)
            if self.model_config.get("completions_api", False):
                formatted_prompt = self.get_chat_formatted_text(
                    input.messages, **(self.chat_template_params or {})
                )
                payload = self._client.build_request(formatted_prompt=formatted_prompt)
            else:
                payload = self._client.build_request(messages=input.messages)

            # Convert to model format tools
            formatted_tools = self._convert_tools_to_model_format(**kwargs)
            if formatted_tools:
                self.generation_params.update(
                    {"tools": formatted_tools, "tool_choice": kwargs.get("tool_choice", "auto")}
                )

            completion = await self._client.send_request(
                payload, str(self.model_config.get("model")), self.generation_params
            )

            self._extract_token_usage(completion)

            if self.model_config.get("completions_api", False):
                resp_text = completion.choices[0].model_dump()["text"]
            else:
                resp_text = completion.choices[0].model_dump()["message"]["content"]
                tool_calls = completion.choices[0].model_dump()["message"]["tool_calls"]
        except openai.RateLimitError as e:
            logger.warn(f"AzureOpenAI api request exceeded rate limit: {e}")
            resp_text = f"{constants.ERROR_PREFIX} Http request failed {e}"
            ret_code = 429
        except Exception as x:
            resp_text = f"{constants.ERROR_PREFIX} Http request failed {x}"
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
        model_url = model_params.url

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

            # Set up the OpenAI client
            self._set_client(model_url, model_params.auth_token)

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
            # Cast to OpenAIClient since BaseClient doesn't have create_speech
            openai_client = cast(OpenAIClient, self._client)
            audio_response = await openai_client.create_speech(
                model=str(self.model_config.get("model")), **tts_params
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

    async def _generate_transcription(
        self, input: ChatPromptValue, model_params: ModelParams, **kwargs: Any
    ) -> ModelResponse:
        """
        Transcribe audio to text using OpenAI/Azure OpenAI Transcription API.
        This method is called when input_type is 'audio' in model config.

        Args:
            input: ChatPromptValue containing audio data URLs to transcribe
            model_params: Model parameters including URL and auth token

        Returns:
            Model Response
        """
        ret_code = 200
        model_url = model_params.url

        try:
            # Extract audio data URLs from messages using utility function
            from sygra.utils.audio_utils import extract_audio_urls_from_messages

            audio_data_urls, text_prompt = extract_audio_urls_from_messages(input.messages)

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

            # Set up the OpenAI client
            self._set_client(model_url, model_params.auth_token)

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

            # Make the transcription API call
            # Cast to OpenAIClient since BaseClient doesn't have create_transcription
            openai_client = cast(OpenAIClient, self._client)
            transcription_response = await openai_client.create_transcription(
                model=str(self.model_config.get("model")), **transcription_params
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

        except openai.RateLimitError as e:
            logger.warning(f"[{self.name()}] OpenAI Transcription API request exceeded rate limit: {e}")
            resp_text = f"{constants.ERROR_PREFIX} Rate limit exceeded: {e}"
            ret_code = 429
        except openai.APIError as e:
            logger.error(f"[{self.name()}] OpenAI Transcription API error: {e}")
            resp_text = f"{constants.ERROR_PREFIX} API error: {e}"
            ret_code = getattr(e, "status_code", 500)
        except Exception as x:
            resp_text = f"{constants.ERROR_PREFIX} Transcription request failed: {x}"
            logger.error(f"[{self.name()}] {resp_text}")
            rcode = self._get_status_from_body(x)
            ret_code = rcode if rcode else 999

        return ModelResponse(llm_response=resp_text, response_code=ret_code)

    async def _generate_audio_chat_completion(
        self, input: ChatPromptValue, model_params: ModelParams, **kwargs: Any
    ) -> ModelResponse:
        """
        Generate response using gpt-4o-audio model with chat completions API.
        This model supports:
        - Audio input (via input_audio in messages)
        - Audio output (via modalities parameter)
        - Text input/output
        - Combined text+audio input/output

        Args:
            input: ChatPromptValue containing messages (can include audio)
            model_params: Model parameters including URL and auth token

        Returns:
            Model Response
            - For audio output: returns base64 encoded audio data URL
            - For text output: returns text response
            - On error: returns error message and error code
        """
        ret_code = 200
        model_url = model_params.url

        try:
            self._set_client(model_url, model_params.auth_token)

            payload = self._client.build_request(messages=input.messages)
            processed_messages = payload["messages"]

            # Process messages to convert audio_url -> input_audio format for gpt-4o-audio
            for message_dict in processed_messages:
                # Handle audio_url -> input_audio conversion for multimodal content
                if isinstance(message_dict.get("content"), list):
                    processed_content = []
                    for item in message_dict["content"]:
                        if isinstance(item, dict) and item.get("type") == "audio_url":
                            # Extract audio URL
                            audio_url = item.get("audio_url", {})
                            if isinstance(audio_url, dict):
                                data_url = audio_url.get("url", "")
                            else:
                                data_url = audio_url

                            # Extract base64 data and format from data URL
                            if data_url.startswith("data:audio/"):
                                # Parse: data:audio/<format>;base64,<data>
                                parts = data_url.split(";base64,")
                                if len(parts) == 2:
                                    mime_parts = parts[0].split(":")
                                    if len(mime_parts) == 2:
                                        format_part = mime_parts[1].replace("audio/", "")
                                        base64_data = parts[1]

                                        # Map MIME types to OpenAI format names
                                        mime_format_map = {"mpeg": "mp3"}
                                        if format_part in mime_format_map:
                                            format_part = mime_format_map[format_part]

                                        # Convert to input_audio format expected by gpt-4o-audio
                                        processed_content.append(
                                            {
                                                "type": "input_audio",
                                                "input_audio": {
                                                    "data": base64_data,
                                                    "format": format_part,
                                                },
                                            }
                                        )
                                    else:
                                        processed_content.append(item)
                                else:
                                    processed_content.append(item)
                            else:
                                processed_content.append(item)
                        else:
                            # Keep other types as-is (text, image_url, etc.)
                            processed_content.append(item)

                    message_dict["content"] = processed_content

            output_type = self.model_config.get("output_type")

            # gpt-4o-audio requires audio in modalities if output involves audio
            has_audio_output = output_type == "audio"

            has_audio_input = any(
                isinstance(msg.get("content"), list)
                and any(item.get("type") == "input_audio" for item in msg.get("content", []))
                for msg in processed_messages
            )

            modalities = ["text"]
            if has_audio_output:
                if "audio" not in modalities:
                    # modality = ["text", "audio"] is required for audio output
                    modalities.append("audio")

            if not has_audio_input:
                has_audio_output = True
                modalities = ["text", "audio"]

            audio_params: dict[str, Any] = {}
            if has_audio_output:
                if (
                    "audio" in self.generation_params
                    and type(self.generation_params["audio"]) is dict
                ):
                    audio_params = self.generation_params["audio"]
                else:
                    logger.info(
                        "Audio generation params not found, using default audio params, voice: alloy, format: wav"
                    )
                    audio_params = {"voice": "alloy", "format": "wav"}
                    self.generation_params["audio"] = audio_params

                logger.debug(
                    f"[{self.name()}] Audio chat completion - modalities: {modalities}, audio params: {audio_params}"
                )

            payload = {"messages": processed_messages}

            if "audio" in modalities:
                payload["modalities"] = modalities

            gen_params = {**self.generation_params}

            completion = await self._client.send_request(
                payload, str(self.model_config.get("model")), gen_params
            )

            choice = completion.choices[0]
            message = choice.model_dump()["message"]

            if "audio" in modalities and message.get("audio"):
                audio_data = message["audio"]

                if isinstance(audio_data, dict):
                    audio_base64 = audio_data.get("data", "")
                    audio_format = audio_params.get("format", "wav")

                    mime_types = {
                        "mp3": "audio/mpeg",
                        "opus": "audio/opus",
                        "aac": "audio/aac",
                        "flac": "audio/flac",
                        "wav": "audio/wav",
                        "pcm": "audio/pcm",
                    }
                    mime_type = mime_types.get(audio_format, "audio/wav")

                    resp_text = f"data:{mime_type};base64,{audio_base64}"

                    # Include transcript if available
                    if message.get("content"):
                        logger.debug(f"[{self.name()}] Transcript: {message['content']}")
                else:
                    resp_text = message.get("content", "").strip()
            else:
                resp_text = message.get("content", "").strip()

        except openai.RateLimitError as e:
            logger.warning(f"[{self.name()}] OpenAI audio chat API rate limit: {e}")
            resp_text = f"{constants.ERROR_PREFIX} Rate limit exceeded: {e}"
            ret_code = 429
        except openai.BadRequestError as e:
            logger.error(f"[{self.name()}] OpenAI audio chat API bad request: {e}")
            resp_text = f"{constants.ERROR_PREFIX} Bad request: {e}"
            ret_code = 400
        except openai.APIError as e:
            logger.error(f"[{self.name()}] OpenAI audio chat API error: {e}")
            resp_text = f"{constants.ERROR_PREFIX} API error: {e}"
            ret_code = getattr(e, "status_code", 500)
        except Exception as x:
            resp_text = f"{constants.ERROR_PREFIX} Audio chat request failed: {x}"
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
        self._set_client(model_url, model_params.auth_token)

        params = self.generation_params

        # Check if streaming is enabled
        is_streaming = params.get("stream", False)

        logger.debug(
            f"[{self.name()}] Image generation parameters - {params}, streaming: {is_streaming}"
        )

        openai_client = cast(OpenAIClient, self._client)
        image_response = await openai_client.create_image(
            model=str(self.model_config.get("model")), prompt=prompt_text, **params
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

        # Set up the OpenAI client
        self._set_client(model_url, model_params.auth_token)

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

        # Decode images using utility function
        from sygra.utils.image_utils import create_image_file_from_data_url

        if supports_multiple_images and num_images > 1:
            # Multiple images for GPT-Image-1
            image_files = [
                create_image_file_from_data_url(data_url, idx)
                for idx, data_url in enumerate(image_data_urls)
            ]
            image_param = image_files
        else:
            # Single image for DALL-E-2 or single image input
            image_file = create_image_file_from_data_url(image_data_urls[0], 0)
            image_param = [image_file]

        # Call the image edit API
        openai_client = cast(OpenAIClient, self._client)
        image_response = await openai_client.edit_image(
            image=image_param, prompt=prompt_text, **params
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


class CustomOllama(BaseCustomModel):
    def __init__(self, model_config: dict[str, Any]) -> None:
        super().__init__(model_config)
        self.model_config = model_config

    def _validate_completions_api_model_support(self) -> None:
        logger.info(f"Model {self.name()} supports completion API.")

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
            self._set_client(model_url, model_params.auth_token)

            # Create JSON schema for guided generation
            json_schema = pydantic_model.model_json_schema()

            # Prepare payload using the client
            if self.model_config.get("completions_api", False):
                formatted_prompt = self.get_chat_formatted_text(
                    input.messages, **(self.chat_template_params or {})
                )
                payload = self._client.build_request(formatted_prompt=formatted_prompt)
            else:
                payload = self._client.build_request(messages=input.messages)

            # Use Ollama's native structured output using format parameter
            extra_params = {**(self.generation_params or {}), "format": json_schema}

            # Send the request using the client
            completion = await self._client.send_request(payload, self.name(), extra_params)

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

            # Extract response text based on API type
            if self.model_config.get("completions_api", False):
                resp_text = completion["response"]
            else:
                resp_text = completion["message"]["content"]

            logger.info(f"[{self.name()}][{model_url}] RESPONSE: Native support call successful")
            logger.debug(f"[{self.name()}] Native structured output response: {resp_text}")

            # Now validate and format the JSON output
            try:
                parsed_data = json.loads(resp_text)
                # Try to validate with pydantic model
                logger.debug(f"[{self.name()}] Validating response against schema")
                pydantic_model(**parsed_data)
                logger.info(f"[{self.name()}] Native structured output generation succeeded")
                return ModelResponse(llm_response=resp_text, response_code=resp_status)
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
        try:
            self._set_client(model_url, model_params.auth_token)
            if self.model_config.get("completions_api", False):
                formatted_prompt = self.get_chat_formatted_text(
                    input.messages, **(self.chat_template_params or {})
                )
                payload = self._client.build_request(formatted_prompt=formatted_prompt)
            else:
                payload = self._client.build_request(messages=input.messages)
            completion = await self._client.send_request(
                payload, self.name(), self.generation_params
            )

            # Extract token usage (Ollama uses different field names)
            if isinstance(completion, dict) and (
                "prompt_eval_count" in completion or "eval_count" in completion
            ):
                self._last_request_usage = {
                    "prompt_tokens": completion.get("prompt_eval_count", 0),
                    "completion_tokens": completion.get("eval_count", 0),
                    "total_tokens": completion.get("prompt_eval_count", 0)
                    + completion.get("eval_count", 0),
                }

            if self.model_config.get("completions_api", False):
                resp_text = completion["response"]
            else:
                resp_text = completion["message"]["content"]
        except Exception as x:
            resp_text = f"{constants.ERROR_PREFIX} Ollama request failed {x}"
            logger.error(resp_text)
            rcode = self._get_status_from_body(x)
            ret_code = rcode if rcode else 999
        return ModelResponse(llm_response=resp_text, response_code=ret_code)


class CustomTriton(BaseCustomModel):
    def _get_payload_config_template(self, inference_server: str, payload_key: str = "default"):
        """
        Get the payload configuration template for the Triton server.

        If the Triton server does not define a payload key, read the default flow.

        Args:
            inference_server (str): Inference server type, as of now we support
                only triton, may extend in future
            payload_key (str): Payload key to read from the configuration file.

        Returns:
            dict: The payload configuration template from the configuration file.
        """
        # if triton server does not define payload key, read the default flow
        try:
            payload_cfg = (
                utils.get_payload(inference_server, payload_key)
                if payload_key
                else utils.get_payload(inference_server)
            )
        except Exception as e:
            logger.error(f"Failed to get payload config: {e}")
            raise Exception(f"Failed to get payload config: {e}")
        return payload_cfg

    def _get_payload_json_template(self, payload_cfg: dict):
        """
        Get the payload JSON template for the Triton server.

        If the Triton server does not define a payload key, read the default flow.

        Args:
            payload_cfg (dict): Payload configuration template from the configuration file.
        Returns:
            dict: The payload JSON template from the configuration file.
        """
        # get the payload JSON
        payload_json_template = payload_cfg.get(constants.PAYLOAD_JSON)
        # payload json must be defined for triton server(for the specific API or default)
        assert payload_json_template is not None, "Payload JSON must be defined for Triton server."
        return payload_json_template

    def _create_triton_request(
        self, payload_dict: dict, messages: list[dict], generation_params: dict
    ):
        """This is the triton request payload.

        Read from the config file and build the final payload

        Args:
            payload_dict: payload template dictionary
            messages: messages to be embedded in the configured payload
            generation_params: parameters to be embedded in the configured payload

        Returns:
            final json
        """

        for inp in payload_dict["inputs"]:
            if inp.get("name") == "request":
                inp["data"] = [json.dumps(messages, ensure_ascii=False)]
            elif inp.get("name") == "options":
                inp["data"] = [json.dumps(generation_params, ensure_ascii=False)]

        return payload_dict

    def _get_response_text(self, resp_text: str, payload_config_template: dict):
        try:
            json_resp = json.loads(resp_text)
            final_resp_text = json_resp["outputs"][0]["data"][0]
            # get the response key
            resp_key = payload_config_template.get(constants.RESPONSE_KEY)
            # if resp_text is a dict, just fetch the data or else extract it from json
            final_resp_text = (
                final_resp_text.get(resp_key, "")
                if isinstance(final_resp_text, dict)
                else json.loads(final_resp_text).get(resp_key)
            )

        except Exception as e:
            logger.error(f"Failed to get response text: {e}")
            try:
                json_resp = json.loads(resp_text)
                outer_error = json.loads(json_resp.get("error", "{}"))
                inner_error = json.loads(outer_error.get("error", "{}"))
                error_msg = inner_error.get("error_message")

                if error_msg == "Invalid JSON returned by model.":
                    logger.error("Invalid JSON returned, JSON mode specified")
                    final_resp_text = inner_error.get("model_output") or inner_error.get(
                        "response_metadata", {}
                    ).get("models", [{}])[0].get("debug_info", {}).get("raw_model_output", "")
                else:
                    logger.error(f"Not a JSON error. Error message: {error_msg}")
                    raise RuntimeError("Not a JSON error")
            except Exception:
                logger.error(f"Unable to parse error response {resp_text}")
                final_resp_text = ""
        return final_resp_text

    def __init__(self, model_config: dict[str, Any]) -> None:
        super().__init__(model_config)
        utils.validate_required_keys(["url", "auth_token"], model_config, "model")
        self.model_config = model_config
        self.auth_token = str(model_config.get("auth_token")).replace("Bearer ", "")

    @track_model_request
    async def _generate_response(
        self, input: ChatPromptValue, model_params: ModelParams, **kwargs: Any
    ) -> ModelResponse:
        ret_code = 200
        model_url = model_params.url
        try:
            # Set Client
            self._set_client(model_url, model_params.auth_token)

            # Build Request
            payload_key = self.model_config.get("payload_key", "default")
            payload_config_template = self._get_payload_config_template(
                constants.INFERENCE_SERVER_TRITON, payload_key
            )
            payload_json_template = self._get_payload_json_template(payload_config_template)
            conversation = utils.convert_messages_from_langchain_to_chat_format(input.messages)
            payload = self._create_triton_request(
                payload_json_template, conversation, self.generation_params
            )
            payload = self._client.build_request_with_payload(payload=payload)

            # Send Request
            resp = await self._client.async_send_request(payload)

            logger.debug(f"[{self.name()}]\n[{model_url}] \n REQUEST DATA: {payload}")

            resp_text = resp.text
            if resp.status_code != 200:
                logger.error(
                    f"[{self.name()}] HTTP request failed with code: {resp.status_code} and error: {resp_text}"
                )
                resp_text = ""
                rcode = self._get_status_from_body(resp_text)
                ret_code = rcode if rcode else 999
            else:
                resp_text = self._get_response_text(resp_text, payload_config_template)

        except Exception as x:
            resp_text = f"Http request failed {x}"
            logger.error(resp_text)
            rcode = self._get_status_from_body(x)
            ret_code = rcode if rcode else 999
        return ModelResponse(llm_response=resp_text, response_code=ret_code)
