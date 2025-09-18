from abc import ABC, abstractmethod
from typing import Any, Optional

from sygra.core.dataset.dataset_config import DataSourceConfig, OutputConfig


class BaseTool(ABC):
    """Base interface for all dataset processing tools."""

    name: str = "base_tool"
    description: str = "Base dataset processing tool"

    @abstractmethod
    def __init__(self, config: dict[str, Any]):
        """Initialize with configuration."""
        pass

    @abstractmethod
    def process(self, input_path: str, output_path: str):
        """
        Process the dataset.

        Args:
            input_path: Path to input dataset
            output_path: Path for output dataset
        """
        pass

    @classmethod
    def from_source_config(
        cls,
        source_config: DataSourceConfig,
        output_config: Optional[OutputConfig] = None,
        **kwargs,
    ) -> "BaseTool":
        """
        Initialize tool from source and output configurations.

        Args:
            source_config: DataSourceConfig for input data
            output_config: Optional OutputConfig for result storage
            **kwargs: Additional tool-specific parameters

        Returns:
            BaseTool: Initialized tool instance
        """
        config = {
            "source_config": source_config.model_dump(),
            "output_config": output_config.model_dump() if output_config else None,
            **kwargs,
        }
        return cls(config)
