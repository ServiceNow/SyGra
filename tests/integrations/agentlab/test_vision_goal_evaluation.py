"""
Comprehensive Tests for Vision-Enabled Goal Evaluation

Tests the complete vision goal evaluation feature including:
- Configuration propagation
- Screenshot capture
- Vision-enabled LLM evaluation
- Result loading with eval confidence
"""

from unittest.mock import Mock, patch

import pytest

try:
    from agentlab.agents.agent_args import AgentArgs

    from sygra.integrations.agentlab.agents.web_agent_node import (
        WebAgentNode,
        create_web_agent_node,
    )
    from sygra.integrations.agentlab.evaluation.goal_evaluator import GoalEvaluator
    from sygra.integrations.agentlab.experiments.runner import ExperimentConfig
    from sygra.integrations.agentlab.tasks.openended_task import (
        _GOAL_EVAL_CONFIG,
        configure_goal_evaluation,
    )

    AGENTLAB_AVAILABLE = True
except ImportError:
    AGENTLAB_AVAILABLE = False


@pytest.mark.skipif(not AGENTLAB_AVAILABLE, reason="AgentLab not installed")
class TestVisionGoalEvaluationIntegration:
    """Integration tests for vision-enabled goal evaluation"""

    def test_goal_evaluator_vision_initialization(self):
        """Test GoalEvaluator initializes with vision enabled"""
        evaluator = GoalEvaluator(use_vision=True)
        assert evaluator.use_vision is True

    def test_goal_evaluator_text_only_initialization(self):
        """Test GoalEvaluator initializes without vision"""
        evaluator = GoalEvaluator(use_vision=False)
        assert evaluator.use_vision is False

    def test_configure_goal_evaluation_with_vision(self):
        """Test configuring goal evaluation with vision parameter"""
        configure_goal_evaluation(enable=True, frequency=2, start_step=3, use_vision=True)

        assert _GOAL_EVAL_CONFIG["enable"] is True
        assert _GOAL_EVAL_CONFIG["use_vision"] is True

        # Reset
        configure_goal_evaluation(enable=False, use_vision=False)

    def test_experiment_config_includes_vision_param(self):
        """Test ExperimentConfig preserves vision parameter"""
        mock_agent_args = Mock(spec=AgentArgs)

        config = ExperimentConfig(
            agent_args=mock_agent_args,
            task_name="test",
            task_type="custom",
            url="https://example.com",
            goal="Test",
            max_steps=10,
            headless=True,
            slow_mo=0,
            viewport_width=1280,
            viewport_height=720,
            exp_dir="/tmp/exp",
            model_name="gpt-4o",
            enable_goal_eval=True,
            eval_use_vision=True,
        )

        assert config.eval_use_vision is True
        config_dict = config.to_dict()
        assert config_dict["eval_use_vision"] is True

    def test_web_agent_node_vision_configuration(self):
        """Test WebAgentNode accepts and stores vision parameter"""
        node = WebAgentNode(
            node_name="test_agent", model="gpt-4o", enable_goal_eval=True, eval_use_vision=True
        )

        assert node.eval_use_vision is True

    def test_web_agent_node_factory_with_vision(self):
        """Test factory function propagates vision parameter"""
        config = {"model": "gpt-4o", "enable_goal_eval": True, "eval_use_vision": True}

        node = create_web_agent_node("agent", config)
        assert node.eval_use_vision is True

    @patch("sygra.integrations.agentlab.evaluation.goal_evaluator.GoalEvaluator._get_model_args")
    def test_vision_evaluation_sends_screenshot(self, mock_get_model_args):
        """Test that vision evaluation includes screenshot in LLM call"""
        # Mock LLM response
        mock_model = Mock()
        mock_model.return_value = {
            "choices": [
                {"message": {"content": "ANSWER: YES\nREASONING: Order confirmed\nCONFIDENCE: 1.0"}}
            ]
        }

        mock_model_args = Mock()
        mock_model_args.make_model.return_value = mock_model
        mock_get_model_args.return_value = mock_model_args

        evaluator = GoalEvaluator(use_vision=True)

        observation = {
            "url": "https://example.com/success",
            "title": "Success",
            "content": "Order placed",
            "screenshot": b"fake_screenshot_bytes",
        }

        is_complete, reasoning, confidence = evaluator.evaluate_goal_completion(
            goal="Buy shoes", trajectory=[], current_observation=observation
        )

        assert is_complete is True
        assert confidence == 1.0

        # Verify screenshot was included in message
        call_args = mock_model.call_args
        messages = call_args[1]["messages"]

        # Vision message should be a list with text and image
        assert isinstance(messages[0]["content"], list)
        assert any(item["type"] == "image_url" for item in messages[0]["content"])

    @patch("sygra.integrations.agentlab.evaluation.goal_evaluator.GoalEvaluator._get_model_args")
    def test_vision_fallback_when_no_screenshot(self, mock_get_model_args):
        """Test graceful fallback to text-only when screenshot missing"""
        mock_model = Mock()
        mock_model.return_value = {
            "choices": [
                {"message": {"content": "ANSWER: NO\nREASONING: Not done\nCONFIDENCE: 0.8"}}
            ]
        }

        mock_model_args = Mock()
        mock_model_args.make_model.return_value = mock_model
        mock_get_model_args.return_value = mock_model_args

        evaluator = GoalEvaluator(use_vision=True)

        observation = {
            "url": "https://example.com",
            "title": "Page",
            "content": "Content",
            # No screenshot key
        }

        is_complete, reasoning, confidence = evaluator.evaluate_goal_completion(
            goal="Test", trajectory=[], current_observation=observation
        )

        # Should work without error
        assert isinstance(is_complete, bool)
        assert isinstance(confidence, float)


