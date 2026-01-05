"""
ServiceNow Search Task Executor - EXACT PAYLOAD MATCHING
Implements the precise payload structure and flow as specified in user requirements.
No deviations from the specified format.
"""

import json
import os
from copy import copy
from datetime import datetime

from sygra.core.graph.graph_postprocessor import GraphPostProcessor
from sygra.core.graph.sygra_message import SygraMessage
from sygra.core.graph.sygra_state import SygraState
from sygra.core.graph.functions.node_processor import NodePreProcessor, NodePostProcessorWithState
from sygra.core.graph.functions.edge_condition import EdgeCondition
from sygra.logger.logger_config import logger
from sygra.utils import constants, utils
from .web_agent_metrics import WebAgentMetricsCalculator
from .error_detection_utils import is_server_error

keep_tool_result_screenshot = False

class ServiceNowRequestResponseLogger:
    """
    Comprehensive logging system for tracking exact request/response payloads.
    Logs everything sent to Claude and received back for debugging.
    """

    @staticmethod
    def setup_logger():
        """Set up logging directory and file structure."""
        # Use the local logs directory within the web_agent_task_flow task
        current_dir = os.path.dirname(os.path.abspath(__file__))
        log_dir = os.path.join(current_dir, 'logs')
        os.makedirs(log_dir, exist_ok=True)

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        log_file = os.path.join(log_dir, f'web_agent_requests_{timestamp}.json')

        return log_file

    @staticmethod
    def log_request(request_payload: dict, step_number: int):
        """Log the exact request payload sent to Claude."""
        log_file = ServiceNowRequestResponseLogger.setup_logger()

        log_entry = {
            "type": "REQUEST",
            "timestamp": datetime.now().isoformat(),
            "retry_number": step_number,
            "payload": request_payload
        }

        # Append to log file
        try:
            if os.path.exists(log_file):
                with open(log_file, 'r') as f:
                    logs = json.load(f)
            else:
                logs = []

            logs.append(log_entry)

            with open(log_file, 'w') as f:
                json.dump(logs, f, indent=2, default=str)

            logger.info(f"ServiceNow Request logged to {log_file}")
        except Exception as e:
            logger.error(f"Failed to log request: {e}")

    @staticmethod
    def log_response(response_data: dict, step_number: int):
        """Log the exact response received from Claude."""
        log_file = ServiceNowRequestResponseLogger.setup_logger()

        log_entry = {
            "type": "RESPONSE",
            "timestamp": datetime.now().isoformat(),
            "retry_number": step_number,
            "response": response_data
        }

        # Append to log file
        try:
            if os.path.exists(log_file):
                with open(log_file, 'r') as f:
                    logs = json.load(f)
            else:
                logs = []

            logs.append(log_entry)

            with open(log_file, 'w') as f:
                json.dump(logs, f, indent=2, default=str)

            logger.info(f"ServiceNow Response logged to {log_file}")
        except Exception as e:
            logger.error(f"Failed to log response: {e}")


# class StateTransform(DataTransform):
#     """
#     Transform mission data from JSON into state variables
#     """
#     @property
#     def name(self) -> str:
#         """Get the name of the state transformation.
#
#         Returns:
#             str: The identifier 'state_transform'.
#         """
#         return "state_transform"
#     def transform(self, data: list[dict[str, Any]]) -> list[dict[str, Any]]:
#         """Populate state with mission data.
#
#         Args:
#             data (list[dict[str, Any]]): List of dictionary records to transform.
#
#         Returns:
#             list[dict[str, Any]]: Transformed records with state variables populated
#         """
#         return [self.state_transform(record) for record in data]
#     @staticmethod
#     def state_transform(data: Dict[str, Any]) -> Dict[str, Any]:
#         """Transform mission data into state format"""
#         logger.info("StateTransform: Loading mission data into state")
#
#         # Extract key fields from mission data and put them in state
#         transformed_data = {
#             'current_user_text': data.get('current_user_text', ''),
#             'current_tool_result': data.get('current_tool_result', {}),
#             'mission': data.get('mission', ''),
#             'navigational_directions': data.get('navigational_directions', ''),
#             'end_goal': data.get('end_goal', ''),
#             'expected_url_pattern': data.get('expected_url_pattern', []),
#             'chat_history': data.get('chat_history', []),
#             'date': datetime.now().strftime('%Y-%m-%d'),
#             # Include all original data as well
#             **data
#         }
#
#         logger.info(f"StateTransform: Loaded mission '{transformed_data.get('mission', 'N/A')}'")
#         return transformed_data


