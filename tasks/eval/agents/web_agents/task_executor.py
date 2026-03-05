"""Web Agent Task Executor.

Handles request/response logging, retry logic, inline evaluation,
and post-processing for web agent tasks.
"""

import json
import os
from copy import copy, deepcopy
from datetime import datetime
from typing import List, Dict, Any

from sygra.core.eval.metrics.unit_metrics.action_within_bbox import ActionWithinBboxMetric
from sygra.core.eval.metrics.unit_metrics.exact_match import ExactMatchMetric
from sygra.core.eval.metrics.unit_metrics.scroll_direction import ScrollDirectionMetric
from sygra.core.eval.metrics.unit_metrics.typed_value_match import TypedValueMatchMetric
from sygra.core.graph.functions.edge_condition import EdgeCondition
from sygra.core.graph.functions.lambda_function import LambdaFunction
from sygra.core.graph.functions.node_processor import NodePreProcessor, NodePostProcessorWithState
from sygra.core.graph.graph_postprocessor import GraphPostProcessor
from sygra.core.graph.sygra_message import SygraMessage
from sygra.core.graph.sygra_state import SygraState
from sygra.logger.logger_config import logger
from sygra.utils import constants, utils

from .constants import (
    LOG_TIMESTAMP_FORMAT,
    LOG_FILE_PREFIX,
    CHAT_HISTORY_STATE_KEY,
    CHAT_HISTORY_BASE_KEY,
    MODEL_RESPONSES_KEY,
    GOLDEN_RESPONSE_KEY,
    CURRENT_TOOL_RESULT_KEY,
    CURRENT_USER_TEXT_KEY,
    ORIGINAL_USER_TEXT_KEY,
    CURRENT_SCREENSHOT_KEY,
    RETRY_CONFIG_KEY,
    RETRY_CONFIG_REQUIRED,
    RETRY_CONFIG_PROMPT_INJECTION,
    CONFIG_VALUE_YES,
    CONFIG_VALUE_NO,
    CHAT_ROLE_USER,
    CHAT_ROLE_ASSISTANT,
    CHAT_ROLE_TOOL,
    CONTENT_TYPE_IMAGE,
    CONTENT_TYPE_TEXT,
    TOOL_EXECUTION_MESSAGE,
    NO_TEXT_RESPONSE_PLACEHOLDER,
    FAILURE_HINT_TOOL_INCORRECT,
    FAILURE_HINT_PARAMS_INCORRECT,
    FAILURE_HINT_RETRY_TEMPLATE,
    RETRY_KEY_PREFIX,
    DEFAULT_MAX_RETRIES,
    IMAGE_SCALE_FACTORS,
    TOOL_NAME_MAPPINGS,
    TOOL_NAME_SUFFIX,
    TOOL_TYPE_CLICK,
    TOOL_TYPE_TYPING,
    TOOL_TYPE_SCROLL,
    PROPERTY_KEY_TOOL,
    SERVER_ERROR_MARKERS
)

# Configuration flag for keeping tool result screenshots in chat history
KEEP_TOOL_RESULT_SCREENSHOT = False

# State keys for evaluation results
EVALUATION_TOOL_MATCH_KEY = "tool_match"
EVALUATION_STEP_MATCH_KEY = "step_match"

# Logging messages
LOG_MESSAGE_REQUEST = "Request logged to {}"
LOG_MESSAGE_RESPONSE = "Response logged to {}"


