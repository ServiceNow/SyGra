"""
Comprehensive unit tests for MetadataCollector.

Tests cover:
- Token statistics tracking
- Model metrics recording
- Node metrics recording
- Cost calculation
- Execution context management
- Dataset metadata
- Thread safety
- JSON export
"""

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from sygra.metadata.metadata_collector import (
    ModelMetrics,
    NodeMetrics,
    TokenStatistics,
    get_metadata_collector,
)


class TestTokenStatistics:
    """Test suite for TokenStatistics class."""

    def test_initialization(self):
        """Test TokenStatistics initialization with default values."""
        stats = TokenStatistics()
        assert stats.total_prompt_tokens == 0
        assert stats.total_completion_tokens == 0
        assert stats.total_tokens == 0
        assert stats.num_requests_with_tokens == 0

    def test_add_usage(self):
        """Test adding token usage."""
        stats = TokenStatistics()
        stats.add_usage(prompt_tokens=100, completion_tokens=50, total_tokens=150)

        assert stats.total_prompt_tokens == 100
        assert stats.total_completion_tokens == 50
        assert stats.total_tokens == 150
        assert stats.num_requests_with_tokens == 1

    def test_add_usage_multiple_requests(self):
        """Test adding token usage from multiple requests."""
        stats = TokenStatistics()
        stats.add_usage(100, 50, 150)
        stats.add_usage(200, 100, 300)

        assert stats.total_prompt_tokens == 300
        assert stats.total_completion_tokens == 150
        assert stats.total_tokens == 450
        assert stats.num_requests_with_tokens == 2

    def test_add_usage_with_zeros(self):
        """Test that zero token requests don't increment counter."""
        stats = TokenStatistics()
        stats.add_usage(0, 0, 0)

        assert stats.total_prompt_tokens == 0
        assert stats.num_requests_with_tokens == 0

    def test_add_usage_with_none_values(self):
        """Test handling None values in token counts."""
        stats = TokenStatistics()
        stats.add_usage(prompt_tokens=None, completion_tokens=None, total_tokens=None)

        assert stats.total_prompt_tokens == 0
        assert stats.num_requests_with_tokens == 0

    def test_get_average_tokens_no_requests(self):
        """Test average calculation with no requests."""
        stats = TokenStatistics()
        averages = stats.get_average_tokens()

        assert averages["avg_prompt_tokens"] == 0.0
        assert averages["avg_completion_tokens"] == 0.0
        assert averages["avg_total_tokens"] == 0.0

    def test_get_average_tokens_with_requests(self):
        """Test average calculation with multiple requests."""
        stats = TokenStatistics()
        stats.add_usage(100, 50, 150)
        stats.add_usage(200, 100, 300)

        averages = stats.get_average_tokens()

        assert averages["avg_prompt_tokens"] == 150.0
        assert averages["avg_completion_tokens"] == 75.0
        assert averages["avg_total_tokens"] == 225.0


