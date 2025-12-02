"""
Unit tests for ServiceNow handler with mocked PySNC client.

These tests validate the ServiceNow integration without requiring a real
ServiceNow instance by mocking the PySNC API.
"""

import sys
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

sys.path.append(str(Path(__file__).parent.parent.parent.parent))
from sygra.core.dataset.dataset_config import DataSourceConfig, OutputConfig
from sygra.core.dataset.servicenow_handler import ServiceNowHandler


class MockGlideElement:
    """Mock GlideElement for testing."""

    def __init__(self, name: str, value: Any = None, display_value: Any = None, link: str = None):
        self._name = name
        self._value = value
        self._display_value = display_value
        self._link = link

    def get_value(self):
        return self._value

    def get_display_value(self):
        return self._display_value

    def get_link(self):
        return self._link


class MockGlideRecord:
    """Mock GlideRecord for testing."""

    def __init__(self, table: str, batch_size: int = 500, rewindable: bool = True):
        self.table = table
        self.batch_size = batch_size
        self.rewindable = rewindable
        self.fields = []
        self.display_value = "all"
        self.exclude_reference_link = True
        self.limit = None
        self._records = []
        self._current_index = -1
        self._query_called = False

    def add_query(self, field: str, *args):
        """Mock add_query."""
        pass

    def add_encoded_query(self, query: str):
        """Mock add_encoded_query."""
        pass

    def order_by(self, field: str):
        """Mock order_by."""
        pass

    def order_by_desc(self, field: str):
        """Mock order_by_desc."""
        pass

    def query(self):
        """Mock query execution."""
        self._query_called = True
        # Simulate some records
        self._records = [
            {
                "sys_id": "123",
                "number": "INC0001",
                "short_description": "Test incident 1",
                "priority": "1",
                "state": "2",
            },
            {
                "sys_id": "456",
                "number": "INC0002",
                "short_description": "Test incident 2",
                "priority": "2",
                "state": "1",
            },
        ]
        self._current_index = -1

    def __iter__(self):
        return self

    def __next__(self):
        self._current_index += 1
        if self._current_index >= len(self._records):
            raise StopIteration
        return self

    def __len__(self):
        return len(self._records)

    def get_element(self, field: str):
        """Get mock element for field."""
        if self._current_index < 0 or self._current_index >= len(self._records):
            return None

        record = self._records[self._current_index]
        value = record.get(field)

        if value is None:
            return None

        # For priority, add display value
        if field == "priority":
            display_map = {"1": "Critical", "2": "High", "3": "Moderate"}
            return MockGlideElement(field, value, display_map.get(value, value))

        return MockGlideElement(field, value)

    def initialize(self):
        """Mock initialize for new record."""
        self._records = [{}]
        self._current_index = 0

    def set_value(self, field: str, value: Any):
        """Mock set_value."""
        if self._current_index >= 0 and self._current_index < len(self._records):
            self._records[self._current_index][field] = value

    def insert(self):
        """Mock insert."""
        return "new_sys_id_123"

    def update(self):
        """Mock update."""
        return True

    def get(self, field: str, value: Any):
        """Mock get for retrieving record."""
        # Simulate finding a record
        self._records = [{field: value, "sys_id": "existing_123"}]
        self._current_index = 0
        return True


class MockServiceNowClient:
    """Mock ServiceNow client for testing."""

    def __init__(self, instance, auth, **kwargs):
        self.instance = instance
        self.auth = auth
        self.kwargs = kwargs

    def GlideRecord(self, table: str, batch_size: int = 500, rewindable: bool = True):
        """Return mock GlideRecord."""
        return MockGlideRecord(table, batch_size, rewindable)


@pytest.fixture
def mock_client():
    """Fixture for mocked ServiceNow client."""
    with patch("sygra.core.dataset.servicenow_handler.ServiceNowClient", MockServiceNowClient):
        yield


