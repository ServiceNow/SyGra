# Desktop Agent Tools Validation

This directory contains modules for extracting golden responses and validating desktop agent tool calls.

## Modules

### 1. `golden_response_extractor.py`
Extracts golden/expected responses from desktop agent records for validation.

**Main Function:**
```python
from tasks.web_agents.desktop_agent_eval.golden_response_extractor import extract_golden_response_from_record

# Extract golden response from a complete record
golden_response = extract_golden_response_from_record(record)
```

**What it does:**
- Extracts tool call from `record['chat_history'][-2]` (penultimate chat entry)
- Uses `record['bbox']` if available (preferred source for bounding boxes)
- Uses `record['typedValue']` for write tool content (overrides chat history value)
- Adds `record['event_type']` for validation context

**Helper Functions:**
- `extract_tool_name(golden_response)` - Get tool name
- `extract_tool_input(golden_response)` - Get tool input parameters
- `extract_bbox(golden_response)` - Get bounding box if present
- `get_mouse_coordinates(golden_response)` - Get (x, y) for mouse_move
- `get_typed_content(golden_response)` - Get content for write tool
- `get_key_name(golden_response)` - Get key for press tool
- `get_hot_keys(golden_response)` - Get key list for hot_key tool
- `get_scroll_value(golden_response)` - Get scroll amount
- `get_scroll_direction(golden_response)` - Get scroll direction

### 2. `desktop_tools_validation.py`
Validates model responses against golden responses for all desktop agent tools.

**Main Function:**
```python
from tasks.agents.desktop_agent_eval.desktop_tools_validation import validate_desktop_tool

# Validate model response
result = validate_desktop_tool(model_response, golden_response)
# Returns: {"correct": bool, "reason": str, ...additional metrics...}
```

**Supported Tools:**
- `mouse_move` - Validates coordinates within bbox or tolerance
- `left_click`, `right_click`, `double_left_click` - Validates tool name match
- `write` - Validates typed content with fuzzy matching
- `press` - Validates key name
- `hot_key` - Validates key sequence
- `horizontal_scroll`, `vertical_scroll` - Validates direction and magnitude
- `screenshot` - Validates tool call
- `get_current_cursor_coords` - Validates tool call

**Validation Constants:**
```python
COORDINATE_TOLERANCE_PIXELS = 50  # Tolerance for mouse coordinates
SCROLL_VALUE_TOLERANCE_PERCENT = 20.0  # Tolerance for scroll amounts
FUZZY_MATCH_THRESHOLD = 0.85  # Threshold for text matching
```

## Usage Examples

### Example 1: Processing Records in `chat_history_to_data.py`

```python
from tasks.agents.desktop_agent_eval.golden_response_extractor import extract_golden_response_from_record

# Process each record to add golden_response
for record in data:
    try:
        golden_response = extract_golden_response_from_record(record)
        record['golden_response'] = golden_response
    except ValueError as e:
        print(f"Error extracting golden response: {e}")
        continue
```

### Example 2: Validating Model Responses

```python
from tasks.agents.desktop_agent_eval.golden_response_extractor import extract_golden_response_from_record
from tasks.agents.desktop_agent_eval.desktop_tools_validation import validate_desktop_tool

# Extract golden response
golden_response = extract_golden_response_from_record(record)

# Model's predicted response
model_response = {
    'tool_name': 'mouse_move',
    'tool_input': {'x': 360, 'y': 345}
}

# Validate
result = validate_desktop_tool(model_response, golden_response)

if result['correct']:
    print(f"✓ Validation passed: {result['reason']}")
else:
    print(f"✗ Validation failed: {result['reason']}")
```

### Example 3: Tool-Specific Validation