class SeedDataProcessor:
    """
    Take image input from state once seed data has been loaded,
    convert it into b64 format and store it in state
    """

    @staticmethod
    def apply(lambda_node_dict: dict, state: SygraState) -> SygraState:
        logger.info("SeedDataProcessor: setting appropriate state variables")
        # Initialize state chat history variable since we use it for injection and payload
        state['__chat_history__'] = state['chat_history']
        try:
            # Safely extract image path with multiple fallback checks
            current_tool_result = state.get("current_tool_result", {})
            image_path = None

            if (isinstance(current_tool_result, dict) and
                    "toolResult" in current_tool_result and
                    "content" in current_tool_result["toolResult"] and
                    isinstance(current_tool_result["toolResult"]["content"], list) and
                    len(current_tool_result["toolResult"]["content"]) > 0):

                content_item = current_tool_result["toolResult"]["content"][0]
                if (isinstance(content_item, dict) and
                        "image" in content_item and
                        isinstance(content_item["image"], dict) and
                        "source" in content_item["image"] and
                        isinstance(content_item["image"]["source"], dict) and
                        "bytes" in content_item["image"]["source"]):
                    image_path = content_item["image"]["source"]["bytes"]

            if image_path:
                state['screenshot_b64'] = image_path
                logger.info(f"SeedDataProcessor: Successfully injected base64 form into state, so it can be rendered in prompt")
            else:
                logger.info("SeedDataProcessor: No base64 image found in current_tool_result structure")
                state['screenshot_b64'] = ''

        except (KeyError, TypeError, AttributeError, IndexError) as e:
            logger.warning(f"SeedDataProcessor: Error accessing current_tool_result structure: {e}")
            state['screenshot_b64'] = ''
        except Exception as e:
            logger.error(f"SeedDataProcessor: Unexpected error in image processing: {e}")
            state['screenshot_b64'] = ''

        return state

