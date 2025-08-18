from langchain_core.tools import tool

from logger.logger_config import logger


@tool
def multiply(a: float, b: float):
    """Multiply two numbers."""
    logger.info(f"Multiplying {a} and {b}")
    return a * b
