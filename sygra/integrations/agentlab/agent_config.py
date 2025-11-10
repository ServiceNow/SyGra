"""Agent configuration builder for AgentLab integration.

Provides a clean interface to build AgentLab AgentArgs from simple parameters.
"""

from agentlab.agents.agent_args import AgentArgs

__all__ = ["AgentConfigBuilder"]


class AgentConfigBuilder:
    """Builds AgentLab agent configurations from simple parameters.

    Encapsulates the complexity of AgentLab's configuration system,
    providing a simple interface for common use cases.
    """

    VISION_MODELS = {"gpt-4o", "gpt-4o-mini", "gpt-4-vision-preview"}

    @staticmethod
    def build(
        model: str = "gpt-4o",
        temperature: float = 0.1,
        use_screenshot: bool = True,
        use_som: bool = True,
        use_html: bool = False,
        use_ax_tree: bool = True,
        enable_chat: bool = True,
    ) -> AgentArgs:
        """Build AgentArgs from simple parameters.

        Args:
            model: Model identifier ("gpt-4o", "gpt-4o-mini")
            temperature: Sampling temperature, range [0.0, 1.0]
            use_screenshot: Enable screenshot observations
            use_som: Enable Set-of-Mark overlays for element identification
            use_html: Enable HTML page structure observations
            use_ax_tree: Enable accessibility tree (can cause agent to use labels instead of BIDs)
            enable_chat: Enable chat actions (send_msg_to_user) for task completion signaling

        Returns:
            Configured AgentArgs instance ready for experiment execution

        Note:
            - When use_som=True, set use_ax_tree=False to ensure agent uses BIDs only.
              Having both enabled can confuse the agent to use accessibility labels
              instead of BID numbers, causing action parsing failures.
            - When enable_chat=True, agent can use send_msg_to_user() to signal task completion.
              This is essential for openended tasks to allow the agent to stop when done.
        """
        import agentlab.agents.dynamic_prompting as dp
        from agentlab.agents.generic_agent.generic_agent import GenericAgentArgs
        from agentlab.agents.generic_agent.generic_agent_prompt import GenericPromptFlags
        from agentlab.llm.llm_configs import AzureModelArgs
        from bgym import HighLevelActionSetArgs

        vision_enabled = model in AgentConfigBuilder.VISION_MODELS

        model_args = AzureModelArgs(
            model_name=model,
            temperature=temperature,
            vision_support=vision_enabled,
        )

        # Configure action subsets based on enable_chat flag
        action_subsets = ["bid"]
        if enable_chat:
            action_subsets.append("chat")

        return GenericAgentArgs(
            chat_model_args=model_args,
            flags=GenericPromptFlags(
                obs=dp.ObsFlags(
                    use_html=use_html,
                    use_ax_tree=use_ax_tree,
                    use_screenshot=use_screenshot,
                    use_som=use_som,
                ),
                action=dp.ActionFlags(
                    multi_actions=False,
                    action_set=HighLevelActionSetArgs(
                        subsets=action_subsets,
                        strict=True,
                        retry_with_force=True,
                    ),
                ),
                use_thinking=True,
                use_plan=True,  # Enable planning to help agent track progress
                enable_chat=enable_chat,
                extra_instructions=(
                    "\n**IMPORTANT**: After each action, verify if the goal is achieved. "
                    "If the goal is complete, you MUST use send_msg_to_user('Goal completed: [explanation]') "
                    "to signal completion. Do NOT continue taking actions after the goal is met."
                    if enable_chat
                    else None
                ),
            ),
        )
