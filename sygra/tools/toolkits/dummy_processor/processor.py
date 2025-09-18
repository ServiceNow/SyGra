import json
import os
from typing import Any, Optional

from sygra.tools.base_tool import BaseTool
from sygra.tools.registry import register_tool
from sygra.utils import utils


@register_tool
class DummyProcessor(BaseTool):
    """A simple dummy tool to test the pipeline."""

    name = "dummy_processor"
    description = "Adds a dummy field to each record"

    def __init__(self, config: dict[str, Any]):
        self.config = config
        self.message = config.get("message", "processed by dummy tool")
        self.field_name = config.get("field_name", "dummy_processed")

    def process(self, input_path: Optional[str] = None, output_path: Optional[str] = None) -> str:
        if not input_path:
            raise ValueError("Input path is required")

        # Determine output path
        if not output_path:
            dir_name, file_name = os.path.split(input_path)
            base_name, ext = os.path.splitext(file_name)
            output_path = os.path.join(dir_name, f"{base_name}_dummy{ext or '.jsonl'}")

        # Load data
        data: list[dict[str, Any]] = []
        with open(input_path, "r", encoding="utf-8") as f:
            if input_path.endswith(".json"):
                data = json.load(f) if isinstance(json.load(f), list) else [json.load(f)]
            else:
                data = [json.loads(line) for line in f if line.strip()]

        # Modify data
        for item in data:
            item[self.field_name] = self.message

        # Write data
        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

        if output_path.endswith(".json"):
            utils.save_json_file(output_path, data)
        else:
            utils.save_jsonl_file(output_path, data)

        return output_path
