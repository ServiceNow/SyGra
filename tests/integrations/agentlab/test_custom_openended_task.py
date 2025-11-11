"""
Tests for Custom OpenEnded Task

Tests OpenEndedTaskWithCompletion and goal evaluation functionality.
"""

import pytest

try:
    from sygra.integrations.agentlab.tasks.openended_task import (
        _GOAL_EVAL_CONFIG,
        configure_goal_evaluation,
    )

    # Note: OpenEndedTaskWithCompletion is meant to be used via patching
    # For testing, we'll test the configuration and utility functions
    AGENTLAB_AVAILABLE = True
except ImportError:
    AGENTLAB_AVAILABLE = False


@pytest.mark.skipif(not AGENTLAB_AVAILABLE, reason="AgentLab not installed")
class TestGoalEvaluationConfiguration:
    """Test goal evaluation configuration"""

    def test_configure_goal_evaluation_default(self):
        """Test configuring goal evaluation with defaults"""
        configure_goal_evaluation()

        # Should update global config
        assert _GOAL_EVAL_CONFIG["enable"] is False
        assert _GOAL_EVAL_CONFIG["frequency"] == 2
        assert _GOAL_EVAL_CONFIG["start_step"] == 3
        assert _GOAL_EVAL_CONFIG["use_vision"] is False

    def test_configure_goal_evaluation_custom(self):
        """Test configuring goal evaluation with custom values"""
        configure_goal_evaluation(enable=True, frequency=5, start_step=1, use_vision=True)

        assert _GOAL_EVAL_CONFIG["enable"] is True
        assert _GOAL_EVAL_CONFIG["frequency"] == 5
        assert _GOAL_EVAL_CONFIG["start_step"] == 1
        assert _GOAL_EVAL_CONFIG["use_vision"] is True

    def test_configure_goal_evaluation_partial(self):
        """Test configuring only some parameters"""
        # First set some values
        configure_goal_evaluation(enable=True, frequency=10)

        # Then change only some
        configure_goal_evaluation(frequency=3)

        # Should update only the specified parameters
        assert _GOAL_EVAL_CONFIG["enable"] is False  # Default value
        assert _GOAL_EVAL_CONFIG["frequency"] == 3

    def test_goal_eval_config_persistence(self):
        """Test that configuration persists across calls"""
        # Set configuration
        configure_goal_evaluation(enable=True, frequency=7)

        # Configuration should persist
        assert _GOAL_EVAL_CONFIG["enable"] is True
        assert _GOAL_EVAL_CONFIG["frequency"] == 7

        # Reset for other tests
        configure_goal_evaluation(enable=False, frequency=2)

    def test_goal_eval_config_is_global(self):
        """Test that configuration is global"""
        # Import should get the same config object
        from sygra.integrations.agentlab.tasks.openended_task import (
            _GOAL_EVAL_CONFIG as imported_config,
        )

        configure_goal_evaluation(enable=True)

        # Both references should see the change
        assert _GOAL_EVAL_CONFIG["enable"] is True
        assert imported_config["enable"] is True

    def test_goal_eval_config_types(self):
        """Test that configuration accepts correct types"""
        configure_goal_evaluation(enable=True, frequency=5, start_step=0, use_vision=False)

        assert isinstance(_GOAL_EVAL_CONFIG["enable"], bool)
        assert isinstance(_GOAL_EVAL_CONFIG["frequency"], int)
        assert isinstance(_GOAL_EVAL_CONFIG["start_step"], int)
        assert isinstance(_GOAL_EVAL_CONFIG["use_vision"], bool)

    def test_goal_eval_config_edge_cases(self):
        """Test configuration with edge case values"""
        # Zero values
        configure_goal_evaluation(frequency=0, start_step=0)
        assert _GOAL_EVAL_CONFIG["frequency"] == 0
        assert _GOAL_EVAL_CONFIG["start_step"] == 0

        # Large values
        configure_goal_evaluation(frequency=1000, start_step=999)
        assert _GOAL_EVAL_CONFIG["frequency"] == 1000
        assert _GOAL_EVAL_CONFIG["start_step"] == 999


