"""Data handler for in-memory sources (a list of records passed from Python)."""

from typing import Any, Optional

from sygra.core.dataset.data_handler_base import DataHandler
from sygra.core.dataset.dataset_config import DataSourceConfig
from sygra.utils import utils


class MemoryHandler(DataHandler):
    """Reads records from ``DataSourceConfig.records``; nothing touches disk.

    ``read()`` returns copies of the records' dicts and lists, so the run can add
    ids and transform records without changing the caller's data.
    """

    def __init__(self, source_config: DataSourceConfig):
        if source_config.records is None:
            raise ValueError("A memory source needs 'records' (a list of dicts)")
        self.source_config = source_config

    def read(self, path: Optional[str] = None) -> list[dict[str, Any]]:
        records = self.source_config.records or []
        for index, record in enumerate(records):
            if not isinstance(record, dict):
                raise ValueError(
                    f"Memory source records must be dicts; record {index} is "
                    f"{type(record).__name__}"
                )
        copied: list[dict[str, Any]] = utils.copy_config(records)
        return copied

    def write(self, data: list[dict[str, Any]], path: str) -> None:
        raise NotImplementedError("A memory source can't be written to")

    def get_files(self) -> list[str]:
        return []
