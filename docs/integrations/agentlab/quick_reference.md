# AgentLab Integration - Quick Reference

Quick reference guide for common tasks and configurations.

## Installation

```bash
# Install dependencies
poetry add agentlab browsergym
playwright install chromium

# Verify installation
python -c "from sygra.integrations.agentlab import AGENTLAB_AVAILABLE; print(AGENTLAB_AVAILABLE)"
```

##

 Environment Setup

Create `.env` file in project root:

```env
SYGRA_GPT-4O_URL=https://your-endpoint.openai.azure.com/
SYGRA_GPT-4O_TOKEN=your-api-key
SYGRA_GPT-4O-MINI_URL=https://your-endpoint.openai.azure.com/
SYGRA_GPT-4O-MINI_TOKEN=your-api-key
```

## Minimal CLI Workflow

**tasks.jsonl:**
```jsonl
{"goal": "Buy shoes", "url": "https://amazon.com", "task_name": "custom.demo", "task_type": "custom"}
```

**graph_config.yaml:**
```yaml
data_config:
  source:
    type: "disk"
    file_path: "tasks.jsonl"

graph_config:
  nodes:
    web_agent:
      node_type: web_agent
      model: gpt-4o
      max_steps: 15
      enable_goal_eval: true
  edges:
    - {from: START, to: web_agent}
    - {from: web_agent, to: END}
```

**Run:**
```bash
poetry run python main.py -t my_task -n 1
```

## Minimal Library Usage

```python
from sygra import Workflow
from sygra.integrations.agentlab import create_custom_task, WebAgentNode

# Create task
task = create_custom_task(
    goal="Search for Python tutorials",
    url="https://www.google.com"
)

# Create workflow
workflow = Workflow("demo")
workflow.source([task])

# Add agent
agent = WebAgentNode(
    node_name="web_agent",
    model="gpt-4o",
    max_steps=15,
    enable_goal_eval=True
)

workflow.add_node("web_agent", agent)
workflow.add_edge("START", "web_agent")
workflow.add_edge("web_agent", "END")

# Run
results = workflow.run()
```

## Common Configurations

### Development Mode (Visual Debugging)

```yaml
web_agent:
  model: gpt-4o
  max_steps: 10
  headless: false      # Show browser
  slow_mo: 600         # Slow down actions
  use_screenshot: true
  use_som: true
  enable_goal_eval: true
  eval_use_vision: true
```

### Production Mode (Headless, Fast)

```yaml
web_agent:
  model: gpt-4o
  max_steps: 20
  headless: true       # No UI
  slow_mo: 0           # Fast
  use_screenshot: true
  use_som: true
  enable_chat: true
  enable_goal_eval: true
  eval_use_vision: true
```

### Budget Mode (Lower Cost)

```yaml
web_agent:
  model: gpt-4o-mini   # Cheaper model
  max_steps: 15
  headless: true
  enable_goal_eval: true
  eval_use_vision: false  # Text-only evaluation
  eval_frequency: 3       # Less frequent checks
  eval_start_step: 5      # Start later
```

## Task Creation (CLI)

### JSONL Format

```jsonl
{"id": "1", "goal": "Task description", "url": "https://example.com", "task_name": "custom.task1", "task_type": "custom"}
```

**Required fields:**
- `goal`: Task description
- `url`: Starting URL
- `task_name`: Format `custom.<id>`
- `task_type`: Must be `"custom"`

## Task Creation (Library)

### Simple Task

```python
from sygra.integrations.agentlab import create_custom_task

task = create_custom_task(
    goal="Search for Python",
    url="https://google.com",
    task_id="search_001"
)
```

### E-commerce Task

```python
from sygra.integrations.agentlab import create_ecommerce_task

task = create_ecommerce_task(
    site_url="https://amazon.com",
    action="search_and_add_to_cart",
    product="wireless mouse",
    quantity=1
)
```

## Accessing Results (CLI)

```bash
# View results
cat tasks/my_task/output_*.json | jq

# Check success
cat tasks/my_task/output_*.json | jq '.agent_result.success'

# View trajectory
cat tasks/my_task/output_*.json | jq '.trajectory[]'

# Check logs
cat tasks/my_task/web_agents/*/experiment.log
```

