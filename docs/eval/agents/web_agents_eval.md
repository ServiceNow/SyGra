# Web Agents Evaluation

## Overview

The `eval.agents.web_agents` module provides a comprehensive framework for evaluating browser automation agents. It includes tools for web interaction, request/response logging, retry logic with intelligent failure hints, inline evaluation, and metrics calculation.

## Architecture

### Core Components

1. **Task Executor** (`task_executor.py`) - Main execution logic with pre/post processors
2. **Tools** (`tools.py`) - Browser interaction tools (click, type, scroll, etc.)
3. **Constants** (`constants.py`) - Configuration constants and state keys
4. **Graph Config** (`graph_config.yaml`) - Workflow configuration and system prompts

## Module Structure

```
tasks/eval/agents/web_agents/
├── task_executor.py       # Core execution logic
├── tools.py              # Browser interaction tools
├── constants.py          # Configuration constants
├── graph_config.yaml     # Workflow and evaluation config
├── chat_history_seed.json # Sample input data
├── logs/                 # Request/response logs
└── metadata/             # Execution metadata
```

---

## Components

### 1. Task Executor (`task_executor.py`)

The task executor provides several classes for managing the evaluation workflow:

#### `RequestResponseLogger`

Comprehensive logging system for tracking exact request/response payloads.

**Methods:**
- `setup_logger()` - Initialize logging directory and file structure
- `log_request(request_payload, step_number)` - Log requests sent to the model
- `log_response(response_payload, step_number)` - Log responses received from the model
- `is_server_error(response)` - Detect server errors in responses

**Log Format:**
```json
{
  "step": 1,
  "timestamp": "2026-03-05T12:00:00",
  "type": "request|response",
  "payload": {...}
}
```

#### `FetchNextActionPreProcessor`

Pre-processes requests before sending to the model.

**Key Features:**
- Manages chat history and state
- Handles retry logic with failure hints
- Injects retry prompts when needed
- Manages screenshot scaling

**Methods:**
- `retry_failure_and_chat_injection(cls, state, lambda_node_dict)` - Inject retry hints into chat
- `apply(cls, lambda_node_dict, state)` - Main preprocessing logic

**Retry Hints:**
- **Tool Incorrect**: Guides agent to use different tool
- **Parameters Incorrect**: Guides agent to fix parameters for same tool

#### `FetchNextActionPostProcessor`

Post-processes model responses.

**Key Features:**
- Logs responses
- Extracts tool calls from model output
- Handles server errors
- Updates state with model responses

**Methods:**
- `apply(cls, lambda_node_dict, state, messages)` - Main post-processing logic

#### `InlineEvaluationLambda`

Performs inline evaluation of model predictions against golden responses.

**Evaluation Metrics:**
- **Tool Match**: Exact match of predicted vs golden tool
- **Step Match**: Comprehensive validation including:
  - Tool correctness
  - Parameter correctness (for click, type, scroll)
  - Bounding box validation (for click)
  - Scroll direction validation
  - Typed value matching

**Methods:**
- `apply(cls, lambda_node_dict, state)` - Execute inline evaluation

**Validation Logic:**
```python
# Tool must match
if predicted_tool != golden_tool:
    return False

# For click: validate coordinates within bounding box
if tool == "click":
    validate_bbox(x, y, golden_bbox)

# For scroll: validate direction
if tool == "scroll":
    validate_direction(predicted_direction, golden_direction)

# For typing: validate text content
if tool == "typing":
    validate_text(predicted_text, golden_text)
```

#### `RetryFlow`

Manages retry logic and determines when to retry failed attempts.

**Methods:**
- `apply(cls, lambda_node_dict, state)` - Determine if retry is needed

**Retry Conditions:**
- Step evaluation failed
- Retry count < max retries
- No server errors

#### `ShouldContinueCondition`

Edge condition to determine if workflow should continue.

**Methods:**
- `apply(cls, edge_dict, state)` - Check continuation conditions

#### `Flatten`

