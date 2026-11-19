"""Regression: results not yet checkpointed are written at the end of non-resumable runs."""

import asyncio
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.append(str(Path(__file__).parent.parent.parent.parent))

from sygra.core.dataset.dataset_processor import DatasetProcessor
from sygra.utils import constants


class _Graph:
    """Succeeds for every record except 'bad', which fails after the others finish."""

    async def ainvoke(self, record, debug=False, config=None):
        if record["id"] == "bad":
            await asyncio.sleep(0.05)
            return {"id": "bad", "answer": f"{constants.ERROR_PREFIX} refused"}
        return {"id": record["id"], "answer": "ok"}


def _run(tmp_path, records):
    graph_config = MagicMock()
    graph_config.config = {}
    graph_config.oasst_mapper = None
    output_file = tmp_path / "output.json"
    processor = DatasetProcessor(
        records,
        _Graph(),  # type: ignore[arg-type]
        graph_config,
        str(output_file),
        num_records_total=len(records),
        batch_size=10,
        checkpoint_interval=10,
    )
    validator = MagicMock()
    validator.return_value.validate.return_value = True
    with patch("sygra.core.dataset.dataset_processor.SchemaValidator", validator):
        asyncio.run(processor._process_and_store_results())
    return json.loads(output_file.read_text()) if output_file.exists() else []


@pytest.mark.parametrize(
    "ids, expected",
    [
        (["a", "b2", "bad"], ["a", "b2"]),  # last record to finish fails
        (["a", "b2", "c"], ["a", "b2", "c"]),  # all succeed: written once, no duplicates
    ],
)
def test_successful_records_are_always_written(tmp_path, ids, expected):
    written = _run(tmp_path, [{"id": i} for i in ids])
    assert sorted(r["id"] for r in written) == expected
