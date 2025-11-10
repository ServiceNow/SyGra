# AgentLab Integration for SyGra

**Vision-enhanced web automation agents powered by AgentLab and GPT-4o**

## Table of Contents

1. [Overview](#overview)
2. [Features](#features)
3. [Installation](#installation)
4. [Quick Start](#quick-start)
5. [Core Concepts](#core-concepts)
6. [Configuration Reference](#configuration-reference)
7. [Goal Evaluation](#goal-evaluation)
8. [Task Creation](#task-creation)
9. [Output Structure](#output-structure)
10. [API Reference](#api-reference)
11. [Examples](#examples)
12. [Advanced Topics](#advanced-topics)
13. [Troubleshooting](#troubleshooting)

---

## Overview

The AgentLab integration brings vision-enabled web automation capabilities to SyGra, enabling LLM agents to:

- **Navigate websites** using visual understanding (screenshots + Set-of-Mark overlays)
- **Interact with web elements** using precise Browser ID (BID) targeting
- **Complete complex tasks** across any website (e-commerce, forms, search, etc.)
- **Automatically detect completion** via agent signals or LLM-based goal evaluation
- **Generate training data** from successful trajectories with full action coordinates

### What Makes It Unique

- **Vision-First**: Uses screenshots with Set-of-Mark (SOM) overlays for visual understanding
- **Precise Interaction**: BID-based actions enable coordinate extraction for training
- **Smart Termination**: Dual completion detection (agent signals + LLM goal evaluation)
- **Production-Ready**: Subprocess isolation, error handling, comprehensive logging
- **Training-Friendly**: Complete trajectories with coordinates for RL/imitation learning

---

## Features

### Core Capabilities

- **Web Agent Node** (`WebAgentNode`): SyGra node for browser automation
- **Custom Tasks**: Create open-ended tasks for any website
- **Visual Grounding**: Screenshot + SOM overlays for element identification
- **BID Actions**: Precise `click('285')`, `fill('42', 'text')` for reliable interaction
- **Chat Actions**: Agent can use `send_msg_to_user()` to signal task completion

### Goal Evaluation

- **Automatic Evaluation**: LLM-based goal assessment at configurable intervals
- **Vision-Enabled**: Uses screenshots for accurate completion detection
- **Confidence Scores**: Returns confidence level (0.0-1.0) with reasoning
- **Early Termination**: Stops execution when goal is achieved (confidence ≥ 0.7)

### Data Collection

- **Complete Trajectories**: Full action history with reasoning
- **Screenshots**: Both regular and SOM overlay images (base64 encoded)
- **Coordinates**: Mouse action coordinates (`center_x`, `center_y`, `bbox`)
- **Metrics**: Steps, cost, success rate, completion reason
- **Export**: Convert trajectories to training datasets (instruction-following, chat, QA)

---

## Installation

### Prerequisites

```bash
# AgentLab and dependencies
pip install agentlab browsergym

# Or using Poetry (recommended)
poetry add agentlab browsergym
```

### Environment Setup

Create a `.env` file in your project root:

```env
# Azure OpenAI credentials (required)
SYGRA_GPT-4O_URL=https://your-azure-endpoint.openai.azure.com/
SYGRA_GPT-4O_TOKEN=your-api-key-here

# Optional: GPT-4o-mini credentials
SYGRA_GPT-4O-MINI_URL=https://your-azure-endpoint.openai.azure.com/
SYGRA_GPT-4O-MINI_TOKEN=your-api-key-here
```

**Note**: The integration automatically maps `SYGRA_<MODEL>_URL` → `AZURE_OPENAI_ENDPOINT` and `SYGRA_<MODEL>_TOKEN` → `AZURE_OPENAI_API_KEY` when experiments run.

### Verify Installation

```python
from sygra.integrations.agentlab import AGENTLAB_AVAILABLE

if AGENTLAB_AVAILABLE:
    print("✓ AgentLab integration is ready!")
else:
    print("✗ AgentLab not installed")
```

---

## Quick Start

### 1. Create Task Data

Create `tasks/my_web_task/tasks.jsonl`:

```jsonl
{"id": "demo1", "goal": "Buy 1 pair of running shoes.", "url": "https://www.amazon.com", "task_name": "custom.demo1", "task_type": "custom"}
```

### 2. Configure Workflow

Create `tasks/my_web_task/graph_config.yaml`:

```yaml
data_config:
  source:
    type: "disk"
    file_path: "tasks/my_web_task/tasks.jsonl"

graph_config:
  nodes:
    web_agent:
      node_type: web_agent
      model: gpt-4o
      max_steps: 15
      headless: false
      use_screenshot: true
      use_som: true
      enable_chat: true

  edges:
    - from: START
      to: web_agent
    - from: web_agent
      to: END

output_config:
  output_map:
    goal: { from: "goal" }
    agent_result: { from: "agent_result" }
    trajectory: { from: "trajectory" }
```

### 3. Run Workflow

```bash
poetry run python main.py -t my_web_task -n 1
```

### 4. Check Results

Results are saved in `tasks/my_web_task/output_*.json` with:
- Agent result summary (steps, success, cost)
- Full trajectory with actions and reasoning
- Screenshots (base64 encoded)
- Experiment artifacts directory path

---

## Core Concepts

### Web Agent Node

The `WebAgentNode` is a SyGra node that executes browser automation tasks using AgentLab:

```python
from sygra.integrations.agentlab import WebAgentNode

node = WebAgentNode(
    node_name="web_agent",
    model="gpt-4o",
    max_steps=15,
    headless=False,
    use_screenshot=True,
    use_som=True,
    enable_chat=True
)
```

**Execution Flow:**
1. Receives task (goal + URL) from state
2. Creates AgentLab experiment in subprocess
3. Agent takes actions until completion or max_steps
4. Loads results (trajectory, screenshots, metrics)
5. Updates state with results

### Browser ID (BID) Actions

AgentLab uses **Browser IDs** for precise element targeting:

```python
# Agent generates BID-based actions
click('285')           # Click element with BID 285
fill('42', 'shoes')    # Fill input field 42 with "shoes"
```

**Why BIDs?**
-  Precise coordinate extraction for training
-  No action parsing failures
-  Works across dynamic page structures

### Set-of-Mark (SOM) Overlays

SOM overlays display BIDs directly on screenshots:

```yaml
use_som: true   # Enable SOM overlays
use_html: false # Disable HTML to avoid confusion
```

**Visual Example:**
```
[Screenshot with overlays]
  285  ← Running Shoes category
  42   ← Search input field
  1760 ← Add to cart button
```

### Completion Detection

Two mechanisms detect task completion:

#### 1. Agent Signal (Chat Action)
Agent uses `send_msg_to_user()` to signal completion:

```python
# Agent's final action
send_msg_to_user("Task completed: Added shoes to cart and checked out")
```

**Configuration:**
```yaml
enable_chat: true  # Required for agent signals
```

#### 2. Goal Evaluation (Automatic)
LLM evaluates goal completion at intervals:

```yaml
enable_goal_eval: true    # Enable automatic evaluation
eval_frequency: 2         # Every 2 steps
eval_start_step: 3        # Start after step 3
eval_use_vision: true     # Use screenshots (more accurate)
```

**How It Works:**
- Takes screenshot at evaluation steps
- LLM analyzes: goal + trajectory + page state + screenshot
- Returns: `(is_complete: bool, reasoning: str, confidence: float)`
- Terminates if `is_complete=True` and `confidence >= 0.7`

---

## Configuration Reference

### WebAgentNode Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `node_name` | str | **required** | Unique node identifier |
| `model` | str | `"gpt-4o"` | Model name (gpt-4o, gpt-4o-mini) |
| `max_steps` | int | `15` | Maximum steps before timeout |
| `headless` | bool | `True` | Run browser in headless mode |
| `use_screenshot` | bool | `True` | Capture screenshots |
| `use_som` | bool | `True` | Enable Set-of-Mark overlays |
| `use_html` | bool | `False` | Include HTML in observations |
| `temperature` | float | `0.1` | LLM sampling temperature |
| `viewport_width` | int | `1280` | Browser viewport width |
| `viewport_height` | int | `720` | Browser viewport height |
| `slow_mo` | int | `0` | Slow down actions (ms) |
| `enable_chat` | bool | `True` | Allow agent completion signals |
| `enable_goal_eval` | bool | `False` | Enable LLM goal evaluation |
| `eval_frequency` | int | `2` | Evaluate every N steps |
| `eval_start_step` | int | `3` | Start evaluating after step N |
| `eval_use_vision` | bool | `False` | Use screenshots in evaluation |

### YAML Configuration Example

```yaml
graph_config:
  nodes:
    web_agent:
      node_type: web_agent

      # Model Configuration
      model: gpt-4o
      temperature: 0.1

      # Execution Limits
      max_steps: 20

      # Browser Settings
      headless: false          # Show browser (useful for debugging)
      viewport_width: 1380
      viewport_height: 820
      slow_mo: 600            # Slow down for observation

      # Observation Settings
      use_screenshot: true     # Required for visual grounding
      use_som: true           # BID overlays (recommended)
      use_html: false         # Disable to avoid confusion

      # Completion Detection
      enable_chat: true        # Agent can signal completion
      enable_goal_eval: true   # LLM-based goal evaluation
      eval_frequency: 2        # Check every 2 steps
      eval_start_step: 3       # Start checking at step 3
      eval_use_vision: true    # Use screenshots (more accurate)
```

---

## Goal Evaluation

### Overview

Goal evaluation enables agents to automatically detect when tasks are complete, without requiring explicit agent signals. This is especially useful for:

- **Complex tasks** where completion is subjective
- **Visual confirmation** (e.g., "order placed" confirmation page)
- **Fallback mechanism** when agent forgets to signal completion

### Configuration

Enable goal evaluation in `graph_config.yaml`:

```yaml
web_agent:
  node_type: web_agent
  model: gpt-4o
  enable_goal_eval: true      # Enable feature
  eval_frequency: 2           # Check every 2 steps
  eval_start_step: 3          # Start at step 3
  eval_use_vision: true       # Use screenshots (recommended)
```

### How It Works

**Evaluation Process:**

1. **Capture State** (every `eval_frequency` steps after `eval_start_step`)
   - Current page URL, title, content
   - Screenshot (if `eval_use_vision=true`)
   - Recent trajectory actions

2. **LLM Evaluation**
   - Prompt: "Has the goal been achieved?"
   - Input: Goal + trajectory + page state + screenshot
   - Output: YES/NO + reasoning + confidence (0.0-1.0)

3. **Termination Decision**
   ```python
   if is_complete and confidence >= 0.7:
       terminate_task()
   ```

**Example Evaluation:**

```
Goal: Buy 1 pair of running shoes
Current URL: https://store.com/order-confirmation
Screenshot: [Shows "Order #12345 confirmed" page]

LLM Response:
  ANSWER: YES
  REASONING: Order confirmation page visible with order number, indicating purchase completed
  CONFIDENCE: 1.0

→ Task terminates successfully
```

### Text-Only vs Vision-Enabled

| Mode | Accuracy | Cost | Use Case |
|------|----------|------|----------|
| **Text-Only** (`eval_use_vision=false`) | Lower | Lower | Simple tasks, URL/text-based confirmation |
| **Vision-Enabled** (`eval_use_vision=true`) | Higher | Higher | Visual confirmation required (order pages, modals) |

**Recommendation**: Use `eval_use_vision=true` for production tasks where accuracy matters.

### Results

Completion information is stored in results:

```json
{
  "agent_result": {
    "success": true,
    "num_steps": 7,
    "completion_reason": "auto_eval",
    "eval_confidence": 0.95,
    "eval_reasoning": "Order confirmation page displayed"
  }
}
```

**Completion Reasons:**
- `"agent_signal"`: Agent used `send_msg_to_user()`
- `"auto_eval"`: Goal evaluation detected completion
- `"user_exit"`: User requested exit
- `"unknown"`: Reached max_steps without completion

---

## Task Creation

### Using Helper Functions

#### Simple Custom Task

```python
from sygra.integrations.agentlab import create_custom_task

task = create_custom_task(
    goal="Search for Python tutorials",
    url="https://www.google.com",
    task_id="search_001"
)
```

#### E-commerce Task

```python
from sygra.integrations.agentlab import create_ecommerce_task

task = create_ecommerce_task(
    site_url="https://www.amazon.com",
    action="search_and_add_to_cart",
    product="wireless mouse",
    quantity=2
)
```

#### Form Filling Task

```python
from sygra.integrations.agentlab import create_form_filling_task

task = create_form_filling_task(
    url="https://forms.example.com/contact",
    goal="Fill out contact form",
    form_data={
        "name": "John Doe",
        "email": "john@example.com",
        "message": "Hello!"
    }
)
```

#### Multiple Tasks

```python
from sygra.integrations.agentlab import create_custom_tasks

tasks = create_custom_tasks([
    {
        "goal": "Search for flights from SFO to JFK",
        "url": "https://www.google.com/flights"
    },
    {
        "goal": "Find hotels in New York",
        "url": "https://www.booking.com"
    }
])
```

### Manual Task Creation

Create tasks in JSONL format:

```jsonl
{"id": "task1", "goal": "Buy shoes", "url": "https://amazon.com", "task_name": "custom.task1", "task_type": "custom"}
{"id": "task2", "goal": "Book flight", "url": "https://expedia.com", "task_name": "custom.task2", "task_type": "custom"}
```

**Required Fields:**
- `goal`: Natural language task description
- `url`: Starting URL
- `task_name`: Unique identifier (format: `custom.<id>`)
- `task_type`: Must be `"custom"`

---

## Output Structure

### Directory Layout

After running a workflow, outputs are organized as:

```
tasks/my_task/
├── graph_config.yaml           # Workflow configuration
├── tasks.jsonl                 # Input tasks
├── output_2025-*.json          # Results summary
└── web_agents/                 # Experiment artifacts
    └── 2025-11-09_*_custom.demo/
        ├── complete_output.json    # Full trajectory with coordinates
        ├── summary_info.json       # Metrics (steps, cost, time)
        ├── completion_info.json    # Completion details
        ├── experiment.log          # Detailed logs
        ├── step_00000/             # Per-step artifacts
        │   ├── action.txt
        │   ├── thoughts.txt
        │   ├── screenshot.png
        │   └── screenshot_som.png
        ├── step_00001/
        └── ...
```

### Output JSON Structure

`output_*.json` contains:

```json
{
  "id": "demo",
  "goal": "Buy 1 pair of running shoes",
  "url": "https://store.com",
  "agent_result": {
    "success": true,
    "num_steps": 7,
    "total_cost": 0.6314,
    "completion_reason": "auto_eval",
    "eval_confidence": 1.0,
    "eval_reasoning": "Order confirmation visible"
  },
  "trajectory": [
    {
      "step": 0,
      "action": "fill('112', 'running shoes')",
      "reasoning": "Need to search for shoes",
      "screenshot": "base64...",
      "som": "base64...",
      "coordinates": {
        "bid": "112",
        "center_x": 350,
        "center_y": 120,
        "bbox": [300, 100, 100, 40]
      }
    }
  ],
  "screenshots": [
    {
      "step": 0,
      "type": "som",
      "path": "step_00000/screenshot_som.png"
    }
  ],
  "exp_dir": "tasks/my_task/web_agents/2025-*/"
}
```

### State Variables

The `WebAgentNode` exposes these state variables (accessible in subsequent nodes):

- **`agent_result`**: Summary dict with `success`, `num_steps`, `total_cost`, `completion_reason`, etc.
- **`trajectory`**: List of step dicts with `action`, `reasoning`, `screenshots`, `coordinates`
- **`screenshots`**: List of screenshot metadata with file paths
- **`exp_dir`**: Path to experiment artifacts directory

**Custom State Variables** (optional):

```yaml
web_agent:
  output_keys:
    - custom_metric
    - success_rate
```

---

## API Reference

### Core Classes

#### `WebAgentNode`

```python
class WebAgentNode(BaseNode):
    """SyGra node for browser automation using AgentLab."""

    def __init__(
        self,
        node_name: str,
        model: str = "gpt-4o",
        max_steps: int = 15,
        headless: bool = True,
        use_screenshot: bool = True,
        use_som: bool = True,
        use_html: bool = False,
        temperature: float = 0.1,
        viewport_width: int = 1280,
        viewport_height: int = 720,
        slow_mo: int = 0,
        enable_chat: bool = True,
        enable_goal_eval: bool = False,
        eval_frequency: int = 2,
        eval_start_step: int = 3,
        eval_use_vision: bool = False,
        **kwargs
    ):
        """Initialize web agent node."""
```

#### `create_web_agent_node`

```python
def create_web_agent_node(
    node_name: str,
    node_config: dict
) -> WebAgentNode:
    """Factory function to create WebAgentNode from YAML config."""
```

### Task Creation Functions

#### `create_custom_task`

```python
def create_custom_task(
    goal: str,
    url: str,
    task_id: Optional[str] = None,
    **metadata
) -> Dict[str, Any]:
    """Create a custom web task."""
```

#### `create_ecommerce_task`

```python
def create_ecommerce_task(
    site_url: str,
    action: str,
    product: Optional[str] = None,
    **metadata
) -> Dict[str, Any]:
    """Create an e-commerce task."""
```

### Utility Functions

#### `convert_trajectory_to_training_format`

```python
def convert_trajectory_to_training_format(
    trajectory: List[Dict[str, Any]],
    format: str = "instruction_following"
) -> Dict[str, Any]:
    """Convert trajectory to training data format.

    Formats: "instruction_following", "conversation", "qa"
    """
```

#### `compute_trajectory_statistics`

```python
def compute_trajectory_statistics(
    trajectories: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """Compute statistics from trajectories."""
```

#### `export_trajectories_to_dataset`

```python
def export_trajectories_to_dataset(
    trajectories: List[Dict[str, Any]],
    output_file: str,
    format: str = "instruction_following",
    filter_successful: bool = True
):
    """Export trajectories to training dataset file (.json or .jsonl)."""
```

---

## Examples

### Example 1: Simple Web Search

```python
# Create task
task = create_custom_task(
    goal="Search for 'machine learning papers' on Google Scholar",
    url="https://scholar.google.com",
    task_id="search_ml"
)

# Save to JSONL
with open("tasks/search/tasks.jsonl", "w") as f:
    json.dump(task, f)
    f.write("\n")
```

### Example 2: E-commerce Purchase

```yaml
# tasks/shopping/graph_config.yaml
graph_config:
  nodes:
    web_agent:
      node_type: web_agent
      model: gpt-4o
      max_steps: 25
      headless: false
      enable_goal_eval: true
      eval_use_vision: true
```

```jsonl
{"goal": "Buy 1 wireless mouse under $30", "url": "https://www.amazon.com", "task_name": "custom.mouse", "task_type": "custom"}
```

### Example 3: Multi-Task Workflow

```python
from sygra.integrations.agentlab import create_custom_tasks

tasks = create_custom_tasks([
    {"goal": "Find flights SFO→NYC", "url": "https://google.com/flights"},
    {"goal": "Book hotel in Manhattan", "url": "https://booking.com"},
    {"goal": "Reserve rental car", "url": "https://enterprise.com"}
])

# Run all tasks
workflow = sygra.Workflow("travel")
workflow.source(tasks)
workflow.add_node("agent", WebAgentNode(...))
workflow.run()
```

### Example 4: Export Training Data

```python
from sygra.integrations.agentlab.utils import (
    export_trajectories_to_dataset,
    extract_successful_trajectories
)

# Load results
results = json.load(open("output.json"))

# Filter successful
successful = extract_successful_trajectories(results, min_steps=3)

# Export to training format
export_trajectories_to_dataset(
    successful,
    output_file="training_data.jsonl",
    format="instruction_following",
    filter_successful=True
)
```

---

## Advanced Topics

### Custom Agent Configuration

Use `AgentConfigBuilder` for advanced agent setup:

```python
from sygra.integrations.agentlab.agent_config import AgentConfigBuilder

agent_args = AgentConfigBuilder.build(
    model="gpt-4o",
    temperature=0.2,
    use_screenshot=True,
    use_som=True,
    use_html=False,
    use_ax_tree=False,  # Disable to force BID-only mode
    enable_chat=True
)

node = WebAgentNode(
    node_name="custom_agent",
    agent_args=agent_args,  # Pass custom config
    max_steps=20
)
```

### Environment Variable Mapping

The integration automatically maps SyGra environment variables:

```python
from sygra.integrations.agentlab.env_setup import EnvironmentMapper

# Manual setup (usually automatic)
EnvironmentMapper.setup(model_name="gpt-4o")

# Maps:
# SYGRA_GPT-4O_URL → AZURE_OPENAI_ENDPOINT
# SYGRA_GPT-4O_TOKEN → AZURE_OPENAI_API_KEY
```

### Subprocess Execution

Experiments run in isolated subprocesses for:
- **Stability**: Errors don't crash main process
- **Clean State**: Each experiment starts fresh
- **Timeout Control**: Can terminate hung experiments

```python
from sygra.integrations.agentlab.experiment_runner import (
    ExperimentConfig,
    ExperimentRunner
)

config = ExperimentConfig(
    agent_args=agent_args,
    task_name="custom.demo",
    task_type="custom",
    url="https://example.com",
    goal="Complete task",
    max_steps=15,
    headless=True,
    enable_goal_eval=True,
    eval_use_vision=True,
    # ... other params
)

result = ExperimentRunner.run(config)
```

### Result Loading

Load experiment results from disk:

```python
from sygra.integrations.agentlab.result_loader import ResultLoader

result = ResultLoader.load(
    exp_dir="/path/to/experiment",
    task_name="custom.demo"
)

print(f"Steps: {result['num_steps']}")
print(f"Success: {result['success']}")
print(f"Completion: {result['completion_reason']}")
```

---

## Troubleshooting

### Common Issues

#### 1. AgentLab Not Found

**Error:**
```
ImportError: No module named 'agentlab'
```

**Solution:**
```bash
poetry add agentlab browsergym
# or
pip install agentlab browsergym
```

#### 2. Missing Environment Variables

**Error:**
```
WARNING - Missing SYGRA_GPT-4O_URL in environment
```

**Solution:**
Create `.env` file with credentials:
```env
SYGRA_GPT-4O_URL=https://...
SYGRA_GPT-4O_TOKEN=...
```

#### 3. Browser Not Launching

**Error:**
```
playwright._impl._errors.Error: Executable doesn't exist
```

**Solution:**
```bash
playwright install chromium
```

#### 4. Action Parsing Failures

**Error:**
```
Action failed: click("Add to cart")
```

**Solution:**
Ensure BID-only mode:
```yaml
use_som: true
use_html: false
use_ax_tree: false  # In custom agent config
```

#### 5. Task Never Completes

**Problem**: Agent takes max_steps without completing.

**Solutions:**

1. **Enable goal evaluation:**
```yaml
enable_goal_eval: true
eval_use_vision: true
```

2. **Enable chat actions:**
```yaml
enable_chat: true
```

3. **Increase max_steps:**
```yaml
max_steps: 30
```

#### 6. High API Costs

**Problem**: Vision-enabled evaluation is expensive.

**Solutions:**

1. **Use text-only evaluation for simple tasks:**
```yaml
eval_use_vision: false
```

2. **Reduce evaluation frequency:**
```yaml
eval_frequency: 3  # Every 3 steps instead of 2
eval_start_step: 5 # Start later
```

3. **Use smaller model:**
```yaml
model: gpt-4o-mini
```

### Debug Mode

Enable verbose logging:

```yaml
web_agent:
  headless: false     # Show browser
  slow_mo: 1000       # Slow down actions (1 second)
```

Check experiment logs:
```bash
cat tasks/my_task/web_agents/*/experiment.log
```

### Testing

Run the example task to verify setup:

```bash
poetry run python main.py -t examples.web_agent_demo -n 1
```

Expected output:
```
- Goal evaluation configured: use_vision=True
- Running experiment in subprocess...
- Evaluation result: complete=True, confidence=1.00
- Task terminated by goal evaluation
```