Post-processor that flattens nested retry structure for analysis.

**Transformation:**
```
Input:  {mission_id: {retry_0: {...}, retry_1: {...}}}
Output: [{mission_id, retry_id: "retry_0", ...}, 
         {mission_id, retry_id: "retry_1", ...}]
```

**Methods:**
- `process(data, metadata)` - Flatten retry structure

**Output Fields:**
- `id`, `mission_id`, `turn`, `mission`, `navigational_directions`
- `golden_response`, `retry_id`, `model_response`
- `tool_match`, `step_match`

---

### 2. Tools (`tools.py`)

Browser interaction tools using LangChain's `@tool` decorator.

#### Available Tools

| Tool | Description | Parameters |
|------|-------------|------------|
| `screenshot_tool` | Capture current page state | `take_screenshot: bool` |
| `click_tool` | Click at coordinates | `x: float, y: float` |
| `type_tool` | Type at coordinates | `x: float, y: float, text: str` |
| `typing_tool` | Type without coordinates | `text: str` |
| `scroll_tool` | Scroll in direction | `direction: str, amount: float` |
| `wait_tool` | Wait for duration | `time: float` (milliseconds) |
| `resume_tool` | Resume after pause | `resume: bool` |
| `hil_tool` | Human-in-the-loop | `wait_for_human: bool` |
| `text_clear_tool` | Clear text field | `clear_text: bool` |
| `slider_tool` | Move slider | `direction: str, amount: float` |

#### Tool Usage Example

```python
# Click at coordinates
click_tool.invoke({"x": 500, "y": 300})

# Type text
typing_tool.invoke({"text": "Hello World"})

# Scroll down
scroll_tool.invoke({"direction": "down", "amount": 200})
```

---

### 3. Constants (`constants.py`)

Configuration constants organized by category.

#### Categories

**Server Error Detection**
- `SERVER_DOWN_ERROR` - Error marker string
- `SERVER_ERROR_MARKERS` - List of error markers

**Tool Configuration**
- `TOOL_NAME_SUFFIX` - Suffix for tool names ("_tool")
- `TOOL_NAME_MAPPINGS` - Tool name aliases
- `TOOL_TYPE_*` - Tool type constants

**Retry Configuration**
- `DEFAULT_MAX_RETRIES` - Default retry limit (3)
- `RETRY_KEY_PREFIX` - Prefix for retry keys

**State Keys**
- `CHAT_HISTORY_STATE_KEY` - Chat history storage key
- `MODEL_RESPONSES_KEY` - Model responses storage key
- `GOLDEN_RESPONSE_KEY` - Golden response key
- `CURRENT_TOOL_RESULT_KEY` - Current tool result key

**Failure Hints**
- `FAILURE_HINT_TOOL_INCORRECT` - Hint for wrong tool
- `FAILURE_HINT_PARAMS_INCORRECT` - Hint for wrong parameters
- `FAILURE_HINT_RETRY_TEMPLATE` - Template for retry messages

---

### 4. Graph Configuration (`graph_config.yaml`)

Defines the evaluation workflow and configuration.

#### Data Configuration

```yaml
data_config:
  source:
    type: "disk"
    file_path: "tasks/eval/agents/web_agents/chat_history_seed.json"
    transformations:
      - AddNewFieldTransform  # Add supported tools, dimensions
      - AddRetryFieldsTransform  # Add retry configuration
```

> **Note:** The `chat_history_seed.json` file currently contains only sample data with a few records for testing and development purposes. This is not a complete dataset.

#### Graph Configuration

**Properties:**
- `chat_conversation: multiturn` - Multi-turn conversation support
- `chat_history_window_size: 1000` - History window size
- `retry_chat_injection` - Retry prompt injection settings

**Nodes:**
- `fetch_next_action_tools` - Main LLM node for action prediction

**Lambdas:**
- `inline_evaluation` - Evaluate predictions inline
- `retry_flow` - Manage retry logic

**Edges:**
- `should_continue` - Conditional edge for workflow control

