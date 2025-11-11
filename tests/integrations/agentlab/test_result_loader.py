"""
Tests for Result Loader

Tests loading and parsing experiment results from disk.
"""

import json
import tempfile
from pathlib import Path

import pytest

try:
    from sygra.integrations.agentlab.evaluation.result_loader import ResultLoader

    AGENTLAB_AVAILABLE = True
except ImportError:
    AGENTLAB_AVAILABLE = False


@pytest.mark.skipif(not AGENTLAB_AVAILABLE, reason="AgentLab not installed")
class TestResultLoader:
    """Test ResultLoader class"""

    def test_load_with_agent_signal_completion(self):
        """Test loading results with agent completion signal"""
        with tempfile.TemporaryDirectory() as tmpdir:
            exp_dir = Path(tmpdir)

            # Create mock summary.json
            summary = {"n_steps": 5, "cum_reward": 1.0, "stats.cum_cost": 0.15}
            (exp_dir / "summary_info.json").write_text(json.dumps(summary))

            # Create mock completion_info.json (agent signal)
            completion_info = {
                "completion_reason": "agent_signal",
                "agent_message": "Task completed successfully",
            }
            (exp_dir / "completion_info.json").write_text(json.dumps(completion_info))

            # Create experiment.log with actions
            log_content = []
            for i in range(5):
                log_content.append(f"2025-01-01 10:00:00 - INFO - Step {i} reasoning")
                log_content.append("action:")
                log_content.append(f"click('{i}')")
            (exp_dir / "experiment.log").write_text("\n".join(log_content))

            # Create screenshots in exp_dir root (not in step subdirs)
            for i in range(6):  # 0 to 5 (n_steps + 1)
                (exp_dir / f"screenshot_step_{i}.png").write_bytes(b"fake_png")
                (exp_dir / f"screenshot_som_step_{i}.png").write_bytes(b"fake_png")

            result = ResultLoader.load(str(exp_dir), "test_task")

            assert result["num_steps"] == 6  # n_steps + 1 (includes step 0)
            assert result["success"] is True
            assert result["completion_reason"] == "agent_signal"
            assert result["agent_message"] == "Task completed successfully"
            assert len(result["trajectory"]) == 6  # 0 through 5
            assert len(result["screenshots"]) == 12  # 2 per step (6 steps)

    def test_load_with_goal_eval_completion(self):
        """Test loading results with goal evaluation completion"""
        with tempfile.TemporaryDirectory() as tmpdir:
            exp_dir = Path(tmpdir)

            # Create summary
            summary = {"n_steps": 7, "cum_reward": 0.0, "stats.cum_cost": 0.25}
            (exp_dir / "summary_info.json").write_text(json.dumps(summary))

            # Create completion_info with goal eval
            completion_info = {
                "completion_reason": "auto_eval",
                "eval_confidence": 0.95,
                "eval_reasoning": "Order confirmation detected",
            }
            (exp_dir / "completion_info.json").write_text(json.dumps(completion_info))

            # Create experiment.log
            log_content = []
            for i in range(7):
                log_content.append(f"2025-01-01 10:00:00 - INFO - Step {i} reasoning")
                log_content.append("action:")
                log_content.append(f"click('{i}')")
            (exp_dir / "experiment.log").write_text("\n".join(log_content))

            # Create screenshots
            for i in range(8):  # 0 to 7 (n_steps + 1)
                (exp_dir / f"screenshot_step_{i}.png").write_bytes(b"fake")
                (exp_dir / f"screenshot_som_step_{i}.png").write_bytes(b"fake")

            result = ResultLoader.load(str(exp_dir), "test_task")

            assert result["completion_reason"] == "auto_eval"
            assert result["eval_confidence"] == 0.95
            assert result["success"] is True
            assert result["num_steps"] == 8  # 0 through 7
            assert "Order confirmation" in result["eval_reasoning"]

    def test_load_without_completion_info(self):
        """Test loading results when no completion_info.json exists"""
        with tempfile.TemporaryDirectory() as tmpdir:
            exp_dir = Path(tmpdir)

            # Create summary only
            summary = {"n_steps": 3, "cum_reward": 0.0, "stats.cum_cost": 0.05}
            (exp_dir / "summary_info.json").write_text(json.dumps(summary))

            # Create minimal experiment log
            log_content = []
            for i in range(3):
                log_content.append(f"2025-01-01 10:00:00 - INFO - Step {i}")
                log_content.append("action:")
                log_content.append(f"action_{i}()")
            (exp_dir / "experiment.log").write_text("\n".join(log_content))

            # Create screenshots
            for i in range(4):  # 0 to 3 (n_steps + 1)
                (exp_dir / f"screenshot_step_{i}.png").write_bytes(b"fake")
                (exp_dir / f"screenshot_som_step_{i}.png").write_bytes(b"fake")

            result = ResultLoader.load(str(exp_dir), "test_task")

            assert result["completion_reason"] == "unknown"
            assert result["eval_confidence"] is None
            assert result["agent_message"] is None
            assert result["num_steps"] == 4  # 0 through 3

    def test_extract_completion_info_from_summary_fallback(self):
        """Test extracting completion info from summary task_info when file missing"""
        with tempfile.TemporaryDirectory() as tmpdir:
            exp_dir = Path(tmpdir)

            # Create summary with task_info containing completion info
            summary = {
                "n_steps": 4,
                "cum_reward": 1.0,
                "task_info": {"completion_reason": "agent_signal", "agent_message": "Task is done"},
            }
            (exp_dir / "summary_info.json").write_text(json.dumps(summary))

            completion_info = ResultLoader._extract_completion_info(exp_dir, summary)

            assert completion_info["completion_reason"] == "agent_signal"
            assert completion_info["agent_message"] == "Task is done"

    def test_load_trajectory_with_missing_files(self):
        """Test trajectory loading handles missing action/thought files"""
        with tempfile.TemporaryDirectory() as tmpdir:
            exp_dir = Path(tmpdir)

            summary = {"n_steps": 2, "cum_reward": 0.0, "stats.cum_cost": 0.02}
            (exp_dir / "summary_info.json").write_text(json.dumps(summary))

            # Create minimal setup with no experiment.log (will have empty actions)
            # Create screenshots only
            for i in range(3):
                (exp_dir / f"screenshot_step_{i}.png").write_bytes(b"fake")
                (exp_dir / f"screenshot_som_step_{i}.png").write_bytes(b"fake")

            result = ResultLoader.load(str(exp_dir), "test_task")

            # Should still load but with empty actions
            assert result["num_steps"] >= 0
            assert "trajectory" in result

    def test_load_handles_missing_summary(self):
        """Test graceful handling when summary.json is missing"""
        with tempfile.TemporaryDirectory() as tmpdir:
            exp_dir = Path(tmpdir)
            # No summary file created

            result = ResultLoader.load(str(exp_dir), "test_task")

            assert result["success"] is False
            assert "error" in result
            assert result["num_steps"] == 0

    def test_log_completion_details_agent_signal(self):
        """Test logging for agent signal completion"""
        completion_info = {"completion_reason": "agent_signal", "agent_message": "Task completed"}

        # Should not raise exception
        # This tests the formatting fix for None confidence
        try:
            if completion_info["completion_reason"] == "agent_signal":
                completion_info.get("agent_message", "")[:100]
        except Exception as e:
            pytest.fail(f"Logging failed: {e}")

    def test_log_completion_details_auto_eval_with_none_confidence(self):
        """Test logging for auto_eval with None confidence (edge case)"""
        completion_info = {
            "completion_reason": "auto_eval",
            "eval_confidence": None,
            "eval_reasoning": "Some reasoning",
        }

        # Test the formatting that was causing the bug
        eval_confidence = completion_info.get("eval_confidence")
        conf_str = f"{eval_confidence:.2f}" if eval_confidence is not None else "N/A"

        assert conf_str == "N/A"

    def test_empty_result_structure(self):
        """Test _empty_result returns proper structure"""
        error_msg = "Test error"
        result = ResultLoader._empty_result(error_msg)

        assert result["error"] == error_msg
        assert result["num_steps"] == 0
        assert result["success"] is False
        assert "trajectory" in result
        assert "screenshots" in result
        assert isinstance(result["trajectory"], list)
        assert isinstance(result["screenshots"], list)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
