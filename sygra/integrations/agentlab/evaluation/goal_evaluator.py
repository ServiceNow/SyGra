"""LLM-based goal evaluation for web agent tasks.

This module provides functionality to automatically evaluate whether a task goal
has been achieved by analyzing the agent's actions and current page state.
"""

from sygra.logger.logger_config import logger


class GoalEvaluator:
    """Evaluates whether a task goal has been achieved using LLM reasoning."""

    def __init__(
        self, model_name: str = "gpt-4o", temperature: float = 0.0, use_vision: bool = False
    ):
        """Initialize goal evaluator.

        Args:
            model_name: Model to use for evaluation
            temperature: Sampling temperature (0.0 for deterministic)
            use_vision: Whether to use vision (screenshots) for evaluation
        """
        self.model_name = model_name
        self.temperature = temperature
        self.use_vision = use_vision

    def evaluate_goal_completion(
        self,
        goal: str,
        trajectory: list[dict],
        current_observation: dict,
    ) -> tuple[bool, str, float]:
        """Evaluate if the goal has been achieved.

        Args:
            goal: The task goal to evaluate
            trajectory: List of steps taken so far
            current_observation: Current page state/observation

        Returns:
            Tuple of (is_complete, reasoning, confidence)
            - is_complete: Whether goal is achieved
            - reasoning: Explanation of the evaluation
            - confidence: Confidence score [0.0, 1.0]
        """
        # Build evaluation prompt
        prompt = self._build_evaluation_prompt(goal, trajectory, current_observation)
        logger.debug(f"Evaluation prompt: {prompt[:500]}")

        # Call LLM for evaluation
        try:
            # Get model from AgentLab
            model_args = self._get_model_args()
            model = model_args.make_model()

            # Build message with or without vision
            if self.use_vision and "screenshot" in current_observation:
                # Vision-enabled: send screenshot + text
                import base64

                screenshot = current_observation["screenshot"]

                # Encode screenshot to base64 if it's bytes
                if isinstance(screenshot, bytes):
                    image_data = base64.b64encode(screenshot).decode("utf-8")
                elif isinstance(screenshot, str):
                    # Assume it's already base64 or a path
                    image_data = screenshot
                else:
                    logger.warning(
                        f"Unknown screenshot type: {type(screenshot)}, falling back to text-only"
                    )
                    self.use_vision = False
                    messages = [{"role": "user", "content": prompt}]

                if self.use_vision:
                    # Format for vision models (OpenAI format)
                    messages = [
                        {
                            "role": "user",
                            "content": [  # type: ignore[dict-item]
                                {"type": "text", "text": prompt},
                                {
                                    "type": "image_url",
                                    "image_url": {"url": f"data:image/png;base64,{image_data}"},
                                },
                            ],
                        }
                    ]
                    logger.debug("Using vision for goal evaluation")
            else:
                # Text-only evaluation
                messages = [{"role": "user", "content": prompt}]
                if self.use_vision:
                    logger.debug("Vision enabled but no screenshot available, using text-only")

            # Call the model (it's callable)
            response = model(
                messages=messages,
                n_samples=1,
                temperature=self.temperature,
            )

            # Parse response - model returns a dict with choices
            if isinstance(response, dict) and "choices" in response:
                response_text = response["choices"][0]["message"]["content"]
            elif isinstance(response, str):
                response_text = response
            else:
                response_text = str(response)

            logger.debug(f"Evaluator response: {response_text[:200]}")

            result = self._parse_evaluation_response(response_text)

            return result

        except Exception as e:
            logger.error(f"Goal evaluation failed: {e}")
            logger.debug("Evaluation error:", exc_info=True)
            # On error, assume goal not complete
            return False, f"Evaluation error: {e}", 0.0

    def _build_evaluation_prompt(
        self, goal: str, trajectory: list[dict], current_observation: dict
    ) -> str:
        """Build prompt for goal evaluation."""

        # Summarize trajectory
        trajectory_summary = self._summarize_trajectory(trajectory)

        # Extract key page state info
        page_info = self._extract_page_info(current_observation)

        vision_note = (
            "\n\nA screenshot of the current page is provided for your analysis."
            if self.use_vision
            else ""
        )

        prompt = f"""You are evaluating whether a web automation task goal has been achieved.

GOAL: {goal}

RECENT ACTIONS:
{trajectory_summary}

CURRENT PAGE:
{page_info}{vision_note}

QUESTION: Has the goal been fully achieved based on the actions taken and current page state?

Respond EXACTLY in this format:
ANSWER: YES or NO
REASONING: [Brief explanation of your decision]
CONFIDENCE: [number between 0.0 and 1.0]

Examples:
- If goal is "Buy 1 pair of shoes" and order confirmation is shown → YES
- If goal is "Buy 1 pair of shoes" but only searched for shoes → NO
- If goal is "Buy 1 pair of shoes" and item is in cart but not purchased → NO
"""
        return prompt

    def _summarize_trajectory(self, trajectory: list[dict]) -> str:
        """Summarize the trajectory of actions."""
        if not trajectory:
            return "No actions taken yet."

        summary_lines = []
        for i, step in enumerate(trajectory, start=1):
            msg = step.get("message", "")
            if isinstance(msg, dict):
                role = msg.get("role", "")
                content = msg.get("message", "")
                if role and content:
                    summary_lines.append(f"{i}. [{role}] {content[:150]}")
            elif isinstance(msg, str):
                summary_lines.append(f"{i}. {msg[:150]}")

        return "\n".join(summary_lines) if summary_lines else "No clear action history available."

    def _extract_page_info(self, observation: dict) -> str:
        """Extract relevant information from current observation."""
        info_parts = []

        # URL
        if "url" in observation:
            info_parts.append(f"URL: {observation['url']}")

        # Page title
        if "title" in observation:
            info_parts.append(f"Title: {observation['title']}")

        # Page content (HTML truncated)
        if "content" in observation:
            content = observation["content"]
            # Look for important indicators
            if "cart" in content.lower():
                info_parts.append("✓ Page mentions 'cart'")
            if "checkout" in content.lower():
                info_parts.append("✓ Page mentions 'checkout'")
            if "success" in content.lower() or "thank you" in content.lower():
                info_parts.append("✓ Page mentions 'success' or 'thank you'")

            # Include truncated content
            info_parts.append(f"\nPage Content (first 800 chars):\n{content[:800]}")

        return "\n".join(info_parts) if info_parts else "No page information available"

    def _parse_evaluation_response(self, response: str) -> tuple[bool, str, float]:
        """Parse the LLM's evaluation response."""
        lines = response.strip().split("\n")

        is_complete = False
        reasoning = ""
        confidence = 0.5

        for line in lines:
            line = line.strip()

            if line.startswith("ANSWER:"):
                answer = line.replace("ANSWER:", "").strip().upper()
                is_complete = "YES" in answer

            elif line.startswith("REASONING:"):
                reasoning = line.replace("REASONING:", "").strip()

            elif line.startswith("CONFIDENCE:"):
                try:
                    confidence = float(line.replace("CONFIDENCE:", "").strip())
                except ValueError:
                    confidence = 0.5

        return is_complete, reasoning, confidence

    def _get_model_args(self):
        """Get model configuration for evaluation."""
        from agentlab.llm.llm_configs import AzureModelArgs  # type: ignore[import-untyped]

        return AzureModelArgs(
            model_name=self.model_name,
            temperature=self.temperature,
            vision_support=False,  # Text-only evaluation
        )


def evaluate_after_each_step(
    goal: str,
    trajectory: list[dict],
    current_observation: dict,
    enable_evaluation: bool = True,
) -> tuple[bool, str]:
    """Convenience function to evaluate goal after each step.

    Args:
        goal: Task goal
        trajectory: Action history
        current_observation: Current page state
        enable_evaluation: Whether to run evaluation (default: True)

    Returns:
        Tuple of (should_stop, reason)
    """
    if not enable_evaluation:
        return False, ""

    # Only evaluate after significant actions (not every step to save cost)
    if len(trajectory) < 3:
        return False, "Too early to evaluate"

    evaluator = GoalEvaluator()
    is_complete, reasoning, confidence = evaluator.evaluate_goal_completion(
        goal, trajectory, current_observation
    )

    if is_complete and confidence > 0.7:
        return True, f"Goal achieved: {reasoning}"

    return False, ""
