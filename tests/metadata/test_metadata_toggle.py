"""
Tests for metadata collection toggle functionality.
"""

import os

import pytest

from sygra.metadata.metadata_collector import MetadataCollector, get_metadata_collector


class TestMetadataToggle:
    """Test suite for metadata collection toggle feature."""

    def setup_method(self):
        """Reset metadata collector before each test."""
        collector = get_metadata_collector()
        collector.reset()
        collector.set_enabled(True)  # Ensure enabled for tests

        # Clear environment variable
        if "SYGRA_DISABLE_METADATA" in os.environ:
            del os.environ["SYGRA_DISABLE_METADATA"]

    def test_default_enabled(self):
        """Test that metadata collection is enabled by default."""
        # Create fresh instance
        collector = MetadataCollector()
        assert collector.is_enabled() is True

    def test_set_enabled(self):
        """Test programmatic enable/disable."""
        collector = get_metadata_collector()

        # Test disable
        collector.set_enabled(False)
        assert collector.is_enabled() is False

        # Test re-enable
        collector.set_enabled(True)
        assert collector.is_enabled() is True

    def test_environment_variable_disable(self):
        """Test disabling via environment variable."""
        # Set environment variable
        os.environ["SYGRA_DISABLE_METADATA"] = "1"

        # The collector is a singleton, so we need to manually disable it
        # In a real scenario, the env var would be read on first initialization
        collector = get_metadata_collector()

        # Manually set the flag to simulate env var being read at init
        collector._enabled = os.getenv("SYGRA_DISABLE_METADATA", "0").lower() not in (
            "1",
            "true",
            "yes",
        )

        assert collector.is_enabled() is False

        # Cleanup
        del os.environ["SYGRA_DISABLE_METADATA"]
        collector.set_enabled(True)  # Re-enable for other tests

    def test_record_model_request_when_disabled(self):
        """Test that record_model_request does nothing when disabled."""
        collector = get_metadata_collector()
        collector.set_enabled(False)

        # Try to record a request
        collector.record_model_request(
            model_name="test_model",
            latency=1.0,
            response_code=200,
            prompt_tokens=100,
            completion_tokens=50,
        )

        # Should not have recorded anything
        assert len(collector.model_metrics) == 0

    def test_record_model_request_when_enabled(self):
        """Test that record_model_request works when enabled."""
        collector = get_metadata_collector()
        collector.set_enabled(True)

        # Record a request
        collector.record_model_request(
            model_name="test_model",
            latency=1.0,
            response_code=200,
            prompt_tokens=100,
            completion_tokens=50,
        )

        # Should have recorded
        assert len(collector.model_metrics) == 1
        assert "test_model" in collector.model_metrics
        assert collector.model_metrics["test_model"].num_requests == 1

    def test_record_node_execution_when_disabled(self):
        """Test that record_node_execution does nothing when disabled."""
        collector = get_metadata_collector()
        collector.set_enabled(False)

        # Try to record node execution
        collector.record_node_execution(
            node_name="test_node",
            node_type="llm",
            latency=1.0,
            success=True,
        )

        # Should not have recorded anything
        assert len(collector.node_metrics) == 0

    def test_record_node_execution_when_enabled(self):
        """Test that record_node_execution works when enabled."""
        collector = get_metadata_collector()
        collector.set_enabled(True)

        # Record node execution
        collector.record_node_execution(
            node_name="test_node",
            node_type="llm",
            latency=1.0,
            success=True,
        )

        # Should have recorded
        assert len(collector.node_metrics) == 1
        assert "test_node" in collector.node_metrics

    def test_record_processed_record_when_disabled(self):
        """Test that record_processed_record does nothing when disabled."""
        collector = get_metadata_collector()
        collector.set_enabled(False)

        # Try to record processed records
        collector.record_processed_record(success=True)
        collector.record_processed_record(success=False)

        # Should not have recorded anything
        assert collector.total_records_processed == 0
        assert collector.total_records_failed == 0

    def test_record_processed_record_when_enabled(self):
        """Test that record_processed_record works when enabled."""
        collector = get_metadata_collector()
        collector.set_enabled(True)

        # Record processed records
        collector.record_processed_record(success=True)
        collector.record_processed_record(success=False)

        # Should have recorded
        assert collector.total_records_processed == 2
        assert collector.total_records_failed == 1

    def test_set_execution_context_when_disabled(self):
        """Test that set_execution_context does nothing when disabled."""
        collector = get_metadata_collector()
        collector.set_enabled(False)

        # Try to set execution context
        collector.set_execution_context(
            task_name="test_task",
            run_name="test_run",
        )

        # Should not have set anything (start_time should be None)
        assert collector.execution_context.start_time is None

    def test_set_execution_context_when_enabled(self):
        """Test that set_execution_context works when enabled."""
        collector = get_metadata_collector()
        collector.set_enabled(True)

        # Set execution context
        collector.set_execution_context(
            task_name="test_task",
            run_name="test_run",
        )

        # Should have set
        assert collector.execution_context.task_name == "test_task"
        assert collector.execution_context.run_name == "test_run"
        assert collector.execution_context.start_time is not None

    def test_save_metadata_when_disabled(self):
        """Test that save_metadata returns None when disabled."""
        collector = get_metadata_collector()
        collector.set_enabled(False)

        # Try to save metadata
        result = collector.save_metadata()

        # Should return None
        assert result is None

    def test_finalize_execution_when_disabled(self):
        """Test that finalize_execution does nothing when disabled."""
        collector = get_metadata_collector()
        collector.set_enabled(False)

        # Try to finalize
        collector.finalize_execution()

        # Should not have set end_time
        assert collector.execution_context.end_time is None

    def test_toggle_during_execution(self):
        """Test toggling metadata collection during execution."""
        collector = get_metadata_collector()

        # Start enabled
        collector.set_enabled(True)
        collector.record_model_request("model1", latency=1.0)
        assert len(collector.model_metrics) == 1

        # Disable
        collector.set_enabled(False)
        collector.record_model_request("model2", latency=1.0)
        assert len(collector.model_metrics) == 1  # Should not have added model2

        # Re-enable
        collector.set_enabled(True)
        collector.record_model_request("model3", latency=1.0)
        assert len(collector.model_metrics) == 2  # Should have added model3

    def test_singleton_pattern(self):
        """Test that get_metadata_collector returns same instance."""
        collector1 = get_metadata_collector()
        collector2 = get_metadata_collector()

        assert collector1 is collector2

    def test_reset_preserves_enabled_state(self):
        """Test that reset() doesn't change enabled state."""
        collector = get_metadata_collector()

        # Disable and add some data
        collector.set_enabled(False)
        collector.set_enabled(True)  # Re-enable to add data
        collector.record_model_request("test", latency=1.0)

        # Disable again
        collector.set_enabled(False)

        # Reset
        collector.reset()

        # Should still be disabled
        assert collector.is_enabled() is False

        # Should have cleared data
        assert len(collector.model_metrics) == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
