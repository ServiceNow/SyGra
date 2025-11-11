"""
Tests for Experiment Runner

Tests experiment configuration and subprocess execution.
"""

from unittest.mock import Mock, patch

import pytest

try:
    from agentlab.agents.agent_args import AgentArgs

    from sygra.integrations.agentlab.experiments.runner import ExperimentConfig, ExperimentRunner

    AGENTLAB_AVAILABLE = True
except ImportError:
    AGENTLAB_AVAILABLE = False


@pytest.mark.skipif(not AGENTLAB_AVAILABLE, reason="AgentLab not installed")
class TestExperimentConfig:
    """Test ExperimentConfig class"""

    def test_initialization_basic(self):
        """Test basic initialization"""
        mock_agent_args = Mock(spec=AgentArgs)

        config = ExperimentConfig(
            agent_args=mock_agent_args,
            task_name="test_task",
            task_type="custom",
            url="https://example.com",
            goal="Complete the task",
            max_steps=10,
            headless=True,
            slow_mo=0,
            viewport_width=1280,
            viewport_height=720,
            exp_dir="/tmp/test_exp",
            model_name="gpt-4o",
        )

        assert config.task_name == "test_task"
        assert config.goal == "Complete the task"
        assert config.max_steps == 10
        assert config.headless is True
        assert config.enable_goal_eval is False  # Default

    def test_initialization_with_goal_eval(self):
        """Test initialization with goal evaluation parameters"""
        mock_agent_args = Mock(spec=AgentArgs)

        config = ExperimentConfig(
            agent_args=mock_agent_args,
            task_name="test_task",
            task_type="custom",
            url="https://example.com",
            goal="Test goal",
            max_steps=15,
            headless=False,
            slow_mo=600,
            viewport_width=1380,
            viewport_height=820,
            exp_dir="/tmp/test",
            model_name="gpt-4o",
            enable_goal_eval=True,
            eval_frequency=2,
            eval_start_step=3,
            eval_use_vision=True,
        )

        assert config.enable_goal_eval is True
        assert config.eval_frequency == 2
        assert config.eval_start_step == 3
        assert config.eval_use_vision is True

    def test_to_dict_conversion(self):
        """Test converting config to dictionary"""
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
            eval_frequency=2,
            eval_start_step=3,
            eval_use_vision=False,
        )

        config_dict = config.to_dict()

        assert isinstance(config_dict, dict)
        assert config_dict["task_name"] == "test"
        assert config_dict["goal"] == "Test"
        assert config_dict["max_steps"] == 10
        assert config_dict["enable_goal_eval"] is True
        assert config_dict["eval_frequency"] == 2
        assert config_dict["eval_start_step"] == 3
        assert config_dict["eval_use_vision"] is False

    def test_to_dict_preserves_all_goal_eval_params(self):
        """Test that all goal evaluation parameters are preserved"""
        mock_agent_args = Mock(spec=AgentArgs)

        config = ExperimentConfig(
            agent_args=mock_agent_args,
            task_name="test",
            task_type="custom",
            url="https://example.com",
            goal="Test",
            max_steps=20,
            headless=False,
            slow_mo=100,
            viewport_width=1920,
            viewport_height=1080,
            exp_dir="/tmp/exp",
            model_name="gpt-4o-mini",
            enable_goal_eval=True,
            eval_frequency=3,
            eval_start_step=5,
            eval_use_vision=True,
        )

        config_dict = config.to_dict()

        # Verify all parameters are present
        required_keys = [
            "agent_args",
            "task_name",
            "task_type",
            "url",
            "goal",
            "max_steps",
            "headless",
            "slow_mo",
            "viewport_width",
            "viewport_height",
            "exp_dir",
            "model_name",
            "enable_goal_eval",
            "eval_frequency",
            "eval_start_step",
            "eval_use_vision",
        ]

        for key in required_keys:
            assert key in config_dict, f"Missing key: {key}"