class TestModelMetrics:
    """Test suite for ModelMetrics class."""

    def test_initialization(self):
        """Test ModelMetrics initialization."""
        metrics = ModelMetrics(model_name="gpt-4o", model_type="OpenAI")

        assert metrics.model_name == "gpt-4o"
        assert metrics.model_type == "OpenAI"
        assert metrics.num_requests == 0
        assert metrics.total_cost_usd == 0.0

    def test_add_request_success(self):
        """Test adding a successful request."""
        metrics = ModelMetrics(model_name="gpt-4o")
        metrics.add_request(
            latency=1.5,
            response_code=200,
            prompt_tokens=100,
            completion_tokens=50,
            total_tokens=150,
            cost_usd=0.001,
        )

        assert metrics.num_requests == 1
        assert metrics.total_latency_seconds == 1.5
        assert metrics.response_codes[200] == 1
        assert metrics.num_failures == 0
        assert metrics.total_cost_usd == 0.001
        assert metrics.token_stats.total_prompt_tokens == 100

    def test_add_request_failure(self):
        """Test adding a failed request."""
        metrics = ModelMetrics(model_name="gpt-4o")
        metrics.add_request(latency=0.5, response_code=500)

        assert metrics.num_requests == 1
        assert metrics.num_failures == 1
        assert metrics.response_codes[500] == 1

    def test_add_request_retry(self):
        """Test adding a retry request."""
        metrics = ModelMetrics(model_name="gpt-4o")
        metrics.add_request(latency=1.0, response_code=429, is_retry=True)

        assert metrics.num_requests == 1
        assert metrics.num_retries == 1
        assert metrics.num_failures == 1

    def test_multiple_requests(self):
        """Test adding multiple requests."""
        metrics = ModelMetrics(model_name="gpt-4o")
        metrics.add_request(1.0, 200, 100, 50, 150, cost_usd=0.001)
        metrics.add_request(2.0, 200, 200, 100, 300, cost_usd=0.002)
        metrics.add_request(0.5, 500)

        assert metrics.num_requests == 3
        assert metrics.num_failures == 1
        assert metrics.total_latency_seconds == 3.5
        assert metrics.total_cost_usd == 0.003
        assert metrics.token_stats.total_tokens == 450

    def test_get_performance_metrics(self):
        """Test performance metrics calculation."""
        metrics = ModelMetrics(model_name="gpt-4o")
        metrics.add_request(1.0, 200, 100, 50, 150)
        metrics.add_request(2.0, 200, 200, 100, 300)

        perf = metrics.to_dict()["performance"]

        assert perf["total_requests"] == 2
        assert perf["average_latency_seconds"] == 1.5
        # tokens_per_second = total_completion_tokens / successful_request_latency
        # = 150 / 3.0 = 50.0
        assert perf["tokens_per_second"] == 50.0
        assert perf["failure_rate"] == 0.0

    def test_get_performance_metrics_with_failures(self):
        """Test performance metrics with failures."""
        metrics = ModelMetrics(model_name="gpt-4o")
        metrics.add_request(1.0, 200)
        metrics.add_request(1.0, 500)

        perf = metrics.to_dict()["performance"]

        assert perf["total_failures"] == 1
        assert perf["failure_rate"] == 0.5


class TestNodeMetrics:
    """Test suite for NodeMetrics class."""

    def test_initialization(self):
        """Test NodeMetrics initialization."""
        metrics = NodeMetrics(node_name="summarizer", node_type="llm")

        assert metrics.node_name == "summarizer"
        assert metrics.node_type == "llm"
        assert metrics.total_executions == 0
        assert metrics.total_failures == 0

    def test_add_execution_success(self):
        """Test adding successful execution."""
        metrics = NodeMetrics(node_name="summarizer", node_type="llm")
        metrics.record_execution(
            latency=1.5,
            success=True,
            prompt_tokens=100,
            completion_tokens=50,
            total_tokens=150,
        )

        assert metrics.total_executions == 1
        assert metrics.total_failures == 0
        assert metrics.total_latency_seconds == 1.5
        assert metrics.token_stats.total_tokens == 150

    def test_add_execution_failure(self):
        """Test adding failed execution."""
        metrics = NodeMetrics(node_name="summarizer", node_type="llm")
        metrics.record_execution(latency=0.5, success=False)

        assert metrics.total_executions == 1
        assert metrics.total_failures == 1

    def test_multiple_executions(self):
        """Test multiple executions."""
        metrics = NodeMetrics(node_name="summarizer", node_type="llm")
        metrics.record_execution(1.0, True, 100, 50, 150)
        metrics.record_execution(2.0, True, 200, 100, 300)
        metrics.record_execution(0.5, False)

        assert metrics.total_executions == 3
        assert metrics.total_failures == 1
        assert metrics.total_latency_seconds == 3.5

    def test_get_metrics(self):
        """Test metrics dictionary generation."""
        metrics = NodeMetrics(node_name="summarizer", node_type="llm", model_name="gpt-4o")
        metrics.record_execution(1.0, True, 100, 50, 150)
        metrics.record_execution(2.0, True, 200, 100, 300)

        result = metrics.to_dict()

        assert result["node_name"] == "summarizer"
        assert result["node_type"] == "llm"
        assert result["model_name"] == "gpt-4o"
        assert result["total_executions"] == 2
        assert result["average_latency_seconds"] == 1.5
        assert result["failure_rate"] == 0.0


