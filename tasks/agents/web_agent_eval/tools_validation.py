import re
from difflib import SequenceMatcher
from tasks.agents.web_agent_eval.constants import SCROLL_THRESHOLD, FUZZY_MATCH_THRESHOLD


def normalize_text(text: str) -> str:
    """Lowercase, strip, and collapse multiple spaces into one."""
    return re.sub(r"\s+", " ", text.strip().lower())


def is_action_within_bbox(action_x: float, action_y: float, bbox: dict) -> bool:
    """
    Validate if an action (x, y) falls inside a bounding box.
    Works for click, type, and other coordinate-based actions.

    Args:
        action_x (float): X coordinate of the action.
        action_y (float): Y coordinate of the action.
        bbox (dict): Bounding box with keys 'x', 'y', 'width', 'height'.

    Returns:
        bool: True if action is inside bbox, False otherwise.
    """
    x_min = bbox["x"]
    y_min = bbox["y"]
    x_max = bbox["x"] + bbox["width"]
    y_max = bbox["y"] + bbox["height"]

    return x_min <= action_x <= x_max and y_min <= action_y <= y_max


# Backward compatibility aliases
def is_click_within_bbox(click_x: float, click_y: float, bbox: dict) -> bool:
    """Backward compatibility wrapper for is_action_within_bbox."""
    return is_action_within_bbox(click_x, click_y, bbox)


def is_type_within_bbox(type_x: float, type_y: float, bbox: dict) -> bool:
    """Backward compatibility wrapper for is_action_within_bbox."""
    return is_action_within_bbox(type_x, type_y, bbox)


def is_typed_value_correct(golden: str, predicted: str, threshold: float = FUZZY_MATCH_THRESHOLD) -> dict:
    """
    Compare golden vs predicted typed values using exact and fuzzy matching.
    Case-insensitive and whitespace-tolerant.

    Args:
        golden (str): Ground truth typed string.
        predicted (str): Tool's predicted typed string.
        threshold (float): Minimum similarity (0–1) for fuzzy match acceptance.

    Returns:
        dict: {
            "exact_match": bool,
            "similarity_score": float,
            "fuzzy_match": bool,
            "differences": list
        }
    """
    # Normalize both
    golden_norm = normalize_text(golden)
    predicted_norm = normalize_text(predicted)

    # Exact check
    exact = golden_norm == predicted_norm

    # Fuzzy similarity
    similarity = SequenceMatcher(None, golden_norm, predicted_norm).ratio()
    fuzzy = similarity >= threshold

    # Collect character-level diffs
    differences = []
    if not exact:
        for opcode, i1, i2, j1, j2 in SequenceMatcher(
            None, golden_norm, predicted_norm
        ).get_opcodes():
            if opcode != "equal":
                differences.append(
                    {
                        "operation": opcode,  # 'replace', 'insert', 'delete'
                        "golden": golden_norm[i1:i2],
                        "predicted": predicted_norm[j1:j2],
                    }
                )

    return {
        "exact_match": exact,
        "similarity_score": similarity,
        "fuzzy_match": fuzzy,
        "differences": differences,
    }


def is_scroll_direction_valid(golden_direction: str, predicted_direction: str) -> bool:
    """
    Validate if the predicted scroll direction matches the golden standard.

    Args:
        golden_direction (str): The ground truth scroll direction.
        predicted_direction (str): The predicted scroll direction.

    Returns:
        bool: True if the predicted direction is valid, False otherwise.
    """
    valid_directions = ["up", "down", "left", "right"]
    return (
        predicted_direction == golden_direction
        and predicted_direction in valid_directions
    )


def is_scroll_amount_valid(
    golden_scroll_amount: float, predicted_scroll_amount: float, tolerance_percent: float = 20.0
) -> dict:
    """
    Validate if the predicted scroll amount is within acceptable range of golden amount.
    
    Args:
        golden_scroll_amount (float): Ground truth scroll amount.
        predicted_scroll_amount (float): Predicted scroll amount.
        tolerance_percent (float): Acceptable percentage tolerance (default 20%).
    
    Returns:
        dict: {
            "is_valid": bool,
            "difference": float,
            "difference_percent": float,
            "tolerance_used": float
        }
    """
    if golden_scroll_amount == 0:
        # Special case: if golden is 0, predicted should also be close to 0
        is_valid = abs(predicted_scroll_amount) <= SCROLL_THRESHOLD  # Allow 10 pixel tolerance for zero
        difference = abs(predicted_scroll_amount)
        difference_percent = float('inf') if predicted_scroll_amount != 0 else 0.0
    else:
        difference = abs(golden_scroll_amount - predicted_scroll_amount)
        difference_percent = (difference / abs(golden_scroll_amount)) * 100
        is_valid = difference_percent <= tolerance_percent
    
    return {
        "is_valid": is_valid,
        "difference": difference,
        "difference_percent": difference_percent,
        "tolerance_used": tolerance_percent
    }