@pytest.mark.skipif(not AGENTLAB_AVAILABLE, reason="AgentLab not installed")
class TestModuleStructure:
    """Test module structure and imports"""

    def test_module_exports(self):
        """Test that module exports expected functions"""
        from sygra.integrations.agentlab.tasks import openended_task

        assert hasattr(openended_task, "configure_goal_evaluation")
        assert hasattr(openended_task, "_GOAL_EVAL_CONFIG")
        assert hasattr(openended_task, "OpenEndedTaskWithCompletion")

    def test_configure_goal_evaluation_callable(self):
        """Test that configure_goal_evaluation is callable"""
        assert callable(configure_goal_evaluation)

    def test_goal_eval_config_structure(self):
        """Test that _GOAL_EVAL_CONFIG has expected structure"""
        expected_keys = {"enable", "frequency", "start_step", "use_vision"}
        assert set(_GOAL_EVAL_CONFIG.keys()) == expected_keys

    def test_openended_task_class_exists(self):
        """Test that OpenEndedTaskWithCompletion class exists"""
        from sygra.integrations.agentlab.tasks.openended_task import OpenEndedTaskWithCompletion

        assert OpenEndedTaskWithCompletion is not None
        assert callable(OpenEndedTaskWithCompletion)

    def test_logger_import(self):
        """Test that logger is properly imported"""
        from sygra.integrations.agentlab.tasks import openended_task

        # Should have logger available (used in the module)
        assert hasattr(openended_task, "logger")


@pytest.mark.skipif(not AGENTLAB_AVAILABLE, reason="AgentLab not installed")
class TestIntegrationPatterns:
    """Test integration patterns and expected usage"""

    def test_configuration_workflow(self):
        """Test typical configuration workflow"""
        # 1. Configure evaluation
        configure_goal_evaluation(enable=True, frequency=2, start_step=3)

        # 2. Configuration should be accessible
        assert _GOAL_EVAL_CONFIG["enable"] is True

        # 3. Should be able to reconfigure
        configure_goal_evaluation(enable=False)
        assert _GOAL_EVAL_CONFIG["enable"] is False

    def test_environment_based_configuration(self):
        """Test that configuration can be environment-based"""
        # Test the module can handle environment-based config
        # This is more about ensuring the module structure supports it

        # Reset to defaults
        configure_goal_evaluation()

        # Should have reasonable defaults
        assert isinstance(_GOAL_EVAL_CONFIG["enable"], bool)
        assert isinstance(_GOAL_EVAL_CONFIG["frequency"], int)
        assert _GOAL_EVAL_CONFIG["frequency"] > 0

    def test_config_modification_safety(self):
        """Test that config can be safely modified"""
        original_config = _GOAL_EVAL_CONFIG.copy()

        try:
            # Modify config
            configure_goal_evaluation(enable=True, frequency=99)

            # Should be able to read modified values
            assert _GOAL_EVAL_CONFIG["enable"] is True
            assert _GOAL_EVAL_CONFIG["frequency"] == 99

        finally:
            # Restore original config
            for key, value in original_config.items():
                _GOAL_EVAL_CONFIG[key] = value

    def test_task_completion_detection_concept(self):
        """Test concepts related to task completion detection"""
        # This tests the concept without instantiating the actual task
        # which requires browsergym integration

        # The module should support completion detection configuration
        configure_goal_evaluation(enable=True)

        # Should be able to configure when evaluation starts
        configure_goal_evaluation(start_step=5)
        assert _GOAL_EVAL_CONFIG["start_step"] == 5

        # Should be able to configure evaluation frequency
        configure_goal_evaluation(frequency=3)
        assert _GOAL_EVAL_CONFIG["frequency"] == 3

    def test_vision_support_configuration(self):
        """Test vision support in goal evaluation"""
        # Test vision can be enabled
        configure_goal_evaluation(use_vision=True)
        assert _GOAL_EVAL_CONFIG["use_vision"] is True

        # Test vision can be disabled
        configure_goal_evaluation(use_vision=False)
        assert _GOAL_EVAL_CONFIG["use_vision"] is False

    def test_default_configuration_values(self):
        """Test that default configuration values are sensible"""
        configure_goal_evaluation()  # Reset to defaults

        # Defaults should be reasonable for production use
        assert _GOAL_EVAL_CONFIG["frequency"] >= 1  # Should evaluate at reasonable intervals
        assert _GOAL_EVAL_CONFIG["start_step"] >= 0  # Should start at reasonable step
        assert isinstance(_GOAL_EVAL_CONFIG["enable"], bool)  # Should be boolean

    def test_parameter_combinations(self):
        """Test various parameter combinations"""
        combinations = [
            {"enable": True, "frequency": 1, "start_step": 0, "use_vision": True},
            {"enable": False, "frequency": 5, "start_step": 10, "use_vision": False},
            {"enable": True, "frequency": 2, "start_step": 1, "use_vision": True},
        ]

        for params in combinations:
            configure_goal_evaluation(**params)

            for key, expected_value in params.items():
                assert _GOAL_EVAL_CONFIG[key] == expected_value

    def test_function_signature_compatibility(self):
        """Test that configure_goal_evaluation has stable signature"""
        import inspect

        sig = inspect.signature(configure_goal_evaluation)
        param_names = list(sig.parameters.keys())

        # Should have expected parameters
        expected_params = ["enable", "frequency", "start_step", "use_vision"]
        for param in expected_params:
            assert param in param_names

        # All parameters should have defaults
        for param in sig.parameters.values():
            assert param.default != inspect.Parameter.empty
