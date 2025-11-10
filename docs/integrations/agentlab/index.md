# AgentLab Integration for SyGra

Vision-enhanced web automation agents powered by AgentLab for autonomous task completion and training data generation.

## Overview

The AgentLab integration extends SyGra with vision-enabled web automation capabilities, enabling LLM agents to:

- Navigate and interact with websites using visual grounding
- Complete complex tasks across any web application
- Generate training data with full action trajectories and coordinates
- Automatically detect task completion using LLM-based evaluation

### Key Capabilities

**Visual Understanding**: Uses screenshots with Set-of-Mark (SOM) overlays for precise element identification

**Browser ID Actions**: Generates BID-based actions (`click('285')`, `fill('42', 'text')`) for reliable interaction and coordinate extraction

**Dual Completion Detection**: Combines agent completion signals with automatic LLM-based goal evaluation

**Production-Ready**: Subprocess isolation, comprehensive error handling, and detailed logging

**Training Data Collection**: Full trajectories with reasoning, screenshots, and mouse coordinates for RL/imitation learning

---

## Installation

### Prerequisites

```bash
# Using Poetry (recommended)
poetry add agentlab browsergym

# Install browser
playwright install chromium
```

### Environment Configuration

Create a `.env` file in your project root with Azure OpenAI credentials:

```env
# Required: GPT-4o credentials
SYGRA_GPT-4O_URL=https://your-endpoint.openai.azure.com/
SYGRA_GPT-4O_TOKEN=your-api-key-here

# Optional: GPT-4o-mini credentials  
SYGRA_GPT-4O-MINI_URL=https://your-endpoint.openai.azure.com/
SYGRA_GPT-4O-MINI_TOKEN=your-api-key-here
```

### Verify Installation

```python
from sygra.integrations.agentlab import AGENTLAB_AVAILABLE

if AGENTLAB_AVAILABLE:
    print("AgentLab integration is ready")
else:
    print("AgentLab not installed")
```

---

## Quick Start

### Using CLI

**Step 1: Create task file**

`tasks/web_shopping/tasks.jsonl`:
```jsonl
{"id": "task1", "goal": "Buy 1 pair of running shoes", "url": "https://www.amazon.com", "task_name": "custom.task1", "task_type": "custom"}
```

**Step 2: Configure workflow**

`tasks/web_shopping/graph_config.yaml`:
```yaml
data_config:
  source:
    type: "disk"
    file_path: "tasks/web_shopping/tasks.jsonl"

graph_config:
  nodes:
    web_agent:
      node_type: web_agent
      model: gpt-4o
      max_steps: 20
      headless: true
      use_screenshot: true
      use_som: true
      enable_chat: true
      enable_goal_eval: true
      eval_use_vision: true

  edges:
    - from: START
      to: web_agent
    - from: web_agent
      to: END

output_config:
  output_map:
    goal:
    - from: "goal"
    agent_result:
    - from: "agent_result"
    trajectory:
    - from: "trajectory"
```

**Step 3: Run workflow**

```bash
# Run single task
poetry run python main.py -t web_shopping -n 1

# Run all tasks in file
poetry run python main.py -t web_shopping
```

**Step 4: Check results**

Results are saved in `tasks/web_shopping/output_*.json`:
```json
{
  "id": "task1",
  "goal": "Buy 1 pair of running shoes",
  "agent_result": {
    "success": true,
    "num_steps": 12,
    "total_cost": 0.45,
    "completion_reason": "auto_eval"
  },
  "trajectory": [...],
  "screenshots": [...],
  "exp_dir": "tasks/web_shopping/web_agents/2025-*/"
}
```

### Using Python Library

**Example 1: Simple workflow**

