"""
Unit tests for MetadataTrackingCallback (LangChain callback handler).

Tests the callback that tracks LLM calls made by LangChain agents.
"""

from uuid import uuid4

import pytest
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, LLMResult

from sygra.metadata.langchain_callback import MetadataTrackingCallback
from sygra.metadata.metadata_collector import get_metadata_collector


class TestMetadataTrackingCallback:
    """Test suite for MetadataTrackingCallback."""

    def setup_method(self):
        """Reset metadata collector before each test."""
        collector = get_metadata_collector()
        collector.reset()
        collector.set_enabled(True)

    def test_initialization(self):
        """Test callback initialization."""
        callback = MetadataTrackingCallback(model_name="gpt-4o")

        assert callback.model_name == "gpt-4o"
        assert len(callback.call_start_times) == 0

    @pytest.mark.asyncio
    async def test_on_llm_start(self):
        """Test on_llm_start callback."""
        callback = MetadataTrackingCallback(model_name="gpt-4o")
        run_id = uuid4()

        # Call on_llm_start
        await callback.on_llm_start(
            serialized={"name": "ChatOpenAI"},
            prompts=["test prompt"],
            run_id=run_id,
        )

        # Should have recorded start time
        assert run_id in callback.call_start_times

    @pytest.mark.asyncio
    async def test_on_llm_end_with_token_usage(self):
        """Test on_llm_end callback with token usage."""
        callback = MetadataTrackingCallback(model_name="gpt-4o")
        collector = get_metadata_collector()
        run_id = uuid4()

        # Start LLM call
        await callback.on_llm_start(serialized={}, prompts=["test"], run_id=run_id)

        # Create mock response with token usage
        llm_output = {
            "token_usage": {
                "prompt_tokens": 100,
                "completion_tokens": 50,
                "total_tokens": 150,
            }
        }
        response = LLMResult(
            generations=[[ChatGeneration(message=AIMessage(content="test response"))]],
            llm_output=llm_output,
        )

        # End LLM call
        await callback.on_llm_end(response, run_id=run_id)

        # Check metadata was recorded
        assert "gpt-4o" in collector.model_metrics
        metrics = collector.model_metrics["gpt-4o"]
        assert metrics.num_requests == 1
        assert metrics.token_stats.total_prompt_tokens == 100
        assert metrics.token_stats.total_completion_tokens == 50
        assert metrics.token_stats.total_tokens == 150

    @pytest.mark.asyncio
    async def test_on_llm_end_without_token_usage(self):
        """Test on_llm_end callback without token usage."""
        callback = MetadataTrackingCallback(model_name="gpt-4o")
        collector = get_metadata_collector()
        run_id = uuid4()

        await callback.on_llm_start(serialized={}, prompts=["test"], run_id=run_id)

        # Response without token usage
        response = LLMResult(
            generations=[[ChatGeneration(message=AIMessage(content="test response"))]],
            llm_output={},
        )

        await callback.on_llm_end(response, run_id=run_id)

        # Should still record request but with 0 tokens
        assert "gpt-4o" in collector.model_metrics
        metrics = collector.model_metrics["gpt-4o"]
        assert metrics.num_requests == 1
        assert metrics.token_stats.total_tokens == 0

    @pytest.mark.asyncio
    async def test_on_llm_error(self):
        """Test on_llm_error callback."""
        callback = MetadataTrackingCallback(model_name="gpt-4o")
        collector = get_metadata_collector()
        run_id = uuid4()

        await callback.on_llm_start(serialized={}, prompts=["test"], run_id=run_id)

        # Simulate error
        error = ValueError("Test error")
        await callback.on_llm_error(error, run_id=run_id)

        # Should record failure
        assert "gpt-4o" in collector.model_metrics
        metrics = collector.model_metrics["gpt-4o"]
        assert metrics.num_requests == 1
        assert metrics.num_failures == 1
        assert metrics.response_codes[999] == 1

    @pytest.mark.asyncio
    async def test_multiple_llm_calls(self):
        """Test multiple LLM calls."""
        callback = MetadataTrackingCallback(model_name="gpt-4o")
        collector = get_metadata_collector()

        # Make 3 calls
        for i in range(3):
            run_id = uuid4()
            await callback.on_llm_start(serialized={}, prompts=["test"], run_id=run_id)

            llm_output = {
                "token_usage": {
                    "prompt_tokens": 100,
                    "completion_tokens": 50,
                    "total_tokens": 150,
                }
            }
            response = LLMResult(
                generations=[[ChatGeneration(message=AIMessage(content="response"))]],
                llm_output=llm_output,
            )

            await callback.on_llm_end(response, run_id=run_id)

        metrics = collector.model_metrics["gpt-4o"]
        assert metrics.num_requests == 3
        assert metrics.token_stats.total_tokens == 450


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
