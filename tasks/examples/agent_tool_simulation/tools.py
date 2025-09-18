from langchain_core.tools import tool

from sygra.logger.logger_config import logger


@tool
def add(a: float, b: float):
    """Add two numbers."""
    logger.info(f"Adding {a} and {b}")
    return a + b