```python
from sygra import Workflow
from sygra.integrations.agentlab import create_custom_task, WebAgentNode

# Create task
task = create_custom_task(
    goal="Search for Python tutorials and open the first result",
    url="https://www.google.com",
    task_id="search_001"
)

# Create workflow
workflow = Workflow("web_search")
workflow.source([task])

# Add web agent node
web_agent = WebAgentNode(
    node_name="search_agent",
    model="gpt-4o",
    max_steps=15,
    headless=True,
    enable_goal_eval=True,
    eval_use_vision=True
)

workflow.add_node("search_agent", web_agent)
workflow.add_edge("START", "search_agent")
workflow.add_edge("search_agent", "END")

# Run workflow
results = workflow.run()

# Access results
for result in results:
    print(f"Task: {result['goal']}")
    print(f"Success: {result['agent_result']['success']}")
    print(f"Steps: {result['agent_result']['num_steps']}")
```

**Example 2: Multiple tasks with custom configuration**

```python
from sygra.integrations.agentlab import create_custom_tasks, create_web_agent_node

# Create multiple tasks
tasks = create_custom_tasks([
    {
        "goal": "Find flights from SFO to JFK",
        "url": "https://www.google.com/flights",
        "task_id": "flight_search"
    },
    {
        "goal": "Search for hotels in Manhattan",
        "url": "https://www.booking.com",
        "task_id": "hotel_search"
    }
])

# Create agent with custom config
agent_config = {
    "model": "gpt-4o",
    "max_steps": 25,
    "headless": True,
    "use_screenshot": True,
    "use_som": True,
    "enable_goal_eval": True,
    "eval_frequency": 3,
    "eval_use_vision": True,
    "temperature": 0.2
}

web_agent = create_web_agent_node("travel_agent", agent_config)

# Build and run workflow
workflow = Workflow("travel_planning")
workflow.source(tasks)
workflow.add_node("travel_agent", web_agent)
workflow.add_edge("START", "travel_agent")
workflow.add_edge("travel_agent", "END")

results = workflow.run()

# Process results
for result in results:
    if result['agent_result']['success']:
        print(f"Completed: {result['goal']}")
        print(f"  Steps: {result['agent_result']['num_steps']}")
        print(f"  Cost: ${result['agent_result']['total_cost']:.2f}")
```

**Example 3: E-commerce workflow**

```python
from sygra.integrations.agentlab import create_ecommerce_task

# Create e-commerce task
task = create_ecommerce_task(
    site_url="https://www.amazon.com",
    action="search_and_add_to_cart",
    product="wireless mouse",
    quantity=1,
    max_price=30
)

# Configure agent for e-commerce
web_agent = WebAgentNode(
    node_name="shopping_agent",
    model="gpt-4o",
    max_steps=30,
    headless=False,  # Show browser for debugging
    slow_mo=500,     # Slow down for observation
    enable_goal_eval=True,
    eval_frequency=2,
    eval_use_vision=True,
    viewport_width=1380,
    viewport_height=820
)

workflow = Workflow("online_shopping")
workflow.source([task])
workflow.add_node("shopping_agent", web_agent)
workflow.add_edge("START", "shopping_agent")
workflow.add_edge("shopping_agent", "END")

results = workflow.run()

# Check if purchase completed
if results[0]['agent_result']['success']:
    print(f"Successfully completed: {results[0]['goal']}")
    print(f"Completion reason: {results[0]['agent_result']['completion_reason']}")
    print(f"Trajectory saved to: {results[0]['exp_dir']}")
```

**Example 4: Export training data**

```python
from sygra.integrations.agentlab.utils import (
    export_trajectories_to_dataset,
    extract_successful_trajectories
)

# Run workflow and get results
results = workflow.run()

# Extract successful trajectories
successful = extract_successful_trajectories(
    results,
    min_steps=3,
    max_steps=25
)

# Export to training dataset
export_trajectories_to_dataset(
    successful,
    output_file="training_data/web_agent_trajectories.jsonl",
    format="instruction_following",
    filter_successful=True
)

print(f"Exported {len(successful)} successful trajectories")
```

---

## Features

### Vision-Enabled Goal Evaluation

Automatically detects task completion using LLM analysis of screenshots and page state.

**Configuration:**
```yaml
web_agent:
  enable_goal_eval: true      # Enable automatic evaluation
  eval_frequency: 2           # Evaluate every N steps
  eval_start_step: 3          # Start evaluating after step N
  eval_use_vision: true       # Use screenshots for evaluation
```