class FetchNextActionPreProcessor(NodePreProcessor):
    """
    Pre-processor that prepares state before LLM call.
    Checks previous retry status and modifies chat_history if previous retry failed.
    
    Reads retry configuration from graph_properties:
    - retry_chat_injection.required: "yes" or "no" - whether to inject retry context
    - retry_chat_injection.retry_prompt_injection: "yes" or "no" - whether to modify prompt
    """


    @staticmethod
    def inline_evaluation(state:SygraState, prev_retry_data: dict, retry_number: int) -> dict:
        """
        Inline evaluation of previous retry data.

        Args:
            state: Current GraspState
            prev_retry_data: Previous retry data containing text_response and tool_calls

        Returns:
            dict: Evaluation results dict
        """
        # Inline evaluation logic here
        # INLINE EVALUATION: Evaluate this retry's success/failure
        logger.info(f"Starting inline evaluation for retry number {retry_number}")
        golden_response = state.get('golden_response', {})
        evaluation_result = None

        tool_calls = prev_retry_data.get('tool_calls', [])

        if golden_response:
            # Create calculator instance for evaluation
            calculator = WebAgentMetricsCalculator()
            evaluation_result = calculator.evaluate_single_record(
                golden_response=golden_response,
                predicted_tool_calls=tool_calls
            )

            success = evaluation_result.get('success', False)
            tool_correct = evaluation_result.get('tool_correct', False)
            params_correct = evaluation_result.get('params_correct', False)
            predicted_event = evaluation_result.get('predicted_event', 'unknown')
            golden_event = evaluation_result.get('golden_event', 'unknown')

            logger.info(f"FetchNextActionPostProcessor: Retry {retry_number} evaluation - "
                        f"Success: {success}, Tool: {tool_correct}, Params: {params_correct}, "
                        f"Predicted: {predicted_event}, Expected: {golden_event}")

            # Store evaluation result for output
            if "retry_evaluations" not in state:
                state["retry_evaluations"] = {}
            state["retry_evaluations"][f"retry_{retry_number}"] = evaluation_result
        return evaluation_result

    @staticmethod
    def retry_failure_and_chat_injection(state:SygraState, curr_retry:int, retry_prompt_injection: str) -> SygraState:
        """Handle retry failure and inject into chat history.
        
        Args:
            state: Current GraspState
            curr_retry: Current retry number
            retry_prompt_injection: "yes" or "no" - whether to modify the user prompt with failure hints
        """

        # Initialize __chat_history__ from base chat_history on first retry
        if curr_retry == 0:
            state['__chat_history__'] = copy(state['chat_history'])
            logger.info(
                f"FetchNextActionPreProcessor: Retry 0 - Initialized __chat_history__ with {len(state['__chat_history__'])} messages")
            return state

        # For retry >= 1, check if previous retry failed
        prev_retry_key = f"retry_{curr_retry - 1}"
        retry_responses = state.get("model_responses", {})

        # If previous retry detail is not present in retry_responses, it is some flow issue. Fallback to base chat_history
        if prev_retry_key not in retry_responses:
            # Previous retry data not found for some reason, just use base chat_history
            logger.warning(f"FetchNextActionPreProcessor: Previous retry data not found for {prev_retry_key}")
            state['__chat_history__'] = copy(state['chat_history'])
            if "original_current_user_text" is not None:
                state["current_user_text"] = state.get("original_current_user_text", "")
            return state

        prev_retry_data = retry_responses[prev_retry_key]
        # Trigger inline evaluation here using prev_retry_data
        evaluation_result = FetchNextActionPreProcessor.inline_evaluation(state, prev_retry_data, curr_retry - 1)
        prev_failed = not evaluation_result.get('success', False)

        if not prev_failed:
            logger.info(
                f"FetchNextActionPreProcessor: Retry {curr_retry} - Previous retry succeeded, using base chat_history")
            state['__chat_history__'] = copy(state['chat_history'])
            # changing the current_user_text is not required because even if one of the past retries has failed, it should be present in the chat history and the modified prompt with failure hint should be sent
            return state

        # Previous retry FAILED - check if it's a valid failure worth learning from or some Server error
        logger.info(
            f"FetchNextActionPreProcessor: Retry {curr_retry} - Previous retry FAILED, checking failure type")

        prev_response_text = prev_retry_data.get('text_response', '')
        prev_tool_calls = prev_retry_data.get('tool_calls', [])

        # Check for errors using error detection utils
        has_server_error = is_server_error(prev_response_text, prev_tool_calls)

        if has_server_error:
            logger.info(f"FetchNextActionPreProcessor: Previous retry was a server error. "
                            f"Not appending to chat history. Using previous chat_history instead.")
            state['__chat_history__'] = copy(state['chat_history'])
            return state

        # Valid failure (wrong tool or wrong parameters) - append to history for learning
        logger.info(f"FetchNextActionPreProcessor: Previous retry was a valid failure (model error). "
                    f"Building failure context for chat history.")

        # Start with base chat_history
        modified_history = copy(state['chat_history'])

        # Build user turn content based on screenshot flag
        user_content = []

        # Add screenshot if keep_tool_result_screenshot is true
        if keep_tool_result_screenshot:
            user_content.append({
                "type": "image_url",
                "image_url": {"url": state.get("current_screenshot", "")}
            })

        # Always add text content
        user_content.append({
            "type": "text",
            "text": state.get("current_user_text","")
        })

        # Create user turn that was sent in the previous retry
        user_turn = {
            "role": "user",
            "content": user_content
        }

        modified_history.append(user_turn)

        # Append the assistant's response from previous retry
        assistant_turn = {
            "role": "assistant",
            "content": prev_response_text if prev_response_text else "[No text response]"
        }

        # Add tool calls if present (in format expected by chat history)
        if prev_tool_calls and len(prev_tool_calls) > 0:
            assistant_turn["tool_calls"] = prev_tool_calls
        else:
            logger.debug(f"No tool calls selected by the assistant.")

        modified_history.append(assistant_turn)

        # Add tool turn if there were tool calls
        if prev_tool_calls and len(prev_tool_calls) > 0:
            for tool_call in prev_tool_calls:
                tool_turn = {
                    "role": "tool",
                    "tool_call_id": tool_call.get("id", ""),
                    "content": "Tool execution completed"
                }
                modified_history.append(tool_turn)
            logger.info(f"FetchNextActionPreProcessor: Added {len(prev_tool_calls)} tool turn(s) after assistant")
        else:
            logger.debug(f"FetchNextActionPreProcessor: No tool turn after assistant since previous retry response had no tool calls")

        logger.info(
            f"FetchNextActionPreProcessor: Appended valid failed retry context. History length: {len(modified_history)}")

        # Copy the modified history properly so that it persists in the next retry
        state['chat_history'] = copy(modified_history)
        state['__chat_history__'] = copy(state['chat_history'])

        # Check if retry prompt injection is enabled (from parameter)
        if retry_prompt_injection == 'yes':
            # Modify current_user_text to indicate this is a retry after failure
            predicted_event = evaluation_result.get('predicted_event', 'unknown')
            golden_event = evaluation_result.get('golden_event', 'unknown')
            tool_correct = evaluation_result.get('tool_correct', False)

            # Should we give golden_event as hint ? Ideally no because that's future observation a.k.a cheating
            if not tool_correct:
                failure_hint = f"Your previous tool call '{predicted_event}' was incorrect. Do NOT use this tool again in the retry, even with different arguments. \nIf you believe the previous tool might still be right, dismiss that belief and proceed with a different tool call."
            else:
                failure_hint = f"Your previous tool call '{predicted_event}' was correct, but had incorrect parameters. Use the same tool again but give the correct parameters in this retry."

            # Store original for next retry
            if state.get("original_current_user_text") is None:
                state["original_current_user_text"] = state.get("current_user_text", "")

            # Modify current_user_text with failure context
            failure_hint_user_text = f"""{failure_hint} You are now retrying this step (Retry {curr_retry}). Always provide a tool call in your response with the correct tool and parameters values. The latest screenshot provided is before executing your previous wrong response. So, you can directly suggest the new different correct approach on the given screenshot without considering any cleanup event. Ensure your response progresses towards mission completion. Follow all system prompt rules and ALWAYS prioritize the user's requirements."""

            state["current_user_text"] = failure_hint_user_text
            logger.info(f"FetchNextActionPreProcessor: Modified current_user_text with failure hint")
        else:
            # Keep original current_user_text unchanged
            logger.info(f"FetchNextActionPreProcessor: retry_prompt_injection is '{retry_prompt_injection}', keeping original prompt")

        return state

    @staticmethod
    def apply(state: SygraState) -> SygraState:
        """Prepare state for LLM call, handling retry failure context."""
        logger.info("FetchNextActionPreProcessor: Setting up for LLM call")
        state['__chat_history__'] = copy(state['chat_history'])
        curr_retry = state.get('curr_retries', 0)

        state["img_width_50"] = state["img_width"]*0.5
        state["img_height_50"] = state["img_height"]*0.5
        state["img_width_25"] = state["img_width"]*0.25
        state["img_height_30"] = state["img_height"]*0.3
        
        # Extract screenshot from current_tool_result
        current_tool_result = state.get("current_tool_result", {})
        if len(current_tool_result.get("content", [])) == 1 and current_tool_result.get("content")[0].get("image"):
            img_fmt = current_tool_result.get("content")[0].get("image", {}).get("format")
            img_content = current_tool_result.get("content")[0].get("image", {}).get("source", {}).get("bytes")
            state["current_screenshot"] = f"data:image/{img_fmt};base64,{img_content}"

        # Read retry configuration from graph_properties
        task_name = utils.current_task
        graph_properties = utils.get_graph_properties(task_name)
        retry_config = graph_properties.get("retry_chat_injection", {})
        
        # Check if retry chat injection is required from graph_properties
        retry_injection_required = retry_config.get("required", "no")
        
        if retry_injection_required == "yes":
            # Logic to handle retry failure cases and injection into chat history
            retry_prompt_injection = retry_config.get("retry_prompt_injection", "no")
            state = FetchNextActionPreProcessor.retry_failure_and_chat_injection(state, curr_retry, retry_prompt_injection)
            logger.info(f"FetchNextActionPreProcessor: Retry chat injection applied (prompt_injection={retry_prompt_injection})")
        else:
            logger.info("FetchNextActionPreProcessor: Retry chat injection disabled by graph_properties")

        return state