class RequestResponseLogger:
    """
    Comprehensive logging system for tracking exact request/response payloads.
    Logs everything sent to the model and received back for debugging.
    """

    @staticmethod
    def setup_logger():
        """Set up logging directory and file structure."""
        current_dir = os.path.dirname(os.path.abspath(__file__))
        log_dir = os.path.join(current_dir, 'logs')
        os.makedirs(log_dir, exist_ok=True)

        timestamp = datetime.now().strftime(LOG_TIMESTAMP_FORMAT)
        log_file = os.path.join(log_dir, f'{LOG_FILE_PREFIX}{timestamp}.json')

        return log_file

    @staticmethod
    def _write_log_entry(log_entry: dict, log_type: str):
        """Write a log entry to the log file.
        
        Args:
            log_entry: Log entry dictionary to write
            log_type: Type of log (REQUEST or RESPONSE) for logging message
        """
        log_file = RequestResponseLogger.setup_logger()
        
        try:
            logs = []
            if os.path.exists(log_file):
                with open(log_file, 'r') as f:
                    logs = json.load(f)

            logs.append(log_entry)

            with open(log_file, 'w') as f:
                json.dump(logs, f, indent=2, default=str)

            log_message = LOG_MESSAGE_REQUEST if log_type == "REQUEST" else LOG_MESSAGE_RESPONSE
            logger.info(log_message.format(log_file))
        except Exception as e:
            logger.error(f"Failed to log {log_type.lower()}: {e}")

    @staticmethod
    def log_request(request_payload: dict, step_number: int):
        """Log the exact request payload sent to the model."""
        log_entry = {
            "type": "REQUEST",
            "timestamp": datetime.now().isoformat(),
            "retry_number": step_number,
            "payload": request_payload
        }
        RequestResponseLogger._write_log_entry(log_entry, "REQUEST")

    @staticmethod
    def log_response(response_data: dict, step_number: int):
        """Log the exact response received from the model."""
        log_entry = {
            "type": "RESPONSE",
            "timestamp": datetime.now().isoformat(),
            "retry_number": step_number,
            "response": response_data
        }
        RequestResponseLogger._write_log_entry(log_entry, "RESPONSE")

    @staticmethod
    def is_server_error(response_text: str, tool_calls: List[Dict[str, Any]] = None) -> bool:
        """
        Detect if the response contains a server/infrastructure error.
        Server errors are transient issues that might be resolved in subsequent retries.

        Args:
            response_text: Model's text response
            tool_calls: Model's tool calls (unused, kept for backward compatibility)

        Returns:
            bool: True if this is a server error, False otherwise
        """
        if not response_text:
            return False
            
        response_lower = response_text.lower()
        for marker in SERVER_ERROR_MARKERS:
            if marker.lower() in response_lower:
                logger.warning(f"Server error detected: {marker}")
                return True

        return False


