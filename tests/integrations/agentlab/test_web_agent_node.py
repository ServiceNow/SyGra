"""
Tests for Web Agent Node

Tests WebAgentNode configuration, state management, and execution flow.
"""

from unittest.mock import patch

import pytest

try:
    from sygra.integrations.agentlab.agents.web_agent_node import (
        WebAgentNode,
        create_web_agent_node,
    )

    AGENTLAB_AVAILABLE = True
except ImportError:
    AGENTLAB_AVAILABLE = False


@pytest.mark.skipif(not AGENTLAB_AVAILABLE, reason="AgentLab not installed")
class TestWebAgentNode:
    """Test WebAgentNode class"""

    def test_initialization_basic(self):
        """Test basic node initialization"""
        node = WebAgentNode(node_name="test_agent", model="gpt-4o", max_steps=10, headless=True)

        assert node.name == "test_agent"
        assert node.max_steps == 10
        assert node.headless is True
        assert node.enable_goal_eval is False

    def test_initialization_with_goal_eval(self):
        """Test initialization with goal evaluation enabled"""
        node = WebAgentNode(
            node_name="eval_agent",
            model="gpt-4o",
            max_steps=15,
            enable_goal_eval=True,
            eval_frequency=2,
            eval_start_step=3,
            eval_use_vision=True,
        )

        assert node.enable_goal_eval is True
        assert node.eval_frequency == 2
        assert node.eval_start_step == 3
        assert node.eval_use_vision is True

    def test_state_variables_registration(self):
        """Test that state variables are properly registered"""
        node = WebAgentNode(node_name="test_agent", model="gpt-4o")

        # Default state variables
        assert "agent_result" in node.state_variables
        assert "trajectory" in node.state_variables
        assert "screenshots" in node.state_variables
        assert "exp_dir" in node.state_variables

    def test_state_variables_with_custom_output_keys(self):
        """Test custom output keys are added to state variables"""
        node_config = {"output_keys": ["custom_metric", "success_rate"]}

        node = WebAgentNode(node_name="test_agent", model="gpt-4o", node_config=node_config)

        assert "custom_metric" in node.state_variables
        assert "success_rate" in node.state_variables

    def test_extract_task_info_from_state(self):
        """Test extracting task information from state"""
        node = WebAgentNode(node_name="test_agent", model="gpt-4o")

        state = {
            "task_name": "custom.test",
            "task_type": "custom",
            "url": "https://example.com",
            "goal": "Complete the task",
        }

        task_info = node._extract_task_info(state)

        assert task_info["task_name"] == "custom.test"
        assert task_info["task_type"] == "custom"
        assert task_info["url"] == "https://example.com"
        assert task_info["goal"] == "Complete the task"

    def test_extract_task_info_defaults(self):
        """Test default values when state keys missing"""
        node = WebAgentNode(node_name="test_agent", model="gpt-4o")

        state = {}  # Empty state

        task_info = node._extract_task_info(state)

        assert task_info["task_name"] == "custom.openended"
        assert task_info["task_type"] == "custom"
        assert task_info["url"] == "https://www.google.com"
        assert task_info["goal"] == "Complete the task"

    def test_log_experiment_summary_agent_signal(self):
        """Test logging for agent signal completion"""
        node = WebAgentNode(node_name="test_agent", model="gpt-4o")

        agent_result = {
            "num_steps": 5,
            "total_cost": 0.15,
            "success": True,
            "completion_reason": "agent_signal",
        }

        # Should not raise exception
        try:
            node._log_experiment_summary(agent_result, "test_task")
        except Exception as e:
            pytest.fail(f"Logging failed: {e}")

    def test_log_experiment_summary_auto_eval(self):
        """Test logging for goal evaluation completion"""
        node = WebAgentNode(node_name="test_agent", model="gpt-4o")

        agent_result = {
            "num_steps": 7,
            "total_cost": 0.25,
            "success": True,
            "completion_reason": "auto_eval",
            "eval_confidence": 0.95,
        }

        # Should not raise exception
        try:
            node._log_experiment_summary(agent_result, "test_task")
        except Exception as e:
            pytest.fail(f"Logging failed: {e}")

    def test_log_experiment_summary_auto_eval_none_confidence(self):
        """Test logging handles None confidence gracefully"""
        node = WebAgentNode(node_name="test_agent", model="gpt-4o")

        agent_result = {
            "num_steps": 7,
            "total_cost": 0.25,
            "success": True,
            "completion_reason": "auto_eval",
            "eval_confidence": None,  # Edge case
        }

        # Should handle None gracefully without format error
        try:
            node._log_experiment_summary(agent_result, "test_task")
        except TypeError as e:
            pytest.fail(f"Should handle None confidence: {e}")

    def test_build_complete_output(self):
        """Test building complete output dictionary"""
        node = WebAgentNode(node_name="test_agent", model="gpt-4o")

        state = {"input_field": "input_value"}
        task_info = {
            "task_name": "test_task",
            "task_type": "custom",
            "url": "https://example.com",
            "goal": "Test goal",
        }
        agent_result = {"num_steps": 5, "success": True, "trajectory": [], "screenshots": []}
        exp_dir = "/tmp/exp"

        output = node._build_complete_output(state, task_info, agent_result, exp_dir)

        assert output["task_name"] == "test_task"
        assert output["url"] == "https://example.com"
        assert output["goal"] == "Test goal"
        assert output["num_steps"] == 5
        assert output["success"] is True
        assert output["exp_dir"] == "/tmp/exp"

    def test_update_state(self):
        """Test state update after experiment"""
        node = WebAgentNode(node_name="test_agent", model="gpt-4o")

        state = {"existing_key": "value"}
        agent_result = {"trajectory": [{"step": 0}], "screenshots": [], "num_steps": 1}
        exp_dir = "/tmp/exp"
        task_name = "test"

        updated_state = node._update_state(state, agent_result, exp_dir, task_name)

        # _update_state returns only updates, not merged state (LangGraph handles merging)
        assert "agent_result" in updated_state
        assert "trajectory" in updated_state
        assert "screenshots" in updated_state
        assert "exp_dir" in updated_state
        # Note: existing_key is not included as _update_state returns only updates

    @patch("sygra.integrations.agentlab.experiments.runner.ExperimentRunner.run")
    @patch("sygra.integrations.agentlab.evaluation.result_loader.ResultLoader.load")
    def test_forward_execution_success(self, mock_load, mock_run):
        """Test successful forward execution"""
        node = WebAgentNode(node_name="test_agent", model="gpt-4o", max_steps=10)

        # Mock experiment runner
        mock_run.return_value = {"completed": True, "exp_dir": "/tmp/exp"}

        # Mock result loader
        mock_load.return_value = {
            "num_steps": 5,
            "success": True,
            "trajectory": [],
            "screenshots": [],
            "total_cost": 0.10,
            "completion_reason": "agent_signal",
        }

        state = {"url": "https://example.com", "goal": "Test goal"}

        result = node.forward(state)

        assert "agent_result" in result
        assert result["agent_result"]["success"] is True

    @patch("sygra.integrations.agentlab.experiments.runner.ExperimentRunner.run")
    def test_forward_execution_failure(self, mock_run):
        """Test forward execution handles failure"""
        node = WebAgentNode(node_name="test_agent", model="gpt-4o")

        # Mock failed experiment
        mock_run.return_value = {"completed": False, "error": "Test error"}

        state = {"url": "https://example.com", "goal": "Test"}

        result = node.forward(state)

        assert "agent_result" in result
        assert result["agent_result"]["success"] is False


