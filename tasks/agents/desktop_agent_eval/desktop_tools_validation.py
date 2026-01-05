"""
Desktop Agent Tools Validation Module

This module validates model responses against golden responses for desktop agent tools.
It provides validation functions for each tool type supported in the desktop agent task.
"""

import re
from typing import Dict, Any, Optional, List
from difflib import SequenceMatcher


# Constants for validation thresholds
COORDINATE_TOLERANCE_PIXELS = 50  # Tolerance for mouse coordinate validation
SCROLL_VALUE_TOLERANCE_PERCENT = 20.0  # Percentage tolerance for scroll amounts
FUZZY_MATCH_THRESHOLD = 0.80  # Threshold for fuzzy string matching (higher than web agents)
BBOX_REQUIRED_TOOLS = ["mouse_move"]  # Tools that require bbox validation


def normalize_text(text: str) -> str:
    """Lowercase, strip, and collapse multiple spaces into one."""
    return re.sub(r"\s+", " ", text.strip().lower())


def is_coordinate_within_bbox(x: int, y: int, bbox: Dict[str, int]) -> bool:
    """
    Check if coordinates fall within a bounding box.
    
    Args:
        x (int): X coordinate
        y (int): Y coordinate
        bbox (dict): Bounding box with keys 'x', 'y', 'width', 'height'
    
    Returns:
        bool: True if coordinates are within bbox, False otherwise
    """
    if not bbox or not all(k in bbox for k in ['x', 'y', 'width', 'height']):
        return False
    
    x_min = bbox['x']
    y_min = bbox['y']
    x_max = bbox['x'] + bbox['width']
    y_max = bbox['y'] + bbox['height']
    
    return x_min <= x <= x_max and y_min <= y <= y_max


def is_coordinate_near_bbox(x: int, y: int, bbox: Dict[str, int], tolerance: int = COORDINATE_TOLERANCE_PIXELS) -> bool:
    """
    Check if coordinates are near a bounding box (within tolerance).
    
    Args:
        x (int): X coordinate
        y (int): Y coordinate
        bbox (dict): Bounding box with keys 'x', 'y', 'width', 'height'
        tolerance (int): Pixel tolerance for proximity
    
    Returns:
        bool: True if coordinates are within tolerance of bbox
    """
    if not bbox or not all(k in bbox for k in ['x', 'y', 'width', 'height']):
        return False
    
    # Expand bbox by tolerance
    x_min = bbox['x'] - tolerance
    y_min = bbox['y'] - tolerance
    x_max = bbox['x'] + bbox['width'] + tolerance
    y_max = bbox['y'] + bbox['height'] + tolerance
    
    return x_min <= x <= x_max and y_min <= y <= y_max


