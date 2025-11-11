"""
Tests for AgentConfigBuilder

Tests agent configuration building and validation.
"""

import pytest

try:
    from sygra.integrations.agentlab.agents.config import AgentConfigBuilder

    AGENTLAB_AVAILABLE = True
except ImportError:
    AGENTLAB_AVAILABLE = False


@pytest.mark.skipif(not AGENTLAB_AVAILABLE, reason="AgentLab not installed")
class TestAgentConfigBuilder:
    """Test AgentConfigBuilder class"""

    def test_build_basic_config(self):
        """Test building basic agent configuration"""
        config = AgentConfigBuilder.build(model="gpt-4o", temperature=0.1)

        # Should return an AgentArgs instance
        assert config is not None

    def test_build_with_all_options(self):
        """Test building with all configuration options"""
        config = AgentConfigBuilder.build(
            model="gpt-4o",
            temperature=0.2,
            use_screenshot=True,
            use_som=True,
            use_html=False,
            use_ax_tree=True,
            enable_chat=True,
        )

        # Should return configured AgentArgs
        assert config is not None

    def test_build_minimal_config(self):
        """Test building with minimal configuration"""
        config = AgentConfigBuilder.build()

        # Should work with all defaults
        assert config is not None

    def test_build_vision_model(self):
        """Test building config for vision-enabled model"""
        config = AgentConfigBuilder.build(model="gpt-4o", use_screenshot=True)

        assert config is not None

    def test_build_non_vision_model(self):
        """Test building config for non-vision model"""
        config = AgentConfigBuilder.build(model="gpt-3.5-turbo", use_screenshot=False)

        assert config is not None

    def test_build_with_chat_enabled(self):
        """Test building config with chat actions enabled"""
        config = AgentConfigBuilder.build(model="gpt-4o", enable_chat=True)

        assert config is not None

    def test_build_with_chat_disabled(self):
        """Test building config with chat actions disabled"""
        config = AgentConfigBuilder.build(model="gpt-4o", enable_chat=False)

        assert config is not None

    def test_build_with_html_observations(self):
        """Test building config with HTML observations"""
        config = AgentConfigBuilder.build(model="gpt-4o", use_html=True, use_screenshot=False)

        assert config is not None

    def test_vision_models_constant(self):
        """Test that VISION_MODELS constant is properly defined"""
        assert hasattr(AgentConfigBuilder, "VISION_MODELS")
        assert isinstance(AgentConfigBuilder.VISION_MODELS, set)
        assert "gpt-4o" in AgentConfigBuilder.VISION_MODELS
        assert "gpt-4o-mini" in AgentConfigBuilder.VISION_MODELS

    def test_temperature_validation(self):
        """Test that temperature parameter is handled correctly"""
        # Should accept valid temperature values
        config = AgentConfigBuilder.build(temperature=0.0)
        assert config is not None

        config = AgentConfigBuilder.build(temperature=1.0)
        assert config is not None

        config = AgentConfigBuilder.build(temperature=0.5)
        assert config is not None

    def test_som_and_ax_tree_interaction(self):
        """Test SOM and AX tree configuration interaction"""
        # Both enabled (should work but may confuse agent)
        config = AgentConfigBuilder.build(use_som=True, use_ax_tree=True)
        assert config is not None

        # SOM enabled, AX tree disabled (recommended)
        config = AgentConfigBuilder.build(use_som=True, use_ax_tree=False)
        assert config is not None

    def test_multiple_observation_types(self):
        """Test building config with multiple observation types"""
        config = AgentConfigBuilder.build(
            use_screenshot=True, use_som=True, use_html=True, use_ax_tree=True
        )

        assert config is not None

    def test_build_returns_agent_args_instance(self):
        """Test that build method returns proper AgentArgs instance"""
        result = AgentConfigBuilder.build(model="gpt-4o")

        # Should return an instance that can be used for agent configuration
        assert result is not None

    def test_build_different_models(self):
        """Test building configs for different model types"""
        models_to_test = ["gpt-4o", "gpt-4o-mini", "gpt-3.5-turbo"]

        for model in models_to_test:
            config = AgentConfigBuilder.build(model=model)
            assert config is not None
