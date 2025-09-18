import importlib
from typing import Optional, Type

from sygra.logger.logger_config import logger
from sygra.tools.base_tool import BaseTool


class ToolRegistry:
    """Registry for all dataset tools."""

    _tools: dict[str, Type[BaseTool]] = {}

    @classmethod
    def register(cls, tool_class: Type[BaseTool]) -> Type[BaseTool]:
        """Register a tool class using its class-level name."""
        tool_name = getattr(tool_class, "name", None)
        if not tool_name:
            raise ValueError(f"Tool {tool_class.__name__} missing class-level 'name'")
        cls._tools[tool_name] = tool_class
        logger.debug(f"🔧 Registered tool: {tool_name}")
        return tool_class

    @classmethod
    def get_tool(cls, name: str) -> Optional[Type[BaseTool]]:
        """Get a tool class by name."""
        return cls._tools.get(name)

    @classmethod
    def list_tools(cls) -> dict[str, str]:
        """List all registered tools and their descriptions."""
        return {name: cls._tools[name].description for name in cls._tools}

    @classmethod
    def available_tools(cls) -> list[str]:
        """Return a list of available tool names."""
        return list(cls._tools.keys())

    @classmethod
    def auto_discover(cls, base_package: str = "sygra.tools.toolkits"):
        """Auto-import all processor.py modules under tools/toolkits/*"""
        import pathlib

        logger.info(f"Auto-discovering tools in {base_package}...")

        base_path = pathlib.Path(__file__).parent / "toolkits"

        for tool_dir in base_path.iterdir():
            if tool_dir.is_dir():
                processor_file = tool_dir / "processor.py"
                if processor_file.exists():
                    # Convert path to module name: sygra.tools.toolkits.tool_name.processor
                    module_name = f"{base_package}.{tool_dir.name}.processor"
                    try:
                        importlib.import_module(module_name)
                        logger.debug(f"Imported: {module_name}")
                    except Exception as e:
                        logger.warning(f"Failed to import {module_name}: {e}")


def register_tool(cls: Type[BaseTool]) -> Type[BaseTool]:
    """Decorator to register a tool class."""
    return ToolRegistry.register(cls)
