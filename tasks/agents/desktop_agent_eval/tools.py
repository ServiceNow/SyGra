from langchain_core.tools import tool

from sygra.logger.logger_config import logger


@tool
def get_current_cursor_coords():
    """Fetches the current cursor coordinates."""
    logger.info("Fetching current cursor coordinates")
    return


@tool
def screenshot():
    """Takes a screenshot of the current status of the screen."""
    logger.info("Taking screenshot")
    return


@tool
def mouse_move(x: int, y: int):
    """Moves the cursor to the new coordinates (x,y) provided in the args.

    Top left corner of image has (0,0) coordinates. x-coords increase from left to right
    while y-coords increases from up to down.

    Args:
        x: x-coordinate
        y: y-coordinate
    """
    logger.info(f"Moving mouse to coordinates: x={x}, y={y}")
    return


@tool
def double_left_click():
    """Performs a double left click on current position of cursor."""
    logger.info("Performing double left click")
    return


@tool
def right_click():
    """Makes a right click at the current position of the cursor."""
    logger.info("Performing right click")
    return


@tool
def left_click():
    """Makes a left click at the current position of the cursor."""
    logger.info("Performing left click")
    return


@tool
def press(key_name: str):
    """Press a keyboard key like 'esc', 'enter' and 'space'

    Args:
        key_name: name of the keyboard key to be pressed.
    """
    logger.info(f"Pressing key: '{key_name}'")
    return


@tool
def hot_key(list_of_keys: list[str]):
    """Takes hot key based actions.

    Args:
        list_of_keys: the list of the keys to be pressed in ordered fashion.
                     e.g. ['command', 's'] for saving, ["command", "a"] for selecting the text in an active block,
                     ['command', 'c'] for copying, ['command', 'v'] for pasting etc.
    """
    logger.info(f"Pressing hot key combination: {list_of_keys}")
    return


# @tool
# def horizontal_scroll(value: int):
#     """Scroll the screen horizontally. -ve for scrolling left, +ve for scrolling right.
#
#     Args:
#         value: number of clicks to scroll horizontally.
#     """
#     logger.info(f"Scrolling horizontally: value={value}")
#     return


@tool
def vertical_scroll(value: int):
    """Scroll the screen vertically. +ve for scrolling up, -ve for scrolling down.

    Args:
        value: number of clicks to scroll vertically.
    """
    logger.info(f"Scrolling vertically: value={value}")
    return


@tool
def write(content: str):
    """Types a string.

    Args:
        content: the string to be typed in.
    """
    logger.info(f"Writing text: '{content}'")
    return

@tool
def drag(x: float, y: float):
    """Starts the drag operation by holding the mouse left-click from the current position of the cursor to x pixels rightwards and y pixels downwards.

    Args:
        x: number of pixels to move towards right.
        y: name of pixels to move downwards.

    """
    logger.info(f"Moving the cursor {x} pixels to the right and {y} pixels downwards")
    return