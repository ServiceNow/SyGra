import json
import os
import statistics
import subprocess
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from threading import Lock
from typing import Any, Optional, Union

from sygra.logger.logger_config import logger


def calculate_latency_statistics(latency_samples: list[float]) -> dict[str, float]:
    """
    Calculate latency statistics including percentiles.

    Args:
        latency_samples: List of latency values in seconds

    Returns:
        Dictionary with min, max, mean, median, std_dev, p50, p95, p99
    """
    n = len(latency_samples)

    # Handle empty or single sample cases
    if n == 0:
        return dict.fromkeys(["min", "max", "mean", "median", "std_dev", "p50", "p95", "p99"], 0.0)

    if n == 1:
        return dict.fromkeys(
            ["min", "max", "mean", "median", "std_dev", "p50", "p95", "p99"], latency_samples[0]
        )

    # Calculate percentiles for 2+ samples
    quantiles = statistics.quantiles(latency_samples, n=100)

    return {
        "min": min(latency_samples),
        "max": max(latency_samples),
        "mean": statistics.mean(latency_samples),
        "median": statistics.median(latency_samples),
        "std_dev": statistics.stdev(latency_samples),
        "p50": quantiles[49],
        "p95": quantiles[94],
        "p99": quantiles[98],
    }


@dataclass
class TokenStatistics:
    """Token usage statistics."""

    total_prompt_tokens: int = 0
    total_completion_tokens: int = 0
    total_tokens: int = 0
    num_requests_with_tokens: int = 0

    def add_usage(
        self,
        prompt_tokens: int,
        completion_tokens: int,
        total_tokens: int,
    ):
        """Add token usage from a single request."""
        prompt_tokens = int(prompt_tokens) if prompt_tokens else 0
        completion_tokens = int(completion_tokens) if completion_tokens else 0
        total_tokens = int(total_tokens) if total_tokens else 0

        if prompt_tokens > 0 or completion_tokens > 0 or total_tokens > 0:
            self.total_prompt_tokens += prompt_tokens
            self.total_completion_tokens += completion_tokens
            self.total_tokens += total_tokens
            self.num_requests_with_tokens += 1

    def get_average_tokens(self) -> dict[str, float]:
        """Calculate average token usage per successful request (requests with tokens)."""
        if self.num_requests_with_tokens == 0:
            result = {
                "avg_prompt_tokens": 0.0,
                "avg_completion_tokens": 0.0,
                "avg_total_tokens": 0.0,
            }
        else:
            result = {
                "avg_prompt_tokens": self.total_prompt_tokens / self.num_requests_with_tokens,
                "avg_completion_tokens": self.total_completion_tokens
                / self.num_requests_with_tokens,
                "avg_total_tokens": self.total_tokens / self.num_requests_with_tokens,
            }

        return result