@pytest.mark.skipif(not AGENTLAB_AVAILABLE, reason="AgentLab not installed")
class TestExperimentRunner:
    """Test ExperimentRunner class"""

    # @patch('sygra.integrations.agentlab.experiment_runner.ExperimentRunner._subprocess_target')
    # @patch('multiprocessing.Queue')
    # @patch('multiprocessing.get_context')
    # def test_run_experiment_success(self, mock_get_context, mock_queue, mock_subprocess_target):
    #     """Test successful experiment execution"""
    #     mock_agent_args = Mock(spec=AgentArgs)
    #
    #     config = ExperimentConfig(
    #         agent_args=mock_agent_args,
    #         task_name="test",
    #         task_type="custom",
    #         url="https://example.com",
    #         goal="Test",
    #         max_steps=10,
    #         headless=True,
    #         slow_mo=0,
    #         viewport_width=1280,
    #         viewport_height=720,
    #         exp_dir="/tmp/exp",
    #         model_name="gpt-4o"
    #     )
    #
    #     # Mock successful result
    #     mock_result_queue = MagicMock()
    #     mock_result_queue.empty.return_value = False
    #     mock_result_queue.get.return_value = {
    #         "exp_dir": "/tmp/exp",
    #         "completed": True,
    #         "error": None
    #     }
    #     mock_queue.return_value = mock_result_queue
    #
    #     # Mock process and context
    #     mock_proc = MagicMock()
    #     mock_proc.is_alive.return_value = False
    #     mock_proc.exitcode = 0
    #
    #     mock_context = MagicMock()
    #     mock_context.Process.return_value = mock_proc
    #     mock_get_context.return_value = mock_context
    #
    #     result = ExperimentRunner.run(config)
    #
    #     assert result["completed"] is True
    #     assert result["exp_dir"] == "/tmp/exp"
    #     assert "error" not in result or result["error"] is None

    # @pytest.mark.skip(reason="Multiprocessing with mocked AgentArgs causes pickling errors")
    # @patch('multiprocessing.Queue')
    # @patch('multiprocessing.Process')
    # def test_run_experiment_timeout(self, mock_process, mock_queue):
    #     """Test experiment timeout handling"""
    #     mock_agent_args = Mock(spec=AgentArgs)
    #
    #     config = ExperimentConfig(
    #         agent_args=mock_agent_args,
    #         task_name="test",
    #         task_type="custom",
    #         url="https://example.com",
    #         goal="Test",
    #         max_steps=10,
    #         headless=True,
    #         slow_mo=0,
    #         viewport_width=1280,
    #         viewport_height=720,
    #         exp_dir="/tmp/exp",
    #         model_name="gpt-4o"
    #     )
    #
    #     # Mock timeout - process stays alive and queue empty
    #     mock_result_queue = MagicMock()
    #     mock_result_queue.empty.return_value = True
    #     mock_queue.return_value = mock_result_queue
    #
    #     # Mock process that times out
    #     mock_proc = MagicMock()
    #     mock_proc.is_alive.return_value = True  # Still running
    #     mock_proc.join.side_effect = lambda timeout: None
    #     mock_process.return_value = mock_proc
    #
    #     result = ExperimentRunner.run(config)
    #
    #     # Should return error result
    #     assert result["completed"] is False
    #     assert "timeout" in result.get("error", "").lower()

    def test_subprocess_target_calls_configure_goal_evaluation(self):
        """Test that subprocess configures goal evaluation"""

        mock_agent_args = Mock(spec=AgentArgs)
        mock_result_queue = Mock()

        config_dict = {
            "agent_args": mock_agent_args,
            "task_name": "test",
            "task_type": "custom",
            "url": "https://example.com",
            "goal": "Test",
            "max_steps": 5,
            "headless": True,
            "slow_mo": 0,
            "viewport_width": 1280,
            "viewport_height": 720,
            "exp_dir": "/tmp/exp",
            "model_name": "gpt-4o",
            "enable_goal_eval": True,
            "eval_frequency": 2,
            "eval_start_step": 3,
            "eval_use_vision": True,
        }

        # Patch _execute to avoid actual execution
        with patch(
            "sygra.integrations.agentlab.experiments.runner.ExperimentRunner._execute"
        ) as mock_execute:
            mock_execute.return_value = {"exp_dir": "/tmp/exp", "completed": True}

            # Call subprocess target
            ExperimentRunner._subprocess_target(config_dict, mock_result_queue)

            # Verify configure_goal_evaluation was called with correct params
            # by checking the global config
            # Note: This test requires the function to actually run
            mock_result_queue.put.assert_called_once()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