class FetchNextActionPreProcessor(NodePreProcessor):
    """
    Pre-processor that prepares state before LLM call.
    Checks previous retry status and modifies chat_history if previous retry failed.
    
    Reads retry configuration from graph_properties:
    - retry_chat_injection.required: "yes" or "no" - whether to inject retry context
    - retry_chat_injection.retry_prompt_injection: "yes" or "no" - whether to modify prompt
    """

    @classmethod
    def retry_failure_and_chat_injection(cls, state: SygraState, curr_retry: int,
                                         retry_prompt_injection: str) -> SygraState:
        """Handle retry failure and inject into chat history.
        
        Args:
            state: Current GraspState
            curr_retry: Current retry number
            retry_prompt_injection: "yes" or "no" - whether to modify the user prompt with failure hints
        """

        if curr_retry == 0:
            state[CHAT_HISTORY_STATE_KEY] = copy(state[CHAT_HISTORY_BASE_KEY])
            logger.info(
                f"{cls.__name__}: Retry 0 - Initialized {CHAT_HISTORY_STATE_KEY} with {len(state[CHAT_HISTORY_STATE_KEY])} messages")
            return state

        prev_retry_key = f"{RETRY_KEY_PREFIX}{curr_retry - 1}"
        retry_responses = state.get(MODEL_RESPONSES_KEY, {})

        if prev_retry_key not in retry_responses:
            logger.warning(f"{cls.__name__}: Previous retry data not found for {prev_retry_key}")
            state[CHAT_HISTORY_STATE_KEY] = copy(state[CHAT_HISTORY_BASE_KEY])
            if ORIGINAL_USER_TEXT_KEY in state:
                state[CURRENT_USER_TEXT_KEY] = state[ORIGINAL_USER_TEXT_KEY]
            return state

        prev_retry_data = retry_responses[prev_retry_key]

        # Get evaluation result from state (populated by InlineEvaluationLambda)
        step_match_results = state.get(EVALUATION_STEP_MATCH_KEY, {})
        evaluation_result = step_match_results.get(prev_retry_key)

        if evaluation_result is None:
            logger.warning(
                f"{cls.__name__}: No evaluation result found in state for retry {curr_retry - 1}")
            prev_failed = True
        else:
            prev_failed = not evaluation_result.get('correct', False)

        if not prev_failed:
            logger.info(
                f"{cls.__name__}: Retry {curr_retry} - Previous retry succeeded, using base chat_history")
            state[CHAT_HISTORY_STATE_KEY] = copy(state[CHAT_HISTORY_BASE_KEY])
            return state

        # Previous retry FAILED - check if it's a valid failure worth learning from or some Server error
        logger.info(
            f"{cls.__name__}: Retry {curr_retry} - Previous retry FAILED, checking failure type")

        prev_response_text = prev_retry_data.get('text_response', '')
        prev_tool_calls = prev_retry_data.get('tool_calls', [])

        # Check for errors using error detection utils
        has_server_error = RequestResponseLogger.is_server_error(prev_response_text, prev_tool_calls)

        if has_server_error:
            logger.info(f"{cls.__name__}: Previous retry was a server error. "
                        f"Not appending to chat history. Using previous chat_history instead.")
            state[CHAT_HISTORY_STATE_KEY] = copy(state[CHAT_HISTORY_BASE_KEY])
            return state

        # Valid failure (wrong tool or wrong parameters) - append to history for learning
        logger.info(f"{cls.__name__}: Previous retry was a valid failure (model error). "
                    f"Building failure context for chat history.")

        modified_history = copy(state[CHAT_HISTORY_BASE_KEY])

        user_content = []

        if KEEP_TOOL_RESULT_SCREENSHOT:
            user_content.append({
                "type": CONTENT_TYPE_IMAGE,
                "image_url": {"url": state.get(CURRENT_SCREENSHOT_KEY, "")}
            })

        user_content.append({
            "type": CONTENT_TYPE_TEXT,
            "text": state.get(CURRENT_USER_TEXT_KEY, "")
        })

        user_turn = {
            "role": CHAT_ROLE_USER,
            "content": user_content
        }

        modified_history.append(user_turn)

        assistant_turn = {
            "role": CHAT_ROLE_ASSISTANT,
            "content": prev_response_text if prev_response_text else NO_TEXT_RESPONSE_PLACEHOLDER
        }

        if prev_tool_calls:
            assistant_turn["tool_calls"] = prev_tool_calls

        modified_history.append(assistant_turn)

        if prev_tool_calls:
            for tool_call in prev_tool_calls:
                tool_turn = {
                    "role": CHAT_ROLE_TOOL,
                    "tool_call_id": tool_call.get("id", ""),
                    "content": TOOL_EXECUTION_MESSAGE
                }
                modified_history.append(tool_turn)
            logger.info(f"{cls.__name__}: Added {len(prev_tool_calls)} tool turn(s) after assistant")

        logger.info(
            f"{cls.__name__}: Appended valid failed retry context. History length: {len(modified_history)}")

        state[CHAT_HISTORY_BASE_KEY] = copy(modified_history)
        state[CHAT_HISTORY_STATE_KEY] = copy(state[CHAT_HISTORY_BASE_KEY])

        if retry_prompt_injection == CONFIG_VALUE_YES:
            # Get evaluation result to determine failure type
            step_match_results = state.get(EVALUATION_STEP_MATCH_KEY, {})
            tool_match_results = state.get(EVALUATION_TOOL_MATCH_KEY, {})

            prev_tool_eval = tool_match_results.get(prev_retry_key)

            # Determine if tool was correct
            tool_correct = prev_tool_eval.get('correct', False) if prev_tool_eval else False

            predicted_tool = cls._extract_predicted_tool(prev_tool_calls)

            failure_hint = (FAILURE_HINT_TOOL_INCORRECT if not tool_correct 
                          else FAILURE_HINT_PARAMS_INCORRECT).format(predicted_tool=predicted_tool)

            if ORIGINAL_USER_TEXT_KEY not in state:
                state[ORIGINAL_USER_TEXT_KEY] = state.get(CURRENT_USER_TEXT_KEY, "")

            state[CURRENT_USER_TEXT_KEY] = FAILURE_HINT_RETRY_TEMPLATE.format(
                failure_hint=failure_hint,
                retry_number=curr_retry
            )
            logger.info(f"{cls.__name__}: Modified current_user_text with failure hint")
        else:
            logger.info(
                f"{cls.__name__}: retry_prompt_injection is '{retry_prompt_injection}', keeping original prompt")

        return state

    @classmethod
    def _extract_predicted_tool(cls, tool_calls: List[Dict[str, Any]]) -> str:
        """Extract and normalize predicted tool name from tool calls.
        
        Args:
            tool_calls: List of tool call dictionaries
            
        Returns:
            Normalized tool name
        """
        if not tool_calls:
            return 'unknown'
            
        predicted_tool_raw = tool_calls[0].get('function', {}).get('name', 'unknown')
        predicted_base_tool = predicted_tool_raw.replace(TOOL_NAME_SUFFIX, '')
        return TOOL_NAME_MAPPINGS.get(predicted_base_tool, predicted_base_tool)

    @classmethod
    def _setup_image_dimensions(cls, state: SygraState) -> None:
        """Setup scaled image dimensions in state.
        
        Args:
            state: Current state to update with image dimensions
        """
        img_width = state.get("img_width", 0)
        img_height = state.get("img_height", 0)
        
        state["img_width_50"] = img_width * IMAGE_SCALE_FACTORS["50_percent"]
        state["img_height_50"] = img_height * IMAGE_SCALE_FACTORS["50_percent"]
        state["img_width_25"] = img_width * IMAGE_SCALE_FACTORS["25_percent"]
        state["img_height_30"] = img_height * IMAGE_SCALE_FACTORS["30_percent"]

    @classmethod
    def _extract_screenshot(cls, state: SygraState) -> None:
        """Extract screenshot from tool result and store in state.
        
        Args:
            state: Current state to update with screenshot
        """
        current_tool_result = state.get(CURRENT_TOOL_RESULT_KEY, {})
        content = current_tool_result.get("content", [])
        
        if len(content) == 1 and content[0].get("image"):
            image_data = content[0]["image"]
            img_fmt = image_data.get("format")
            img_content = image_data.get("source", {}).get("bytes")
            if img_fmt and img_content:
                state[CURRENT_SCREENSHOT_KEY] = f"data:image/{img_fmt};base64,{img_content}"

    @classmethod
    def apply(cls, state: SygraState) -> SygraState:
        """Prepare state for LLM call, handling retry failure context."""
        logger.info(f"{cls.__name__}: Setting up for LLM call")
        state[CHAT_HISTORY_STATE_KEY] = copy(state[CHAT_HISTORY_BASE_KEY])
        curr_retry = state.get('curr_retries', 0)

        cls._setup_image_dimensions(state)
        cls._extract_screenshot(state)

        task_name = utils.current_task
        graph_properties = utils.get_graph_properties(task_name)
        retry_config = graph_properties.get(RETRY_CONFIG_KEY, {})
        retry_injection_required = retry_config.get(RETRY_CONFIG_REQUIRED, CONFIG_VALUE_NO)

        if retry_injection_required == CONFIG_VALUE_YES:
            retry_prompt_injection = retry_config.get(RETRY_CONFIG_PROMPT_INJECTION, CONFIG_VALUE_NO)
            state = cls.retry_failure_and_chat_injection(state, curr_retry, retry_prompt_injection)
            logger.info(f"{cls.__name__}: Retry chat injection applied (prompt_injection={retry_prompt_injection})")
        else:
            logger.info(f"{cls.__name__}: Retry chat injection disabled by graph_properties")

        return state


