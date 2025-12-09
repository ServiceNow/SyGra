"""Configuration module for data handling operations.

This module provides configuration classes for data sources and outputs,
supporting both HuggingFace datasets and local file operations. It uses
Pydantic for validation and type checking of configuration parameters.
"""

from enum import Enum
from typing import Any, Optional, Union

from pydantic import BaseModel, field_validator


class DataSourceType(Enum):
    """Enumeration of supported data source types.

    Attributes:
        HUGGINGFACE: HuggingFace dataset source
        DISK_FILE: Local file system source
        SERVICENOW: ServiceNow table source
    """

    HUGGINGFACE = "hf"
    DISK_FILE = "disk"
    SERVICENOW = "servicenow"


class TransformConfig(BaseModel):
    """Configuration for data transformations.

    Attributes:
        transform (str): Fully qualified path to transformation class
        params (dict[str, Any]): Parameters for the transformation
    """

    transform: str
    params: Optional[dict[str, Any]] = None


class OutputType(Enum):
    """Enumeration of supported output types.

    Attributes:
        HUGGINGFACE: HuggingFace dataset output
        JSON: JSON file output
        JSONL: JSON Lines file output
        CSV: CSV file output
        PARQUET: Parquet file output
        SERVICENOW: ServiceNow table output
    """

    HUGGINGFACE = "hf"
    JSON = "json"
    JSONL = "jsonl"
    CSV = "csv"
    PARQUET = "parquet"
    SERVICENOW = "servicenow"
    NONE = None


class ShardConfig(BaseModel):
    """Configuration for sharded dataset operations.

    Attributes:
        regex (str): Regular expression pattern for matching shard files
        index (Optional[list[int]]): Optional list of specific shard indices to process
    """

    regex: str = "*"
    index: Optional[list[int]] = None


class DataSourceConfig(BaseModel):
    """Configuration for data sources.

    This class provides configuration options for HuggingFace datasets,
    local file system sources, and ServiceNow tables, including transformation specs.

    For ServiceNow sources:
    - Connection credentials (instance, username, password) are read from
      environment variables: SNOW_INSTANCE, SNOW_USERNAME, SNOW_PASSWORD
    - Only query details (table, filters, fields, etc.) need to be specified
    - Config values for credentials are optional overrides

    Attributes:
        alias (Optional[str]): Optional alias for this dataset
        join_type (Optional[str]): Optional join type for this dataset
        primary_key (Optional[str]): Optional primary key from primary dataset, where join_type is column based
        join_key (Optional[str]): Optional join key for this dataset, where join_type is column based
        type (DataSourceType): Type of data source
        repo_id (Optional[str]): HuggingFace repository ID
        config_name (Optional[str]): HuggingFace dataset configuration name
        split (Union[str, list[str]]): Dataset split(s) to use
        token (Optional[str]): HuggingFace API token
        streaming (bool): Whether to stream the dataset
        shard (Optional[ShardConfig]): Configuration for sharded datasets
        file_format (Optional[str]): Format for local files
        file_path (Optional[str]): Path to local file
        encoding (str): Character encoding for text files
        table (Optional[str]): ServiceNow table name for queries
        filters (Optional[dict]): Filters for ServiceNow queries
        fields (Optional[list[str]]): Fields to retrieve from ServiceNow
        transformations (Optional[list[TransformConfig]]): List of transformations to apply
    """

    alias: Optional[str] = None
    join_type: Optional[str] = None
    primary_key: Optional[str] = None
    join_key: Optional[str] = None

    type: DataSourceType

    # For Hugging Face datasets
    repo_id: Optional[str] = None
    config_name: Optional[str] = None
    split: Union[str, list[str]] = "train"
    token: Optional[str] = None
    streaming: bool = False
    shard: Optional[ShardConfig] = None

    # For disk files
    file_format: Optional[str] = None
    file_path: Optional[str] = None
    encoding: str = "utf-8"

    # For ServiceNow tables
    instance: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None
    oauth_client_id: Optional[str] = None
    oauth_client_secret: Optional[str] = None
    table: Optional[str] = None
    query: Optional[str] = None
    filters: Optional[dict[str, Any]] = None
    fields: Optional[list[str]] = None
    limit: Optional[int] = None
    batch_size: int = 100
    order_by: Optional[str] = None
    order_desc: bool = False
    display_value: str = "all"
    exclude_reference_link: bool = True
    proxy: Optional[str] = None
    verify_ssl: Optional[bool] = None
    cert: Optional[str] = None
    auto_retry: bool = True

    # Transformation functions
    transformations: Optional[list[TransformConfig]] = None

    @classmethod
    @field_validator("transformations", mode="before")
    def validate_transformations(
        cls, v: Optional[list[dict[str, Any]]]
    ) -> Optional[list[TransformConfig]]:
        """Validate and convert transformation configurations.

        Args:
            v (Optional[list[dict[str, Any]]]): Raw transformation configurations

        Returns:
            Optional[list[TransformConfig]]: Validated transformation configurations
        """
        if not v:
            return []
        return [TransformConfig(**t) if isinstance(t, dict) else t for t in v]

    @classmethod
    @field_validator("split", mode="before")
    def validate_split(cls, v: Union[str, list[str]]) -> Union[str, list[str]]:
        """Validate dataset split configuration.

        Args:
            v (Union[str, list[str]]): Split configuration

        Returns:
            Union[str, list[str]]: Validated split configuration

        Raises:
            ValueError: If split list is empty
        """
        if isinstance(v, list):
            if not v:
                raise ValueError("Split list cannot be empty")
            return list(dict.fromkeys(v))
        return v

    @property
    def splits(self) -> list[str]:
        """Get list of dataset splits.

        Returns:
            list[str]: list of split names
        """
        return [self.split] if isinstance(self.split, str) else self.split

    @classmethod
    def from_dict(cls, config: dict[str, Any]) -> "DataSourceConfig":
        """Create configuration from dictionary.

        Args:
            config (dict[str, Any]): Configuration dictionary

        Returns:
            DataSourceConfig: Validated configuration object
        """
        if "transformations" in config:
            config["transformations"] = [TransformConfig(**t) for t in config["transformations"]]

        return cls(**config)


