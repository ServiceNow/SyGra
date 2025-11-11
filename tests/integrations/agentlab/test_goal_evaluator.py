"""
Tests for Goal Evaluator

Tests LLM-based goal evaluation including text-only and vision-enabled modes.
"""

from unittest.mock import Mock, patch

import pytest

try:
    from sygra.integrations.agentlab.evaluation.goal_evaluator import GoalEvaluator

    AGENTLAB_AVAILABLE = True
except ImportError:
    AGENTLAB_AVAILABLE = False


@pytest.mark.skipif(not AGENTLAB_AVAILABLE, reason="AgentLab not installed")
class TestGoalEvaluator:
    """Test GoalEvaluator class"""

    def test_initialization_text_only(self):
        """Test initializing evaluator without vision"""
        evaluator = GoalEvaluator(model_name="gpt-4o", temperature=0.0, use_vision=False)

        assert evaluator.model_name == "gpt-4o"
        assert evaluator.temperature == 0.0
        assert evaluator.use_vision is False

    def test_initialization_with_vision(self):
        """Test initializing evaluator with vision enabled"""
        evaluator = GoalEvaluator(model_name="gpt-4o", temperature=0.0, use_vision=True)

        assert evaluator.use_vision is True

    @patch("sygra.integrations.agentlab.evaluation.goal_evaluator.GoalEvaluator._get_model_args")
    def test_evaluate_goal_completion_text_only(self, mock_get_model_args):
        """Test text-only goal evaluation"""
        # Setup mock model
        mock_model = Mock()
        mock_model.return_value = {
            "choices": [
                {
                    "message": {
                        "content": "ANSWER: YES\nREASONING: Task completed successfully\nCONFIDENCE: 0.95"
                    }
                }
            ]
        }

        mock_model_args = Mock()
        mock_model_args.make_model.return_value = mock_model
        mock_get_model_args.return_value = mock_model_args

        evaluator = GoalEvaluator(use_vision=False)

        goal = "Buy 1 pair of running shoes"
        trajectory = [
            {"message": "Searching for shoes"},
            {"message": "Adding to cart"},
            {"message": "Checking out"},
        ]
        observation = {
            "url": "https://example.com/success",
            "title": "Order Confirmation",
            "content": "Thank you for your order",
        }

        is_complete, reasoning, confidence = evaluator.evaluate_goal_completion(
            goal, trajectory, observation
        )

        assert is_complete is True
        assert "Task completed successfully" in reasoning
        assert confidence == 0.95

        # Verify model was called with text-only message
        mock_model.assert_called_once()
        call_args = mock_model.call_args
        messages = call_args[1]["messages"]
        assert isinstance(messages[0]["content"], str)  # Text-only

    @patch("sygra.integrations.agentlab.evaluation.goal_evaluator.GoalEvaluator._get_model_args")
    def test_evaluate_goal_completion_with_vision(self, mock_get_model_args):
        """Test vision-enabled goal evaluation"""
        # Setup mock model
        mock_model = Mock()
        mock_model.return_value = {
            "choices": [
                {
                    "message": {
                        "content": "ANSWER: YES\nREASONING: Order confirmation visible\nCONFIDENCE: 1.0"
                    }
                }
            ]
        }

        mock_model_args = Mock()
        mock_model_args.make_model.return_value = mock_model
        mock_get_model_args.return_value = mock_model_args

        evaluator = GoalEvaluator(use_vision=True)

        goal = "Buy 1 pair of running shoes"
        trajectory = [{"message": "Placed order"}]
        observation = {
            "url": "https://example.com/success",
            "title": "Order Confirmation",
            "content": "Order placed",
            "screenshot": b"fake_png_data",
        }

        is_complete, reasoning, confidence = evaluator.evaluate_goal_completion(
            goal, trajectory, observation
        )

        assert is_complete is True
        assert confidence == 1.0

        # Verify model was called with vision message
        mock_model.assert_called_once()
        call_args = mock_model.call_args
        messages = call_args[1]["messages"]
        assert isinstance(messages[0]["content"], list)  # Multi-modal

    @patch("sygra.integrations.agentlab.evaluation.goal_evaluator.GoalEvaluator._get_model_args")
    def test_evaluate_goal_not_complete(self, mock_get_model_args):
        """Test evaluation when goal is not complete"""
        mock_model = Mock()
        mock_model.return_value = {
            "choices": [
                {
                    "message": {
                        "content": "ANSWER: NO\nREASONING: Only searched, not purchased\nCONFIDENCE: 0.85"
                    }
                }
            ]
        }

        mock_model_args = Mock()
        mock_model_args.make_model.return_value = mock_model
        mock_get_model_args.return_value = mock_model_args

        evaluator = GoalEvaluator()

        goal = "Buy 1 pair of running shoes"
        trajectory = [{"message": "Searched for shoes"}]
        observation = {
            "url": "https://example.com/search",
            "title": "Search Results",
            "content": "Search results for running shoes",
        }

        is_complete, reasoning, confidence = evaluator.evaluate_goal_completion(
            goal, trajectory, observation
        )

        assert is_complete is False
        assert "Only searched" in reasoning
        assert confidence == 0.85

    def test_parse_evaluation_response_valid(self):
        """Test parsing valid evaluation response"""
        evaluator = GoalEvaluator()

        response = """
        ANSWER: YES
        REASONING: The order has been successfully placed
        CONFIDENCE: 0.95
        """

        is_complete, reasoning, confidence = evaluator._parse_evaluation_response(response)

        assert is_complete is True
        assert "order has been successfully placed" in reasoning
        assert confidence == 0.95

    def test_parse_evaluation_response_no(self):
        """Test parsing NO response"""
        evaluator = GoalEvaluator()

        response = """
        ANSWER: NO
        REASONING: Item only added to cart, not purchased
        CONFIDENCE: 0.90
        """

        is_complete, reasoning, confidence = evaluator._parse_evaluation_response(response)

        assert is_complete is False
        assert "not purchased" in reasoning
        assert confidence == 0.90

    def test_parse_evaluation_response_malformed(self):
        """Test handling malformed response"""
        evaluator = GoalEvaluator()

        response = "Some random text without proper format"

        is_complete, reasoning, confidence = evaluator._parse_evaluation_response(response)

        # Should return conservative defaults
        assert is_complete is False
        assert reasoning == ""  # No REASONING: line found
        assert confidence == 0.5  # Default confidence

    def test_build_evaluation_prompt(self):
        """Test prompt building"""
        evaluator = GoalEvaluator(use_vision=False)

        goal = "Buy shoes"
        trajectory = [{"message": "Searched"}]
        observation = {"url": "http://example.com", "title": "Test"}

        prompt = evaluator._build_evaluation_prompt(goal, trajectory, observation)

        assert "Buy shoes" in prompt
        assert "ANSWER: YES or NO" in prompt
        assert "REASONING:" in prompt
        assert "CONFIDENCE:" in prompt

    def test_build_evaluation_prompt_with_vision(self):
        """Test prompt includes vision note when enabled"""
        evaluator = GoalEvaluator(use_vision=True)

        goal = "Buy shoes"
        trajectory = []
        observation = {"url": "http://example.com"}

        prompt = evaluator._build_evaluation_prompt(goal, trajectory, observation)

        assert "screenshot" in prompt.lower()

    def test_extract_page_info(self):
        """Test page info extraction"""
        evaluator = GoalEvaluator()

        observation = {
            "url": "https://example.com/cart",
            "title": "Shopping Cart",
            "content": "Your cart contains 1 item. Total: $50. Proceed to checkout.",
        }

        page_info = evaluator._extract_page_info(observation)

        assert "https://example.com/cart" in page_info
        assert "Shopping Cart" in page_info
        assert "cart" in page_info.lower()
        assert "checkout" in page_info.lower()

    def test_summarize_trajectory_empty(self):
        """Test trajectory summarization with empty list"""
        evaluator = GoalEvaluator()

        summary = evaluator._summarize_trajectory([])

        assert "No actions" in summary or "yet" in summary

    def test_summarize_trajectory_with_messages(self):
        """Test trajectory summarization with messages"""
        evaluator = GoalEvaluator()

        trajectory = [
            {"message": "Step 1: Searching"},
            {"message": "Step 2: Adding to cart"},
            {"message": "Step 3: Checkout"},
        ]

        summary = evaluator._summarize_trajectory(trajectory)

        assert "Searching" in summary
        assert "Adding to cart" in summary
        assert "Checkout" in summary


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