class FetchNextActionPostProcessor(NodePostProcessorWithState):
    """
    Post-processor that handles model response.
    Stores current retry's model response for use by next retry's PreProcessor.
    """

    @classmethod
    def apply(cls, resp: SygraMessage, state: SygraState) -> SygraState:
        """Process and store model's response."""
        logger.info(f"{cls.__name__}: Processing model response")

        retry_number = state["curr_retries"]
        RequestResponseLogger.log_response(resp.message, retry_number)

        response_text = resp.message.content if hasattr(resp.message, 'content') else str(resp.message)
        tool_calls = state.get("tool_calls", [])

        response_dict = {
            'text_response': response_text,
            'tool_calls': tool_calls
        }

        if MODEL_RESPONSES_KEY not in state:
            state[MODEL_RESPONSES_KEY] = {}

        retry_key = f"{RETRY_KEY_PREFIX}{retry_number}"
        state[MODEL_RESPONSES_KEY][retry_key] = response_dict
        
        chat_history_len = len(state.get(CHAT_HISTORY_STATE_KEY, []))
        logger.info(f"{cls.__name__}: Stored {retry_key} response (chat history length: {chat_history_len})")

        return state


class InlineEvaluationLambda(LambdaFunction):
    """
    Lambda node for inline evaluation of retry attempts.
    Evaluates the retry's success/failure and stores results in state.
    """

    @classmethod
    def apply(cls, lambda_node_dict: dict, state: SygraState) -> SygraState:
        """
        Evaluate the previous retry attempt and store results in state.

        Args:
            lambda_node_dict: Configuration dictionary
            state: Current state

        Returns:
            Updated state with evaluation results
        """
        retry_number = state.get('curr_retries', 0)

        # Get previous retry data
        retry_key = f"{RETRY_KEY_PREFIX}{retry_number}"
        retry_responses = state.get(MODEL_RESPONSES_KEY, {})

        if retry_key not in retry_responses:
            logger.warning(f"{cls.__name__}: No data found for {retry_key}")
            return state

        retry_data = retry_responses[retry_key]

        logger.info(f"{cls.__name__}: Starting evaluation for retry {retry_number}")
        golden_response = state.get(GOLDEN_RESPONSE_KEY, {})
        golden_tool = golden_response.get('tool', 'unknown')
        golden_params = golden_response.get('properties', {})
        golden_params[PROPERTY_KEY_TOOL] = golden_tool

        tool_calls = retry_data.get('tool_calls', [])
        if not tool_calls:
            logger.warning(f"{cls.__name__}: No tool calls found for retry {retry_number}")
            return state

        tool_call = tool_calls[0]
        if not isinstance(tool_call, dict):
            logger.warning(f"{cls.__name__}: Invalid tool call format: {tool_call}")
            return state

        predicted_tool = cls._extract_and_normalize_tool(tool_call)
        predicted_params = cls._parse_tool_arguments(tool_call, predicted_tool)

        # Evaluate tool match (tool identification)
        validator = ExactMatchMetric(key=PROPERTY_KEY_TOOL)
        tool_results = validator.evaluate(
            golden=[{PROPERTY_KEY_TOOL: golden_tool}],
            predicted=[{PROPERTY_KEY_TOOL: predicted_tool}]
        )
        if EVALUATION_TOOL_MATCH_KEY not in state:
            state[EVALUATION_TOOL_MATCH_KEY] = {}
        state[EVALUATION_TOOL_MATCH_KEY][retry_key] = tool_results[0].to_dict()

        # Evaluate step match (tool + parameters)
        step_results = None
        if predicted_tool == TOOL_TYPE_CLICK:
            metric = ActionWithinBboxMetric()
            step_results = metric.evaluate(
                golden=[golden_params],
                predicted=[predicted_params],
            )
        elif predicted_tool == TOOL_TYPE_TYPING:
            metric = TypedValueMatchMetric()
            step_results = metric.evaluate(
                golden=[golden_params],
                predicted=[predicted_params],
            )
        elif predicted_tool == TOOL_TYPE_SCROLL:
            metric = ScrollDirectionMetric()
            step_results = metric.evaluate(
                golden=[golden_params],
                predicted=[predicted_params],
            )
        else:
            logger.warning(f"{cls.__name__}: Unknown tool type for parameter validation: {predicted_tool}")
            # For unknown tools, use tool match result as step match
            step_results = tool_results

        if EVALUATION_STEP_MATCH_KEY not in state:
            state[EVALUATION_STEP_MATCH_KEY] = {}
        if step_results:
            state[EVALUATION_STEP_MATCH_KEY][retry_key] = step_results[0].to_dict()

        return state

    @classmethod
    def _extract_and_normalize_tool(cls, tool_call: Dict[str, Any]) -> str:
        """Extract and normalize tool name from tool call.
        
        Args:
            tool_call: Tool call dictionary
            
        Returns:
            Normalized tool name
        """
        predicted_tool_raw = tool_call.get('function', {}).get('name', '')
        predicted_base_tool = predicted_tool_raw.replace(TOOL_NAME_SUFFIX, '')
        return TOOL_NAME_MAPPINGS.get(predicted_base_tool, predicted_base_tool)

    @classmethod
    def _parse_tool_arguments(cls, tool_call: Dict[str, Any], tool_name: str) -> Dict[str, Any]:
        """Parse and prepare tool arguments.
        
        Args:
            tool_call: Tool call dictionary
            tool_name: Normalized tool name
            
        Returns:
            Parsed arguments dictionary with tool name
        """
        predicted_params = tool_call.get('function', {}).get('arguments', {})
        
        if isinstance(predicted_params, str):
            try:
                predicted_params = json.loads(predicted_params)
            except (json.JSONDecodeError, TypeError):
                logger.warning(f"{cls.__name__}: Failed to parse arguments as JSON: {predicted_params}")
                predicted_params = {}
        
        predicted_params[PROPERTY_KEY_TOOL] = tool_name
        return predicted_params