## Accessing Results (Library)

```python
import json

# Load results
with open("output.json") as f:
    data = json.load(f)

# Check success
print(f"Success: {data['agent_result']['success']}")
print(f"Steps: {data['agent_result']['num_steps']}")
print(f"Cost: ${data['agent_result']['total_cost']:.2f}")

# Get trajectory
for step in data['trajectory']:
    print(f"Step {step['step']}: {step['action']}")
    # step['screenshot'] contains base64 image
    # step['coordinates'] contains mouse coordinates
```

## Export Training Data

```python
from sygra.integrations.agentlab.utils.utils import export_trajectories_to_dataset

# Load results
results = json.load(open("output.json"))

# Export
export_trajectories_to_dataset(
    results,
    output_file="training.jsonl",
    format="instruction_following",  # or "conversation", "qa"
    filter_successful=True
)
```

## Configuration Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `model` | str | `gpt-4o` | LLM model |
| `max_steps` | int | `15` | Max actions |
| `headless` | bool | `true` | Hide browser |
| `use_screenshot` | bool | `true` | Capture screens |
| `use_som` | bool | `true` | BID overlays |
| `use_html` | bool | `false` | HTML observations |
| `temperature` | float | `0.1` | LLM temperature |
| `viewport_width` | int | `1280` | Browser width |
| `viewport_height` | int | `720` | Browser height |
| `slow_mo` | int | `0` | Action delay (ms) |
| `enable_chat` | bool | `true` | Agent signals |
| `enable_goal_eval` | bool | `false` | Auto evaluation |
| `eval_frequency` | int | `2` | Eval interval |
| `eval_start_step` | int | `3` | Eval start |
| `eval_use_vision` | bool | `false` | Vision eval |

## Completion Detection

### Agent Signal (Chat Action)

```yaml
enable_chat: true
```

Agent uses: `send_msg_to_user("Task completed")`

### Goal Evaluation (Automatic)

```yaml
enable_goal_eval: true
eval_frequency: 2
eval_start_step: 3
eval_use_vision: true  # Recommended
```

LLM evaluates: "Is the goal achieved?"

### Both (Recommended)

```yaml
enable_chat: true
enable_goal_eval: true
```

Stops on whichever triggers first.

## Actions Reference

Agent generates BID-based actions:

```python
click('285')              # Click element 285
fill('42', 'text')        # Fill input 42
scroll('down')            # Scroll page
send_msg_to_user('Done')  # Signal completion
```

**Important:** Actions like `click("Add to cart")` will FAIL. Always use BID numbers.

## Troubleshooting

| Issue | Solution |
|-------|----------|
| `ImportError: agentlab` | `poetry add agentlab browsergym` |
| Missing environment vars | Create `.env` with credentials |
| `Executable doesn't exist` | `playwright install chromium` |
| Agent never completes | Enable `enable_goal_eval: true` |
| Action parsing fails | Use `use_som: true, use_html: false` |
| High costs | Use `gpt-4o-mini` or `eval_use_vision: false` |

## Debug Commands

```bash
# Test installation
python -c "from sygra.integrations.agentlab import AGENTLAB_AVAILABLE; print(AGENTLAB_AVAILABLE)"

# Run with visual browser
poetry run python main.py -t my_task -n 1

# Check logs
cat tasks/my_task/web_agents/*/experiment.log

# View results
cat tasks/my_task/output_*.json | jq
```

## Best Practices

**Recommended Settings:**
- Use `enable_goal_eval: true` for production
- Set `eval_use_vision: true` for visual confirmation tasks
- Keep `max_steps` reasonable (15-25)
- Use BID-only mode (`use_som: true`, `use_html: false`)
- Enable `enable_chat: true` as fallback

**Avoid:**
- Running `headless: false` in production (slower)
- Setting `max_steps` too high (wastes API calls)
- Using both `use_html: true` and `use_som: true` (causes confusion)
- Vague goals without clear end state

## Examples

See `/tasks/examples/web_agent_demo/` for complete working example.
