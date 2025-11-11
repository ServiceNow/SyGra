# AgentLab Integration

The AgentLab integration is organized into focused, maintainable modules with clear separation of concerns.

## Components

### **agents/** - Core Agent Functionality
- **`config.py`**: Agent configuration builder with vision models, action sets
- **`web_agent_node.py`**: Main SyGra node implementation for web automation

**Key Features:**
- Vision-enabled agent configuration
- SyGra node integration
- State management and result processing

### **tasks/** - Task Management
- **`custom_tasks.py`**: Factory functions for creating web tasks
- **`openended_task.py`**: Enhanced OpenEnded task with completion detection
- **`patches.py`**: Runtime patching of browsergym task classes

**Key Features:**
- Multiple task types (search, ecommerce, forms, navigation)
- Automatic goal evaluation integration
- Task completion detection

### **experiments/** - Experiment Execution
- **`runner.py`**: Subprocess-isolated experiment execution
- **`env_setup.py`**: Environment variable mapping and configuration

**Key Features:**
- Subprocess isolation for stability
- SyGra ↔ AgentLab environment variable mapping
- Timeout and error handling

### **display/** - SOM & Display Coordination
- **`coordinator.py`**: Cross-platform display environment setup
- **`overlay_fix.py`**: Production SOM coordinate fix for high-DPI displays

**Key Features:**
- Automatic high-DPI display detection
- Cross-platform coordinate scaling
- Runtime patching of SOM overlay functions

### **evaluation/** - Goal Evaluation & Results
- **`goal_evaluator.py`**: LLM-based goal completion evaluation
- **`result_loader.py`**: Experiment result loading and processing

**Key Features:**
- Vision-enabled goal evaluation
- Automatic completion detection
- Result parsing and analysis

### **utils/** - Utility Functions
- **`utils.py`**: Trajectory processing, data export, statistics

**Key Features:**
- Training data export
- Trajectory analysis
- Action extraction


## Imports

### **Public API**
```python
# Use the main module for common functionality
from sygra.integrations.agentlab import (
    create_custom_task,
    WebAgentNode,
    create_web_agent_node
)
```

### **Modules**
```python
# Direct access to specific modules
from sygra.integrations.agentlab.agents.config import AgentConfigBuilder
from sygra.integrations.agentlab.display.overlay_fix import patch_som_overlay
from sygra.integrations.agentlab.evaluation.goal_evaluator import GoalEvaluator
```
