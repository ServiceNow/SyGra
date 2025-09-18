import os
from typing import Any, Dict, Optional

from sygra.data_mapper.mapper import (  # Assuming you've modularized it to mapper.py
    DataMapper,
)
from sygra.logger.logger_config import logger
from sygra.tools.base_tool import BaseTool
from sygra.tools.registry import register_tool
from sygra.utils import utils


@register_tool
class OASSTMapper(BaseTool):
    name = "oasst_mapper"
    description = "Transforms conversational data into OASST format"

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.mapper = DataMapper(config=self.config)

    def process(self, input_path: Optional[str], output_path: Optional[str]) -> str:
        if not input_path:
            raise ValueError("Input path is required.")
        if not output_path:
            raise ValueError("Output path is required.")

        logger.info("Running OASST mapping pipeline...")
        data = (
            utils.load_jsonl_file(input_path)
            if input_path.endswith(".jsonl")
            else utils.load_json_file(input_path)
        )
        logger.info(f"Loaded {len(data)} records from {input_path}")

        try:
            mapped_data = self.mapper.map_all_items(data)
        except Exception as e:
            logger.error(f"Failed during mapping: {e}")
            mapped_data = data  # fallback to original

        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

        if output_path.endswith(".jsonl"):
            utils.save_jsonl_file(output_path, mapped_data)
        else:
            utils.save_json_file(output_path, mapped_data)

        logger.info(f"OASST-mapped data written to: {output_path}")
        return output_path
