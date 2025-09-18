from abc import ABC

from langchain_core.tools import tool

from sygra.logger.logger_config import logger


class ToolClass(ABC):
    def not_a_tool(self):
        return "not a tool"

    @tool
    def subtract(a: float, b: float):
        """Subtract b from a."""
        logger.info(f"Subtracting {b} from {a}")
        return a - b

    @tool
    def divide(a: float, b: float):
        """Divide two numbers."""
        logger.info(f"Dividing {a} by {b}")
        return a / b
