"""Self-contained SyGra library example: FAQ entries from in-memory help articles.

It runs from plain Python with ``FakeProvider``: no API keys, no network and no
files outside this directory. It shows:

- ``Workflow.from_config()`` with prompt files resolved against ``base_dir``;
- hooks passed as Python objects: a configured post-processor and edge condition;
- an in-memory source, record ids and ``write_output=False``;
- model roles mapped to models per run;
- usage and cost in the returned ``RunResult``.

Run it with::

    python tasks/examples/library_pipeline/pipeline.py
"""

import asyncio
import json
from pathlib import Path
from typing import Any, Optional

import sygra
from sygra import FakeProvider, LLMRequest, RunResult, Workflow
from sygra.hooks import EdgeCondition, NodePostProcessorWithState, SygraMessage
from sygra.utils import constants

HERE = Path(__file__).resolve().parent

# Synthetic toy data. The last article has no id, so SyGra gives it record_id(row).
ARTICLES = [
    {
        "id": "kb-1",
        "title": "Reset a password",
        "body": "Open Settings, choose Security and select Reset password. A reset link is "
        "emailed to you",
    },
    {
        "id": "kb-2",
        "title": "Request a laptop",
        "body": "Submit the hardware request form. Approval takes two business days",
    },
    {"title": "Connect to VPN", "body": "Install the VPN client"},
]


class ParseJson(NodePostProcessorWithState):
    """Copy fields from a JSON reply into the state; missing or bad JSON gives None."""

    def __init__(self, *fields: str):
        self.fields = fields

    def apply(self, resp: SygraMessage, state: dict[str, Any]) -> dict[str, Any]:  # type: ignore[override]
        try:
            data = json.loads(resp.message.content)
        except (TypeError, ValueError):
            data = {}
        for field in self.fields:
            state[field] = data.get(field) if isinstance(data, dict) else None
        return state


class ShortAnswersNeedReview(EdgeCondition):
    """Send answers shorter than ``min_words`` to the reviewer; others are done."""

    def __init__(self, min_words: int):
        self.min_words = min_words

    def apply(self, state: dict[str, Any]) -> str:  # type: ignore[override]
        words = len(str(state.get("answer") or "").split())
        return "review" if words < self.min_words else constants.SYGRA_END


def build_config() -> dict[str, Any]:
    """The pipeline as a plain dict, shaped like a task's graph_config.yaml."""
    return {
        "data_config": {"source": {"type": "memory", "records": ARTICLES}},
        "graph_config": {
            "nodes": {
                "generate": {
                    "node_type": "llm",
                    "model": {"role": "generator"},
                    "prompt": [{"user": {"file": "prompts/generate_faq.txt"}}],
                    "post_process": ParseJson("question", "answer"),
                    "output_keys": ["question", "answer"],
                },
                "review": {
                    "node_type": "llm",
                    "model": {"role": "reviewer", "parameters": {"temperature": 0}},
                    "prompt": [{"user": {"file": "prompts/review_faq.txt"}}],
                    "post_process": ParseJson("verdict"),
                    "output_keys": "verdict",
                },
            },
            "edges": [
                {"from": "START", "to": "generate"},
                {
                    "from": "generate",
                    "condition": ShortAnswersNeedReview(min_words=8),
                    "path_map": {"review": "review", "END": "END"},
                },
                {"from": "review", "to": "END"},
            ],
        },
        "output_config": {
            "output_map": {
                "title": {"from": "title"},
                "question": {"from": "question"},
                "answer": {"from": "answer"},
                "verdict": {"from": "verdict"},
            }
        },
        # Defaults; run(model_roles=...) can override them per run.
        "model_roles": {
            "generator": {"name": "faq-writer", "model_type": "external"},
            "reviewer": {"name": "faq-reviewer", "model_type": "external"},
        },
    }


def fake_llm(request: LLMRequest) -> str:
    """Stand-in for a real model: builds replies from the ``Key: value`` prompt lines."""
    lines = request.messages[-1]["content"].splitlines()
    fields = dict(line.split(": ", 1) for line in lines if ": " in line)
    if "Answer" in fields:  # review prompt
        verdict = "approve" if len(fields["Answer"].split()) >= 5 else "revise"
        return json.dumps({"verdict": f"{verdict} by {request.model}"})
    first_sentence = fields["Article"].split(". ")[0]
    return json.dumps(
        {"question": f"How do I {fields['Title'].lower()}?", "answer": f"{first_sentence}."}
    )


def price(model: str, usage: Any) -> float:
    """Toy price list: $1 per million tokens."""
    return float(usage.total_tokens) * 1e-6


async def run_pipeline(model_roles: Optional[dict[str, Any]] = None) -> RunResult:
    workflow = Workflow.from_config(build_config(), base_dir=HERE, name="faq_pipeline")
    workflow.llm_provider(
        FakeProvider(
            fake_llm,
            usage=sygra.TokenUsage(prompt_tokens=20, completion_tokens=10, total_tokens=30),
        )
    )
    return await workflow.arun(write_output=False, model_roles=model_roles, cost_fn=price)


async def main() -> None:
    result = await run_pipeline()
    by_id = {record["id"]: record for record in result}
    for record_id in ("kb-1", "kb-2", sygra.record_id(ARTICLES[2])):
        print(json.dumps(by_id[record_id], indent=2))
    print("usage by model:", {name: u.total_tokens for name, u in result.usage_by_model.items()})
    print(f"cost: ${result.cost_usd:.6f}")

    # Same graph, different reviewer, no edits to the config.
    other = await run_pipeline({"reviewer": {"name": "second-opinion", "model_type": "external"}})
    print("reviewers:", sorted({r["verdict"] for r in other if r["verdict"]}))


if __name__ == "__main__":
    asyncio.run(main())