class OutputConfig(BaseModel):
    """Configuration for data output operations.

    This class provides configuration options for HuggingFace datasets,
    local file system outputs, and ServiceNow tables.

    For ServiceNow outputs:
    - Connection credentials (instance, username, password) are read from
      environment variables: SNOW_INSTANCE, SNOW_USERNAME, SNOW_PASSWORD
    - Only operation details (table, operation, key_field) need to be specified
    - Config values for credentials are optional overrides

    Attributes:
        alias (str): Alias for output configuration
        type (OutputType): Type of output
        repo_id (Optional[str]): HuggingFace repository ID
        config_name (Optional[str]): HuggingFace dataset configuration name
        split (str): Dataset split to write
        token (Optional[str]): HuggingFace API token
        private (bool): Whether to create private HuggingFace dataset
        chunk_size (int): Size of chunks for writing
        filename (Optional[str]): Output filename
        file_path (Optional[str]): Output file path
        encoding (str): Character encoding for text files
        table (Optional[str]): ServiceNow table name for output
        operation (str): ServiceNow operation (insert/update/upsert)
        key_field (str): Field to match for update/upsert operations
    """

    alias: Optional[str] = None
    type: OutputType = None
    repo_id: Optional[str] = None
    type: Optional[OutputType] = None
    repo_id: Optional[str] = None
    config_name: Optional[str] = None
    split: str = "train"
    token: Optional[str] = None
    private: bool = True
    chunk_size: int = 1000
    filename: Optional[str] = None
    file_path: Optional[str] = None
    encoding: str = "utf-8"

    # For ServiceNow output
    instance: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None
    oauth_client_id: Optional[str] = None
    oauth_client_secret: Optional[str] = None
    table: Optional[str] = None
    operation: str = "insert"  # insert, update, or upsert
    key_field: str = "sys_id"  # Field to match for update/upsert
    proxy: Optional[str] = None
    verify_ssl: Optional[bool] = None
    cert: Optional[str] = None
    auto_retry: bool = True

    @classmethod
    def from_dict(cls, config: dict[str, Any]) -> "OutputConfig":
        """Create configuration from dictionary.

        Args:
            config (dict[str, Any]): Configuration dictionary

        Returns:
            OutputConfig: Validated configuration object
        """
        return cls(
            alias=config.get("alias"),
            type=OutputType(config.get("type", OutputType.NONE)),
            repo_id=config.get("repo_id"),
            config_name=config.get("config_name"),
            split=config.get("split", "train"),
            token=config.get("token"),
            private=config.get("private", True),
            chunk_size=config.get("chunk_size", 1000),
            filename=config.get("filename"),
            file_path=config.get("file_path"),
            encoding=config.get("encoding", "utf-8"),
            # ServiceNow fields
            instance=config.get("instance"),
            username=config.get("username"),
            password=config.get("password"),
            oauth_client_id=config.get("oauth_client_id"),
            oauth_client_secret=config.get("oauth_client_secret"),
            table=config.get("table"),
            operation=config.get("operation", "insert"),
            key_field=config.get("key_field", "sys_id"),
            proxy=config.get("proxy"),
            verify_ssl=config.get("verify_ssl"),
            cert=config.get("cert"),
            auto_retry=config.get("auto_retry", True),
        )