@dataclass
class ModelMetrics:
    """Comprehensive metrics for a model."""

    model_name: str
    model_type: str = "unknown"
    model_url: Optional[str] = None

    # Token statistics
    token_stats: TokenStatistics = field(default_factory=TokenStatistics)

    # Performance metrics
    total_latency_seconds: float = 0.0
    successful_request_latency: float = 0.0
    num_requests: int = 0
    num_retries: int = 0
    num_failures: int = 0
    response_codes: dict[int, int] = field(default_factory=lambda: defaultdict(int))

    # Latency tracking for percentile calculations
    latency_samples: list[float] = field(default_factory=list)

    # Cost tracking
    total_cost_usd: float = 0.0

    # Model parameters used
    parameters: dict[str, Any] = field(default_factory=dict)

    def add_request(
        self,
        latency: float,
        response_code: int,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        total_tokens: int = 0,
        is_retry: bool = False,
        cost_usd: float = 0.0,
    ):
        """Record metrics from a model request."""
        self.total_latency_seconds += latency
        self.num_requests += 1
        self.response_codes[response_code] = self.response_codes.get(response_code, 0) + 1

        # Track latency sample for percentile calculations
        self.latency_samples.append(latency)

        if is_retry:
            self.num_retries += 1

        if response_code != 200:
            self.num_failures += 1
        else:
            # Track latency only for successful requests (for tokens/sec calculation)
            self.successful_request_latency += latency

        # Track cost
        self.total_cost_usd += cost_usd

        # Always call add_usage - it will filter out requests with no tokens internally
        self.token_stats.add_usage(prompt_tokens, completion_tokens, total_tokens)

    def get_average_latency(self) -> float:
        """Calculate average latency per request."""
        return self.total_latency_seconds / self.num_requests if self.num_requests > 0 else 0.0

    def get_tokens_per_second(self) -> float:
        """Calculate token generation speed based on successful requests only."""
        if self.successful_request_latency == 0:
            return 0.0
        return self.token_stats.total_completion_tokens / self.successful_request_latency

    def to_dict(self) -> dict[str, Any]:
        """Convert metrics to dictionary."""
        return {
            "model_name": self.model_name,
            "model_type": self.model_type,
            "model_url": self.model_url,
            "token_statistics": {
                "total_prompt_tokens": self.token_stats.total_prompt_tokens,
                "total_completion_tokens": self.token_stats.total_completion_tokens,
                "total_tokens": self.token_stats.total_tokens,
                **self.token_stats.get_average_tokens(),
            },
            "performance": {
                "total_requests": self.num_requests,
                "total_retries": self.num_retries,
                "total_failures": self.num_failures,
                "failure_rate": (
                    self.num_failures / self.num_requests if self.num_requests > 0 else 0.0
                ),
                "total_latency_seconds": round(self.total_latency_seconds, 3),
                "average_latency_seconds": round(self.get_average_latency(), 3),
                "tokens_per_second": round(self.get_tokens_per_second(), 2),
                "latency_statistics": {
                    k: round(v, 3)
                    for k, v in calculate_latency_statistics(self.latency_samples).items()
                },
            },
            "cost": {
                "total_cost_usd": round(self.total_cost_usd, 6),
                "average_cost_per_request": round(
                    self.total_cost_usd / self.num_requests if self.num_requests > 0 else 0.0, 6
                ),
            },
            "response_code_distribution": dict(self.response_codes),
            "parameters": self.parameters,
        }


@dataclass
class NodeMetrics:
    """Metrics for a specific node in the graph."""

    node_name: str
    node_type: str
    model_name: Optional[str] = None

    total_executions: int = 0
    total_failures: int = 0
    total_latency_seconds: float = 0.0

    # Latency tracking for percentile calculations
    latency_samples: list[float] = field(default_factory=list)

    # Token statistics for this node
    token_stats: TokenStatistics = field(default_factory=TokenStatistics)

    # Cost tracking
    total_cost_usd: float = 0.0

    def record_execution(
        self,
        latency: float,
        success: bool,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        total_tokens: int = 0,
        cost_usd: float = 0.0,
    ):
        """Record a node execution with optional token usage and cost."""
        self.total_executions += 1
        self.total_latency_seconds += latency
        self.latency_samples.append(latency)
        self.total_cost_usd += cost_usd

        if not success:
            self.total_failures += 1

        # Record token usage if provided
        if prompt_tokens > 0 or completion_tokens > 0 or total_tokens > 0:
            self.token_stats.add_usage(prompt_tokens, completion_tokens, total_tokens)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        avg_latency = (
            self.total_latency_seconds / self.total_executions if self.total_executions > 0 else 0.0
        )

        result: dict[str, Any] = {
            "node_name": self.node_name,
            "node_type": self.node_type,
            "model_name": self.model_name,
            "total_executions": self.total_executions,
            "total_failures": self.total_failures,
            "failure_rate": (
                self.total_failures / self.total_executions if self.total_executions > 0 else 0.0
            ),
            "total_latency_seconds": round(self.total_latency_seconds, 3),
            "average_latency_seconds": round(avg_latency, 3),
            "latency_statistics": {
                k: round(v, 3)
                for k, v in calculate_latency_statistics(self.latency_samples).items()
            },
        }

        # Add cost information if there's any cost
        if self.total_cost_usd > 0:
            result["cost"] = {
                "total_cost_usd": round(self.total_cost_usd, 6),
                "average_cost_per_execution": round(
                    (
                        self.total_cost_usd / self.total_executions
                        if self.total_executions > 0
                        else 0.0
                    ),
                    6,
                ),
            }

        # Add token statistics if the node has any token usage
        if self.token_stats.num_requests_with_tokens > 0:
            avg_tokens = self.token_stats.get_average_tokens()
            token_stats: dict[str, Union[int, float]] = {
                "total_prompt_tokens": self.token_stats.total_prompt_tokens,
                "total_completion_tokens": self.token_stats.total_completion_tokens,
                "total_tokens": self.token_stats.total_tokens,
                "avg_prompt_tokens": avg_tokens["avg_prompt_tokens"],
                "avg_completion_tokens": avg_tokens["avg_completion_tokens"],
                "avg_total_tokens": avg_tokens["avg_total_tokens"],
            }
            result["token_statistics"] = token_stats

        return result