```python
from tasks.agents.desktop_agent_eval.desktop_tools_validation import (
    validate_mouse_move,
    validate_write_tool,
    validate_click_tool
)

# Validate mouse_move specifically
result = validate_mouse_move(model_response, golden_response)
print(f"Within bbox: {result['within_bbox']}")
print(f"Distance: {result['distance_from_golden']:.2f}px")

# Validate write tool
result = validate_write_tool(model_response, golden_response)
print(f"Exact match: {result['exact_match']}")
print(f"Similarity: {result['similarity_score']:.2%}")
```

## Record Structure

### Input Record Format
```python
record = {
    'scenario_id': 1,
    'step_id': 12,
    'objective': 'Task description',
    'chat_history': [
        {'role': 'user', 'content': [...]},
        {'role': 'assistant', 'content': [
            {'text': 'Description'},
            {'toolUse': {
                'name': 'tool_name',
                'input': {...},
                'toolUseId': 'id'
            }}
        ]},
        {'role': 'user', 'content': [...]}  # Last entry
    ],
    'bbox': {'x': 352, 'y': 341, 'width': 128, 'height': 30},  # Optional but preferred
    'typedValue': 'text content',  # For write tool
    'event_type': 'click',  # Event type
    # ... other fields
}
```

### Golden Response Format
```python
golden_response = {
    'tool_name': 'mouse_move',
    'tool_input': {'x': 414, 'y': 356},
    'tool_use_id': 'tooluse_xyz',
    'bbox': {'x': 352, 'y': 341, 'width': 128, 'height': 30},
    'event_type': 'mouse_move',
    'properties': {
        'bbox': {...},
        'typedValue': '...'  # If applicable
    }
}
```

### Model Response Format
```python
model_response = {
    'tool_name': 'mouse_move',
    'tool_input': {'x': 360, 'y': 345}
}
```

### Validation Result Format
```python
result = {
    'correct': True,
    'reason': 'Coordinates within bounding box',
    # Tool-specific additional fields:
    'within_bbox': True,  # For mouse_move
    'near_bbox': True,
    'distance_from_golden': 8.94,
    'similarity_score': 0.95,  # For write tool
    'exact_match': False,
    # ... etc
}
```

## Integration Points

### 1. Data Preparation (`chat_history_to_data.py`)
Use `extract_golden_response_from_record()` to populate `golden_response` field for each record.

### 2. Model Evaluation (`desktop_agent_metrics.py`)
Use `validate_desktop_tool()` to compare model predictions against golden responses.

### 3. Task Executor (`task_executor.py`)
Extract golden responses during execution for real-time validation.

## Validation Logic

### Mouse Move
- **Primary**: Check if coordinates within bbox
- **Secondary**: Check if coordinates near bbox (within 50px tolerance)
- **Tertiary**: Check distance from golden coordinates

### Click Tools
- Simple tool name matching (left_click, right_click, double_left_click)

### Write Tool
- Normalize text (lowercase, strip whitespace)
- Exact match check
- Fuzzy match with 85% similarity threshold
- Uses `typedValue` from record if available (overrides chat history)

### Press Tool
- Normalize and compare key names (case-insensitive)

### Hot Key Tool
- Compare key sequences (order matters)
- Normalize each key name

### Scroll Tools
- Validate direction (sign of value)
- Validate magnitude within 20% tolerance

## Testing

Run the example usage script to see all modules in action:
```bash
python -m tasks.agents.desktop_agent_eval.example_usage
```

Run individual module tests:
```bash
python -m tasks.agents.desktop_agent_eval.golden_response_extractor
python -m tasks.agents.desktop_agent_eval.desktop_tools_validation
```

## Notes

- **bbox preference**: If `record['bbox']` exists, it's used instead of any bbox in chat_history
- **typedValue override**: For write tool, `record['typedValue']` overrides the content in tool_input
- **chat_history[-2]**: Always the penultimate entry, which should be the assistant's tool call
- **Fuzzy matching**: Desktop agents use higher threshold (0.85) than web agents (0.2) for text matching
- **Coordinate tolerance**: 50px tolerance for mouse movements (configurable)
