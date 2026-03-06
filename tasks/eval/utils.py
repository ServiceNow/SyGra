import json
from datetime import datetime

"""
Utilities for evaluation tasks.

Includes helpers to parse model responses as JSON, run unit metrics in a graph node,
and collate metric results into an evaluation report.
"""

from typing import Any, Optional

import pandas as pd
import regex

from sygra.core.eval.metrics.aggregator_metrics.aggregator_metric_registry import AggregatorMetricRegistry
from sygra.core.eval.metrics.unit_metrics.unit_metric_registry import UnitMetricRegistry
from sygra.core.eval.metrics.unit_metrics.unit_metric_result import UnitMetricResult
from sygra.core.graph.functions.lambda_function import LambdaFunction
from sygra.core.graph.graph_postprocessor import GraphPostProcessor
from sygra.core.graph.sygra_state import SygraState
from sygra.logger.logger_config import logger


def parse_response_as_json(s: Any) -> Optional[dict[str, Any]]:
    """Parse a model response into a JSON object.

    This helper first attempts to parse the full string as JSON. If that fails, it
    falls back to extracting the first balanced JSON object substring (supports
    nested braces) and parsing that.

    Returns `None` if parsing fails.
    """

    JSON_REGEX_PATTERN = regex.compile(r"\{(?:[^{}]|(?R))*\}")

    if s is None:
        return None

    text = s if isinstance(s, str) else str(s)
    try:
        parsed = json.loads(text)
        return parsed if isinstance(parsed, dict) else {"value": parsed}
    except json.decoder.JSONDecodeError as e:
        match = JSON_REGEX_PATTERN.search(text)
        if not match:
            logger.error("No json string found: " + e.msg)
            logger.error(text)
            return None
        try:
            parsed = json.loads(match[0])
            return parsed if isinstance(parsed, dict) else {"value": parsed}
        except json.decoder.JSONDecodeError as e2:
            logger.error("Unable to parse json string: " + e2.msg)
            logger.error(text)
            return None


class UnitMetrics(LambdaFunction):
    """Graph lambda that evaluates configured unit metrics and stores results in state."""

    @staticmethod
    def apply(lambda_node_dict: dict, state: SygraState) -> SygraState:
        golden_topic = [{"text": state[lambda_node_dict["golden_key"]]}]
        predicted_answer = [{"text": state[lambda_node_dict["predicted_key"]]}]
        for unit_metric in lambda_node_dict.get("unit_metrics_map", []):
            unit_metric_name = unit_metric["name"]
            unit_metric_params = unit_metric.get("params", {})
            validator = UnitMetricRegistry.get_metric(unit_metric_name, **unit_metric_params)
            results = validator.evaluate(golden=golden_topic, predicted=predicted_answer)
            if results:
                state[unit_metric_name] = results[0].to_dict()
        return state


class MetricCollatorPostProcessor(GraphPostProcessor):
    """
    Post-processor that calculates evaluation metrics from the task.

    Note: Records with structural errors (raised as StructuralError exceptions during
    preprocessing) will not reach this post-processor and will be automatically skipped
    from metrics calculation.
    """

    def __init__(
            self,
            aggregator_metrics_map: Optional[list[dict[str, Any]]] = None,
            **kwargs: Any
    ):
        self.aggregator_metrics_map = aggregator_metrics_map or []

    def process(self, data: list, metadata: dict) -> list:
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

        try:
            if not data:
                logger.warning("MetricCollatorPostProcessor: No data provided")
                return [{
                    "evaluation_summary": {
                        "total_records": 0,
                        "status": "no_data"
                    },
                    "results": {}
                }]

            df = pd.DataFrame(data)
            results: dict[str, Any] = {}
            for aggregator_metric in self.aggregator_metrics_map:
                aggregator_metric_name = aggregator_metric["name"]
                aggregator_metric_params = aggregator_metric.get("params", {})
                unit_metrics_field = aggregator_metric.get("unit_metrics_results", "")

                if isinstance(unit_metrics_field, list):
                    unit_metrics_field = unit_metrics_field[0] if unit_metrics_field else ""

                if not unit_metrics_field or unit_metrics_field not in df.columns:
                    raise KeyError(
                        f"Missing unit metric results field '{unit_metrics_field}' in data. "
                        f"Available columns: {list(df.columns)}"
                    )

                # Build unit metric results with enriched metadata
                metadata_mapping = aggregator_metric.get("metadata", {})
                
                unit_metrics_results = []
                for idx, row in df.iterrows():
                    unit_result_data = row[unit_metrics_field]
                    
                    if isinstance(unit_result_data, dict):
                        # Enrich metadata with fields specified in graph config
                        if metadata_mapping:
                            if "metadata" not in unit_result_data:
                                unit_result_data["metadata"] = {}
                            
                            # Generic mapping: store source values with metadata keys
                            for metadata_key, source_field in metadata_mapping.items():
                                source_value = row.get(source_field, "unknown")
                                unit_result_data["metadata"][metadata_key] = source_value
                        
                        unit_metrics_results.append(UnitMetricResult(**unit_result_data))
                    elif isinstance(unit_result_data, UnitMetricResult):
                        unit_metrics_results.append(unit_result_data)

                metric = AggregatorMetricRegistry.get_metric(
                    aggregator_metric_name, **aggregator_metric_params
                )
                metric_result = metric.calculate(unit_metrics_results)

                results[unit_metrics_field + "-" + aggregator_metric_name] = metric_result

            return [{
                "evaluation_summary": {
                    "total_records": len(data),
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "status": "success"
                },
                "results": results
            }]

        except Exception as e:
            logger.error(f"MetricCollatorPostProcessor: Fatal error calculating metrics: {e}")
            # Return error report but don't fail completely - downstream still gets something
            return [{
                "evaluation_summary": {
                    "total_records": len(data) if data else 0,
                    "status": "fatal_error",
                    "error": str(e)
                },
                "results": {}
            }]