class FetchNextActionPostProcessor(NodePostProcessorWithState):
    """
    Post-processor that handles Claude/GPT-4o response.
    Stores current retry's model response for use by next retry's PreProcessor.
    """

    @staticmethod
    def apply(resp: SygraMessage, state: SygraState) -> SygraState:
        """Process and store Claude's response with evaluation."""
        logger.info("FetchNextActionPostProcessor: Processing Claude response")

        # Log the raw response for debugging
        retry_number = state["curr_retries"]
        ServiceNowRequestResponseLogger.log_response(resp.message, retry_number)

        # Extract response content
        llm_response = resp.message

        # Handle the response based on type
        if hasattr(llm_response, 'content'):
            content = llm_response.content
        else:
            content = str(llm_response)

        # Parse tool calls if any
        tool_calls = []
        # load json response
        try:
            # resp_dict = json.loads(content)
            # response_text = resp_dict.get("resp_text", "")
            # tool_calls = resp_dict.get("tool_calls", [])
            response_text = content
            tool_calls = state.get("tool_calls", [])
        except:
            response_text = str(content) if content else ""
            tool_calls = []

        # Update state
        response_dict = {}

        response_dict['text_response'] = response_text
        response_dict['tool_calls'] = tool_calls

        if "model_responses" not in state:
            state["model_responses"] = {}

        state["model_responses"]["retry_" + str(retry_number)] = response_dict
        chat_history = state.get('__chat_history__', [])
        logger.info(
            f"FetchNextActionPostProcessor: Retry number {retry_number}, chat history length: {len(chat_history)}")

        logger.info(f"FetchNextActionPostProcessor: Stored retry_{retry_number} response for inline evaluation at preprocessor in next retry")
        
        return state




