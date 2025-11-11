"""
AgentLab Integration for SyGra

Vision-Enhanced Web Agents using AgentLab's proven approach:
- Screenshots + Set-of-Mark (SoM) for visual understanding
- Browser ID (BID) actions for precise element interaction
- ExpArgs.run() for proper experiment execution

Quick Start:
    >>> from sygra.integrations.agentlab import (
    ...     create_web_agent,
    ...     create_custom_task
    ... )
    >>>
    >>> task = create_custom_task(
    ...     goal="Search for Python tutorials",
    ...     url="https://www.google.com"
    ... )
    >>>
    >>> workflow = sygra.Workflow("demo")
    >>> workflow.source([task])
    >>> workflow.add_node("agent", create_vision_web_agent())
    >>> workflow.run()
"""

try:
    from agentlab.agents.agent_args import AgentArgs  # type: ignore
    from bgym import EnvArgs  # type: ignore

    AGENTLAB_AVAILABLE = True

    # Core components - updated imports for organized structure
    # Custom task creation
    from sygra.integrations.agentlab.agents.web_agent_node import (
        WebAgentNode,
        create_web_agent_node,
    )
    from sygra.integrations.agentlab.tasks.custom_tasks import (
        CustomWebTask,
        create_custom_task,
        create_custom_tasks,
        create_ecommerce_task,
        create_form_filling_task,
        create_search_task,
        create_web_navigation_task,
    )

except ImportError:
    AGENTLAB_AVAILABLE = False
    AgentArgs = None  # type: ignore
    EnvArgs = None  # type: ignore
    WebAgentNode = None  # type: ignore
    create_web_agent_node = None  # type: ignore
    create_custom_task = None  # type: ignore
    create_custom_tasks = None  # type: ignore
    create_web_navigation_task = None  # type: ignore
    create_form_filling_task = None  # type: ignore
    create_search_task = None  # type: ignore
    create_ecommerce_task = None  # type: ignore
    CustomWebTask = None  # type: ignore

__all__ = [
    "create_custom_task",  # Create custom web tasks
    "create_custom_tasks",  # Create multiple tasks
    "create_web_navigation_task",  # Navigation task
    "create_form_filling_task",  # Form filling task
    "create_search_task",  # Search task
    "create_ecommerce_task",  # E-commerce task
    "CustomWebTask",  # Custom task class
    "WebAgentNode",  # Web agent node implementation
    "create_web_agent_node",  # Factory function
    "AGENTLAB_AVAILABLE",  # Check if AgentLab is installed
]