@pytest.mark.skipif(not AGENTLAB_AVAILABLE, reason="AgentLab not installed")
class TestCreateWebAgentNode:
    """Test create_web_agent_node factory function"""

    def test_create_from_config_basic(self):
        """Test creating node from basic config"""
        config = {"model": "gpt-4o", "max_steps": 15, "headless": True}

        node = create_web_agent_node("test_agent", config)

        assert node.name == "test_agent"
        assert node.max_steps == 15
        assert node.headless is True

    def test_create_from_config_with_goal_eval(self):
        """Test creating node with goal evaluation config"""
        config = {
            "model": "gpt-4o-mini",
            "max_steps": 20,
            "enable_goal_eval": True,
            "eval_frequency": 3,
            "eval_start_step": 5,
            "eval_use_vision": True,
        }

        node = create_web_agent_node("eval_agent", config)

        assert node.enable_goal_eval is True
        assert node.eval_frequency == 3
        assert node.eval_start_step == 5
        assert node.eval_use_vision is True

    def test_create_from_config_defaults(self):
        """Test factory uses proper defaults"""
        config = {}  # Empty config

        node = create_web_agent_node("default_agent", config)

        assert node.max_steps == 15
        assert node.headless is True
        assert node.enable_goal_eval is False
        assert node.eval_frequency == 2
        assert node.eval_start_step == 3
        assert node.eval_use_vision is False

    def test_create_from_config_with_viewport(self):
        """Test viewport configuration"""
        config = {"viewport_width": 1920, "viewport_height": 1080, "slow_mo": 600}

        node = create_web_agent_node("agent", config)

        assert node.viewport_width == 1920
        assert node.viewport_height == 1080
        assert node.slow_mo == 600

    def test_create_from_config_with_model_options(self):
        """Test model configuration options"""
        config = {"use_screenshot": True, "use_som": True, "use_html": False, "temperature": 0.3}

        node = create_web_agent_node("agent", config)

        # These are passed to AgentConfigBuilder
        # Verify node was created successfully
        assert node.name == "agent"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