@dataclass
class DatasetMetadata:
    """Metadata about the dataset used."""

    source_type: str = "unknown"
    source_path: Optional[str] = None
    num_records_processed: int = 0
    start_index: int = 0
    dataset_version: Optional[str] = None
    dataset_hash: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "source_type": self.source_type,
            "source_path": self.source_path,
            "num_records_processed": self.num_records_processed,
            "start_index": self.start_index,
            "dataset_version": self.dataset_version,
            "dataset_hash": self.dataset_hash,
        }


@dataclass
class ExecutionContext:
    """Context information about the execution environment."""

    task_name: str
    run_name: Optional[str] = None
    output_dir: Optional[str] = None
    batch_size: int = 50
    checkpoint_interval: int = 100
    resumable: bool = False
    debug: bool = False

    # Environment info
    python_version: Optional[str] = None
    sygra_version: Optional[str] = None

    # Git info for reproducibility
    git_commit_hash: Optional[str] = None
    git_branch: Optional[str] = None
    git_is_dirty: bool = False

    # Timing
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    duration_seconds: Optional[float] = None

    # Run timestamp (for matching with output files)
    run_timestamp: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "task_name": self.task_name,
            "run_name": self.run_name,
            "output_dir": self.output_dir,
            "batch_size": self.batch_size,
            "checkpoint_interval": self.checkpoint_interval,
            "resumable": self.resumable,
            "debug": self.debug,
            "environment": {
                "python_version": self.python_version,
                "sygra_version": self.sygra_version,
            },
            "git": {
                "commit_hash": self.git_commit_hash,
                "branch": self.git_branch,
                "is_dirty": self.git_is_dirty,
            },
            "timing": {
                "start_time": self.start_time.isoformat() if self.start_time else None,
                "end_time": self.end_time.isoformat() if self.end_time else None,
                "duration_seconds": (
                    round(self.duration_seconds, 3) if self.duration_seconds else None
                ),
            },
        }


