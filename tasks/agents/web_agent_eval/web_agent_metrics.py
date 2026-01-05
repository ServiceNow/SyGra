"""
Web Agent Metrics Calculator

Core metrics calculation class for web agent evaluation.
Calculates comprehensive metrics matching the exact structure from discussed excel:
- Overall: event(tool), confusion_matrix(tool), step(tool+params), confusion_matrix(step), step_metrics
- Mission: step_count, step_efficiency, successful

Usage:
    # For inline evaluation (in PreProcessor)
    result = WebAgentMetricsCalculator.evaluate_single_record(golden_response, predicted_tool_calls)
    
    # For comprehensive metrics (in MetricCollatorPostProcessor)
    metrics = WebAgentMetricsCalculator.calculate_metrics_from_data(data, metadata)
"""
import json
import math
from collections import defaultdict
from typing import Dict, List, Any, Optional

from sygra.logger.logger_config import logger
from sygra.utils import utils
from .constants import RETRY_FAILURE_PENALTY
from .tools_validation import is_action_within_bbox, is_scroll_direction_valid, is_typed_value_correct


class WebAgentMetricsCalculator:
    """Calculate comprehensive metrics for web agent evaluation"""

    def __init__(self):
        self.overall_results = []  # Store all validation results for overall metrics
        self.mission_results = defaultdict(list)  # Store results per mission
        # Events with parameter validation
        self.events_with_params = ['click', 'typing', 'scroll']
        # Events with identification only (no parameter validation)
        self.events_identification_only = ['HIL', 'waiting', 'slider-drag', 'clear-typing']
        # All events combined
        self.events = self.events_with_params + self.events_identification_only

    async def calculate_metrics(self, data: List[Dict], metadata: dict) -> Dict[str, Any]:
        """
        Calculate all metrics from the evaluation data
        
        Args:
            data: List of records with model_responses and golden_response
            metadata: extra information to process
            
        Returns:
            Complete metrics dictionary with overall and mission-level results matching discussed structure
        """
        total_records = len(data)
        processed_records = 0
        skipped_records = 0

        logger.info(f"WebAgentMetricsCalculator: Starting metrics calculation for {total_records} records")

        # Process all records and collect validation results
        for i, record in enumerate(data):
            try:
                if self._is_valid_record(record):
                    self._process_record(record)
                    processed_records += 1
                else:
                    skipped_records += 1
                    logger.warning(f"Skipped invalid record {i}: {record.get('id', 'unknown')}")
            except Exception as e:
                skipped_records += 1
                logger.error(f"Error processing record {i} ({record.get('id', 'unknown')}): {e}")
                continue

        logger.info(
            f"WebAgentMetricsCalculator: Processed {processed_records}/{total_records} records, skipped {skipped_records}")

        # Calculate overall metrics (matching discussed structure)
        overall_metrics = self._calculate_overall_metrics()

        # Calculate mission-level metrics (only step_count, step_efficiency, successful)
        mission_metrics = self._calculate_mission_metrics()
        efficiency_metrics = self._calculate_efficiency_metrics()

        # Store mission level data to display for dashboard
        output_file = metadata.get('output_file')
        if output_file and len(output_file) > 0:
            output_file = output_file.replace("output", "mission_data")
        else:
            logger.warning(f"No output file provided, generating mission_data.json in current working directory.")
            output_file = "mission_data.json"
        with open(output_file, "w") as mission_file:
            mission_file.write(json.dumps(self.mission_results, indent=4))

        result = {
            "overall": overall_metrics,
            "efficiency": efficiency_metrics,
            "mission": mission_metrics,
            "summary": {
                "total_records": total_records,
                "processed_records": processed_records,
                "skipped_records": skipped_records
            }
        }
        metrics_dict = {
            "Mission Efficiency": mission_metrics,
            "Event Efficiency": efficiency_metrics,
            "Event Identification": overall_metrics['event(tool)'],
            "Step Completeness": overall_metrics['step(tool+params)'],
            "Pass K": overall_metrics['pass_k']
        }
        result['ai_summary'] = await self.generate_summaries("openai_gpt41", metrics_dict)
        return result

    @staticmethod
    def _normalize_golden_response(golden_response: Any) -> List[Dict[str, Any]]:
        if isinstance(golden_response, list):
            return [g for g in golden_response if isinstance(g, dict)]
        if isinstance(golden_response, dict):
            return [golden_response]
        return []

    @staticmethod
    def _select_primary_golden_event(golden_list: List[Dict[str, Any]]) -> str:
        for g in golden_list:
            event = g.get('event')
            if isinstance(event, str) and event:
                return event
        return 'unknown'

    def _is_valid_record(self, record: Dict[str, Any]) -> bool:
        """Check if record has valid golden_response and model_responses"""
        try:
            # Check if record has required fields
            if not isinstance(record, dict):
                return False

            golden_response = record.get('golden_response')
            golden_list = self._normalize_golden_response(golden_response)
            if not golden_list:
                logger.warning(f"Record {record.get('id', 'unknown')}: Missing or invalid golden_response")
                return False

            has_any_valid_golden = False
            for golden in golden_list:
                if not golden.get('event'):
                    continue

                properties = golden.get('properties', {})
                if not isinstance(properties, dict):
                    continue

                event_type = golden.get('event', '')
                if event_type in ['click', 'typing']:
                    required_bbox_keys = ['x', 'y', 'width', 'height']
                    if any(key not in properties for key in required_bbox_keys):
                        continue

                has_any_valid_golden = True
                break

            if not has_any_valid_golden:
                logger.warning(f"Record {record.get('id', 'unknown')}: No valid golden candidates")
                return False

            # Check model_responses
            model_responses = record.get('model_responses')
            if not model_responses or not isinstance(model_responses, dict):
                logger.warning(f"Record {record.get('id', 'unknown')}: Missing or invalid model_responses")
                return False

            # Check if there's at least one retry with tool_calls
            has_valid_retry = False
            for retry_key, retry_data in model_responses.items():
                if isinstance(retry_data, dict) and retry_data.get('tool_calls'):
                    has_valid_retry = True
                    break

            if not has_valid_retry:
                logger.warning(f"Record {record.get('id', 'unknown')}: No valid retries with tool_calls")
                return False

            return True

        except Exception as e:
            logger.error(f"Error validating record {record.get('id', 'unknown')}: {e}")
            return False

    def _process_record(self, record: Dict[str, Any]):
        """Process single record and validate all retry attempts"""
        mission_id = record.get('mission_id', 'unknown')
        golden_response = record.get('golden_response', {})
        golden_list = self._normalize_golden_response(golden_response)
        model_responses = record.get('model_responses', {})

        step_results = []  # Results for this step across all retries

        # Process each retry
        for retry_key in sorted(model_responses.keys()):  # retry_0, retry_1, retry_2
            try:
                retry_data = model_responses[retry_key]
                if not isinstance(retry_data, dict):
                    logger.warning(f"Invalid retry data for {mission_id} {retry_key}: not a dict")
                    continue

                result = self._validate_single_attempt(golden_list, retry_data)
                if result is not None:  # Only store valid results
                    result['retry_id'] = retry_key
                    result['text_response'] = retry_data.get('text_response', '')
                    result['golden response'] = golden_list
                    result['retry_data'] = retry_data
                    self.overall_results.append(result)
                    step_results.append(result)

            except Exception as e:
                logger.error(f"Error processing retry {retry_key} for {mission_id}: {e}")
                continue

        # Store step results for mission metrics if we have any
        if step_results:
            self.mission_results[mission_id].append({
                'mission': record.get('mission', ''),
                'step_id': record.get('id', ''),
                'results': step_results
            })
        else:
            logger.warning(f"No valid results for any retry in record {mission_id}")

    def _validate_single_attempt(self, golden_list: List[Dict[str, Any]], predicted: Dict) -> Optional[Dict[str, Any]]:
        """Validate a single retry attempt against golden response"""
        try:
            tool_calls = predicted.get('tool_calls', [])

            primary_golden_event = self._select_primary_golden_event(golden_list)

            if not tool_calls:
                return {
                    'tool_correct': False,
                    'params_correct': False,
                    'step_correct': False,
                    'golden_event': primary_golden_event,
                    'predicted_event': 'none'
                }

            # Get first tool call (assuming single action per retry)
            tool_call = tool_calls[0]
            if not isinstance(tool_call, dict):
                logger.warning(f"Invalid tool call format: {tool_call}")
                return None

            # Handle naming discrepancy: click_tool -> click, type_tool -> typing, scroll_tool -> scroll
            # Right now the mapping is hard coded putting _tool, but ideally these 2 should be same
            predicted_tool_raw = tool_call.get('function', {}).get('name', '')
            if predicted_tool_raw.endswith('_tool'):
                predicted_tool = predicted_tool_raw.replace('_tool', '')
                # Handle type_tool -> typing conversion
                if predicted_tool == 'type':
                    predicted_tool = 'typing'
                # Handle typing_tool -> typing conversion
                elif predicted_tool == 'typing':
                    predicted_tool = 'typing'
                # Handle text_clear_tool -> clear-typing conversion
                elif predicted_tool == 'text_clear':
                    predicted_tool = 'clear-typing'
                # Handle hil_tool -> HIL conversion
                elif predicted_tool == 'hil':
                    predicted_tool = 'HIL'
                # Handle wait_tool -> waiting conversion
                elif predicted_tool == 'wait':
                    predicted_tool = 'waiting'
                # Handle slider_tool -> slider-drag conversion
                elif predicted_tool == 'slider':
                    predicted_tool = 'slider-drag'
            else:
                predicted_tool = predicted_tool_raw

            predicted_params = tool_call.get('function', {}).get('arguments', {})
            if not isinstance(predicted_params, dict):
                try:
                    predicted_params = json.loads(predicted_params)
                except:
                    predicted_params = {}

            matched_golden: Optional[Dict[str, Any]] = None
            for golden in golden_list:
                golden_event = golden.get('event', '')
                if not golden_event:
                    continue
                if predicted_tool != golden_event:
                    continue
                if self._validate_parameters(golden, predicted_params, golden_event):
                    matched_golden = golden
                    break

            if matched_golden is not None:
                golden_event = matched_golden.get('event', '')
                tool_correct = True
                params_correct = True
                step_correct = True
            else:
                golden_events = [g.get('event', '') for g in golden_list if isinstance(g.get('event', ''), str)]
                tool_correct = predicted_tool in golden_events
                golden_event = predicted_tool if tool_correct else primary_golden_event
                params_correct = False
                step_correct = False

            return {
                'tool_correct': tool_correct,
                'params_correct': params_correct,
                'step_correct': step_correct,  # This is tool + params combined
                'golden_event': golden_event,
                'predicted_event': predicted_tool
            }

        except Exception as e:
            logger.error(f"Error in _validate_single_attempt: {e}")
            return None

    def _validate_parameters(self, golden: Dict, predicted_params: Dict, event_type: str) -> bool:
        """Validate parameters based on event type using tools_validation methods"""
        try:
            golden_props = golden.get('properties', {})

            if not isinstance(predicted_params, dict):
                logger.warning(f"Invalid predicted_params format for {event_type}: {predicted_params}")
                return False

            # For identification-only events, if tool is correct, params are automatically correct
            # These events don't have parameter validation - only event type matching matters
            if event_type in self.events_identification_only:
                logger.debug(f"Event {event_type} is identification-only, params validation skipped (auto-pass)")
                return True  # Auto-pass params validation for identification-only events

            # Parameter validation for events with params
            if event_type == 'click':
                # Check if click coordinates are within bounding box
                pred_x = predicted_params.get('x', 0)
                pred_y = predicted_params.get('y', 0)
                return is_action_within_bbox(pred_x, pred_y, golden_props)

            elif event_type == 'typing':

                # Check if typed text matches expected text
                expected_text = golden_props.get('text', '')
                predicted_text = predicted_params.get('text', '')

                if not expected_text or not predicted_text:
                    # If either text is missing, only validate coordinates
                    logger.debug(
                        f"Missing text for typing validation - expected: '{expected_text}', predicted: '{predicted_text}'")
                    return False

                # Use is_typed_value_correct to validate text similarity
                text_validation = is_typed_value_correct(expected_text, predicted_text)
                logger.info(f"The expected vs predicted texts are {expected_text} and {predicted_text}")
                logger.info(f"The text validation result is {text_validation}")

                text_correct = text_validation.get('fuzzy_match', False)  # Use fuzzy match (threshold default 0.8)

                # Log text validation details for debugging
                logger.debug(f"Typing text validation - Expected: '{expected_text}', Predicted: '{predicted_text}', "
                             f"Exact: {text_validation.get('exact_match', False)}, "
                             f"Similarity: {text_validation.get('similarity_score', 0):.3f}, "
                             f"Fuzzy: {text_correct}")

                # Both coordinates and text must be correct for typing to be valid
                logger.info(f"The value for text_correct is {text_correct}")
                return text_correct

            elif event_type == 'scroll':
                # Check if scroll direction matches
                golden_direction = golden_props.get('direction', '')
                predicted_direction = predicted_params.get('direction', '')
                return is_scroll_direction_valid(golden_direction, predicted_direction)

            return False  # Unknown event type

        except Exception as e:
            logger.error(f"Error validating parameters for {event_type}: {e}")
            return False

    def _calculate_overall_metrics(self) -> Dict[str, Any]:
        """Calculate overall metrics matching discussed structure exactly"""
        if not self.overall_results:
            return {
                "event(tool)": {"accuracy": 0, "precision": 0, "recall": 0, "f1": 0},
                "confusion_matrix(tool)": {},
                "step(tool+params)": {"accuracy": 0, "precision": 0, "recall": 0, "f1": 0},
                "confusion_matrix(step)": {},
                "step_metrics": {"step_efficiency": 0, "total_steps": 0, "successful_steps": 0}
            }

        # Calculate event(tool) metrics - just tool correctness
        event_tool_metrics = self._calculate_tool_metrics()

        # Calculate confusion matrix for tools
        tool_confusion_matrix = self._calculate_tool_confusion_matrix()

        # Calculate step(tool+params) metrics - tool + params correctness
        step_metrics = self._calculate_step_metrics()

        # Calculate confusion matrix for steps
        step_confusion_matrix = self._calculate_step_confusion_matrix()

        # Calculate step efficiency metrics
        step_efficiency_metrics = self._calculate_step_efficiency_metrics()

        # Calculate pass_k
        pass_k = self._calculate_step_pass_k_metrics()

        return {
            "event(tool)": event_tool_metrics,
            "confusion_matrix(tool)": tool_confusion_matrix,
            "step(tool+params)": step_metrics,
            "confusion_matrix(step)": step_confusion_matrix,
            "step_metrics": step_efficiency_metrics,
            "pass_k": pass_k
        }

    def _calculate_tool_metrics(self) -> Dict[str, Any]:
        """Calculate event(tool) metrics - just tool correctness"""
        total_requests = len(self.overall_results)
        tool_correct_count = sum(1 for r in self.overall_results if r['tool_correct'])

        # Overall tool accuracy
        overall_accuracy = tool_correct_count / total_requests if total_requests > 0 else 0

        # # Get unique events for per-event metrics
        # events = ['click', 'typing', 'scroll']

        # Calculate precision, recall, F1 per event
        event_details = {}
        all_precisions = []
        all_recalls = []
        all_f1s = []

        for event in self.events:
            # True positives: correctly predicted this event
            tp = sum(1 for r in self.overall_results if r['golden_event'] == event and r['predicted_event'] == event)
            # False positives: predicted this event but was wrong
            fp = sum(1 for r in self.overall_results if r['predicted_event'] == event and r['golden_event'] != event)
            # False negatives: golden was this event but predicted differently
            fn = sum(1 for r in self.overall_results if r['golden_event'] == event and r['predicted_event'] != event)

            # Calculate metrics
            precision = tp / (tp + fp) if (tp + fp) > 0 else 0
            recall = tp / (tp + fn) if (tp + fn) > 0 else 0
            f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0

            # Accuracy for this event type
            event_total = sum(1 for r in self.overall_results if r['golden_event'] == event)
            accuracy = tp / event_total if event_total > 0 else 0

            event_details[event] = {
                "accuracy": accuracy,
                "precision": precision,
                "recall": recall,
                "f1": f1
            }

            all_precisions.append(precision)
            all_recalls.append(recall)
            all_f1s.append(f1)

        # Calculate macro averages
        avg_precision = sum(all_precisions) / len(all_precisions) if all_precisions else 0
        avg_recall = sum(all_recalls) / len(all_recalls) if all_recalls else 0
        avg_f1 = sum(all_f1s) / len(all_f1s) if all_f1s else 0

        return {
            "average": {
                "accuracy": overall_accuracy,
                "precision": avg_precision,
                "recall": avg_recall,
                "f1": avg_f1
            },
            **event_details
        }

    def _calculate_tool_confusion_matrix(self) -> Dict[str, Dict[str, int]]:
        """Calculate confusion matrix for tools only"""
        matrix = defaultdict(lambda: defaultdict(int))

        for result in self.overall_results:
            golden = result['golden_event']
            predicted = result['predicted_event']
            matrix[golden][predicted] += 1

        return dict(matrix)

    def _calculate_step_metrics(self) -> Dict[str, Any]:
        """Calculate step(tool+params) metrics - tool + params correctness
        
        NOTE: Only calculates for events with parameter validation (click, typing, scroll).
        Identification-only events (HIL, waiting, slider-drag, clear-typing) are excluded
        since they don't have meaningful parameter validation.
        """
        # Filter results to only include events with parameter validation
        step_results = [r for r in self.overall_results if r['golden_event'] in self.events_with_params]

        total_requests = len(step_results)
        step_correct_count = sum(1 for r in step_results if r['step_correct'])

        # Overall step accuracy (only for events with params)
        overall_accuracy = step_correct_count / total_requests if total_requests > 0 else 0

        # Calculate precision, recall, F1 per event for steps
        # Only for events with parameter validation
        event_details = {}
        all_precisions = []
        all_recalls = []
        all_f1s = []

        for event in self.events:
            # True positives: correctly predicted this event AND params correct
            tp = sum(1 for r in self.overall_results if r['golden_event'] == event and r['step_correct'])
            # False positives: predicted this event but step was wrong (tool or params wrong)
            fp = sum(1 for r in self.overall_results if r['predicted_event'] == event and not r['step_correct'])
            # False negatives: golden was this event but step was wrong
            fn = sum(1 for r in self.overall_results if r['golden_event'] == event and not r['step_correct'])

            # Calculate metrics
            precision = tp / (tp + fp) if (tp + fp) > 0 else 0
            recall = tp / (tp + fn) if (tp + fn) > 0 else 0
            f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0

            # Accuracy for this event type
            event_total = sum(1 for r in self.overall_results if r['golden_event'] == event)
            accuracy = tp / event_total if event_total > 0 else 0

            event_details[event] = {
                "accuracy": accuracy,
                "precision": precision,
                "recall": recall,
                "f1": f1
            }

            all_precisions.append(precision)
            all_recalls.append(recall)
            all_f1s.append(f1)

        # Calculate macro averages
        avg_precision = sum(all_precisions) / len(all_precisions) if all_precisions else 0
        avg_recall = sum(all_recalls) / len(all_recalls) if all_recalls else 0
        avg_f1 = sum(all_f1s) / len(all_f1s) if all_f1s else 0

        return {
            "average": {
                "accuracy": overall_accuracy,
                "precision": avg_precision,
                "recall": avg_recall,
                "f1": avg_f1
            },
            **event_details
        }

    def _calculate_step_confusion_matrix(self) -> Dict[str, Dict[str, int]]:
        """Calculate confusion matrix for steps (tool+params)
        
        NOTE: Only includes events with parameter validation (click, typing, scroll).
        Identification-only events are excluded from step confusion matrix.
        """
        matrix = defaultdict(lambda: defaultdict(int))

        for result in self.overall_results:
            golden = result['golden_event']

            # Only include events with parameter validation in step confusion matrix
            if golden not in self.events_with_params:
                continue

            # For step confusion, predicted is only counted if step was correct
            if result['step_correct']:
                predicted = result['predicted_event']
            else:
                predicted = 'incorrect'  # Mark as incorrect step
            matrix[golden][predicted] += 1

        return dict(matrix)

    def _calculate_step_efficiency_metrics(self) -> Dict[str, Any]:
        """Calculate both retry-level and step-level efficiency metrics"""
        # RETRY-LEVEL METRICS: Each individual attempt/retry
        event_metrics = defaultdict(lambda: defaultdict(int))
        total_retries = len(self.overall_results)
        successful_retries = sum(1 for r in self.overall_results if r['step_correct'])
        total_retry_accuracy = successful_retries / total_retries if total_retries > 0 else 0

        # STEP-LEVEL METRICS: Each step (successful if at least 1 retry succeeded)
        total_steps = 0
        successful_steps = 0

        # Count steps across all missions
        for mission_id, mission_steps in self.mission_results.items():
            for step_data in mission_steps:
                event = step_data['results'][0]['golden_event']
                if event in self.events:
                    event_metrics[event]['total_steps'] += 1
                    total_steps += 1
                    # Step is successful if at least one retry succeeded
                    step_success = any(r['step_correct'] for r in step_data['results'])
                    if step_success:
                        successful_steps += 1
                        event_metrics[event]['successful_steps'] += 1

        # event_metrics['average']['total_steps'] = total_steps
        # event_metrics['average']['successful_steps'] = successful_steps
        step_accuracy = successful_steps / total_steps if total_steps > 0 else 0

        for event in self.events:
            successful_steps = event_metrics[event]['successful_steps']
            total_steps = event_metrics[event]['total_steps']
            event_metrics[event]['step_accuracy'] = successful_steps / total_steps if total_steps > 0 else 0

        return {
            # Retry-level metrics (individual attempts)
            "total_retry_accuracy": total_retry_accuracy,
            "total_retries": total_retries,
            "successful_retries": successful_retries,

            # Step-level metrics (at least 1 retry succeeded)
            "events": {
                "average": {
                    "total_steps": total_steps,
                    "successful_steps": successful_steps,
                    "step_accuracy": step_accuracy
                },
                **event_metrics
            }
        }

    def _calculate_mission_metrics(self) -> Dict[str, Any]:
        """Calculate mission-level metrics - ONLY step_count, step_efficiency, successful"""
        mission_metrics = {}

        for mission_id, mission_steps in self.mission_results.items():
            # Flatten all results for this mission
            all_mission_results = []
            for step_data in mission_steps:
                all_mission_results.extend(step_data['results'])

            if not all_mission_results:
                continue

            total_steps = len(mission_steps)
            # Retry Step count is number of retries required for first success for a step
            # Incorporate case where all retries fail for a step
            retry_step_count = 0
            for step_data in mission_steps:
                task_success = False
                for i in range(len(step_data['results'])):
                    if step_data['results'][i]['step_correct']:
                        task_success = True
                        retry_step_count += i + 1
                        break
                # Penalize retry in case of complete failure
                if not task_success:
                    retry_step_count += RETRY_FAILURE_PENALTY

            # Step efficiency measures the number of retries required for a step to succeed. Best case it is 1.
            step_efficiency = total_steps / retry_step_count if retry_step_count > 0 else 0

            # Mission is successful if all steps are successful
            successful = all(any(r['step_correct'] for r in step_data['results']) for step_data in mission_steps)

            mission_metrics[mission_id] = {
                "mission_description": mission_steps[0]['mission'],
                "total_step_count": total_steps,
                "retry_step_count": retry_step_count,
                "step_efficiency": step_efficiency,
                "successful": successful
            }

        return mission_metrics

    def _calculate_efficiency_metrics(self) -> Dict[str, Any]:
        """Calculate event-level efficiency metrics - total_step_count, retry_step_count, step_efficiency"""
        # events = ['average', 'click', 'typing', 'scroll']
        event_metrics = defaultdict(lambda: defaultdict(int))

        average_total_steps = 0
        average_retry_steps = 0

        for mission_id, mission_steps in self.mission_results.items():
            if not mission_steps:
                continue

            total_steps = len(mission_steps)
            retry_step_count = 0

            for step_data in mission_steps:
                results = step_data['results']
                if not results:
                    continue

                event = results[0]['golden_event']
                if event in self.events:
                    metrics = event_metrics[event]
                    metrics['total_step_count'] += 1

                    # Find first successful attempt, else penalize with retry failure penalty
                    first_success = next((i for i, r in enumerate(results) if r['step_correct']), None)
                    if first_success is not None:
                        retries = first_success + 1
                    else:
                        retries = RETRY_FAILURE_PENALTY  # failure penalty

                    metrics['retry_step_count'] += retries
                    retry_step_count += retries

            average_total_steps += total_steps
            average_retry_steps += retry_step_count

        average_step_efficiency = average_total_steps / average_retry_steps if average_retry_steps > 0 else 0

        # Compute step efficiency
        for event in self.events:
            total = event_metrics[event]['total_step_count']
            retries = event_metrics[event]['retry_step_count']
            event_metrics[event]['step_efficiency'] = total / retries if retries > 0 else 0

        return {
            "average": {
                "total_step_count": average_total_steps,
                "retry_step_count": average_retry_steps,
                "step_efficiency": average_step_efficiency
            },
            **event_metrics
        }

    @staticmethod
    def pass_at_k(n: int, c: int, k: int) -> float:
        """Calculate pass@k metric: probability that at least one of k independent attempts will succeed.

        Args:
            n (int): Total number of attempts/samples
            c (int): Number of correct solutions
            k (int): Number of samples to draw

        Returns:
            float: Pass@k probability (0 to 1)

        Raises:
            ValueError: If invalid parameters are provided
        """
        if n <= 0 or c < 0 or k <= 0:
            raise ValueError("n and k must be positive, c must be non-negative")
        if c > n:
            raise ValueError("Number of correct solutions (c) cannot exceed total attempts (n)")
        if k > n:
            raise ValueError("Sample size (k) cannot exceed total attempts (n)")

        # If all solutions are correct, pass@k = 1
        if c == n:
            return 1.0

        # If no solutions are correct, pass@k = 0
        if c == 0:
            return 0.0

        # Calculate using the complement: 1 - P(all k samples are incorrect)
        # P(all incorrect) = C(n-c, k) / C(n, k)
        try:
            prob_all_incorrect = math.comb(n - c, k) / math.comb(n, k)
            return 1.0 - prob_all_incorrect
        except (ValueError, ZeroDivisionError):
            # Handle edge cases where combinations are invalid
            return 0.0

    @staticmethod
    def pass_power_k(success_rate: float, k: int) -> float:
        """Calculate pass^k metric: probability that an agent would succeed on all k independent attempts.

        Args:
            success_rate (float): Raw success rate on a single attempt (0 to 1)
            k (int): Number of consecutive attempts

        Returns:
            float: Pass^k probability (0 to 1)

        Raises:
            ValueError: If invalid parameters are provided
        """
        if not 0 <= success_rate <= 1:
            raise ValueError("Success rate must be between 0 and 1")
        if k <= 0:
            raise ValueError("k must be positive")

        return success_rate ** k

    @staticmethod
    def calculate_success_rate(n: int, c: int) -> float:
        """Calculate raw success rate from total attempts and correct solutions.

        Args:
            n (int): Total number of attempts
            c (int): Number of correct solutions

        Returns:
            float: Success rate (0 to 1)
        """
        if n <= 0:
            raise ValueError("Total attempts (n) must be positive")
        if c < 0:
            raise ValueError("Correct solutions (c) must be non-negative")
        if c > n:
            raise ValueError("Correct solutions (c) cannot exceed total attempts (n)")

        return c / n

    def calc_pass_k_metrics(self, attempt_result: list, k: int) -> dict:
        """Calculate pass@k and pass^k metrics for the same data.

        Args:
            attempt_result (list): List containing results of different attempts
            k (int): Number of samples/attempts

        Returns:
            dict: Dictionary containing both metrics and related information
        """
        n = len(attempt_result)
        c = sum(attempt_result)
        success_rate = self.calculate_success_rate(n, c)
        pass_at_k_value = self.pass_at_k(n, c, k)
        pass_power_k_value = self.pass_power_k(success_rate, k)

        return {
            "success_rate": success_rate,
            "pass_at_k": pass_at_k_value,
            "pass_power_k": pass_power_k_value,
            "difference": pass_at_k_value - pass_power_k_value,
            "parameters": {"n": n, "c": c, "k": k},
        }

    def _calculate_step_pass_k_metrics(self) -> Dict[str, Any]:
        """Calculate step-level pass@k and pass^k metrics."""

        event_metrics = defaultdict(dict)

        n = 3
        ks = (1, 2, 3)

        events = list(self.events) + ["average"]

        # Initialize data structures
        for event in events:
            event_metrics[event]["total_steps"] = 0
            for k in ks:
                event_metrics[event][k] = {
                    "pass_at_k": 0.0,
                    "pass_power_k": 0.0
                }

        # Accumulation
        for mission_steps in self.mission_results.values():
            for step_data in mission_steps:
                event = step_data["results"][0]["golden_event"]
                if event not in self.events:
                    continue

                # Increment counters
                event_metrics[event]["total_steps"] += 1
                event_metrics["average"]["total_steps"] += 1

                # Number of correct predictions
                c = sum(r["step_correct"] for r in step_data["results"])
                success_rate = self.calculate_success_rate(n, c)

                for k in ks:
                    pass_at_k_value = self.pass_at_k(n, c, k)
                    pass_power_k_value = self.pass_power_k(success_rate, k)

                    event_metrics[event][k]["pass_at_k"] += pass_at_k_value
                    event_metrics[event][k]["pass_power_k"] += pass_power_k_value

                    event_metrics["average"][k]["pass_at_k"] += pass_at_k_value
                    event_metrics["average"][k]["pass_power_k"] += pass_power_k_value

        # Normalization
        for event in events:
            total = event_metrics[event]["total_steps"]
            if total == 0:
                continue

            for k in ks:
                event_metrics[event][k]["pass_at_k"] /= total
                event_metrics[event][k]["pass_power_k"] /= total

        return event_metrics

    @staticmethod
    async def get_model_summary(model, metrics: dict[str, Any]):
        """Get model summary for the given metrics"""
        system_prompt = """You are analysing report of a web agent. Help me summarize the metrics and gather insights. 
        Here, web agent has various events like click, type, etc. We have captured performance of various domains for these. 

        Event Identification is if the golden event and web agent predicted event match. Eg. If golden event is click, whether agent identifies as click too.
        Step Completeness is if event and tool both are correct. Eg. If click is identified correctly and click position is correct too.

        Each web agent mission consists of steps. The agent will retry maximum 3 times till it succeeds.
        Here, total_step_count refers to the total steps in missions. 
        retry_step_count refers to the amount of retries required. 
        step_efficiency is total_step_count/retry_step_count.
        successful refers to a mission being successful if all the steps in it succeed, else false."""

        user_prompt = f"""Generate a summary under 300 words of the insights gathered for a web agent from the below provided metrics. 
        Specify overall Pros and Cons with respect to which domains (obtained from mission_description) and events perform well and which do not.You do not have to take any action. You just need to analyze the metrics provided and give the AI summary.

        Metrics: {metrics}"""
        summary = await utils.get_model_response(model, system_prompt, user_prompt)

        user_prompt = f"""Generate a short summary of the insights gathered for a web agent with below metrics.
         Focus on domains (obtained from mission_description) and events perform well and which do not.
         Keep it under 75 words.
         
         Metrics: {metrics}"""
        short_summary = await utils.get_model_response(model, system_prompt, user_prompt)

        final_summary = summary + "\n\n**Short Summary:**\n" + short_summary
        return final_summary

    async def generate_summaries(self, model_name: str, metrics_dict: dict[str, Any]):
        """Get model summary for the given metrics"""
        ai_summary = dict()
        try:
            model = utils.get_model(model_name)
            ai_summary['Event Identification'] = await self.get_model_summary(model,
                                                                              metrics_dict['Event Identification'])
            ai_summary['Step Completeness'] = await self.get_model_summary(model, metrics_dict['Step Completeness'])
            ai_summary['Mission Efficiency'] = await self.get_model_summary(model, metrics_dict['Mission Efficiency'])
            ai_summary['Event Efficiency'] = await self.get_model_summary(model, metrics_dict['Event Efficiency'])
            ai_summary['Pass K'] = await self.get_model_summary(model, metrics_dict['Pass K'])
            ai_summary['overall'] = await self.get_model_summary(model, metrics_dict)

        except Exception as e:
            logger.warning(f"Error generating summary: {e}")
        return ai_summary

    def evaluate_single_record(
            self,
            golden_response: Any,
            predicted_tool_calls: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Lightweight inline evaluation for single record during graph execution.
        Used by PreProcessor to determine if previous retry succeeded or failed.
        
        Args:
            golden_response: Expected response with event and properties
            predicted_tool_calls: Model's predicted tool calls
            
        Returns:
            dict: {
                'success': bool,
                'tool_correct': bool,
                'params_correct': bool,
                'predicted_event': str,
                'golden_event': str
            }
        """
        try:
            # Validate inputs
            golden_list = self._normalize_golden_response(golden_response)
            if not golden_list:
                return {
                    'success': False,
                    'tool_correct': False,
                    'params_correct': False,
                    'predicted_event': 'none',
                    'golden_event': 'unknown'
                }

            if not predicted_tool_calls or len(predicted_tool_calls) == 0:
                return {
                    'success': False,
                    'tool_correct': False,
                    'params_correct': False,
                    'predicted_event': 'none',
                    'golden_event': self._select_primary_golden_event(golden_list)
                }

            # Create predicted dict in the format expected by _validate_single_attempt
            predicted_dict = {
                'tool_calls': predicted_tool_calls
            }

            # Call the existing validation method directly
            result = self._validate_single_attempt(golden_list, predicted_dict)

            if result is None:
                return {
                    'success': False,
                    'tool_correct': False,
                    'params_correct': False,
                    'predicted_event': 'invalid',
                    'golden_event': self._select_primary_golden_event(golden_list)
                }

            # Map the result to inline evaluation format
            # step_correct in calculator = success in inline evaluation
            return {
                'success': result.get('step_correct', False),
                'tool_correct': result.get('tool_correct', False),
                'params_correct': result.get('params_correct', False),
                'predicted_event': result.get('predicted_event', 'unknown'),
                'golden_event': result.get('golden_event', 'unknown')
            }

        except Exception as e:
            logger.error(f"Error in evaluate_single_record: {e}")
            return {
                'success': False,
                'tool_correct': False,
                'params_correct': False,
                'predicted_event': 'error',
                'golden_event': self._select_primary_golden_event(self._normalize_golden_response(golden_response))
            }