#### System Prompt Structure

The system prompt guides the agent with:
1. **Core Principles** - Think before acting, tool restrictions, trust screenshots
2. **Action Guidelines** - Pop-ups, ads, disabled elements, extraction, retries
3. **Interaction Rules** - Clicks, typing, scrolling, modals, dropdowns, tabs
4. **User Confirmation** - Authentication, sensitive data, destructive actions
5. **Mission Context** - Mission description, navigational directions
6. **Screenshot Specs** - Dimensions, coordinate system

#### Post-Processors

**Flatten**
```yaml
post_processors:
  - name: tasks.eval.agents.web_agents.task_executor.Flatten
```

**MetricCollatorPostProcessor**
```yaml
- name: tasks.eval.utils.MetricCollatorPostProcessor
  params:
    aggregator_metrics_map:
      - name: "accuracy"
        unit_metrics_results: ["step_match"]
      - name: "pass@k"
        params: {k: 3}
        unit_metrics_results: ["step_match"]
      - name: "pass^k"
        params: {k: 3}
        unit_metrics_results: ["step_match"]
      - name: "step_efficiency"
        params: {key: "tool"}
        metadata:
          mission_id: "mission_id"
          step_id: "turn"
          retry_id: "retry_id"
        unit_metrics_results: ["step_match"]
```

---

## Evaluation Metrics

### Unit Metrics (Inline)

Evaluated during execution:

1. **Tool Match** - Exact tool name match
2. **Step Match** - Comprehensive step validation:
   - Tool correctness
   - Parameter validation
   - Bounding box validation (click)
   - Direction validation (scroll)
   - Text matching (typing)

### Aggregator Metrics (Post-Processing)

Calculated after execution:

1. **Accuracy** - Overall success rate
2. **Pass@k** - Probability of success in k attempts
   - Returns: `pass@1`, `pass@2`, ..., `pass@k`
3. **Pass^k** - Probability of success in all k attempts
   - Returns: `success_rate`, `pass^1`, `pass^2`, ..., `pass^k`
4. **Step Efficiency** - Efficiency based on retry attempts
   - Metrics: `step_efficiency`, `first_attempt_correct`, `retry_correct`, `never_correct`
   - Penalty per retry: 0.2 (configurable)

---

## Workflow

### Execution Flow

```
1. Load Data (chat_history_seed.json)
   ↓
2. Add Transformations (tools, dimensions, retry fields)
   ↓
3. For each mission/step:
   ├─→ FetchNextActionPreProcessor
   │   ├─ Manage chat history
   │   ├─ Inject retry hints (if retry)
   │   └─ Log request
   ↓
   ├─→ LLM Node (fetch_next_action_tools)
   │   └─ Generate action prediction
   ↓
   ├─→ FetchNextActionPostProcessor
   │   ├─ Extract tool call
   │   ├─ Log response
   │   └─ Update state
   ↓
   ├─→ InlineEvaluationLambda
   │   ├─ Evaluate tool match
   │   ├─ Evaluate step match
   │   └─ Store results
   ↓
   ├─→ RetryFlow
   │   └─ Determine if retry needed
   ↓
   └─→ ShouldContinueCondition
       └─ Check if workflow continues
   ↓
4. Flatten (Post-Processor)
   └─ Flatten retry structure
   ↓
5. MetricCollatorPostProcessor
   └─ Calculate aggregator metrics
```

### Retry Logic

```
Initial Attempt (retry_0)
   ↓
   Evaluate
   ↓
   Failed? → Yes → Inject Failure Hint
                   ↓
                   Retry Attempt (retry_1)
                   ↓
                   Evaluate
                   ↓
                   Failed? → Yes → Inject Failure Hint
                                   ↓
                                   Retry Attempt (retry_2)
                                   ↓
                                   Max retries reached → Stop
```

**Failure Hints:**
- **Tool Incorrect**: "Do NOT use this tool again. Use a different tool."
- **Parameters Incorrect**: "Use the same tool with correct parameters."

