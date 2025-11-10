# SyGra Integrations

SyGra integrates with external frameworks and tools to extend its capabilities beyond core synthetic data generation.

## Available Integrations

### AgentLab - Vision-Enhanced Web Automation

Build autonomous web agents that can navigate websites, complete tasks, and generate training data using GPT-4o and visual grounding.

**Key Features:**
- **Vision-First**: Screenshots + Set-of-Mark (SOM) overlays for visual understanding
- **Precise Interaction**: Browser ID (BID) actions for exact targeting
- **Smart Completion**: Agent signals + LLM-based goal evaluation
- **Training Data**: Complete trajectories with coordinates for RL/imitation learning

**Quick Start:**

```yaml
# graph_config.yaml
graph_config:
  nodes:
    web_agent:
      node_type: web_agent
      model: gpt-4o
      max_steps: 15
      enable_goal_eval: true
      eval_use_vision: true
```

**Documentation:**
- **[Overview](./agentlab/index.md)** - Getting started and features
- **[Complete Guide](./agentlab/documentation.md)** - Comprehensive documentation
- **[Quick Reference](./agentlab/quick_reference.md)** - One-page cheat sheet

**Use Cases:**
- Collect training data for web agents (with action coordinates)
- Automate web testing and quality assurance
- Build autonomous task completion systems
- Research agent capabilities on real websites
