"""
Unit tests for metadata integration decorator (@track_model_request).

Tests the decorator that automatically tracks model requests for custom models.
"""

from unittest.mock import patch

import pytest

from sygra.core.models.model_response import ModelResponse
from sygra.metadata.metadata_collector import get_metadata_collector
from sygra.metadata.metadata_integration import track_model_request


class MockModel:
    """Mock model class for testing the decorator."""

    def __init__(self, model_name="test_model", model_type="test"):
        self._model_name = model_name
        self._model_type = model_type
        self.model_config = {
            "type": model_type,
            "parameters": {"temperature": 0.7, "max_tokens": 100},
        }
        self._last_request_usage = None

    def name(self):
        """Return model name."""
        return self._model_name

    def model_type(self):
        """Return model type."""
        return self._model_type

    @track_model_request
    async def async_generate(self, prompt):
        """Async method that generates a response."""
        # Simulate token usage
        self._last_request_usage = {
            "prompt_tokens": 100,
            "completion_tokens": 50,
            "total_tokens": 150,
        }
        return ModelResponse(llm_response="Generated response", response_code=200)

    @track_model_request
    def sync_generate(self, prompt):
        """Sync method that generates a response."""
        # Simulate token usage
        self._last_request_usage = {
            "prompt_tokens": 100,
            "completion_tokens": 50,
            "total_tokens": 150,
        }
        return ModelResponse(llm_response="Generated response", response_code=200)

    @track_model_request
    async def async_generate_with_error(self, prompt):
        """Async method that raises an error."""
        raise ValueError("Test error")

    @track_model_request
    def sync_generate_with_error(self, prompt):
        """Sync method that raises an error."""
        raise ValueError("Test error")


class TestTrackModelRequestDecorator:
    """Test suite for @track_model_request decorator."""

    def setup_method(self):
        """Reset metadata collector before each test."""
        collector = get_metadata_collector()
        collector.reset()
        collector.set_enabled(True)

    @pytest.mark.asyncio
    async def test_async_decorator_success(self):
        """Test decorator with async function - successful request."""
        model = MockModel(model_name="gpt-4o", model_type="OpenAI")
        collector = get_metadata_collector()

        model_response: ModelResponse = await model.async_generate("test prompt")

        assert model_response.llm_response == "Generated response"
        assert model_response.response_code == 200

        # Check metadata was recorded
        assert "gpt-4o" in collector.model_metrics
        metrics = collector.model_metrics["gpt-4o"]
        assert metrics.num_requests == 1
        assert metrics.token_stats.total_prompt_tokens == 100
        assert metrics.token_stats.total_completion_tokens == 50
        assert metrics.response_codes[200] == 1

    def test_sync_decorator_success(self):
        """Test decorator with sync function - successful request."""
        model = MockModel(model_name="gpt-4o", model_type="OpenAI")
        collector = get_metadata_collector()

        model_response: ModelResponse = model.sync_generate("test prompt")

        assert model_response.llm_response == "Generated response"
        assert model_response.response_code == 200

        # Check metadata was recorded
        assert "gpt-4o" in collector.model_metrics
        metrics = collector.model_metrics["gpt-4o"]
        assert metrics.num_requests == 1
        assert metrics.token_stats.total_tokens == 150

    @pytest.mark.asyncio
    async def test_async_decorator_with_error(self):
        """Test decorator with async function - error handling."""
        model = MockModel(model_name="gpt-4o")
        collector = get_metadata_collector()

        with pytest.raises(ValueError, match="Test error"):
            await model.async_generate_with_error("test prompt")

        # Check that failure was recorded
        assert "gpt-4o" in collector.model_metrics
        metrics = collector.model_metrics["gpt-4o"]
        assert metrics.num_requests == 1
        assert metrics.num_failures == 1
        assert metrics.response_codes[999] == 1  # Error code

    def test_sync_decorator_with_error(self):
        """Test decorator with sync function - error handling."""
        model = MockModel(model_name="gpt-4o")
        collector = get_metadata_collector()

        with pytest.raises(ValueError, match="Test error"):
            model.sync_generate_with_error("test prompt")

        # Check that failure was recorded
        assert "gpt-4o" in collector.model_metrics
        metrics = collector.model_metrics["gpt-4o"]
        assert metrics.num_requests == 1
        assert metrics.num_failures == 1

    @pytest.mark.asyncio
    async def test_decorator_captures_latency(self):
        """Test that decorator captures request latency."""
        model = MockModel(model_name="gpt-4o")
        collector = get_metadata_collector()

        await model.async_generate("test prompt")

        metrics = collector.model_metrics["gpt-4o"]
        assert metrics.total_latency_seconds >= 0  # Latency can be 0 for very fast operations
        assert len(metrics.latency_samples) == 1

    @pytest.mark.asyncio
    async def test_decorator_captures_model_config(self):
        """Test that decorator captures model configuration."""
        model = MockModel(model_name="gpt-4o", model_type="OpenAI")
        collector = get_metadata_collector()

        await model.async_generate("test prompt")

        metrics = collector.model_metrics["gpt-4o"]
        assert metrics.model_type == "OpenAI"
        assert "temperature" in metrics.parameters
        assert metrics.parameters["temperature"] == 0.7

    @pytest.mark.asyncio
    async def test_decorator_multiple_requests(self):
        """Test decorator with multiple requests."""
        model = MockModel(model_name="gpt-4o")
        collector = get_metadata_collector()

        # Make multiple requests
        for _ in range(5):
            await model.async_generate("test prompt")

        metrics = collector.model_metrics["gpt-4o"]
        assert metrics.num_requests == 5
        assert metrics.token_stats.total_tokens == 750  # 150 * 5

    @pytest.mark.asyncio
    async def test_decorator_when_disabled(self):
        """Test that decorator doesn't record when metadata is disabled."""
        model = MockModel(model_name="gpt-4o")
        collector = get_metadata_collector()
        collector.set_enabled(False)

        await model.async_generate("test prompt")

        # Should not have recorded anything
        assert len(collector.model_metrics) == 0

    @pytest.mark.asyncio
    async def test_decorator_with_no_token_usage(self):
        """Test decorator when model doesn't provide token usage."""

        class ModelWithoutTokens(MockModel):
            @track_model_request
            async def async_generate(self, prompt):
                # Don't set _last_request_usage
                return ModelResponse(llm_response="Generated response", response_code=200)

        model = ModelWithoutTokens(model_name="gpt-4o")
        collector = get_metadata_collector()

        await model.async_generate("test prompt")

        # Should still record the request
        assert "gpt-4o" in collector.model_metrics
        metrics = collector.model_metrics["gpt-4o"]
        assert metrics.num_requests == 1
        # But no tokens
        assert metrics.token_stats.total_tokens == 0

    @pytest.mark.asyncio
    async def test_decorator_with_cost_calculation(self):
        """Test that decorator calculates costs."""
        model = MockModel(model_name="gpt-4o-mini", model_type="OpenAI")
        collector = get_metadata_collector()

        with patch("sygra.metadata.metadata_integration.calculate_cost") as mock_calc:
            mock_calc.return_value = 0.001

            await model.async_generate("test prompt")

            # Verify calculate_cost was called
            mock_calc.assert_called_once_with("gpt-4o-mini", 100, 50)

            # Verify cost was recorded
            metrics = collector.model_metrics["gpt-4o-mini"]
            assert metrics.total_cost_usd == 0.001

    def test_decorator_preserves_function_metadata(self):
        """Test that decorator preserves original function metadata."""
        model = MockModel()

        # Check that function name and docstring are preserved
        assert model.sync_generate.__name__ == "sync_generate"
        assert "Sync method" in model.sync_generate.__doc__

    @pytest.mark.asyncio
    async def test_decorator_with_api_version_in_config(self):
        """Test decorator handles api_version in model config."""

        class ModelWithAPIVersion(MockModel):
            def __init__(self):
                super().__init__()
                self.model_config = {
                    "type": "OpenAI",
                    "api_version": "2024-02-15-preview",
                    "parameters": {"temperature": 0.7},
                }

            @track_model_request
            async def async_generate(self, prompt):
                self._last_request_usage = {
                    "prompt_tokens": 100,
                    "completion_tokens": 50,
                    "total_tokens": 150,
                }
                return ModelResponse(llm_response="response", response_code=200)

        model = ModelWithAPIVersion()
        collector = get_metadata_collector()

        await model.async_generate("test")

        metrics = collector.model_metrics["test_model"]
        # api_version should be in parameters
        assert "api_version" in metrics.parameters
        assert metrics.parameters["api_version"] == "2024-02-15-preview"


