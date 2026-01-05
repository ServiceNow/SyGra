"""
Module to extract golden/expected response from desktop agent chat history.

This module parses the penultimate entry in chat_history (data[i]['chat_history'][-2])
to extract the golden tool call and its properties for validation purposes.
"""

import json
from typing import Dict, Any, Optional


def extract_golden_response_from_record(record: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract golden response from a complete record.
    
    This is the main entry point that extracts golden response from:
    1. record['chat_history'][-2] for tool call information
    2. record['bbox'] for bounding box (preferred if available)
    3. record['typedValue'] for typed text content
    4. record['event_type'] for event type validation
    
    Args:
        record (dict): Complete record with keys:
            - 'chat_history': List of chat messages
            - 'bbox': Bounding box dict (optional, preferred)
            - 'typedValue': Typed text value (optional)
            - 'event_type': Event type string
    
    Returns:
        dict: Golden response with structure:
            {
                "tool_name": str,
                "tool_input": dict,
                "tool_use_id": str,
                "bbox": dict (if applicable),
                "event_type": str,
                "properties": dict (additional properties)
            }
    
    Raises:
        ValueError: If the record format is invalid or chat_history is empty
    """
    chat_history = record.get('chat_history', [])
    
    if not chat_history or len(chat_history) < 2:
        raise ValueError(f"chat_history must have at least 2 entries, got {len(chat_history)}")
    
    # Extract from chat_history[-2]
    chat_history_entry = chat_history[-2]
    golden_response = extract_golden_response_from_chat_entry(chat_history_entry)
    
    # Prefer bbox from record if available
    record_bbox = record.get('bbox')
    if record_bbox and isinstance(record_bbox, dict):
        golden_response['bbox'] = [record_bbox]
        golden_response['properties']['bbox'] = [record_bbox]
    elif record_bbox and isinstance(record_bbox, list):
        golden_response['bbox'] = record_bbox
        golden_response['properties']['bbox'] = record_bbox
    
    # Add typedValue if present (for write tool)
    typed_value = record.get('typedValue')
    if typed_value is not None:
        golden_response['properties']['typedValue'] = typed_value
        # Update tool_input for write tool
        if golden_response['tool_name'] == 'write':
            golden_response['tool_input']['content'] = typed_value
    
    # Add event_type for validation
    event_type = record.get('event_type')
    if event_type:
        golden_response['event_type'] = event_type
    
    return golden_response


def extract_golden_response_from_chat_entry(chat_history_entry: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract golden response from a single chat history entry.
    
    The chat_history_entry is expected to be data[i]['chat_history'][-2], which is a dict
    with 'role': 'assistant' and 'content' containing the tool call.
    
    Args:
        chat_history_entry (dict): Assistant message dict with 'content' and 'role'
    
    Returns:
        dict: Golden response with structure:
            {
                "tool_name": str,
                "tool_input": dict,
                "tool_use_id": str,
                "bbox": dict (empty if not in chat),
                "properties": dict
            }
    
    Raises:
        ValueError: If the chat_history_entry format is invalid
    """
    # Validate assistant message structure
    if not isinstance(chat_history_entry, dict):
        raise ValueError(f"Expected chat_history_entry to be dict, got: {type(chat_history_entry)}")
    
    if chat_history_entry.get("role") != "assistant":
        raise ValueError(f"Expected role 'assistant', got: {chat_history_entry.get('role')}")
    
    content = chat_history_entry.get("content", [])
    if not isinstance(content, list):
        raise ValueError(f"Expected content to be list, got: {type(content)}")
    
    # Find the toolUse in content
    tool_use_data = None
    for content_item in content:
        if isinstance(content_item, dict) and "toolUse" in content_item:
            tool_use_data = content_item["toolUse"]
            break
    
    if tool_use_data is None:
        raise ValueError("No toolUse found in assistant message content")
    
    # Extract tool information
    tool_name = tool_use_data.get("name", "")
    tool_input = tool_use_data.get("input", {})
    tool_use_id = tool_use_data.get("toolUseId", "")
    
    # Build golden response
    golden_response = {
        "tool_name": tool_name,
        "tool_input": tool_input,
        "tool_use_id": tool_use_id,
        "bbox": {},  # Will be populated from record if available
        "properties": {}
    }
    
    return golden_response


def extract_tool_name(golden_response: Dict[str, Any]) -> str:
    """Extract tool name from golden response."""
    return golden_response.get("tool_name", "")


def extract_tool_input(golden_response: Dict[str, Any]) -> Dict[str, Any]:
    """Extract tool input parameters from golden response."""
    return golden_response.get("tool_input", {})


def extract_bbox(golden_response: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Extract bounding box from golden response if present."""
    bbox = golden_response.get("bbox", {})
    return bbox if bbox else None


def get_mouse_coordinates(golden_response: Dict[str, Any]) -> Optional[tuple]:
    """
    Extract mouse coordinates from golden response for mouse_move tool.
    
    Returns:
        tuple: (x, y) coordinates or None if not applicable
    """
    tool_name = extract_tool_name(golden_response)
    tool_input = extract_tool_input(golden_response)
    
    if tool_name == "mouse_move":
        x = tool_input.get("x")
        y = tool_input.get("y")
        if x is not None and y is not None:
            return (x, y)
    
    return None


def get_typed_content(golden_response: Dict[str, Any]) -> Optional[str]:
    """
    Extract typed content from golden response for write tool.
    
    Returns:
        str: The content to be typed, or None if not applicable
    """
    tool_name = extract_tool_name(golden_response)
    tool_input = extract_tool_input(golden_response)
    
    if tool_name == "write":
        return tool_input.get("content")
    
    return None


def get_key_name(golden_response: Dict[str, Any]) -> Optional[str]:
    """
    Extract key name from golden response for press tool.
    
    Returns:
        str: The key name to be pressed, or None if not applicable
    """
    tool_name = extract_tool_name(golden_response)
    tool_input = extract_tool_input(golden_response)
    
    if tool_name == "press":
        return tool_input.get("key_name")
    
    return None


def get_hot_keys(golden_response: Dict[str, Any]) -> Optional[list]:
    """
    Extract hot key list from golden response for hot_key tool.
    
    Returns:
        list: List of keys to be pressed, or None if not applicable
    """
    tool_name = extract_tool_name(golden_response)
    tool_input = extract_tool_input(golden_response)
    
    if tool_name == "hot_key":
        return tool_input.get("list_of_keys")
    
    return None


def get_scroll_value(golden_response: Dict[str, Any]) -> Optional[int]:
    """
    Extract scroll value from golden response for scroll tools.
    
    Returns:
        int: Scroll value (positive or negative), or None if not applicable
    """
    tool_name = extract_tool_name(golden_response)
    tool_input = extract_tool_input(golden_response)
    
    if tool_name in ["horizontal_scroll", "vertical_scroll"]:
        return tool_input.get("value")
    
    return None


def get_scroll_direction(golden_response: Dict[str, Any]) -> Optional[str]:
    """
    Determine scroll direction from golden response.
    
    Returns:
        str: One of "up", "down", "left", "right", or None if not applicable
    """
    tool_name = extract_tool_name(golden_response)
    scroll_value = get_scroll_value(golden_response)
    
    if scroll_value is None:
        return None
    
    if tool_name == "vertical_scroll":
        # Positive for scrolling up, negative for scrolling down
        return "up" if scroll_value > 0 else "down"
    elif tool_name == "horizontal_scroll":
        # Negative for scrolling left, positive for scrolling right
        return "left" if scroll_value < 0 else "right"
    
    return None


# Example usage and testing
if __name__ == "__main__":
    # Sample test data from the provided example
    sample_chat_entry = {
        'content': [
            {'text': 'I can see the cursor is positioned over the "Upload a file" button. Now I need to click on it to initiate the file upload process for the CSV file.'},
            {'toolUse': {
                'input': {},
                'name': 'left_click',
                'toolUseId': 'tooluse_SjNmShNPSv-QJ2CI8SmOrg'
            }}
        ],
        'role': 'assistant'
    }
    
    # Test 1: Extract from chat entry only
    print("=== Test 1: Extract from chat entry ===")
    golden = extract_golden_response_from_chat_entry(sample_chat_entry)
    print("Extracted Golden Response:")
    print(json.dumps(golden, indent=2))
    
    # Test 2: Extract from complete record with bbox
    print("\n=== Test 2: Extract from complete record with bbox ===")
    sample_record = {
        'chat_history': [
            {'role': 'user', 'content': [{'text': 'Start task'}]},
            sample_chat_entry,
            {'role': 'user', 'content': [{'text': 'Continue'}]}
        ],
        'bbox': {'x': 352, 'y': 341, 'width': 128, 'height': 30},
        'typedValue': None,
        'event_type': 'click'
    }
    
    golden_from_record = extract_golden_response_from_record(sample_record)
    print("Extracted Golden Response from Record:")
    print(json.dumps(golden_from_record, indent=2))
    
    # Test 3: Extract from record with write tool and typedValue
    print("\n=== Test 3: Extract from record with write tool ===")
    write_chat_entry = {
        'content': [
            {'text': 'Let me use the write tool as my next action.'},
            {'toolUse': {
                'input': {'content': 'microsoft office 365'},
                'name': 'write',
                'toolUseId': 'tooluse_gkiwdXZ1T8eaQNVNVfrcmQ'
            }}
        ],
        'role': 'assistant'
    }
    
    write_record = {
        'chat_history': [
            {'role': 'user', 'content': [{'text': 'Start task'}]},
            write_chat_entry,
            {'role': 'user', 'content': [{'text': 'Continue'}]}
        ],
        'bbox': {},
        'typedValue': 'Microsoft Office 365',  # This should override the content in tool_input
        'event_type': 'typing'
    }
    
    golden_write = extract_golden_response_from_record(write_record)
    print("Extracted Golden Response for Write Tool:")
    print(json.dumps(golden_write, indent=2))
    
    # Test helper functions
    print("\n=== Test helper functions ===")
    print(f"Tool Name: {extract_tool_name(golden_from_record)}")
    print(f"Tool Input: {extract_tool_input(golden_from_record)}")
    print(f"BBox: {extract_bbox(golden_from_record)}")
    print(f"Typed Content: {get_typed_content(golden_write)}")