def validate_mouse_move(model_response: Dict[str, Any], golden_response: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate mouse_move tool call.
    
    Args:
        model_response (dict): Model's predicted response with tool_name and tool_input
        golden_response (dict): Golden response with tool_name, tool_input, and bbox
    
    Returns:
        dict: Validation result with 'correct', 'reason', and detailed metrics
    """
    # Check tool name matches
    if model_response.get("tool_name") != "mouse_move":
        return {
            "correct": False,
            "reason": f"Tool name mismatch: expected 'mouse_move', got '{model_response.get('tool_name')}'",
            "within_bbox": False,
            "near_bbox": False
        }
    
    # Extract coordinates
    model_input = model_response.get("tool_input", {})
    golden_input = golden_response.get("tool_input", {})
    golden_bbox = golden_response.get("bbox", [])
    
    model_x = model_input.get("x")
    model_y = model_input.get("y")
    golden_x = golden_input.get("x")
    golden_y = golden_input.get("y")
    
    if model_x is None or model_y is None:
        return {
            "correct": False,
            "reason": "Model response missing x or y coordinates",
            "within_bbox": False,
            "near_bbox": False
        }

    # Handle bbox as either dict or list of dicts
    bbox_list = []
    if isinstance(golden_bbox, list):
        bbox_list = golden_bbox
    elif isinstance(golden_bbox, dict) and golden_bbox:
        bbox_list = [golden_bbox]

    # Check if within any bbox (if bboxes available)
    within_bbox = False
    near_bbox = False

    if bbox_list:
        for bbox in bbox_list:
            if is_coordinate_within_bbox(model_x, model_y, bbox):
                within_bbox = True
                break

        if not within_bbox:
            for bbox in bbox_list:
                if is_coordinate_near_bbox(model_x, model_y, bbox):
                    near_bbox = True
                    break
    # Calculate distance from golden coordinates
    if golden_x is not None and golden_y is not None:
        distance = ((model_x - golden_x) ** 2 + (model_y - golden_y) ** 2) ** 0.5
        within_tolerance = distance <= COORDINATE_TOLERANCE_PIXELS
    else:
        distance = None
        within_tolerance = None
    
    # Determine correctness
    correct = False
    reason = ""
    
    if within_bbox:
        correct = True
        reason = "Coordinates within bounding box"
    # elif near_bbox:
    #     correct = True
    #     reason = f"Coordinates near bounding box (within {COORDINATE_TOLERANCE_PIXELS}px tolerance)"
    # elif within_tolerance:
    #     correct = True
    #     reason = f"Coordinates within tolerance of golden coordinates (distance: {distance:.2f}px)"
    else:
        if golden_bbox:
            reason = f"Coordinates outside bounding box and tolerance. Distance from golden: {distance:.2f}px" if distance else "Coordinates outside bounding box"
        else:
            # reason = f"Coordinates too far from golden (distance: {distance:.2f}px, tolerance: {COORDINATE_TOLERANCE_PIXELS}px)" if distance else "Unable to validate coordinates"
            reason = f"Unable to validate coordinates"
    
    return {
        "correct": correct,
        "reason": reason,
        "within_bbox": within_bbox,
        "near_bbox": near_bbox,
        "distance_from_golden": distance,
        "model_coords": (model_x, model_y),
        "golden_coords": (golden_x, golden_y) if golden_x is not None else None
    }


def validate_click_tool(model_response: Dict[str, Any], golden_response: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate click tools (left_click, right_click, double_left_click).
    
    These tools don't have input parameters but must match the tool name.
    
    Args:
        model_response (dict): Model's predicted response
        golden_response (dict): Golden response
    
    Returns:
        dict: Validation result
    """
    model_tool = model_response.get("tool_name")
    golden_tool = golden_response.get("tool_name")
    
    valid_click_tools = ["left_click", "right_click", "double_left_click"]
    
    if model_tool not in valid_click_tools:
        return {
            "correct": False,
            "reason": f"Invalid click tool: '{model_tool}'"
        }
    
    if model_tool == golden_tool:
        return {
            "correct": True,
            "reason": f"Click tool matches: {model_tool}"
        }
    else:
        return {
            "correct": False,
            "reason": f"Click tool mismatch: expected '{golden_tool}', got '{model_tool}'"
        }


def validate_write_tool(model_response: Dict[str, Any], golden_response: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate write tool (typing text).
    
    Args:
        model_response (dict): Model's predicted response
        golden_response (dict): Golden response
    
    Returns:
        dict: Validation result with fuzzy matching details
    """
    if model_response.get("tool_name") != "write":
        return {
            "correct": False,
            "reason": f"Tool name mismatch: expected 'write', got '{model_response.get('tool_name')}'",
            "exact_match": False,
            "fuzzy_match": False,
            "similarity_score": 0.0
        }
    
    model_input = model_response.get("tool_input", {})
    golden_input = golden_response.get("tool_input", {})
    
    model_content = model_input.get("content", "")
    golden_content = golden_input.get("content", "")
    
    if not golden_content:
        return {
            "correct": False,
            "reason": "Golden content is empty",
            "exact_match": False,
            "fuzzy_match": False,
            "similarity_score": 0.0
        }
    
    # Normalize for comparison
    model_norm = normalize_text(model_content)
    golden_norm = normalize_text(golden_content)
    
    # Exact match
    exact_match = model_norm == golden_norm
    
    # Fuzzy match
    similarity = SequenceMatcher(None, model_norm, golden_norm).ratio()
    fuzzy_match = similarity >= FUZZY_MATCH_THRESHOLD
    
    # Determine correctness
    correct = exact_match or fuzzy_match
    
    if exact_match:
        reason = "Exact text match"
    elif fuzzy_match:
        reason = f"Fuzzy text match (similarity: {similarity:.2%})"
    else:
        reason = f"Text mismatch (similarity: {similarity:.2%}, threshold: {FUZZY_MATCH_THRESHOLD:.2%})"
    
    return {
        "correct": correct,
        "reason": reason,
        "exact_match": exact_match,
        "fuzzy_match": fuzzy_match,
        "similarity_score": similarity,
        "model_content": model_content,
        "golden_content": golden_content
    }


def validate_press_tool(model_response: Dict[str, Any], golden_response: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate press tool (single key press).
    
    Args:
        model_response (dict): Model's predicted response
        golden_response (dict): Golden response
    
    Returns:
        dict: Validation result
    """
    if model_response.get("tool_name") != "press":
        return {
            "correct": False,
            "reason": f"Tool name mismatch: expected 'press', got '{model_response.get('tool_name')}'"
        }
    
    model_input = model_response.get("tool_input", {})
    golden_input = golden_response.get("tool_input", {})
    
    model_key = normalize_text(model_input.get("key_name", ""))
    golden_key = normalize_text(golden_input.get("key_name", ""))
    
    if model_key == golden_key:
        return {
            "correct": True,
            "reason": f"Key name matches: '{golden_key}'",
            "model_key": model_key,
            "golden_key": golden_key
        }
    else:
        return {
            "correct": False,
            "reason": f"Key name mismatch: expected '{golden_key}', got '{model_key}'",
            "model_key": model_key,
            "golden_key": golden_key
        }


def validate_hot_key_tool(model_response: Dict[str, Any], golden_response: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate hot_key tool (multiple keys pressed together).
    
    Args:
        model_response (dict): Model's predicted response
        golden_response (dict): Golden response
    
    Returns:
        dict: Validation result
    """
    if model_response.get("tool_name") != "hot_key":
        return {
            "correct": False,
            "reason": f"Tool name mismatch: expected 'hot_key', got '{model_response.get('tool_name')}'"
        }
    
    model_input = model_response.get("tool_input", {})
    golden_input = golden_response.get("tool_input", {})
    
    model_keys = model_input.get("list_of_keys", [])
    golden_keys = golden_input.get("list_of_keys", [])
    
    # Normalize keys
    model_keys_norm = [normalize_text(k) for k in model_keys]
    golden_keys_norm = [normalize_text(k) for k in golden_keys]
    
    # Check if lists match (order matters for hot keys)
    if model_keys_norm == golden_keys_norm:
        return {
            "correct": True,
            "reason": f"Hot key sequence matches: {golden_keys}",
            "model_keys": model_keys,
            "golden_keys": golden_keys
        }
    else:
        return {
            "correct": False,
            "reason": f"Hot key mismatch: expected {golden_keys}, got {model_keys}",
            "model_keys": model_keys,
            "golden_keys": golden_keys
        }


def validate_scroll_tool(model_response: Dict[str, Any], golden_response: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate scroll tools (horizontal_scroll, vertical_scroll).
    
    Args:
        model_response (dict): Model's predicted response
        golden_response (dict): Golden response
    
    Returns:
        dict: Validation result with scroll direction and amount validation
    """
    model_tool = model_response.get("tool_name")
    golden_tool = golden_response.get("tool_name")
    
    valid_scroll_tools = ["horizontal_scroll", "vertical_scroll"]
    
    if model_tool not in valid_scroll_tools:
        return {
            "correct": False,
            "reason": f"Invalid scroll tool: '{model_tool}'"
        }
    
    if model_tool != golden_tool:
        return {
            "correct": False,
            "reason": f"Scroll tool mismatch: expected '{golden_tool}', got '{model_tool}'"
        }
    
    model_input = model_response.get("tool_input", {})
    golden_input = golden_response.get("tool_input", {})
    
    model_value = model_input.get("value")
    golden_value = golden_input.get("value")
    
    if model_value is None:
        return {
            "correct": False,
            "reason": "Model response missing scroll value"
        }
    
    if golden_value is None:
        return {
            "correct": False,
            "reason": "Golden response missing scroll value"
        }
    
    # Check direction (sign of value)
    model_direction = "positive" if model_value > 0 else "negative" if model_value < 0 else "zero"
    golden_direction = "positive" if golden_value > 0 else "negative" if golden_value < 0 else "zero"
    
    direction_matches = model_direction == golden_direction
    
    # Check magnitude within tolerance
    # if golden_value == 0:
    #     magnitude_valid = model_value == 0
    #     difference_percent = 0.0 if model_value == 0 else float('inf')
    # else:
    #     difference = abs(model_value - golden_value)
    #     difference_percent = (difference / abs(golden_value)) * 100
    #     magnitude_valid = difference_percent <= SCROLL_VALUE_TOLERANCE_PERCENT
    
    # # Determine correctness
    # correct = direction_matches and magnitude_valid

    # Determine correctness only based on direction
    correct = direction_matches


    
    if correct:
        reason = f"Scroll validation passed: {model_tool} with value {model_value}"
    else:
        reason = f"Scroll direction mismatch: expected {golden_direction}, got {model_direction}"
    # elif not direction_matches:
    #     reason = f"Scroll direction mismatch: expected {golden_direction}, got {model_direction}"
    # else:
    #     reason = f"Scroll amount outside tolerance: difference {difference_percent:.1f}% (threshold: {SCROLL_VALUE_TOLERANCE_PERCENT}%)"
    
    return {
        "correct": correct,
        "reason": reason,
        "direction_matches": direction_matches,
        # "magnitude_valid": magnitude_valid,
        "model_value": model_value,
        "golden_value": golden_value,
        # "difference_percent": difference_percent
    }


def validate_screenshot_tool(model_response: Dict[str, Any], golden_response: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate screenshot tool (no parameters).
    
    Args:
        model_response (dict): Model's predicted response
        golden_response (dict): Golden response
    
    Returns:
        dict: Validation result
    """
    if model_response.get("tool_name") == "screenshot":
        return {
            "correct": True,
            "reason": "Screenshot tool called correctly"
        }
    else:
        return {
            "correct": False,
            "reason": f"Tool name mismatch: expected 'screenshot', got '{model_response.get('tool_name')}'"
        }


def validate_drag_tool(model_response: Dict[str, Any], golden_response: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate drag tool (dragging from current position by x and y pixels).

    The drag tool moves the cursor x pixels to the right and y pixels downwards
    from the current cursor position while holding left-click.

    Args:
        model_response (dict): Model's predicted response with tool_name and tool_input
        golden_response (dict): Golden response with tool_name, tool_input, and bbox (can be dict or list of dicts)

    Returns:
        dict: Validation result with 'correct', 'reason', and detailed metrics
    """
    # Check tool name matches
    if model_response.get("tool_name") != "drag":
        return {
            "correct": False,
            "reason": f"Tool name mismatch: expected 'drag', got '{model_response.get('tool_name')}'",
            "within_bbox": False,
            "near_bbox": False
        }

    # Extract coordinates
    model_input = model_response.get("tool_input", {})
    golden_input = golden_response.get("tool_input", {})
    golden_bbox = golden_response.get("bbox", [])

    model_x = model_input.get("x")
    model_y = model_input.get("y")
    golden_x = golden_input.get("x")
    golden_y = golden_input.get("y")

    if model_x is None or model_y is None:
        return {
            "correct": False,
            "reason": "Model response missing x or y coordinates",
            "within_bbox": False,
            "near_bbox": False
        }

    # Handle bbox as either dict or list of dicts
    bbox_list = []
    if isinstance(golden_bbox, list):
        bbox_list = golden_bbox
    elif isinstance(golden_bbox, dict) and golden_bbox:
        bbox_list = [golden_bbox]

    # Check if within any bbox (if bboxes available)
    within_bbox = False
    near_bbox = False

    if bbox_list:
        for bbox in bbox_list:
            if is_coordinate_within_bbox(model_x, model_y, bbox):
                within_bbox = True
                break

        if not within_bbox:
            for bbox in bbox_list:
                if is_coordinate_near_bbox(model_x, model_y, bbox):
                    near_bbox = True
                    break

    # Calculate distance from golden coordinates
    if golden_x is not None and golden_y is not None:
        distance = ((model_x - golden_x) ** 2 + (model_y - golden_y) ** 2) ** 0.5
        within_tolerance = distance <= COORDINATE_TOLERANCE_PIXELS
    else:
        distance = None
        within_tolerance = None

    # Determine correctness
    correct = False
    reason = ""

    if within_bbox:
        correct = True
        reason = "Coordinates within bounding box"
    else:
        if bbox_list:
            reason = f"Coordinates outside bounding box and tolerance. Distance from golden: {distance:.2f}px" if distance else "Coordinates outside bounding box"
        else:
            reason = f"Unable to validate coordinates"

    return {
        "correct": correct,
        "reason": reason,
        "within_bbox": within_bbox,
        "near_bbox": near_bbox,
        "distance_from_golden": distance,
        "model_coords": (model_x, model_y),
        "golden_coords": (golden_x, golden_y) if golden_x is not None else None
    }


def validate_get_cursor_coords_tool(model_response: Dict[str, Any], golden_response: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate get_current_cursor_coords tool (no parameters).
    
    Args:
        model_response (dict): Model's predicted response
        golden_response (dict): Golden response
    
    Returns:
        dict: Validation result
    """
    if model_response.get("tool_name") == "get_current_cursor_coords":
        return {
            "correct": True,
            "reason": "Get cursor coords tool called correctly"
        }
    else:
        return {
            "correct": False,
            "reason": f"Tool name mismatch: expected 'get_current_cursor_coords', got '{model_response.get('tool_name')}'"
        }


def validate_desktop_tool(model_response: Dict[str, Any], golden_response: Dict[str, Any]) -> Dict[str, Any]:
    """
    Main validation function that routes to appropriate validator based on tool type.
    
    Args:
        model_response (dict): Model's predicted response with structure:
            {
                "tool_name": str,
                "tool_input": dict,
                ...
            }
        golden_response (dict): Golden response with structure:
            {
                "tool_name": str,
                "tool_input": dict,
                "bbox": dict (optional),
                ...
            }
    
    Returns:
        dict: Validation result with 'correct' (bool) and 'reason' (str) at minimum
    """
    golden_tool = golden_response.get("tool_name", "")
    
    # Route to appropriate validator
    if golden_tool == "mouse_move":
        return validate_mouse_move(model_response, golden_response)
    elif golden_tool in ["left_click", "right_click", "double_left_click"]:
        return validate_click_tool(model_response, golden_response)
    elif golden_tool == "write":
        return validate_write_tool(model_response, golden_response)
    elif golden_tool == "press":
        return validate_press_tool(model_response, golden_response)
    elif golden_tool == "hot_key":
        return validate_hot_key_tool(model_response, golden_response)
    elif golden_tool in ["horizontal_scroll", "vertical_scroll"]:
        return validate_scroll_tool(model_response, golden_response)
    elif golden_tool == "screenshot":
        return validate_screenshot_tool(model_response, golden_response)
    elif golden_tool == "get_current_cursor_coords":
        return validate_get_cursor_coords_tool(model_response, golden_response)
    elif golden_tool == "drag":
        return validate_drag_tool(model_response, golden_response)
    else:
        return {
            "correct": False,
            "reason": f"Unknown tool type: '{golden_tool}'"
        }


# Example usage
if __name__ == "__main__":
    # Test mouse_move validation
    print("=== Testing mouse_move validation ===")
    model_resp = {
        "tool_name": "mouse_move",
        "tool_input": {"x": 360, "y": 345}
    }
    golden_resp = {
        "tool_name": "mouse_move",
        "tool_input": {"x": 352, "y": 341},
        "bbox": {"x": 352, "y": 341, "width": 128, "height": 30}
    }
    result = validate_desktop_tool(model_resp, golden_resp)
    print(f"Result: {result}\n")
    
    # Test write validation
    print("=== Testing write validation ===")
    model_resp = {
        "tool_name": "write",
        "tool_input": {"content": "microsoft office 365"}
    }
    golden_resp = {
        "tool_name": "write",
        "tool_input": {"content": "Microsoft Office 365"}
    }
    result = validate_desktop_tool(model_resp, golden_resp)
    print(f"Result: {result}\n")
    
    # Test press validation
    print("=== Testing press validation ===")
    model_resp = {
        "tool_name": "press",
        "tool_input": {"key_name": "enter"}
    }
    golden_resp = {
        "tool_name": "press",
        "tool_input": {"key_name": "enter"}
    }
    result = validate_desktop_tool(model_resp, golden_resp)
    print(f"Result: {result}\n")
    
    # Test hot_key validation
    print("=== Testing hot_key validation ===")
    model_resp = {
        "tool_name": "hot_key",
        "tool_input": {"list_of_keys": ["command", "s"]}
    }
    golden_resp = {
        "tool_name": "hot_key",
        "tool_input": {"list_of_keys": ["command", "s"]}
    }
    result = validate_desktop_tool(model_resp, golden_resp)
    print(f"Result: {result}\n")
    
    # Test left_click validation
    print("=== Testing left_click validation ===")
    model_resp = {
        "tool_name": "left_click",
        "tool_input": {}
    }
    golden_resp = {
        "tool_name": "left_click",
        "tool_input": {},
        "bbox": {"x": 352, "y": 341, "width": 128, "height": 30}
    }
    result = validate_desktop_tool(model_resp, golden_resp)
    print(f"Result: {result}\n")
