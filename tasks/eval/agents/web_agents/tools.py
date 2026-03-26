from langchain_core.tools import tool

from sygra.logger.logger_config import logger

@tool
def screenshot_tool(take_screenshot: bool):
    """Take a screenshot to see the current state of the page.

    Args:
        take_screenshot: Whether or not to take a screenshot
    """
    logger.info(f"Taking screenshot: {take_screenshot}")
    return

@tool
def click_tool(x: float, y: float):
    """Click on an element on the page using x and y coordinates.

    Args:
        x: The x coordinate of the element to click on.
        y: The y coordinate of the element to click on.
    """
    logger.info(f"Clicking at coordinates: x={x}, y={y}")
    return


@tool
def type_tool(x: float, y: float, text: str):
    """Simulates a type action on the screen using coordinates of the mouse and the text to be typed.

    Args:
        x: The x coordinate of the click.
        y: The y coordinate of the click.
        text: The text to be typed.
    """
    logger.info(f"Typing at coordinates: x={x}, y={y} with text='{text}'")
    return


@tool
def typing_tool(text: str):
    """Type text into an element on the page (coordinate-free version).

    Args:
        text: The text to be typed.
    """
    logger.info(f"Typing text: '{text}'")
    return


@tool
def scroll_tool(direction: str, amount: float):
    """Scroll in a chosen direction by a specified amount.

    Args:
        direction: The direction to scroll in.
        amount: The amount of pixels to scroll by.
    """
    logger.info(f"Scrolling direction='{direction}', amount={amount}")
    return


@tool
def wait_tool(time: float):
    """Wait for a specified amount of time in milliseconds.

    Args:
        time: The amount of time to wait in milliseconds.
    """
    logger.info(f"Waiting for time(ms)={time}")
    return


@tool
def resume_tool(resume: bool):
    """Resume the current task after waiting or user input.

    Args:
        resume: Whether or not to resume the task execution.
    """
    logger.info(f"Resuming task: {resume}")
    return


@tool
def hil_tool(wait_for_human: bool):
    """Human in the loop. Wait for human input.

    Args:
        wait_for_human: Whether or not to wait for the human to intervene.
    """
    logger.info(f"Wait for human in loop: {wait_for_human}")
    return


@tool
def text_clear_tool(clear_text: bool):
    """Clears all the text from the element before typing new text.

    Args:
        clear_text: Whether or not to clear the text from the element.
    """
    logger.info(f"Clearing text: {clear_text}")
    return


@tool
def slider_tool(direction: str, amount: float):
    """Move a slider in a chosen direction by a specified amount.

    Args:
        direction: The direction to move the slider.
        amount: The amount of pixels to move the slider by.
    """
    logger.info(f"Moving slider direction='{direction}', amount={amount}")
    return