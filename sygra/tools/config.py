from typing import Any, Optional

from pydantic import BaseModel, RootModel, field_validator

from sygra.core.dataset.dataset_config import DataSourceConfig, OutputConfig
from sygra.utils import utils


class ToolConfig(BaseModel):
    """Configuration for a single tool."""

    config: dict[str, Any]

    @field_validator("config")
    @classmethod
    def validate_config_not_empty(cls, v):
        if not v:
            raise ValueError("Tool configuration cannot be empty")
        return v


class ToolsConfig(RootModel[dict[str, ToolConfig]]):
    """Top-level tools configuration, mapping tool names to ToolConfig."""

    def __iter__(self):
        return iter(self.root.items())

    def __getitem__(self, key):
        return self.root[key]

    def get(self, key, default=None):
        return self.root.get(key, default)

    def items(self):
        return self.root.items()

    def keys(self):
        return self.root.keys()

    def values(self):
        return self.root.values()


class DataConfig(BaseModel):
    """Data configuration section."""

    source: dict[str, Any]
    sink: Optional[dict[str, Any]] = None

    def get_source_config(self) -> DataSourceConfig:
        """Parse and return source configuration."""
        return DataSourceConfig.from_dict(self.source)

    def get_sink_config(self) -> Optional[OutputConfig]:
        """Parse and return sink configuration."""
        if not self.sink:
            return None
        return OutputConfig.from_dict(self.sink)


class Config(BaseModel):
    """Root pipeline configuration."""

    data_config: Optional[DataConfig] = None
    tools: Optional[ToolsConfig] = None

    @classmethod
    def from_file(cls, config_path: str) -> "Config":
        """Load configuration from a YAML file."""
        config_dict = utils.load_yaml_file(config_path)
        return cls.model_validate(config_dict)

    @classmethod
    def from_dict(cls, config_dict: dict[str, Any]) -> "Config":
        """Create configuration from a dictionary."""
        return cls.model_validate(config_dict)