---

## Usage

### Running Evaluation

```bash
# Run the web agent evaluation
python -m sygra.cli.run_graph \
  --config tasks/eval/agents/web_agents/graph_config.yaml
```

### Input Data Format

The input data is stored in `tasks/eval/agents/web_agents/chat_history_seed.json`. Currently, this file contains **sample data with only one mission** for testing and development purposes.

#### Sample Data Structure

Each record in the input file represents one step (turn) of a mission:

```json
{
  "id": "mission_01_2",
  "mission_id": "mission_01",
  "mission": "search for one way flight from hyd to chennai on nov 1 2025",
  "date": "2025-11-11 15:12:56",
  "navigational_directions": "",
  "turn": 2,
  "chat_history": [
    {
      "role": "system",
      "content": [
        {
          "text": "You are a web automation agent...",
          "type": "text"
        }
      ]
    },
    {
      "role": "user",
      "content": [
        {
          "text": "Help me now to complete the assigned mission...",
          "type": "text"
        }
      ]
    },
    {
      "content": "I'll help you search for a one-way flight...",
      "role": "assistant",
      "tool_calls": [
        {
          "id": "tooluse_O5Dr64r9RC-lW8BNsdHTng",
          "type": "function",
          "function": {
            "name": "screenshot_tool",
            "arguments": "{\"take_screenshot\": true}"
          }
        }
      ]
    },
    {
      "role": "tool",
      "tool_call_id": "tooluse_O5Dr64r9RC-lW8BNsdHTng",
      "name": "screenshot_tool",
      "content": "success"
    }
  ],
  "current_user_text": "You are now midway through the assigned mission...",
  "current_tool_result": {
    "role": "tool",
    "tool_call_id": "tooluse_O5Dr64r9RC-lW8BNsdHTng",
    "name": "screenshot_tool",
    "content": [
      {
        "image": {
          "format": "png",
          "source": {
            "bytes": "iVBORw0KGgoAAAANSUhEUgAAA+gAAAPoCAIAAADCwUOz..."
          }
        }
      }
    ]
  },
  "golden_response": {
    "tool": "click",
    "properties": {
      "x": 146.44,
      "y": 94.44,
      "width": 82.04,
      "height": 61.11,
      "offset_x": 0.0,
      "offset_y": 0.0
    }
  }
}
```

#### Field Descriptions

| Field | Type | Description |
|-------|------|-------------|
| `id` | string | Unique identifier for this step (format: `mission_id_turn`) |
| `mission_id` | string | Identifier for the mission this step belongs to |
| `mission` | string | Description of the overall mission/task |
| `date` | string | Timestamp of the mission |
| `navigational_directions` | string | Optional hints or directions for this step |
| `turn` | integer | Step number within the mission (1-indexed) |
| `chat_history` | array | Complete conversation history up to this point |
| `current_user_text` | string | The prompt text for the current step |
| `current_tool_result` | object | Result from the previous tool execution (includes screenshot) |
| `golden_response` | object | Expected correct response for evaluation |

#### Golden Response Structure

The `golden_response` contains the ground truth for evaluation:

**For Click Actions:**
```json
{
  "tool": "click",
  "properties": {
    "x": 146.44,
    "y": 94.44,
    "width": 82.04,
    "height": 61.11,
    "offset_x": 0.0,
    "offset_y": 0.0
  }
}
```

**For Typing Actions:**
```json
{
  "tool": "typing",
  "properties": {
    "text": "Hyderabad"
  }
}
```

**For Scroll Actions:**
```json
{
  "tool": "scroll",
  "properties": {
    "direction": "down",
    "amount": 200
  }
}
```

#### Current Sample Data

The `chat_history_seed.json` file currently contains:
- **1 mission** (`mission_01`)
- **Multiple steps/turns** for that mission
- Complete chat history for each step
- Screenshots embedded as base64 in `current_tool_result`
- Golden responses for evaluation