class TestDecoratorEdgeCases:
    """Test edge cases and error conditions."""

    def setup_method(self):
        """Reset metadata collector before each test."""
        collector = get_metadata_collector()
        collector.reset()
        collector.set_enabled(True)

    @pytest.mark.asyncio
    async def test_decorator_with_missing_name_method(self):
        """Test decorator when model doesn't have name() method."""

        class ModelWithoutName:
            model_config = {}
            _last_request_usage = None

            @track_model_request
            async def async_generate(self, prompt):
                return ModelResponse(llm_response="response", response_code=200)

        model = ModelWithoutName()
        collector = get_metadata_collector()

        await model.async_generate("test")

        # Should use "unknown" as model name
        assert "unknown" in collector.model_metrics

    @pytest.mark.asyncio
    async def test_decorator_with_callable_model_type(self):
        """Test decorator when model_type is a callable."""

        class ModelWithCallableType:
            def name(self):
                return "test_model"

            def model_type(self):
                return "CustomType"

            model_config = {"type": "CustomType"}
            _last_request_usage = None

            @track_model_request
            async def async_generate(self, prompt):
                return ModelResponse(llm_response="response", response_code=200)

        model = ModelWithCallableType()
        collector = get_metadata_collector()

        await model.async_generate("test")

        metrics = collector.model_metrics["test_model"]
        # Model type comes from config, not from the method
        assert metrics.model_type == "CustomType"

    @pytest.mark.asyncio
    async def test_decorator_with_non_dict_model_config(self):
        """Test decorator when model_config is not a dict."""

        class ModelWithBadConfig:
            def name(self):
                return "test_model"

            model_config = "not a dict"
            _last_request_usage = None

            @track_model_request
            async def async_generate(self, prompt):
                return ModelResponse(llm_response="response", response_code=200)

        model = ModelWithBadConfig()
        collector = get_metadata_collector()

        # Should not crash
        await model.async_generate("test")

        assert "test_model" in collector.model_metrics

    @pytest.mark.asyncio
    async def test_decorator_with_partial_token_usage(self):
        """Test decorator with partial token usage information."""

        class ModelWithPartialTokens:
            def name(self):
                return "test_model"

            model_config = {}

            @track_model_request
            async def async_generate(self, prompt):
                # Only set some token fields
                self._last_request_usage = {"prompt_tokens": 100}
                return ModelResponse(llm_response="response", response_code=200)

        model = ModelWithPartialTokens()
        collector = get_metadata_collector()

        await model.async_generate("test")

        metrics = collector.model_metrics["test_model"]
        assert metrics.token_stats.total_prompt_tokens == 100
        assert metrics.token_stats.total_completion_tokens == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