class TestMetadataCollector:
    """Test suite for MetadataCollector class."""

    def setup_method(self):
        """Reset metadata collector before each test."""
        collector = get_metadata_collector()
        collector.reset()
        collector.set_enabled(True)

    def test_singleton_pattern(self):
        """Test that get_metadata_collector returns same instance."""
        collector1 = get_metadata_collector()
        collector2 = get_metadata_collector()

        assert collector1 is collector2

    def test_initialization(self):
        """Test MetadataCollector initialization."""
        collector = get_metadata_collector()

        assert collector.is_enabled() is True
        assert len(collector.model_metrics) == 0
        assert len(collector.node_metrics) == 0
        assert collector.total_records_processed == 0

    def test_set_execution_context(self):
        """Test setting execution context."""
        collector = get_metadata_collector()
        collector.set_execution_context(
            task_name="test_task",
            run_name="test_run",
            output_dir="/tmp/output",
            batch_size=10,
        )

        assert collector.execution_context.task_name == "test_task"
        assert collector.execution_context.run_name == "test_run"
        assert collector.execution_context.output_dir == "/tmp/output"
        assert collector.execution_context.batch_size == 10
        assert collector.execution_context.start_time is not None

    def test_set_dataset_metadata(self):
        """Test setting dataset metadata."""
        collector = get_metadata_collector()
        collector.set_dataset_metadata(
            source_type="hf",
            source_path="test/dataset",
            num_records=100,
            start_index=0,
        )

        assert collector.dataset_metadata.source_type == "hf"
        assert collector.dataset_metadata.source_path == "test/dataset"
        assert collector.dataset_metadata.num_records_processed == 100

    def test_record_model_request(self):
        """Test recording model request."""
        collector = get_metadata_collector()
        collector.record_model_request(
            model_name="gpt-4o",
            latency=1.5,
            response_code=200,
            prompt_tokens=100,
            completion_tokens=50,
            total_tokens=150,
            cost_usd=0.001,
        )

        assert "gpt-4o" in collector.model_metrics
        assert collector.model_metrics["gpt-4o"].num_requests == 1
        assert collector.model_metrics["gpt-4o"].total_cost_usd == 0.001

    def test_record_model_request_with_config(self):
        """Test recording model request with configuration."""
        collector = get_metadata_collector()
        model_config = {
            "type": "OpenAI",
            "parameters": {"temperature": 0.7, "max_tokens": 100},
        }

        collector.record_model_request(
            model_name="gpt-4o",
            latency=1.0,
            response_code=200,
            model_config=model_config,
        )

        metrics = collector.model_metrics["gpt-4o"]
        assert metrics.model_type == "OpenAI"
        assert metrics.parameters["temperature"] == 0.7

    def test_record_node_execution(self):
        """Test recording node execution."""
        collector = get_metadata_collector()
        collector.record_node_execution(
            node_name="summarizer",
            node_type="llm",
            latency=1.5,
            success=True,
            model_name="gpt-4o",
            prompt_tokens=100,
            completion_tokens=50,
            total_tokens=150,
        )

        assert "summarizer" in collector.node_metrics
        assert collector.node_metrics["summarizer"].total_executions == 1
        assert collector.node_metrics["summarizer"].model_name == "gpt-4o"

    def test_record_processed_record(self):
        """Test recording processed records."""
        collector = get_metadata_collector()
        collector.record_processed_record(success=True)
        collector.record_processed_record(success=True)
        collector.record_processed_record(success=False)

        assert collector.total_records_processed == 3
        assert collector.total_records_failed == 1

    def test_finalize_execution(self):
        """Test finalizing execution."""
        collector = get_metadata_collector()
        collector.set_execution_context(task_name="test")
        collector.finalize_execution()

        assert collector.execution_context.end_time is not None
        assert collector.execution_context.duration_seconds is not None
        assert collector.execution_context.duration_seconds > 0

    def test_get_aggregate_statistics(self):
        """Test aggregate statistics calculation."""
        collector = get_metadata_collector()

        # Add some data
        collector.record_model_request(
            "gpt-4o",
            latency=1.0,
            response_code=200,
            prompt_tokens=100,
            completion_tokens=50,
            total_tokens=150,
            cost_usd=0.001,
        )
        collector.record_model_request(
            "gpt-4o",
            latency=1.0,
            response_code=200,
            prompt_tokens=100,
            completion_tokens=50,
            total_tokens=150,
            cost_usd=0.001,
        )
        collector.record_processed_record(success=True)
        collector.record_processed_record(success=True)

        summary = collector.get_metadata_summary()
        stats = summary["aggregate_statistics"]

        assert stats["records"]["total_processed"] == 2
        assert stats["records"]["success_rate"] == 1.0
        # Total tokens across all models
        assert stats["tokens"]["total_tokens"] == 300
        assert stats["requests"]["total_requests"] == 2
        # Cost should be rounded to 6 decimals
        assert abs(stats["cost"]["total_cost_usd"] - 0.002) < 0.000001

    def test_get_metadata_summary(self):
        """Test full metadata summary generation."""
        collector = get_metadata_collector()
        collector.set_execution_context(task_name="test_task")
        collector.record_model_request(
            "gpt-4o",
            latency=1.0,
            response_code=200,
            prompt_tokens=100,
            completion_tokens=50,
            total_tokens=150,
        )
        collector.record_node_execution("summarizer", "llm", 1.0, True)

        summary = collector.get_metadata_summary()

        assert "metadata_version" in summary
        assert "execution" in summary
        assert "models" in summary
        assert "nodes" in summary
        assert "aggregate_statistics" in summary
        assert "gpt-4o" in summary["models"]
        assert "summarizer" in summary["nodes"]

    def test_save_metadata_to_file(self):
        """Test saving metadata to JSON file."""
        collector = get_metadata_collector()
        collector.set_execution_context(task_name="test_task")
        collector.record_model_request("gpt-4o", latency=1.0, response_code=200)
        collector.finalize_execution()

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "metadata.json"
            filepath = collector.save_metadata(output_path=output_path)

            assert filepath is not None
            assert Path(filepath).exists()

            # Verify JSON content
            with open(filepath) as f:
                data = json.load(f)
                assert data["execution"]["task_name"] == "test_task"
                assert "gpt-4o" in data["models"]

    def test_reset(self):
        """Test resetting collector state."""
        collector = get_metadata_collector()
        collector.record_model_request("gpt-4o", latency=1.0, response_code=200)
        collector.record_node_execution("summarizer", "llm", 1.0, True)

        assert len(collector.model_metrics) > 0
        assert len(collector.node_metrics) > 0

        collector.reset()

        assert len(collector.model_metrics) == 0
        assert len(collector.node_metrics) == 0
        assert collector.total_records_processed == 0

    def test_cost_accumulation(self):
        """Test that costs accumulate correctly."""
        collector = get_metadata_collector()
        collector.record_model_request("gpt-4o", latency=1.0, response_code=200, cost_usd=0.001)
        collector.record_model_request("gpt-4o", latency=1.0, response_code=200, cost_usd=0.002)
        collector.record_model_request("claude-3", latency=1.0, response_code=200, cost_usd=0.003)

        # Check per-model costs
        assert collector.model_metrics["gpt-4o"].total_cost_usd == 0.003
        assert collector.model_metrics["claude-3"].total_cost_usd == 0.003

        # Check aggregate cost
        summary = collector.get_metadata_summary()
        assert summary["aggregate_statistics"]["cost"]["total_cost_usd"] == 0.006

    def test_multiple_models(self):
        """Test tracking multiple models."""
        collector = get_metadata_collector()
        collector.record_model_request(
            "gpt-4o",
            latency=1.0,
            response_code=200,
            prompt_tokens=100,
            completion_tokens=50,
            total_tokens=150,
        )
        collector.record_model_request(
            "claude-3",
            latency=2.0,
            response_code=200,
            prompt_tokens=200,
            completion_tokens=100,
            total_tokens=300,
        )

        assert len(collector.model_metrics) == 2
        assert "gpt-4o" in collector.model_metrics
        assert "claude-3" in collector.model_metrics

        # Check total requests across all models
        summary = collector.get_metadata_summary()
        assert summary["aggregate_statistics"]["requests"]["total_requests"] == 2

    def test_multiple_nodes(self):
        """Test tracking multiple nodes."""
        collector = get_metadata_collector()
        collector.record_node_execution("summarizer", "llm", 1.0, True)
        collector.record_node_execution("reviewer", "agent", 2.0, True)

        assert len(collector.node_metrics) == 2
        assert "summarizer" in collector.node_metrics
        assert "reviewer" in collector.node_metrics

    def test_failure_tracking(self):
        """Test failure tracking across models and nodes."""
        collector = get_metadata_collector()

        # Model requests - only non-200 are failures
        collector.record_model_request("gpt-4o", latency=1.0, response_code=200)  # Success
        collector.record_model_request("gpt-4o", latency=1.0, response_code=500)  # Failure
        collector.record_model_request(
            "gpt-4o", latency=1.0, response_code=429, is_retry=True
        )  # Failure + retry

        # Node failures
        collector.record_node_execution("summarizer", "llm", 1.0, True)
        collector.record_node_execution("summarizer", "llm", 1.0, False)

        # Check model failures: 500 and 429 are failures (response_code != 200)
        assert collector.model_metrics["gpt-4o"].num_failures == 2
        assert collector.model_metrics["gpt-4o"].num_retries == 1
        assert collector.node_metrics["summarizer"].total_failures == 1

    @patch("sygra.metadata.metadata_collector.subprocess.run")
    def test_git_info_capture(self, mock_run):
        """Test capturing git information."""
        # Mock git commands
        mock_run.side_effect = [
            MagicMock(stdout="abc123\n", returncode=0),  # commit hash
            MagicMock(stdout="main\n", returncode=0),  # branch
            MagicMock(stdout="", returncode=0),  # status (clean)
        ]

        collector = get_metadata_collector()
        # Trigger git info capture by setting execution context
        collector.set_execution_context(task_name="test")

        # Check git info in execution context
        assert collector.execution_context.git_commit_hash == "abc123"
        assert collector.execution_context.git_branch == "main"
        assert collector.execution_context.git_is_dirty is False

    def test_environment_info_capture(self):
        """Test capturing environment information."""
        collector = get_metadata_collector()
        # Trigger environment info capture by setting execution context
        collector.set_execution_context(task_name="test")

        # Check environment info in execution context
        assert collector.execution_context.python_version is not None
        assert collector.execution_context.sygra_version is not None
        assert len(collector.execution_context.python_version) > 0