**How it works:**
1. Captures screenshot and page state at configured intervals
2. LLM evaluates: "Has the goal been achieved?"
3. Returns completion status, reasoning, and confidence (0.0-1.0)
4. Terminates task if complete and confidence >= 0.7

**Benefits:**
- Eliminates need for manual completion signals
- Visual confirmation of success (order pages, confirmation modals)
- Higher accuracy than text-only evaluation
- Automatic early stopping to reduce costs

### Browser ID (BID) Actions

Uses Browser IDs for precise element targeting:

```python
# Agent generates BID-based actions
click('285')              # Click element with BID 285
fill('42', 'search text') # Fill input field 42
scroll('down')            # Scroll page down
```

**Advantages:**
- Enables coordinate extraction for training data
- Eliminates action parsing failures
- Works reliably across dynamic page structures
- Supports precise element targeting

### Set-of-Mark (SOM) Overlays

Displays Browser IDs directly on screenshots for visual grounding:

```yaml
use_som: true   # Enable SOM overlays
use_html: false # Disable HTML to avoid confusion
```

The agent sees screenshots with overlaid element IDs, enabling it to reference specific elements by their BID numbers.

### Training Data Collection

Collects complete trajectories with:

- Full action sequences with reasoning
- Screenshots (regular and SOM overlays, base64 encoded)
- Mouse action coordinates (`center_x`, `center_y`, `bbox`)
- Success indicators and completion reasons
- Execution metrics (steps, cost, time)

**Export formats:**
- `instruction_following`: Goal -> actions -> outcome
- `conversation`: Multi-turn dialogue format
- `qa`: Question-answer pairs

---

## Configuration

### Complete Configuration Reference

```yaml
graph_config:
  nodes:
    web_agent:
      # Required
      node_type: web_agent

      # Model Configuration
      model: gpt-4o                  # or gpt-4o-mini
      temperature: 0.1               # Sampling temperature (0.0-1.0)

      # Execution Control
      max_steps: 20                  # Maximum actions before timeout

      # Browser Settings
      headless: true                 # Run without UI (faster)
      viewport_width: 1280           # Browser window width
      viewport_height: 720           # Browser window height
      slow_mo: 0                     # Delay between actions (ms)

      # Observation Settings
      use_screenshot: true           # Capture screenshots
      use_som: true                  # Enable SOM overlays (recommended)
      use_html: false                # Include HTML in observations

      # Completion Detection
      enable_chat: true              # Allow agent completion signals
      enable_goal_eval: true         # Enable LLM goal evaluation
      eval_frequency: 2              # Evaluate every N steps
      eval_start_step: 3             # Start evaluating after step N
      eval_use_vision: true          # Use screenshots in evaluation
```

### Common Configuration Patterns

**Development (visual debugging):**
```yaml
headless: false
slow_mo: 600
max_steps: 10
enable_goal_eval: true
eval_use_vision: true
```

**Production (fast, headless):**
```yaml
headless: true
slow_mo: 0
max_steps: 20
enable_goal_eval: true
eval_use_vision: true
```

**Budget-conscious (lower costs):**
```yaml
model: gpt-4o-mini
headless: true
enable_goal_eval: true
eval_use_vision: false  # Text-only evaluation
eval_frequency: 3       # Less frequent evaluation
```

---

## Output Structure

### Output JSON Structure

```json
{
  "id": "task1",
  "goal": "Buy 1 pair of running shoes",
  "url": "https://www.amazon.com",
  "task_name": "custom.task1",
  "agent_result": {
    "success": true,
    "num_steps": 12,
    "total_cost": 0.6314,
    "completion_reason": "auto_eval",
    "eval_confidence": 1.0,
    "eval_reasoning": "Order confirmation page displayed"
  },
  "trajectory": [
    {
      "step": 0,
      "action": "fill('112', 'running shoes')",
      "reasoning": "Need to search for running shoes",
      "screenshot": "base64_encoded_image...",
      "som": "base64_encoded_som_image...",
      "coordinates": {
        "bid": "112",
        "center_x": 350,
        "center_y": 120,
        "bbox": [300, 100, 100, 40],
        "clickable": true,
        "visibility": 1.0
      }
    }
  ],
  "screenshots": [...],
  "exp_dir": "tasks/my_task/web_agents/2025-*/"
}
```