class RetryFlow(LambdaFunction):
    """
    Determines whether to continue the flow or end based on retry count.
    """

    @classmethod
    def apply(cls, lambda_node_dict: dict, state: SygraState) -> SygraState:
        """Validate current state and determine next action."""
        curr_retry = state.get("curr_retries", 0) + 1
        max_retries = state.get("max_retries", DEFAULT_MAX_RETRIES)
        mission_id = state.get("id")

        state["curr_retries"] = curr_retry
        state["should_continue"] = curr_retry < max_retries

        if state["should_continue"]:
            logger.info(f"{cls.__name__}: Mission {mission_id} completed retry {curr_retry}, continuing")
        else:
            logger.info(f"{cls.__name__}: Mission {mission_id} reached max retries ({max_retries})")

        return state


class ShouldContinueCondition(EdgeCondition):
    """
    Edge condition for determining whether to continue the flow.
    """

    @classmethod
    def apply(cls, state: SygraState) -> str:
        should_continue = state.get('should_continue', False)

        if should_continue:
            logger.info(f"{cls.__name__}: Continuing to fetch_next_action_tools")
            return 'fetch_next_action_tools'
        else:
            logger.info(f"{cls.__name__}: Ending flow")
            return constants.SYGRA_END


class Flatten(GraphPostProcessor):
    """Flattens nested retry structure so each retry becomes a separate record."""

    def process(self, data: list, metadata: dict) -> list:
        """Process data by flattening retry structure.
        
        Args:
            data: List of mission records with nested retry data
            metadata: Additional metadata
            
        Returns:
            Flattened list where each retry is a separate record
        """

        flattened = []

        for mission in data:
            base_fields = {
                "id": mission.get("id"),
                "mission_id": mission.get("mission_id"),
                "turn": mission.get("turn"),
                "mission": mission.get("mission"),
                "navigational_directions": mission.get("navigational_directions"),
                "golden_response": mission.get("golden_response"),
            }

            model_responses = mission.get(MODEL_RESPONSES_KEY, {})
            tool_matches = mission.get(EVALUATION_TOOL_MATCH_KEY, {})
            step_matches = mission.get(EVALUATION_STEP_MATCH_KEY, {})

            if not model_responses:
                continue

            for retry_id, model_response in model_responses.items():
                row = deepcopy(base_fields)

                row["retry_id"] = retry_id
                row["model_response"] = model_response
                row["tool_match"] = tool_matches.get(retry_id)
                row["step_match"] = step_matches.get(retry_id)

                flattened.append(row)

        return flattened