class MetadataCollector:
    """
    Central metadata collector for Sygra runs.

    This class collects comprehensive metadata about Sygra task executions including:
    - Model usage statistics (tokens, latency, failures)
    - Node execution metrics
    - Dataset information
    - Execution context and versioning

    Thread-safe singleton implementation.

    Metadata collection can be disabled globally by setting the environment variable:
        SYGRA_DISABLE_METADATA=1
    Or programmatically by calling:
        collector.set_enabled(False)
    """

    _instance: Optional["MetadataCollector"] = None
    _lock = Lock()
    _initialized: bool
    _enabled: bool = True  # Metadata collection enabled by default

    def __new__(cls):
        """Singleton pattern to ensure one collector per process."""
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self):
        """Initialize the metadata collector."""
        if self._initialized:
            return

        self._initialized = True
        self._lock = Lock()

        # Check if metadata collection is disabled via environment variable
        self._enabled = os.getenv("SYGRA_DISABLE_METADATA", "0").lower() not in ("1", "true", "yes")

        # Metrics storage
        self.model_metrics: dict[str, ModelMetrics] = {}
        self.node_metrics: dict[str, NodeMetrics] = {}
        self.dataset_metadata = DatasetMetadata()
        self.execution_context = ExecutionContext(task_name="unknown")

        # Track overall execution
        self.total_records_processed = 0
        self.total_records_failed = 0

        if self._enabled:
            logger.debug("MetadataCollector initialized (enabled)")
        else:
            logger.info("MetadataCollector initialized (DISABLED via SYGRA_DISABLE_METADATA)")

    def is_enabled(self) -> bool:
        """Check if metadata collection is enabled."""
        return self._enabled

    def set_enabled(self, enabled: bool):
        """Enable or disable metadata collection.

        Args:
            enabled: True to enable metadata collection, False to disable
        """
        with self._lock:
            self._enabled = enabled
            if enabled:
                logger.info("Metadata collection ENABLED")
            else:
                logger.info("Metadata collection DISABLED")

    def reset(self):
        """Reset all collected metadata (useful for testing or new runs)."""
        with self._lock:
            self.model_metrics.clear()
            self.node_metrics.clear()
            self.dataset_metadata = DatasetMetadata()
            self.execution_context = ExecutionContext(task_name="unknown")
            self.total_records_processed = 0
            self.total_records_failed = 0
            logger.debug("MetadataCollector reset")

    def set_execution_context(
        self,
        task_name: str,
        run_name: Optional[str] = None,
        output_dir: Optional[str] = None,
        batch_size: int = 50,
        checkpoint_interval: int = 100,
        resumable: bool = False,
        debug: bool = False,
        run_timestamp: Optional[str] = None,
    ):
        """Set the execution context for this run."""
        if not self._enabled:
            return

        with self._lock:
            self.execution_context.task_name = task_name
            self.execution_context.run_name = run_name
            self.execution_context.output_dir = output_dir
            self.execution_context.batch_size = batch_size
            self.execution_context.checkpoint_interval = checkpoint_interval
            self.execution_context.resumable = resumable
            self.execution_context.debug = debug
            self.execution_context.run_timestamp = run_timestamp

            # Capture environment info
            self._capture_environment_info()

            # Start timing
            self.execution_context.start_time = datetime.now()

            logger.debug(f"Execution context set for task: {task_name}")

    def _capture_environment_info(self):
        """Capture environment information for reproducibility."""
        # Python version
        import sys

        self.execution_context.python_version = sys.version

        # Sygra version
        try:
            from sygra import __version__

            self.execution_context.sygra_version = __version__
        except Exception:
            self.execution_context.sygra_version = "unknown"

        # Git information
        self._capture_git_info()

    def _capture_git_info(self):
        """Capture git information for code versioning."""
        try:
            # Get git commit hash
            result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                capture_output=True,
                text=True,
                timeout=2,
                check=False,
            )
            if result.returncode == 0:
                self.execution_context.git_commit_hash = result.stdout.strip()

            # Get git branch
            result = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                capture_output=True,
                text=True,
                timeout=2,
                check=False,
            )
            if result.returncode == 0:
                self.execution_context.git_branch = result.stdout.strip()

            # Check if working directory is dirty
            result_dirty = subprocess.run(
                ["git", "diff-index", "--quiet", "HEAD", "--"],
                timeout=2,
                check=False,
            )
            self.execution_context.git_is_dirty = result_dirty.returncode != 0

        except Exception as e:
            logger.debug(f"Could not capture git info: {e}")

    def set_dataset_metadata(
        self,
        source_type: str,
        source_path: Optional[str] = None,
        num_records: Optional[int] = None,
        start_index: int = 0,
        dataset_version: Optional[str] = None,
        dataset_hash: Optional[str] = None,
    ):
        """Set dataset metadata."""
        if not self._enabled:
            return

        with self._lock:
            self.dataset_metadata.source_type = source_type
            self.dataset_metadata.source_path = source_path
            if num_records is not None:
                self.dataset_metadata.num_records_processed = num_records
            self.dataset_metadata.start_index = start_index
            self.dataset_metadata.dataset_version = dataset_version
            self.dataset_metadata.dataset_hash = dataset_hash

    def record_model_request(
        self,
        model_name: str,
        node_name: Optional[str] = None,
        latency: float = 0.0,
        response_code: int = 200,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        total_tokens: int = 0,
        is_retry: bool = False,
        model_config: Optional[dict[str, Any]] = None,
        cost_usd: float = 0.0,
    ):
        """
        Record a model request with comprehensive metrics.

        Args:
            model_name: Name of the model used
            node_name: Name of the node making the request
            latency: Request latency in seconds
            response_code: HTTP response code
            prompt_tokens: Number of prompt tokens
            completion_tokens: Number of completion tokens
            total_tokens: Total number of tokens
            is_retry: Whether this was a retry attempt
            model_config: Model configuration dict
            cost_usd: Cost of the request in USD
        """
        if not self._enabled:
            return

        with self._lock:
            # Initialize model metrics if needed
            if model_name not in self.model_metrics:
                model_type = "unknown"
                model_url = None
                parameters = {}

                if model_config:
                    model_type = model_config.get("type", "unknown")
                    model_url = model_config.get("url")
                    parameters = model_config.get("parameters", {})

                self.model_metrics[model_name] = ModelMetrics(
                    model_name=model_name,
                    model_type=model_type,
                    model_url=model_url,
                    parameters=parameters,
                )

            # Record the request
            self.model_metrics[model_name].add_request(
                latency=latency,
                response_code=response_code,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total_tokens,
                is_retry=is_retry,
                cost_usd=cost_usd,
            )

            logger.debug(
                f"Recorded model request: {model_name} (node: {node_name}, "
                f"tokens: {total_tokens}, latency: {latency:.3f}s, cost: ${cost_usd:.6f}, code: {response_code})"
            )

    def record_node_execution(
        self,
        node_name: str,
        node_type: str,
        latency: float,
        success: bool,
        model_name: Optional[str] = None,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        total_tokens: int = 0,
        cost_usd: float = 0.0,
    ):
        """Record a node execution with optional token usage and cost."""
        if not self._enabled:
            return

        with self._lock:
            if node_name not in self.node_metrics:
                self.node_metrics[node_name] = NodeMetrics(
                    node_name=node_name,
                    node_type=node_type,
                    model_name=model_name,
                )

            self.node_metrics[node_name].record_execution(
                latency, success, prompt_tokens, completion_tokens, total_tokens, cost_usd
            )

    def record_processed_record(self, success: bool = True):
        """Record that a record was processed."""
        if not self._enabled:
            return

        with self._lock:
            self.total_records_processed += 1
            if not success:
                self.total_records_failed += 1

    def finalize_execution(self):
        """Finalize the execution and compute final statistics."""
        if not self._enabled:
            return

        with self._lock:
            self.execution_context.end_time = datetime.now()
            if self.execution_context.start_time:
                duration = self.execution_context.end_time - self.execution_context.start_time
                self.execution_context.duration_seconds = duration.total_seconds()

            logger.info("Execution finalized")

    def get_metadata_summary(self) -> dict[str, Any]:
        """
        Get a comprehensive summary of all collected metadata.

        Returns:
            Dictionary containing all metadata organized by category
        """
        with self._lock:
            # Aggregate token statistics across all models
            total_prompt_tokens = sum(
                m.token_stats.total_prompt_tokens for m in self.model_metrics.values()
            )
            total_completion_tokens = sum(
                m.token_stats.total_completion_tokens for m in self.model_metrics.values()
            )
            total_tokens = sum(m.token_stats.total_tokens for m in self.model_metrics.values())

            # Aggregate performance statistics
            total_requests = sum(m.num_requests for m in self.model_metrics.values())
            total_retries = sum(m.num_retries for m in self.model_metrics.values())
            total_failures = sum(m.num_failures for m in self.model_metrics.values())

            # Aggregate cost statistics
            total_cost = sum(m.total_cost_usd for m in self.model_metrics.values())

            return {
                "metadata_version": "1.0.0",
                "generated_at": datetime.now().isoformat(),
                "execution": self.execution_context.to_dict(),
                "dataset": self.dataset_metadata.to_dict(),
                "aggregate_statistics": {
                    "records": {
                        "total_processed": self.total_records_processed,
                        "total_failed": self.total_records_failed,
                        "success_rate": (
                            (self.total_records_processed - self.total_records_failed)
                            / self.total_records_processed
                            if self.total_records_processed > 0
                            else 0.0
                        ),
                    },
                    "tokens": {
                        "total_prompt_tokens": total_prompt_tokens,
                        "total_completion_tokens": total_completion_tokens,
                        "total_tokens": total_tokens,
                    },
                    "requests": {
                        "total_requests": total_requests,
                        "total_retries": total_retries,
                        "total_failures": total_failures,
                        "retry_rate": total_retries / total_requests if total_requests > 0 else 0.0,
                        "failure_rate": (
                            total_failures / total_requests if total_requests > 0 else 0.0
                        ),
                    },
                    "cost": {
                        "total_cost_usd": round(total_cost, 6),
                        "average_cost_per_record": round(
                            (
                                total_cost / self.total_records_processed
                                if self.total_records_processed > 0
                                else 0.0
                            ),
                            6,
                        ),
                    },
                },
                "models": {name: metrics.to_dict() for name, metrics in self.model_metrics.items()},
                "nodes": {name: metrics.to_dict() for name, metrics in self.node_metrics.items()},
            }

    def save_metadata(self, output_path: Optional[Union[str, Path]] = None):
        """
        Save metadata to a JSON file.

        Args:
            output_path: Path where to save the metadata. If None, will save to
                        a 'metadata' subdirectory in the output directory.

        Returns:
            Path to saved metadata file, or None if metadata collection is disabled
        """
        if not self._enabled:
            logger.debug("Metadata collection is disabled, skipping save")
            return None

        # Finalize before saving
        if self.execution_context.end_time is None:
            self.finalize_execution()

        # Determine output path
        if output_path is None:
            # Determine base output directory
            if self.execution_context.output_dir:
                # Explicit output directory provided
                base_output_dir = Path(self.execution_context.output_dir)
            else:
                from sygra.utils import utils

                task_name = self.execution_context.task_name
                task_dir = utils._normalize_task_path(task_name)
                base_output_dir = Path(task_dir)

            # Create metadata subdirectory
            metadata_dir = base_output_dir / "metadata"
            metadata_dir.mkdir(parents=True, exist_ok=True)

            if self.execution_context.run_timestamp:
                timestamp = self.execution_context.run_timestamp
            else:
                # Fallback to current time if run_timestamp not set
                timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

            task_name_safe = self.execution_context.task_name.replace("/", "_").replace(".", "_")
            filename = f"metadata_{task_name_safe}_{timestamp}.json"
            output_path = metadata_dir / filename
        else:
            output_path = Path(output_path)
            # Ensure directory exists
            output_path.parent.mkdir(parents=True, exist_ok=True)

        # Get metadata and save
        metadata = self.get_metadata_summary()

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)

        logger.info(f"Metadata saved to: {output_path}")
        return output_path