---

## API Reference

### Task Creation Functions

#### create_custom_task

```python
def create_custom_task(
    goal: str,
    url: str,
    task_id: Optional[str] = None,
    **metadata
) -> dict[str, Any]:
    """Create a custom web task.

    Args:
        goal: Natural language task description
        url: Starting URL for the task
        task_id: Optional unique identifier
        **metadata: Additional task metadata

    Returns:
        Task dictionary for SyGra workflow
    """
```

#### create_ecommerce_task

```python
def create_ecommerce_task(
    site_url: str,
    action: str,
    product: Optional[str] = None,
    **metadata
) -> dict[str, Any]:
    """Create an e-commerce task.

    Args:
        site_url: E-commerce website URL
        action: Action to perform (search, add_to_cart, checkout, etc.)
        product: Product name/description
        **metadata: Additional metadata (quantity, max_price, etc.)

    Returns:
        Task dictionary
    """
```

### WebAgentNode Class

```python
class WebAgentNode(BaseNode):
    """SyGra node for browser automation using AgentLab.

    Executes web automation tasks using vision-enabled agents with
    automatic goal evaluation and comprehensive result tracking.
    """

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

### Utility Functions

#### export_trajectories_to_dataset

```python
def export_trajectories_to_dataset(
    trajectories: List[Dict[str, Any]],
    output_file: str,
    format: str = "instruction_following",
    filter_successful: bool = True
):
    """Export trajectories to training dataset.

    Args:
        trajectories: List of agent execution results
        output_file: Output file path (.json or .jsonl)
        format: Training data format (instruction_following, conversation, qa)
        filter_successful: Only include successful trajectories
    """
```

#### compute_trajectory_statistics

```python
def compute_trajectory_statistics(
    trajectories: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """Compute aggregate statistics from trajectories.

    Returns:
        Dictionary with total_trajectories, success_rate, avg_steps,
        avg_cost, and other metrics
    """
```

---

## Testing

Run the comprehensive test suite:

```bash
# Run all AgentLab integration tests
pytest tests/integrations/agentlab/ -v

# Run specific test module
pytest tests/integrations/agentlab/test_goal_evaluator.py -v
```

---

## Troubleshooting

### Common Issues

**Issue: AgentLab not found**
```
ImportError: No module named 'agentlab'
```
**Solution:** Install dependencies
```bash
poetry add agentlab browsergym
playwright install chromium
```

**Issue: Missing environment variables**
```
WARNING - Missing SYGRA_GPT-4O_URL in environment
```
**Solution:** Create `.env` file with Azure OpenAI credentials

**Issue: Browser won't launch**
```
playwright._impl._errors.Error: Executable doesn't exist
```
**Solution:** Install Playwright browsers
```bash
playwright install chromium
```

**Issue: Action parsing failures**
```
Action failed: click("Add to cart")
```
**Solution:** Enable BID-only mode
```yaml
use_som: true
use_html: false
```

**Issue: Task never completes**

**Solution:** Enable goal evaluation
```yaml
enable_goal_eval: true
eval_use_vision: true
```

**Issue: High API costs**

**Solutions:**
- Use `gpt-4o-mini` model
- Set `eval_use_vision: false` for simple tasks
- Reduce `eval_frequency` (e.g., 3 instead of 2)
- Set appropriate `max_steps` limit

### Debug Mode

Enable visual debugging:

```yaml
web_agent:
  headless: false    # Show browser
  slow_mo: 1000      # Slow down actions (1 second)
  max_steps: 10      # Limit steps for debugging
```

Check experiment logs:
```bash
cat tasks/my_task/web_agents/*/experiment.log
```