> **Note:** This is sample data for testing purposes. A production dataset would contain multiple missions with various web automation scenarios.

### Output Format

**Flattened Output:**
```json
{
  "id": "mission_1_step_1",
  "mission_id": "mission_1",
  "turn": 1,
  "retry_id": "retry_0",
  "model_response": {...},
  "tool_match": {"correct": true, "score": 1.0},
  "step_match": {"correct": true, "score": 1.0}
}
```

**Metrics Output:**
```json
{
  "evaluation_summary": {
    "total_records": 100,
    "timestamp": "2026-03-05 12:00:00",
    "status": "success"
  },
  "results": {
    "step_match-accuracy": 0.85,
    "step_match-pass@1": 0.75,
    "step_match-pass@2": 0.90,
    "step_match-pass@3": 0.95,
    "step_match-pass^1": 0.75,
    "step_match-pass^2": 0.5625,
    "step_match-pass^3": 0.421875,
    "step_match-step_efficiency": {
      "step_efficiency": 0.82,
      "first_attempt_correct": 75,
      "retry_correct": 10,
      "never_correct": 15
    }
  }
}
```

---

## Configuration

### Retry Configuration

```python
# In graph_config.yaml
max_retries: 3
retry_chat_injection:
  required: "yes"
  retry_prompt_injection: "yes"
```

### Metadata Mapping

```yaml
# For step_efficiency metric
metadata:
  mission_id: "mission_id"  # Maps to mission_id field
  step_id: "turn"           # Maps to turn field
  retry_id: "retry_id"      # Maps to retry_id field
```

### Image Scaling

```python
IMAGE_SCALE_FACTORS = {
    "50_percent": 0.5,
    "25_percent": 0.25,
    "30_percent": 0.3
}
```

---

## Logging

### Request/Response Logs

Location: `tasks/eval/agents/web_agents/logs/`

Format: `web_agent_requests_YYYYMMDD_HHMMSS.json`

### Log Entry Structure

```json
{
  "step": 1,
  "timestamp": "2026-03-05T12:00:00.000000",
  "type": "request",
  "payload": {
    "messages": [...],
    "tools": [...],
    "model": "..."
  }
}
```

---

## Error Handling

### Server Errors

Detected by `RequestResponseLogger.is_server_error()`:
- Checks for `SERVER_ERROR_MARKERS` in response
- Prevents retry on server errors
- Logs error details

### Validation Errors

Handled by inline evaluation:
- Tool mismatch
- Parameter validation failures
- Bounding box violations
- Direction mismatches

---

## Best Practices

1. **Always log requests/responses** for debugging
2. **Use retry hints** to guide agent corrections
3. **Validate inline** to catch errors early
4. **Configure metadata** for metrics that need context
5. **Monitor step efficiency** to optimize retry strategy
6. **Review logs** when debugging failures

---

## Extending the Module

### Adding New Tools

```python
# In tools.py
@tool
def new_tool(param1: type1, param2: type2):
    """Tool description.
    
    Args:
        param1: Description
        param2: Description
    """
    logger.info(f"Executing new_tool: {param1}, {param2}")
    return
```

### Adding New Metrics

```yaml
# In graph_config.yaml
- name: "custom_metric"
  params:
    custom_param: value
  metadata:
    field1: "source_field1"
  unit_metrics_results:
    - "step_match"
```

### Customizing Retry Logic

```python
# In task_executor.py
class CustomRetryFlow(LambdaFunction):
    @classmethod
    def apply(cls, lambda_node_dict: dict, state: SygraState) -> SygraState:
        # Custom retry logic
        return state
```

---

## Troubleshooting

### Common Issues

**Issue: Metrics not receiving metadata**
- Solution: Ensure metadata mapping is configured in graph_config.yaml

**Issue: Retry hints not appearing**
- Solution: Check `retry_chat_injection.required` is set to "yes"

**Issue: Step match always failing**
- Solution: Verify golden response format matches expected structure

**Issue: Logs not being created**
- Solution: Check logs directory exists and has write permissions