# Global singleton instance
_metadata_collector = None


def get_metadata_collector() -> MetadataCollector:
    """Get the global metadata collector instance."""
    global _metadata_collector
    if _metadata_collector is None:
        _metadata_collector = MetadataCollector()
    return _metadata_collector


# Convenience functions for common operations


def record_model_usage(
    model_name: str,
    response_obj: Any,
    latency: float,
    response_code: int = 200,
    node_name: Optional[str] = None,
    is_retry: bool = False,
    model_config: Optional[dict[str, Any]] = None,
):
    """
    Record model usage from a response object.

    This function extracts token information from OpenAI-compatible response objects
    and records them in the metadata collector.

    Args:
        model_name: Name of the model
        response_obj: The response object from the model (OpenAI format)
        latency: Request latency in seconds
        response_code: HTTP response code
        node_name: Name of the node making the request
        is_retry: Whether this was a retry
        model_config: Model configuration
    """
    collector = get_metadata_collector()

    # Extract token usage from response
    prompt_tokens = 0
    completion_tokens = 0
    total_tokens = 0

    try:
        # Try to extract usage from OpenAI-compatible response
        if hasattr(response_obj, "usage"):
            usage = response_obj.usage
            if hasattr(usage, "prompt_tokens"):
                prompt_tokens = usage.prompt_tokens
            if hasattr(usage, "completion_tokens"):
                completion_tokens = usage.completion_tokens
            if hasattr(usage, "total_tokens"):
                total_tokens = usage.total_tokens
        # Handle dict-like responses
        elif isinstance(response_obj, dict) and "usage" in response_obj:
            usage = response_obj["usage"]
            prompt_tokens = usage.get("prompt_tokens", 0)
            completion_tokens = usage.get("completion_tokens", 0)
            total_tokens = usage.get("total_tokens", 0)
    except Exception as e:
        logger.debug(f"Could not extract token usage from response: {e}")

    collector.record_model_request(
        model_name=model_name,
        node_name=node_name,
        latency=latency,
        response_code=response_code,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
        is_retry=is_retry,
        model_config=model_config,
    )