class TestMetadataCollectorThreadSafety:
    """Test thread safety of MetadataCollector."""

    def setup_method(self):
        """Reset metadata collector before each test."""
        collector = get_metadata_collector()
        collector.reset()
        collector.set_enabled(True)

    def test_concurrent_model_requests(self):
        """Test concurrent model request recording."""
        import threading

        collector = get_metadata_collector()
        num_threads = 10
        requests_per_thread = 100

        def record_requests():
            for _ in range(requests_per_thread):
                collector.record_model_request(
                    "gpt-4o",
                    latency=1.0,
                    response_code=200,
                    prompt_tokens=100,
                    completion_tokens=50,
                    total_tokens=150,
                )

        threads = [threading.Thread(target=record_requests) for _ in range(num_threads)]

        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        # Should have recorded all requests
        expected_total = num_threads * requests_per_thread
        assert collector.model_metrics["gpt-4o"].num_requests == expected_total

        # Check aggregate total
        summary = collector.get_metadata_summary()
        assert summary["aggregate_statistics"]["requests"]["total_requests"] == expected_total

    def test_concurrent_node_executions(self):
        """Test concurrent node execution recording."""
        import threading

        collector = get_metadata_collector()
        num_threads = 10
        executions_per_thread = 100

        def record_executions():
            for _ in range(executions_per_thread):
                collector.record_node_execution("summarizer", "llm", 1.0, True)

        threads = [threading.Thread(target=record_executions) for _ in range(num_threads)]

        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        expected_total = num_threads * executions_per_thread
        assert collector.node_metrics["summarizer"].total_executions == expected_total


class TestMetadataCollectorDisabled:
    """Test MetadataCollector when disabled."""

    def setup_method(self):
        """Reset and disable metadata collector."""
        collector = get_metadata_collector()
        collector.reset()
        collector.set_enabled(False)

    def test_record_model_request_when_disabled(self):
        """Test that recording does nothing when disabled."""
        collector = get_metadata_collector()
        collector.record_model_request(
            "gpt-4o",
            latency=1.0,
            response_code=200,
            prompt_tokens=100,
            completion_tokens=50,
            total_tokens=150,
        )

        assert len(collector.model_metrics) == 0

    def test_record_node_execution_when_disabled(self):
        """Test that node recording does nothing when disabled."""
        collector = get_metadata_collector()
        collector.record_node_execution("summarizer", "llm", 1.0, True)

        assert len(collector.node_metrics) == 0

    def test_save_metadata_when_disabled(self):
        """Test that save returns None when disabled."""
        collector = get_metadata_collector()
        result = collector.save_metadata()

        assert result is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
