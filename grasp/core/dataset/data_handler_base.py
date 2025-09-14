"""Base module for data handling operations.

This module provides the abstract base class for implementing data handlers
that can read from and write to different data sources.
"""

from abc import ABC, abstractmethod
from typing import Any, Iterator, Optional, Union


class DataHandler(ABC):
    """Abstract base class for handling data operations.

    This class defines the interface for reading and writing data across different
    storage systems like HuggingFace datasets and local files.

    Attributes:
        None
    """

    @abstractmethod
    def read(
        self, path: Optional[str] = None
    ) -> Union[list[dict[str, Any]], Iterator[dict[str, Any]]]:
        """Read data from the specified source.

        Args:
            path (Optional[str]): Path to the data source. If None, uses default configuration.

        Returns:
            Union[list[dict[str, Any]], Iterator[dict[str, Any]]]: Data as a list of dictionaries
                or an iterator of dictionaries.

        Raises:
            NotImplementedError: When the method is not implemented by a derived class.
        """
        pass

    @abstractmethod
    def write(self, data: list[dict[str, Any]], path: str) -> None:
        """Write data to the specified destination.

        Args:
            data (list[dict[str, Any]]): List of dictionaries containing the data to write.
            path (str): Path where the data should be written.

        Raises:
            NotImplementedError: When the method is not implemented by a derived class.
        """
        pass

    @abstractmethod
    def get_files(self) -> list[str]:
        """Get list of available files in the data source.

        For file systems, returns list of matching files.
        For HuggingFace, returns list of dataset files (including shards if enabled).

        Returns:
            list[str]: List of file paths available in the data source.

        Raises:
            NotImplementedError: When the method is not implemented by a derived class.
        """
        pass
