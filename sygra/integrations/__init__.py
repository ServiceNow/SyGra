"""
SyGra Integrations Module

Provides integration adapters for external frameworks and tools.

Available Integrations:
- AgentLab: Web agent evaluation framework integration
"""

try:
    from sygra.integrations.agentlab import AGENTLAB_AVAILABLE

    __all__ = [
        "AGENTLAB_AVAILABLE",
    ]
except ImportError:
    # AgentLab integration not available
    __all__ = []
