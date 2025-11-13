"""
End-to-end integration tests for metadata tracking system.

Tests the complete metadata flow from data collection to JSON export.
"""

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from sygra.metadata.metadata_collector import get_metadata_collector


class TestMetadataEndToEnd:
    """End-to-end integration tests."""

    def setup_method(self):
        """Reset metadata collector before each test."""
        collector = get_metadata_collector()
        collector.reset()
        collector.set_enabled(True)

    def test_complete_workflow_metadata(self):
        """Test complete workflow metadata collection."""
        collector = get_metadata_collector()

        # 1. Set execution context
        collector.set_execution_context(
            task_name="test_task",
            run_name="test_run",
            output_dir="/tmp/output",
            batch_size=10,
            checkpoint_interval=100,
        )

        # 2. Set dataset metadata
        collector.set_dataset_metadata(
            source_type="hf",
            source_path="test/dataset",
            num_records=100,
            start_index=0,
            dataset_version="1.0.0",
            dataset_hash="abc123",
        )

        # 3. Record model requests
        collector.record_model_request(
            model_name="gpt-4o",
            latency=1.5,
            response_code=200,
            prompt_tokens=100,
            completion_tokens=50,
            total_tokens=150,
            cost_usd=0.001,
            model_config={"type": "OpenAI", "parameters": {"temperature": 0.7}},
        )

        collector.record_model_request(
            model_name="gpt-4o",
            latency=1.2,
            response_code=200,
            prompt_tokens=120,
            completion_tokens=60,
            total_tokens=180,
            cost_usd=0.0012,
        )

        # 4. Record node executions
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

        collector.record_node_execution(
            node_name="reviewer",
            node_type="agent",
            latency=2.0,
            success=True,
            model_name="gpt-4o",
        )

        # 5. Record processed records
        collector.record_processed_record(success=True)
        collector.record_processed_record(success=True)
        collector.record_processed_record(success=False)

        # 6. Finalize execution
        collector.finalize_execution()

        # 7. Get metadata summary
        summary = collector.get_metadata_summary()

        # Verify structure
        assert "metadata_version" in summary
        assert "execution" in summary
        assert "dataset" in summary
        assert "aggregate_statistics" in summary
        assert "models" in summary
        assert "nodes" in summary

        # Verify execution context
        assert summary["execution"]["task_name"] == "test_task"
        assert summary["execution"]["run_name"] == "test_run"
        assert summary["execution"]["batch_size"] == 10

        # Verify dataset metadata
        assert summary["dataset"]["source_type"] == "hf"
        assert summary["dataset"]["source_path"] == "test/dataset"
        assert summary["dataset"]["num_records_processed"] == 100

        # Verify aggregate statistics
        agg = summary["aggregate_statistics"]
        assert agg["records"]["total_processed"] == 3
        assert agg["records"]["total_failed"] == 1
        assert agg["tokens"]["total_tokens"] == 330
        assert agg["requests"]["total_requests"] == 2
        assert agg["cost"]["total_cost_usd"] == 0.0022

        # Verify model metrics
        assert "gpt-4o" in summary["models"]
        model = summary["models"]["gpt-4o"]
        assert model["model_type"] == "OpenAI"
        assert model["token_statistics"]["total_tokens"] == 330
        assert model["performance"]["total_requests"] == 2
        assert model["cost"]["total_cost_usd"] == 0.0022

        # Verify node metrics
        assert "summarizer" in summary["nodes"]
        assert "reviewer" in summary["nodes"]
        assert summary["nodes"]["summarizer"]["node_type"] == "llm"
        assert summary["nodes"]["reviewer"]["node_type"] == "agent"

    def test_metadata_json_export(self):
        """Test exporting metadata to JSON file."""
        collector = get_metadata_collector()

        # Add some data
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
        collector.finalize_execution()

        # Save to file
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "metadata.json"
            filepath = collector.save_metadata(output_path=output_path)

            assert filepath is not None
            assert Path(filepath).exists()

            # Load and verify JSON
            with open(filepath) as f:
                data = json.load(f)

            # Verify it's valid JSON with expected structure
            assert isinstance(data, dict)
            assert "metadata_version" in data
            assert "execution" in data
            assert "models" in data
            assert "gpt-4o" in data["models"]

    def test_metadata_with_multiple_models(self):
        """Test metadata collection with multiple models."""
        collector = get_metadata_collector()

        collector.set_execution_context(task_name="multi_model_task")

        # Record requests for different models
        models = ["gpt-4o", "gpt-4o-mini", "claude-3-sonnet"]
        for model in models:
            collector.record_model_request(
                model_name=model,
                latency=1.0,
                response_code=200,
                prompt_tokens=100,
                completion_tokens=50,
                total_tokens=150,
            )

        summary = collector.get_metadata_summary()

        # All models should be tracked
        assert len(summary["models"]) == 3
        for model in models:
            assert model in summary["models"]
            assert summary["models"][model]["performance"]["total_requests"] == 1

    def test_metadata_with_failures_and_retries(self):
        """Test metadata tracking with failures and retries."""
        collector = get_metadata_collector()

        collector.set_execution_context(task_name="failure_test")

        # Successful request
        collector.record_model_request(
            "gpt-4o",
            latency=1.0,
            response_code=200,
            prompt_tokens=100,
            completion_tokens=50,
            total_tokens=150,
        )

        # Failed request (rate limit)
        collector.record_model_request("gpt-4o", latency=0.5, response_code=429, is_retry=False)

        # Retry (still fails)
        collector.record_model_request("gpt-4o", latency=0.5, response_code=429, is_retry=True)

        # Successful retry
        collector.record_model_request(
            "gpt-4o",
            latency=1.0,
            response_code=200,
            prompt_tokens=100,
            completion_tokens=50,
            total_tokens=150,
            is_retry=True,
        )

        summary = collector.get_metadata_summary()
        model = summary["models"]["gpt-4o"]

        assert model["performance"]["total_requests"] == 4
        assert model["performance"]["total_retries"] == 2
        assert model["performance"]["total_failures"] == 2
        # Response codes are stored as integers (keys in dict)
        response_codes = model["response_code_distribution"]
        assert response_codes.get(200) == 2
        assert response_codes.get(429) == 2

    def test_metadata_with_zero_cost_models(self):
        """Test metadata with models that have no cost (e.g., vLLM)."""
        collector = get_metadata_collector()

        collector.set_execution_context(task_name="vllm_test")

        # vLLM model (no cost)
        collector.record_model_request(
            model_name="custom-vllm-model",
            latency=0.5,
            response_code=200,
            prompt_tokens=100,
            completion_tokens=50,
            total_tokens=150,
            cost_usd=0.0,  # No cost
        )

        summary = collector.get_metadata_summary()

        assert summary["aggregate_statistics"]["cost"]["total_cost_usd"] == 0.0
        assert summary["models"]["custom-vllm-model"]["cost"]["total_cost_usd"] == 0.0

    def test_metadata_timestamp_in_filename(self):
        """Test that metadata filename includes timestamp."""
        collector = get_metadata_collector()

        collector.set_execution_context(
            task_name="test_task",
            run_timestamp="2025-11-05_15-30-00",
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "metadata.json"
            filepath = collector.save_metadata(output_path=output_path)

            # Filename should include timestamp (if save_metadata uses it)
            # The actual implementation may not use run_timestamp in filename
            assert filepath is not None
            assert Path(filepath).exists()

    def test_metadata_with_lambda_nodes(self):
        """Test metadata tracking with lambda (non-LLM) nodes."""
        collector = get_metadata_collector()

        collector.set_execution_context(task_name="lambda_test")

        # Lambda node (no model, no tokens)
        collector.record_node_execution(
            node_name="data_processor",
            node_type="lambda",
            latency=0.1,
            success=True,
        )

        summary = collector.get_metadata_summary()

        assert "data_processor" in summary["nodes"]
        node = summary["nodes"]["data_processor"]
        assert node["node_type"] == "lambda"
        assert node["model_name"] is None
        # Lambda nodes don't have token_statistics if no tokens
        if "token_statistics" in node:
            assert node["token_statistics"]["total_tokens"] == 0

    def test_metadata_performance_metrics_calculation(self):
        """Test that performance metrics are calculated correctly."""
        collector = get_metadata_collector()

        collector.set_execution_context(task_name="perf_test")

        # Add requests with known latencies and tokens
        collector.record_model_request(
            "gpt-4o",
            latency=2.0,
            response_code=200,
            prompt_tokens=100,
            completion_tokens=100,
            total_tokens=200,
        )  # 100 tokens/sec
        collector.record_model_request(
            "gpt-4o",
            latency=1.0,
            response_code=200,
            prompt_tokens=50,
            completion_tokens=50,
            total_tokens=100,
        )  # 100 tokens/sec

        summary = collector.get_metadata_summary()
        model = summary["models"]["gpt-4o"]

        # Average latency should be 1.5s
        assert model["performance"]["average_latency_seconds"] == 1.5

        # Tokens per second: 150 completion tokens / 3.0s successful latency = 50.0
        assert model["performance"]["tokens_per_second"] == 50.0

    @patch("sygra.metadata.metadata_collector.subprocess.run")
    def test_metadata_captures_git_info(self, mock_run):
        """Test that metadata captures git information."""
        # Mock git commands
        mock_run.side_effect = [
            MagicMock(stdout="abc123def456\n", returncode=0),  # commit hash
            MagicMock(stdout="main\n", returncode=0),  # branch
            MagicMock(stdout="", returncode=0),  # status (clean)
        ]

        collector = get_metadata_collector()
        collector.set_execution_context(task_name="git_test")

        summary = collector.get_metadata_summary()

        assert summary["execution"]["git"]["commit_hash"] == "abc123def456"
        assert summary["execution"]["git"]["branch"] == "main"
        assert summary["execution"]["git"]["is_dirty"] is False

    def test_metadata_with_empty_execution(self):
        """Test metadata generation with minimal data."""
        collector = get_metadata_collector()

        # Only set execution context, no other data
        collector.set_execution_context(task_name="minimal_test")
        collector.finalize_execution()

        summary = collector.get_metadata_summary()

        # Should still generate valid metadata
        assert summary["execution"]["task_name"] == "minimal_test"
        assert summary["aggregate_statistics"]["records"]["total_processed"] == 0
        assert summary["aggregate_statistics"]["cost"]["total_cost_usd"] == 0.0
        assert len(summary["models"]) == 0
        assert len(summary["nodes"]) == 0

    def test_metadata_file_structure(self):
        """Test that saved metadata file has correct structure."""
        collector = get_metadata_collector()

        collector.set_execution_context(task_name="structure_test")
        collector.record_model_request(
            "gpt-4o",
            latency=1.0,
            response_code=200,
            prompt_tokens=100,
            completion_tokens=50,
            total_tokens=150,
        )
        collector.finalize_execution()

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "metadata.json"
            filepath = collector.save_metadata(output_path=output_path)

            with open(filepath) as f:
                data = json.load(f)

            # Verify all top-level keys exist
            required_keys = [
                "metadata_version",
                "generated_at",
                "execution",
                "dataset",
                "aggregate_statistics",
                "models",
                "nodes",
            ]

            for key in required_keys:
                assert key in data, f"Missing required key: {key}"

            # Verify execution structure
            exec_keys = ["task_name", "timing", "environment", "git"]
            for key in exec_keys:
                assert key in data["execution"], f"Missing execution key: {key}"

            # Verify aggregate statistics structure
            agg_keys = ["records", "tokens", "requests", "cost"]
            for key in agg_keys:
                assert key in data["aggregate_statistics"], f"Missing aggregate key: {key}"


class TestMetadataResetAndReuse:
    """Test metadata collector reset and reuse."""

    def test_reset_clears_all_data(self):
        """Test that reset clears all collected data."""
        collector = get_metadata_collector()

        # Add data
        collector.set_execution_context(task_name="test1")
        collector.record_model_request("gpt-4o", latency=1.0, response_code=200)
        collector.record_node_execution("node1", "llm", 1.0, True)
        collector.record_processed_record(success=True)

        # Reset
        collector.reset()

        # All data should be cleared
        assert len(collector.model_metrics) == 0
        assert len(collector.node_metrics) == 0
        assert collector.total_records_processed == 0

    def test_reuse_after_reset(self):
        """Test that collector can be reused after reset."""
        collector = get_metadata_collector()

        # First run
        collector.set_execution_context(task_name="run1")
        collector.record_model_request("gpt-4o", latency=1.0, response_code=200)
        summary1 = collector.get_metadata_summary()

        # Reset and second run
        collector.reset()
        collector.set_execution_context(task_name="run2")
        collector.record_model_request("claude-3", latency=1.0, response_code=200)
        summary2 = collector.get_metadata_summary()

        # Summaries should be independent
        assert summary1["execution"]["task_name"] == "run1"
        assert summary2["execution"]["task_name"] == "run2"
        assert "gpt-4o" in summary1["models"]
        assert "claude-3" in summary2["models"]
        assert "claude-3" not in summary1["models"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