class RetryFlow:
    """
    Determines whether to continue the flow or end based on retry count.
    """

    @staticmethod
    def apply(lambda_node_dict: dict, state: SygraState) -> SygraState:
        """Validate current state and determine next action."""
        logger.info("RetryFlow: Checking retry count for current mission and deciding whether to continue or end")

        curr_retry = state.get("curr_retries", 0)
        max_retries = state.get("max_retries", 3)
        mission_id = state.get("id")
        
        # Increment retry count
        curr_retry += 1
        state["curr_retries"] = curr_retry
        
        logger.info(f"RetryFlow: Mission {mission_id} has completed {curr_retry} retries.")
        
        # Check if we should continue or end
        if curr_retry < max_retries:
            state["should_continue"] = True
            logger.info(f"RetryFlow: Mission {mission_id} going into retry number {curr_retry + 1}")
        else:
            state["should_continue"] = False
            logger.info(f"RetryFlow: Maximum retries reached {max_retries}")
        
        # No longer need separate state dumping since outputs are handled by graph output_config

        return state



class DecideLLMNode(EdgeCondition):
    """
    Edge condition for determining whether to call llm with tools or not.
    """

    @staticmethod
    def apply(state: SygraState) -> str:
        no_switch = True
        current_tool_result = state.get("current_tool_result", {})

        if (isinstance(current_tool_result, dict) and
                "role" in current_tool_result and
                "content" in current_tool_result and
                isinstance(current_tool_result["content"], list) and
                len(current_tool_result["content"]) > 0):
            no_switch = False

        if no_switch:
            logger.info("Tools are not present")
            return 'fetch_next_action'
        else:
            logger.info("Tools are present in current tools")
            return 'fetch_next_action_tools'

