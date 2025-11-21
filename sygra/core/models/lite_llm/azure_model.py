from typing import Any

from langchain_core.prompt_values import ChatPromptValue
from litellm import BadRequestError, acompletion
from openai import APIError, RateLimitError

from sygra.core.models.custom_models import BaseCustomModel, ModelParams
from sygra.core.models.model_response import ModelResponse
from sygra.logger.logger_config import logger
from sygra.metadata.metadata_integration import track_model_request
from sygra.utils import constants, utils


class CustomAzure(BaseCustomModel):
    def __init__(self, model_config: dict[str, Any]) -> None:
        super().__init__(model_config)
        utils.validate_required_keys(["url", "auth_token"], model_config, "model")
        self.model_config = model_config
        self.model_name = self.model_config.get("model", self.name())

    def _get_model_prefix(self) -> str:
        return "azure_ai"

    @track_model_request
    async def _generate_response(
        self, input: ChatPromptValue, model_params: ModelParams, **kwargs: Any
    ) -> ModelResponse:
        model_url = model_params.url
        ret_code = 200
        tool_calls = None
        try:
            # Convert to model format tools
            formatted_tools = self._convert_tools_to_model_format(**kwargs)
            if formatted_tools:
                self.generation_params.update(
                    {
                        "tools": formatted_tools,
                        "tool_choice": kwargs.get("tool_choice", "auto"),
                        "allowed_openai_params": ["tool_choice"],
                    }
                )
            # Convert input to messages
            messages = self._get_messages(input)
            # Send the request using the litellm
            completion = await acompletion(
                model=self._get_lite_llm_model_name(),
                messages=messages,
                api_base=model_params.url,
                api_key=model_params.auth_token,
                **self.generation_params,
            )
            self._extract_token_usage(completion)
            logger.debug(f"[{self.name()}]\n[{model_url}] \n REQUEST DATA: {messages}")
            # Get the response text
            resp_text = completion.choices[0].model_dump()["message"]["content"]
            # Get the tool calls
            tool_calls = completion.choices[0].model_dump()["message"]["tool_calls"]
            # Get finish reason
            finish_reason = completion.choices[0].model_dump()["finish_reason"]
            if finish_reason == "content_filter":
                ret_code = 400
                resp_text = f"{constants.ERROR_PREFIX} Blocked by azure content filter"
                logger.error(
                    f"[{self.name()}] Azure request failed with code: {ret_code} and error: {resp_text}"
                )
                return ModelResponse(
                    llm_response=resp_text, response_code=ret_code, finish_reason=finish_reason
                )
        except RateLimitError as e:
            logger.warning(f"[{self.name()}] Azure API request exceeded rate limit: {e.message}")
            resp_text = (
                f"{constants.ERROR_PREFIX} Azure API request exceeded rate limit: {e.message}"
            )
            ret_code = getattr(e, "status_code", 429)
        except BadRequestError as e:
            logger.error(f"[{self.name()}] Azure API bad request: {e.message}")
            resp_text = f"{constants.ERROR_PREFIX} Azure API bad request: {e.message}"
            ret_code = getattr(e, "status_code", 400)
        except APIError as e:
            logger.error(f"[{self.name()}] Azure API error: {e.message}")
            resp_text = f"{constants.ERROR_PREFIX} Azure API error: {e.message}"
            ret_code = getattr(e, "status_code", 500)
        except Exception as e:
            logger.error(f"[{self.name()}] Azure text generation failed: {e}")
            resp_text = f"{constants.ERROR_PREFIX} Azure text generation failed: {e}"
            rcode = self._get_status_from_body(e)
            ret_code = rcode if rcode else 999
        return ModelResponse(llm_response=resp_text, response_code=ret_code, tool_calls=tool_calls)
