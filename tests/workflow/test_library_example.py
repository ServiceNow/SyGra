"""Runs the public library example (tasks/examples/library_pipeline) so it keeps working."""

import importlib.util
import sys
from pathlib import Path

import pytest

sys.path.append(str(Path(__file__).parent.parent.parent))

import sygra

ROOT = Path(__file__).parent.parent.parent
EXAMPLE = ROOT / "tasks" / "examples" / "library_pipeline" / "pipeline.py"


def _load_example():
    spec = importlib.util.spec_from_file_location("library_pipeline_example", EXAMPLE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.asyncio
async def test_library_example_runs_from_another_directory(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    example = _load_example()

    result = await example.run_pipeline()

    by_id = {r["id"]: r for r in result}
    vpn_id = sygra.record_id(example.ARTICLES[2])
    assert set(by_id) == {"kb-1", "kb-2", vpn_id}
    # Long answers skip review; short ones go to the reviewer role.
    assert by_id["kb-1"]["verdict"] is None
    assert by_id["kb-2"]["verdict"] == "approve by faq-reviewer"
    assert by_id[vpn_id]["verdict"] == "revise by faq-reviewer"
    assert set(result.usage_by_model) == {"faq-writer", "faq-reviewer"}
    assert result.cost_usd == pytest.approx(150e-6)
    assert result.output_file is None
    assert not list(tmp_path.glob("*output*"))  # nothing written to the working directory

    other = await example.run_pipeline(
        {"reviewer": {"name": "second-opinion", "model_type": "external"}}
    )
    assert {r["verdict"] for r in other if r["verdict"]} == {
        "approve by second-opinion",
        "revise by second-opinion",
    }
