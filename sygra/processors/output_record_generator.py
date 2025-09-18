from abc import ABC
from typing import Any

from sygra.core.graph.sygra_state import SygraState


class BaseOutputGenerator(ABC):
    """
    Provides default logic for building the final record from 'output_map'.
    Each derived class can define transform methods if they want to transform the data.
    """

    def __init__(self, config: dict[str, Any]):
        self.config = config
        self.output_map = config.get("output_map", {})  # optional

    def generate(self, state: SygraState) -> dict[str, Any]:
        """
        Create the final record.

        Args:
            state: SygraState object

        Returns:
            dict: The final record
        """
        record = self._build_record(state)

        return record

    def _build_record(self, state: SygraState) -> dict[str, Any]:
        """
        Default method for building a record from output_map.
        If the derived class wants a purely code-based approach, it can override this entirely.

        Args:
            state: SygraState object

        Returns:
            dict: The final record
        """
        record = {}
        for field_name, mapping in self.output_map.items():
            record[field_name] = self._resolve_field(mapping, state)
        return record

    def _resolve_field(self, mapping: dict[str, Any], state: SygraState) -> Any:
        """
        Resolves each entry in output_map.

        Args:
            mapping: Mapping for a field
            state: SygraState object

        Returns:
            Any: The resolved data
        """

        # literal (using the 'value' key)
        if "value" in mapping:
            data = mapping["value"]
        # from the state (using the 'from' key)
        elif "from" in mapping:
            data = state.get(mapping["from"], None)
        else:
            raise ValueError(f"Invalid mapping: {mapping}")

        if "transform" in mapping:
            transform_name = mapping["transform"]
            method = getattr(self, f"{transform_name}", None)
            if not callable(method):
                raise ValueError(
                    f"Transform '{transform_name}' is not defined in class '{self.__class__.__name__}'."
                )
            data = method(data, state)

        return data