class ShouldContinueCondition(EdgeCondition):
    """
    Edge condition for determining whether to continue the flow.
    """

    @staticmethod
    def apply(state: SygraState) -> str:
        should_continue = state.get('should_continue', False)

        if should_continue:
            logger.info("ShouldContinueCondition: Continuing to seed_data_processor")
            return 'seed_data_processor'
        else:
            logger.info("ShouldContinueCondition: Ending flow")
            return constants.SYGRA_END

class MetricCollatorPostProcessor(GraphPostProcessor):
    """
    Post-processor that calculates comprehensive web agent metrics from evaluation data.
    
    Note: Records with structural errors (raised as StructuralError exceptions during 
    preprocessing) will not reach this post-processor and will be automatically skipped 
    from metrics calculation.
    """

    async def process(self, data: list, metadata: dict) -> list:
        """
        Calculate comprehensive metrics from evaluation data.
        Handles invalid records gracefully - skips them and continues with valid data.
        
        Args:
            data: List of evaluation records with model_responses and golden_response
            metadata: Any extract information to pass from dataset_processor like model name or file name etc
            
        Returns:
            Metrics report list for downstream usage (always returns a report, even if no valid data)
        """
        logger.info(f"MetricCollatorPostProcessor: Starting metrics calculation for {len(data)} records")
        import re
        output_file = metadata.get("output_file")
        try:
            timestamp = re.sub(r".*/output_","",output_file).replace(".json","")
            if timestamp or len(timestamp) == 0:
                timestamp = datetime.now().isoformat()
        except:
            timestamp = datetime.now().isoformat()
        try:
            if not data:
                logger.warning("MetricCollatorPostProcessor: No data provided")
                return [{
                    "evaluation_summary": {
                        "total_records": 0,
                        "timestamp": timestamp,
                        "evaluation_type": "web_agent_metrics",
                        "status": "no_data"
                    },
                    "results": {
                        "overall": {},
                        "mission": {},
                        "summary": {"total_records": 0, "processed_records": 0, "skipped_records": 0}
                    }
                }]
            
            # Calculate comprehensive metrics (handles invalid records internally)
            calculator = WebAgentMetricsCalculator()
            metrics = await calculator.calculate_metrics(data, metadata)
            
            # Extract processing summary
            summary = metrics.get('summary', {})
            processed_records = summary.get('processed_records', 0)
            skipped_records = summary.get('skipped_records', 0)
            
            # Create metrics report
            metrics_report = {
                "evaluation_summary": {
                    "total_records": len(data),
                    "processed_records": processed_records,
                    "skipped_records": skipped_records,
                    "timestamp": timestamp,
                    "evaluation_type": "web_agent_metrics",
                    "status": "success"
                },
                "results": metrics
            }
            
            # Log results
            logger.info(f"MetricCollatorPostProcessor: Processed {processed_records}/{len(data)} records")
            if skipped_records > 0:
                logger.warning(f"MetricCollatorPostProcessor: Skipped {skipped_records} invalid records")
            
            # Log overall accuracy if available
            overall_accuracy = metrics.get('overall', {}).get('event', {}).get('accuracy')
            if overall_accuracy is not None:
                logger.info(f"Overall accuracy: {overall_accuracy:.3f}")
            
            # Return metrics report for downstream usage
            return [metrics_report]
            
        except Exception as e:
            logger.error(f"MetricCollatorPostProcessor: Fatal error calculating metrics: {e}")
            # Return error report but don't fail completely - downstream still gets something
            return [{
                "evaluation_summary": {
                    "total_records": len(data) if data else 0,
                    "processed_records": 0,
                    "skipped_records": len(data) if data else 0,
                    "timestamp": timestamp,
                    "evaluation_type": "web_agent_metrics",
                    "status": "fatal_error",
                    "error": str(e)
                },
                "results": {
                    "overall": {},
                    "mission": {},
                    "summary": {"total_records": len(data) if data else 0, "processed_records": 0, "skipped_records": len(data) if data else 0}
                }
            }]
