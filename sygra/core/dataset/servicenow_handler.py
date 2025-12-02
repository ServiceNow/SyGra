"""ServiceNow data handler implementation using PySNC.

This module provides functionality for reading from and writing to ServiceNow tables,
using the PySNC library as the underlying API client.
"""

import os
from typing import Any, Iterator, Optional, Union

from pysnc import ServiceNowClient  # type: ignore[import-untyped]
from pysnc.auth import ServiceNowPasswordGrantFlow  # type: ignore[import-untyped]

from sygra.core.dataset.data_handler_base import DataHandler
from sygra.core.dataset.dataset_config import DataSourceConfig, OutputConfig
from sygra.logger.logger_config import logger


class ServiceNowHandler(DataHandler):
    """Handler for interacting with ServiceNow tables.

    This class provides methods for reading from and writing to ServiceNow tables
    using the PySNC library. It supports various authentication methods, query filtering,
    field selection, and batch operations.

    Args:
        source_config (Optional[DataSourceConfig]): Configuration for reading from ServiceNow.
        output_config (Optional[OutputConfig]): Configuration for writing to ServiceNow.

    Attributes:
        source_config (DataSourceConfig): Configuration for source table.
        output_config (OutputConfig): Configuration for output table.
        client (ServiceNowClient): PySNC client instance.
    """

    def __init__(
        self,
        source_config: Optional[DataSourceConfig],
        output_config: Optional[OutputConfig] = None,
    ):
        self.source_config: Optional[DataSourceConfig] = source_config
        self.output_config: Optional[OutputConfig] = output_config
        self.client: Optional[ServiceNowClient] = None

        # Initialize client if source config is provided
        if source_config:
            self._init_client(source_config)

    def _init_client(self, config: DataSourceConfig) -> None:
        """Initialize ServiceNow client from configuration.

        Reads from environment variables if not provided in config:
        - SNOW_INSTANCE
        - SNOW_USERNAME (handled in _build_auth)
        - SNOW_PASSWORD (handled in _build_auth)

        Args:
            config (DataSourceConfig): Configuration containing connection details.

        Raises:
            ValueError: If required configuration is missing or invalid.
            AuthenticationException: If authentication fails.
        """
        # Get instance URL (from config or environment)
        instance = self._get_config_value(config, "instance") or os.getenv("SNOW_INSTANCE")
        if not instance:
            raise ValueError(
                "ServiceNow instance is required. "
                "Provide in config or set SNOW_INSTANCE environment variable."
            )

        # Determine authentication method
        auth = self._build_auth(config)

        # Get connection options
        proxy = self._get_config_value(config, "proxy")
        verify_ssl = self._get_config_value(config, "verify_ssl")
        cert = self._get_config_value(config, "cert")
        self._get_config_value(config, "auto_retry", True)

        try:
            self.client = ServiceNowClient(
                instance=instance,
                auth=auth,
                proxy=proxy,
                verify=verify_ssl,
                cert=cert,
            )
            logger.info(f"Successfully connected to ServiceNow instance: {instance}")
        except Exception as e:
            logger.error(f"Failed to initialize ServiceNow client: {str(e)}")
            raise

    def _build_auth(self, config: DataSourceConfig) -> Union[tuple, ServiceNowPasswordGrantFlow]:
        """Build authentication credentials from configuration.

        Args:
            config (DataSourceConfig): Configuration containing auth details.

        Returns:
            Union[tuple, ServiceNowPasswordGrantFlow]: Authentication credentials.

        Raises:
            ValueError: If no valid authentication method is configured.
        """
        # Try username/password (basic auth)
        username = self._get_config_value(config, "username") or os.getenv("SNOW_USERNAME")
        password = self._get_config_value(config, "password") or os.getenv("SNOW_PASSWORD")

        # Try OAuth2 credentials
        client_id = self._get_config_value(config, "oauth_client_id") or os.getenv(
            "SNOW_OAUTH_CLIENT_ID"
        )
        client_secret = self._get_config_value(config, "oauth_client_secret") or os.getenv(
            "SNOW_OAUTH_CLIENT_SECRET"
        )

        # If OAuth credentials are provided, use password grant flow
        if client_id and client_secret and username and password:
            return ServiceNowPasswordGrantFlow(
                username=username,
                password=password,
                client_id=client_id,
                client_secret=client_secret,
            )

        # Fall back to basic auth if just username/password
        if username and password:
            return (username, password)

        raise ValueError(
            "No valid authentication method found. Provide username/password or OAuth2 credentials."
        )

    def _get_config_value(
        self, config: Union[DataSourceConfig, OutputConfig], key: str, default: Any = None
    ) -> Any:
        """Get configuration value, supporting both dict and object access.

        Args:
            config (Union[DataSourceConfig, OutputConfig]): Configuration object.
            key (str): Configuration key.
            default (Any): Default value if key not found.

        Returns:
            Any: Configuration value or default.
        """
        # Try object attribute access (Pydantic model)
        if hasattr(config, key):
            value = getattr(config, key)
            return value if value is not None else default

        # Try dict access (for flexibility)
        if isinstance(config, dict):
            return config.get(key, default)

        return default

    def read(
        self, path: Optional[str] = None
    ) -> Union[list[dict[str, Any]], Iterator[dict[str, Any]]]:
        """Read data from ServiceNow table.

        Args:
            path (Optional[str]): Not used for ServiceNow (required by interface).

        Returns:
            Union[list[dict[str, Any]], Iterator[dict[str, Any]]]: Table records.

        Raises:
            ValueError: If required configuration is missing.
            RuntimeError: If reading operation fails.
        """
        try:
            if not self.source_config:
                raise ValueError("Source configuration is required to read from ServiceNow")

            if not self.client:
                self._init_client(self.source_config)

            table = self._get_config_value(self.source_config, "table")
            if not table:
                raise ValueError("Table name is required")

            # Get query parameters
            batch_size = self._get_config_value(self.source_config, "batch_size", 100)
            streaming = self._get_config_value(self.source_config, "streaming", False)

            # Create GlideRecord
            assert self.client is not None
            gr = self.client.GlideRecord(table, batch_size=batch_size)

            # Build query
            self._build_query(gr)

            # Set field limits if specified
            fields = self._get_config_value(self.source_config, "fields")
            if fields:
                gr.fields = fields

            # Set display value mode
            display_value = self._get_config_value(self.source_config, "display_value", "all")
            try:
                gr.display_value = display_value
            except Exception as e:
                logger.debug(f"Could not set display_value (older pysnc version): {e}")

            # Set reference link exclusion (may not be supported in older pysnc versions)
            exclude_ref_link = self._get_config_value(
                self.source_config, "exclude_reference_link", True
            )
            try:
                gr.exclude_reference_link = exclude_ref_link
            except (AttributeError, Exception) as e:
                logger.debug(
                    f"Could not set exclude_reference_link (not supported in this pysnc version): {e}"
                )

            # Set limit if specified
            limit = self._get_config_value(self.source_config, "limit")
            if limit:
                gr.limit = limit

            # Set ordering if specified
            order_by = self._get_config_value(self.source_config, "order_by")
            order_desc = self._get_config_value(self.source_config, "order_desc", False)
            if order_by:
                if order_desc:
                    gr.order_by_desc(order_by)
                else:
                    gr.order_by(order_by)

            # Execute query
            gr.query()

            logger.info(f"Successfully queried ServiceNow table '{table}', found {len(gr)} records")

            # Return as iterator or list based on streaming setting
            if streaming:
                return self._record_iterator(gr)
            else:
                return self._format_records(gr)

        except Exception as e:
            logger.error(f"Failed to read from ServiceNow: {str(e)}")
            raise RuntimeError(f"Failed to read from ServiceNow: {str(e)}") from e

    def _build_query(self, gr) -> None:
        """Build ServiceNow query from configuration.

        Args:
            gr: GlideRecord instance to configure.
        """
        if not self.source_config:
            return

        # Handle encoded query (direct ServiceNow query string)
        encoded_query = self._get_config_value(self.source_config, "query")
        if encoded_query:
            gr.add_encoded_query(encoded_query)
            return

        # Handle dict-based filters
        filters = self._get_config_value(self.source_config, "filters")
        if not filters:
            return

        for field, value in filters.items():
            if isinstance(value, list):
                # Multiple values - use IN operator
                query_str = "^OR".join([f"{field}={v}" for v in value])
                gr.add_encoded_query(query_str)
            elif isinstance(value, dict):
                # Complex query with operator
                operator = value.get("operator", "=")
                val = value.get("value")
                gr.add_query(field, operator, val)
            else:
                # Simple equality
                gr.add_query(field, value)

    def _format_records(self, gr) -> list[dict[str, Any]]:
        """Format GlideRecord results as list of dicts.

        Args:
            gr: GlideRecord instance with query results.

        Returns:
            list[dict[str, Any]]: Formatted records.
        """
        records = []
        for record in gr:
            formatted = self._format_record(record)
            records.append(formatted)
        return records

    def _record_iterator(self, gr) -> Iterator[dict[str, Any]]:
        """Create iterator over GlideRecord results.

        Args:
            gr: GlideRecord instance with query results.

        Yields:
            dict[str, Any]: Formatted record.
        """
        for record in gr:
            yield self._format_record(record)

    def _format_record(self, record) -> dict[str, Any]:
        """Format a single GlideRecord as a dict.

        Args:
            record: GlideRecord instance at current position.

        Returns:
            dict[str, Any]: Formatted record with value/display_value pairs.
        """
        formatted: dict[str, Any] = {}

        if not record.fields:
            return formatted

        for field in record.fields:
            element = record.get_element(field)
            if element is None:
                formatted[field] = None
            else:
                # Store both value and display_value
                value = element.get_value()
                display_value = element.get_display_value()

                # Try to get link (may not be supported in older pysnc versions)
                link = None
                try:
                    link = element.get_link()
                except (AttributeError, Exception):
                    pass  # get_link() not supported in this pysnc version

                if display_value and display_value != value:
                    formatted[field] = {
                        "value": value,
                        "display_value": display_value,
                    }
                    if link:
                        formatted[field]["link"] = link
                else:
                    # If display_value same as value, just store value
                    formatted[field] = value

        return formatted

    def write(self, data: list[dict[str, Any]], path: Optional[str] = None) -> None:
        """Write data to ServiceNow table.

        Args:
            data (list[dict[str, Any]]): Data to write.
            path (str, optional): Not used for ServiceNow (required by interface).

        Raises:
            ValueError: If output configuration is missing.
            RuntimeError: If writing operation fails.
        """
        if not self.output_config:
            raise ValueError("Output configuration required for writing to ServiceNow")

        try:
            # Initialize client if not already done
            if not self.client:
                # Use output_config for connection (with env variable fallback)
                instance = self._get_config_value(self.output_config, "instance") or os.getenv(
                    "SNOW_INSTANCE"
                )

                if not instance:
                    raise ValueError(
                        "ServiceNow instance is required for write operation. "
                        "Provide in output config or set SNOW_INSTANCE environment variable."
                    )

                # Create temporary source config for client init
                # Extract only the fields needed for connection
                temp_config = DataSourceConfig(
                    type="servicenow",  # type: ignore
                    instance=instance,
                    username=self._get_config_value(self.output_config, "username"),
                    password=self._get_config_value(self.output_config, "password"),
                    oauth_client_id=self._get_config_value(self.output_config, "oauth_client_id"),
                    oauth_client_secret=self._get_config_value(
                        self.output_config, "oauth_client_secret"
                    ),
                    token=self._get_config_value(self.output_config, "token"),
                    proxy=self._get_config_value(self.output_config, "proxy"),
                    verify_ssl=self._get_config_value(self.output_config, "verify_ssl"),
                    cert=self._get_config_value(self.output_config, "cert"),
                    auto_retry=self._get_config_value(self.output_config, "auto_retry", True),
                )
                self._init_client(temp_config)
                logger.info(
                    f"Initialized ServiceNow client from output_config for instance: {instance}"
                )

            if not self.client:
                raise RuntimeError("Failed to initialize ServiceNow client for write operation")

            table = self._get_config_value(self.output_config, "table")
            if not table:
                raise ValueError("Table name is required for output")

            operation = self._get_config_value(self.output_config, "operation", "insert")
            key_field = self._get_config_value(self.output_config, "key_field", "sys_id")

            # Check if table exists, create if it doesn't (for custom tables)
            if table.startswith("u_"):  # Custom tables start with u_
                if not self._table_exists(table):
                    logger.info(f"Table '{table}' does not exist, creating it...")
                    self._create_table(table, data)

            logger.info(
                f"Writing {len(data)} records to ServiceNow table '{table}' (operation: {operation})"
            )
            logger.debug(f"Sample record: {data[0] if data else 'No data'}")

            if operation == "insert":
                self._insert_records(table, data)
            elif operation == "update":
                self._update_records(table, data, key_field)
            elif operation == "upsert":
                self._upsert_records(table, data, key_field)
            else:
                raise ValueError(f"Unknown operation: {operation}")

            logger.info(f"Successfully wrote {len(data)} records to ServiceNow")

        except Exception as e:
            import traceback

            error_msg = f"Failed to write to ServiceNow: {str(e)}\n{traceback.format_exc()}"
            logger.error(error_msg)
            raise RuntimeError(f"Failed to write to ServiceNow: {str(e)}") from e

    def _insert_records(self, table: str, data: list[dict[str, Any]]) -> None:
        """Insert new records into ServiceNow table.

        Args:
            table (str): Table name.
            data (list[dict[str, Any]]): Records to insert.
        """
        assert self.client is not None
        import json

        logger.info(f"Inserting {len(data)} records. Sample data structure:")
        if data:
            sample = data[0]
            logger.info(f"  Sample record keys: {list(sample.keys())}")
            logger.info(f"  Sample record (first 500 chars): {str(sample)[:500]}...")

        for idx, record_data in enumerate(data):
            try:
                gr = self.client.GlideRecord(table)
                gr.initialize()

                # Set field values
                fields_set = 0
                for field, value in record_data.items():
                    if field == "sys_id":
                        continue  # Let ServiceNow generate sys_id

                    # Extract and serialize the value
                    extracted_value = self._extract_value(value)

                    # Convert complex types to JSON strings
                    if isinstance(extracted_value, (dict, list)):
                        extracted_value = json.dumps(extracted_value)

                    # Convert to string for ServiceNow
                    if extracted_value is not None:
                        # For custom tables (starting with u_), prefix field names with u_ as well
                        snow_field = (
                            f"u_{field}"
                            if table.startswith("u_") and not field.startswith("u_")
                            else field
                        )
                        gr.set_value(snow_field, str(extracted_value))
                        fields_set += 1
                        logger.debug(
                            f"  Set field '{snow_field}' = {str(extracted_value)[:100]}..."
                        )

                logger.info(f"Record {idx+1}/{len(data)}: Set {fields_set} fields")

                # Insert
                sys_id = gr.insert()
                if sys_id:
                    logger.info(f"Inserted record {idx+1}/{len(data)} with sys_id: {sys_id}")
                else:
                    logger.warning(
                        f"Failed to insert record {idx+1}/{len(data)}, no sys_id returned"
                    )
            except Exception as e:
                logger.error(f"Failed to insert record {idx+1}/{len(data)}: {str(e)}")
                logger.error(f"Record data: {record_data}")
                raise

    def _update_records(self, table: str, data: list[dict[str, Any]], key_field: str) -> None:
        """Update existing records in ServiceNow table.

        Args:
            table (str): Table name.
            data (list[dict[str, Any]]): Records to update.
            key_field (str): Field to use for matching records.
        """
        assert self.client is not None

        for record_data in data:
            if key_field not in record_data:
                logger.warning(f"Skipping record without key field '{key_field}'")
                continue

            key_value = self._extract_value(record_data[key_field])

            gr = self.client.GlideRecord(table)
            if not gr.get(key_field, key_value):
                logger.warning(f"Record not found for {key_field}={key_value}")
                continue

            # Update field values
            for field, value in record_data.items():
                if field == key_field:
                    continue  # Don't update key field
                # For custom tables, prefix field names with u_
                snow_field = (
                    f"u_{field}" if table.startswith("u_") and not field.startswith("u_") else field
                )
                gr.set_value(snow_field, self._extract_value(value))

            # Update
            gr.update()
            logger.debug(f"Updated record with {key_field}={key_value}")

    def _upsert_records(self, table: str, data: list[dict[str, Any]], key_field: str) -> None:
        """Insert or update records in ServiceNow table.

        Args:
            table (str): Table name.
            data (list[dict[str, Any]]): Records to upsert.
            key_field (str): Field to use for matching records.
        """
        assert self.client is not None

        for record_data in data:
            if key_field not in record_data:
                logger.warning(f"Skipping record without key field '{key_field}'")
                continue

            key_value = self._extract_value(record_data[key_field])

            gr = self.client.GlideRecord(table)
            exists = gr.get(key_field, key_value)

            if not exists:
                # Insert new record
                gr.initialize()

            # Set field values
            for field, value in record_data.items():
                # For custom tables, prefix field names with u_
                snow_field = (
                    f"u_{field}" if table.startswith("u_") and not field.startswith("u_") else field
                )
                gr.set_value(snow_field, self._extract_value(value))

            # Insert or update
            if exists:
                gr.update()
                logger.debug(f"Updated record with {key_field}={key_value}")
            else:
                sys_id = gr.insert()
                logger.debug(f"Inserted record with sys_id: {sys_id}")

    def _extract_value(self, value: Any) -> Any:
        """Extract raw value from value/display_value dict.

        Args:
            value (Any): Value which may be a dict with value/display_value.

        Returns:
            Any: Raw value.
        """
        if isinstance(value, dict) and "value" in value:
            return value["value"]
        return value

    def _table_exists(self, table_name: str) -> bool:
        """Check if a table exists in ServiceNow.

        Args:
            table_name (str): Name of the table to check.

        Returns:
            bool: True if table exists, False otherwise.
        """
        assert self.client is not None

        try:
            # Query sys_db_object to check if table exists
            gr = self.client.GlideRecord("sys_db_object")
            gr.add_query("name", table_name)
            gr.query()

            exists = gr.next()
            logger.debug(f"Table '{table_name}' {'exists' if exists else 'does not exist'}")
            return bool(exists)
        except Exception as e:
            logger.warning(f"Could not check if table exists: {e}. Assuming it exists.")
            return True  # Fail safe - assume exists to avoid accidental creation

    def _create_table(self, table_name: str, sample_data: list[dict[str, Any]]) -> None:
        """Create a custom table in ServiceNow with fields based on sample data.

        Args:
            table_name (str): Name of the table to create (must start with u_).
            sample_data (list[dict[str, Any]]): Sample data to infer field structure.
        """
        assert self.client is not None

        if not table_name.startswith("u_"):
            raise ValueError(
                f"Can only auto-create custom tables (starting with 'u_'): {table_name}"
            )

        try:
            logger.info(f"Creating table '{table_name}' in ServiceNow...")

            # Create the table (sys_db_object)
            table_gr = self.client.GlideRecord("sys_db_object")
            table_gr.initialize()
            table_gr.set_value("name", table_name)
            table_gr.set_value("label", self._generate_label(table_name))
            table_gr.set_value("is_extendable", "false")
            table_gr.set_value("access", "public")

            table_sys_id = table_gr.insert()

            if not table_sys_id:
                raise RuntimeError(f"Failed to create table '{table_name}'")

            logger.info(f"Created table '{table_name}' with sys_id: {table_sys_id}")

            # Analyze sample data to determine fields
            if sample_data:
                sample_record = sample_data[0]
                field_count = 0

                # Create fields based on sample data
                for field_name, value in sample_record.items():
                    if field_name in [
                        "sys_id",
                        "sys_created_on",
                        "sys_created_by",
                        "sys_updated_on",
                        "sys_updated_by",
                    ]:
                        continue  # Skip system fields

                    try:
                        self._create_field(table_name, field_name, value)
                        field_count += 1
                    except Exception as field_error:
                        logger.warning(f"Could not create field '{field_name}': {field_error}")

                logger.info(f"Created {field_count} fields in table '{table_name}'")

            logger.info(f"Table '{table_name}' successfully created and ready for use")

        except Exception as e:
            logger.error(f"Failed to create table '{table_name}': {str(e)}")
            raise RuntimeError(f"Failed to create table '{table_name}': {str(e)}") from e

    def _generate_label(self, table_name: str) -> str:
        """Generate a human-readable label from table name.

        Args:
            table_name (str): Technical table name (e.g., u_incident_analysis).

        Returns:
            str: Human-readable label (e.g., Incident Analysis).
        """
        # Remove u_ prefix and convert underscores to spaces
        label = table_name.replace("u_", "").replace("_", " ")
        # Capitalize each word
        return " ".join(word.capitalize() for word in label.split())

    def _create_field(self, table_name: str, field_name: str, sample_value: Any) -> None:
        """Create a field in a ServiceNow table.

        Args:
            table_name (str): Name of the table.
            field_name (str): Name of the field to create.
            sample_value (Any): Sample value to infer field type.
        """
        assert self.client is not None

        # Determine field type based on sample value
        extracted_value = self._extract_value(sample_value)

        if isinstance(extracted_value, bool):
            field_type = "boolean"
            max_length = 40
        elif isinstance(extracted_value, int):
            field_type = "integer"
            max_length = 40
        elif isinstance(extracted_value, (dict, list)):
            # Store complex types as JSON strings
            field_type = "string"
            max_length = 4000
        elif isinstance(extracted_value, str) and len(str(extracted_value)) > 255:
            field_type = "string"
            max_length = 4000
        else:
            field_type = "string"
            max_length = 255

        try:
            # Create field (sys_dictionary)
            field_gr = self.client.GlideRecord("sys_dictionary")
            field_gr.initialize()
            field_gr.set_value("name", table_name)
            field_gr.set_value("element", field_name)
            field_gr.set_value("column_label", self._generate_label(field_name))
            field_gr.set_value("internal_type", field_type)
            field_gr.set_value("max_length", str(max_length))
            field_gr.set_value("active", "true")
            field_gr.set_value("read_only", "false")

            field_sys_id = field_gr.insert()

            if field_sys_id:
                logger.debug(
                    f"Created field '{field_name}' ({field_type}, max_length={max_length})"
                )
            else:
                logger.warning(f"Failed to create field '{field_name}'")

        except Exception as e:
            logger.warning(f"Could not create field '{field_name}': {e}")

    def get_files(self) -> list[str]:
        """Get list of available tables in ServiceNow instance.

        Note: This returns a list of commonly used tables. For a complete list,
        use the ServiceNow Table API to query sys_db_object.

        Returns:
            list[str]: List of table names.

        Raises:
            RuntimeError: If operation fails.
        """
        try:
            if not self.source_config:
                raise ValueError("Source configuration is required")

            # For ServiceNow, "files" concept maps to tables
            # Return the configured table or common tables
            table = self._get_config_value(self.source_config, "table")
            if table:
                return [table]

            # Return list of common ServiceNow tables
            common_tables = [
                "incident",
                "problem",
                "change_request",
                "cmdb_ci",
                "cmdb_ci_server",
                "sys_user",
                "sys_user_group",
                "task",
            ]
            logger.info(f"Returning {len(common_tables)} common ServiceNow tables")
            return common_tables

        except Exception as e:
            logger.error(f"Failed to get tables: {str(e)}")
            raise RuntimeError(f"Failed to get tables: {str(e)}") from e