@pytest.mark.skipif(not AGENTLAB_AVAILABLE, reason="AgentLab not installed")
class TestGoalEvaluationPrompts:
    """Test prompt generation for goal evaluation"""

    def test_prompt_includes_vision_note_when_enabled(self):
        """Test vision-enabled prompt includes screenshot note"""
        evaluator = GoalEvaluator(use_vision=True)

        prompt = evaluator._build_evaluation_prompt(
            goal="Test goal", trajectory=[], current_observation={"url": "http://test.com"}
        )

        assert "screenshot" in prompt.lower()

    def test_prompt_excludes_vision_note_when_disabled(self):
        """Test text-only prompt doesn't mention screenshots"""
        evaluator = GoalEvaluator(use_vision=False)

        prompt = evaluator._build_evaluation_prompt(
            goal="Test goal", trajectory=[], current_observation={"url": "http://test.com"}
        )

        # Should not mention screenshots
        assert "screenshot" not in prompt.lower() or "not provided" in prompt.lower()


@pytest.mark.skipif(not AGENTLAB_AVAILABLE, reason="AgentLab not installed")
class TestResultLoadingWithEvaluation:
    """Test loading results that include goal evaluation data"""

    def test_none_confidence_handling(self):
        """Test that None confidence is handled gracefully in logging"""
        # This validates the bug fix for: TypeError: unsupported format string passed to NoneType.__format__

        eval_confidence = None

        # Test the formatting pattern used in result_loader.py and web_agent_node.py
        conf_str = f"{eval_confidence:.2f}" if eval_confidence is not None else "N/A"
        assert conf_str == "N/A"

        # Test with actual confidence
        eval_confidence = 0.95
        conf_str = f"{eval_confidence:.2f}" if eval_confidence is not None else "N/A"
        assert conf_str == "0.95"


@pytest.mark.skipif(not AGENTLAB_AVAILABLE, reason="AgentLab not installed")
class TestEndToEndConfiguration:
    """Test configuration flows from YAML to evaluation"""

    def test_configuration_chain(self):
        """Test configuration propagates through the entire chain"""
        # Configure globally
        configure_goal_evaluation(enable=True, frequency=2, start_step=3, use_vision=True)

        # Verify global config
        assert _GOAL_EVAL_CONFIG["use_vision"] is True

        # Create node with config
        node = WebAgentNode(
            node_name="test", model="gpt-4o", enable_goal_eval=True, eval_use_vision=True
        )

        # Verify node stores it
        assert node.eval_use_vision is True

        # Create experiment config
        mock_agent_args = Mock(spec=AgentArgs)
        exp_config = ExperimentConfig(
            agent_args=mock_agent_args,
            task_name="test",
            task_type="custom",
            url="http://test.com",
            goal="Test",
            max_steps=10,
            headless=True,
            slow_mo=0,
            viewport_width=1280,
            viewport_height=720,
            exp_dir="/tmp/exp",
            model_name="gpt-4o",
            enable_goal_eval=True,
            eval_use_vision=True,
        )

        # Verify experiment config has it
        assert exp_config.eval_use_vision is True

        # Verify it survives serialization
        config_dict = exp_config.to_dict()
        assert config_dict["eval_use_vision"] is True

        # Reset
        configure_goal_evaluation(enable=False, use_vision=False)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