@pytest.fixture
def source_config():
    """Fixture for source configuration."""
    return DataSourceConfig(
        type="servicenow",
        instance="dev00000",
        username="admin",
        password="password",
        table="incident",
        filters={"active": "true"},
        fields=["sys_id", "number", "short_description", "priority", "state"],
        limit=10,
        batch_size=100,
    )


@pytest.fixture
def output_config():
    """Fixture for output configuration."""
    return OutputConfig(
        type="servicenow",
        instance="dev00000",
        username="admin",
        password="password",
        table="incident",
        operation="insert",
    )


class TestServiceNowHandlerInit:
    """Test handler initialization."""

    def test_init_with_source_config(self, mock_client, source_config):
        """Test initialization with source config."""
        handler = ServiceNowHandler(source_config)

        assert handler.source_config == source_config
        assert handler.client is not None

    def test_init_with_output_config(self, mock_client, output_config):
        """Test initialization with output config only."""
        handler = ServiceNowHandler(None, output_config)

        assert handler.output_config == output_config
        assert handler.client is None  # Not initialized until write

    @patch.dict("os.environ", {}, clear=True)
    def test_init_without_instance(self, mock_client):
        """Test initialization fails without instance."""
        config = DataSourceConfig(
            type="servicenow", username="admin", password="password", table="incident"
        )

        with pytest.raises(ValueError, match="instance is required"):
            ServiceNowHandler(config)


class TestServiceNowHandlerRead:
    """Test reading from ServiceNow."""

    def test_read_basic(self, mock_client, source_config):
        """Test basic read operation."""
        handler = ServiceNowHandler(source_config)

        records = handler.read()

        assert isinstance(records, list)
        assert len(records) == 2
        assert records[0]["number"] == "INC0001"
        assert records[1]["number"] == "INC0002"

    def test_read_with_display_values(self, mock_client, source_config):
        """Test read with display values."""
        handler = ServiceNowHandler(source_config)

        records = handler.read()

        # Priority should have display value
        assert isinstance(records[0]["priority"], dict)
        assert records[0]["priority"]["value"] == "1"
        assert records[0]["priority"]["display_value"] == "Critical"

    def test_read_streaming(self, mock_client, source_config):
        """Test streaming read."""
        source_config.streaming = True
        handler = ServiceNowHandler(source_config)

        records_iter = handler.read()
        records = list(records_iter)

        assert len(records) == 2
        assert records[0]["number"] == "INC0001"

    def test_read_without_config(self, mock_client):
        """Test read fails without config."""
        handler = ServiceNowHandler(None)

        with pytest.raises(RuntimeError, match="Source configuration is required"):
            handler.read()

    def test_read_without_table(self, mock_client):
        """Test read fails without table."""
        config = DataSourceConfig(
            type="servicenow", instance="dev00000", username="admin", password="password"
        )

        handler = ServiceNowHandler(config)

        with pytest.raises(RuntimeError, match="Table name is required"):
            handler.read()


class TestServiceNowHandlerWrite:
    """Test writing to ServiceNow."""

    def test_write_insert(self, mock_client, output_config):
        """Test insert operation."""
        handler = ServiceNowHandler(None, output_config)

        data = [{"number": "INC0003", "short_description": "New incident", "priority": "1"}]

        # Should not raise
        handler.write(data)

    def test_write_update(self, mock_client, output_config):
        """Test update operation."""
        output_config.operation = "update"
        output_config.key_field = "sys_id"

        handler = ServiceNowHandler(None, output_config)

        data = [{"sys_id": "123", "short_description": "Updated incident", "priority": "2"}]

        # Should not raise
        handler.write(data)

    def test_write_upsert(self, mock_client, output_config):
        """Test upsert operation."""
        output_config.operation = "upsert"
        output_config.key_field = "number"

        handler = ServiceNowHandler(None, output_config)

        data = [{"number": "INC0001", "short_description": "Upserted incident"}]

        # Should not raise
        handler.write(data)

    def test_write_without_config(self, mock_client):
        """Test write fails without config."""
        handler = ServiceNowHandler(None, None)

        with pytest.raises(ValueError, match="Output configuration required"):
            handler.write([{"field": "value"}])

    def test_write_with_display_value_dict(self, mock_client, output_config):
        """Test write extracts value from value/display_value dict."""
        handler = ServiceNowHandler(None, output_config)

        data = [{"priority": {"value": "1", "display_value": "Critical"}}]

        # Should extract value and write successfully
        handler.write(data)


class TestServiceNowHandlerGetFiles:
    """Test get_files method."""

    def test_get_files_with_table(self, mock_client, source_config):
        """Test get_files returns configured table."""
        handler = ServiceNowHandler(source_config)

        files = handler.get_files()

        assert files == ["incident"]

    def test_get_files_without_table(self, mock_client):
        """Test get_files returns common tables when no table configured."""
        config = DataSourceConfig(
            type="servicenow", instance="dev00000", username="admin", password="password"
        )

        handler = ServiceNowHandler(config)

        files = handler.get_files()

        assert isinstance(files, list)
        assert "incident" in files
        assert "problem" in files
        assert "change_request" in files


class TestServiceNowHandlerAuth:
    """Test authentication methods."""

    def test_basic_auth(self, mock_client):
        """Test basic authentication."""
        config = DataSourceConfig(
            type="servicenow",
            instance="dev00000",
            username="admin",
            password="password",
            table="incident",
        )

        handler = ServiceNowHandler(config)

        assert handler.client is not None

    def test_oauth_auth(self, mock_client):
        """Test OAuth2 authentication."""
        with patch("sygra.core.dataset.servicenow_handler.ServiceNowPasswordGrantFlow"):
            config = DataSourceConfig(
                type="servicenow",
                instance="dev00000",
                username="admin",
                password="password",
                oauth_client_id="client123",
                oauth_client_secret="secret456",
                table="incident",
            )

            handler = ServiceNowHandler(config)

            assert handler.client is not None

    @patch.dict("os.environ", {}, clear=True)
    def test_no_auth(self, mock_client):
        """Test fails without authentication."""
        config = DataSourceConfig(type="servicenow", instance="dev00000", table="incident")

        with pytest.raises(ValueError, match="No valid authentication method"):
            ServiceNowHandler(config)


class TestServiceNowHandlerQuery:
    """Test query building."""

    def test_query_with_filters(self, mock_client):
        """Test query with dict filters."""
        config = DataSourceConfig(
            type="servicenow",
            instance="dev00000",
            username="admin",
            password="password",
            table="incident",
            filters={"active": "true", "priority": "1", "state": "2"},
        )

        handler = ServiceNowHandler(config)
        records = handler.read()

        assert len(records) == 2

    def test_query_with_encoded_query(self, mock_client):
        """Test query with encoded query string."""
        config = DataSourceConfig(
            type="servicenow",
            instance="dev00000",
            username="admin",
            password="password",
            table="incident",
            query="active=true^priorityIN1,2,3",
        )

        handler = ServiceNowHandler(config)
        records = handler.read()

        assert len(records) == 2

    def test_query_with_list_values(self, mock_client):
        """Test query with list values (OR condition)."""
        config = DataSourceConfig(
            type="servicenow",
            instance="dev00000",
            username="admin",
            password="password",
            table="incident",
            filters={"priority": ["1", "2", "3"]},
        )

        handler = ServiceNowHandler(config)
        records = handler.read()

        assert len(records) == 2

    def test_query_with_operator(self, mock_client):
        """Test query with custom operator."""
        config = DataSourceConfig(
            type="servicenow",
            instance="dev00000",
            username="admin",
            password="password",
            table="incident",
            filters={"priority": {"operator": ">=", "value": "2"}},
        )

        handler = ServiceNowHandler(config)
        records = handler.read()

        assert len(records) == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
