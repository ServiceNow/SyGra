"""
Flatten all DAG types from ServiceNow-AI/BFCL_agentic_judge_bench into a JSONL
for the SyGra query-rewriting pipeline.

Each output record:
  {
    "id":                 "<dag_type>_<original_id>",
    "dag_type":           "linear" | "fan_out" | ...,
    "user_message":       "<original verbose query>",
    "expected_tool_calls":"<JSON string — list of {name, arguments} for grounding>",
    "available_tools":    "<JSON string>",
    "system_prompt":      "<string>",
    "expected_responses": "<JSON string — full assistant turn list>"
  }

Usage:
    python prepare_input.py
    python prepare_input.py --dags linear fan_out fan_in diamond optional_enrichment loop_like
    python prepare_input.py --dags mix_sample --output input_flat.jsonl
"""

import argparse
import json
from pathlib import Path

from datasets import load_dataset

DIR = Path(__file__).parent

ALL_DAGS = ["linear", "fan_out", "fan_in", "diamond", "optional_enrichment", "loop_like"]


def extract_expected_tool_calls(expected_responses_raw) -> list:
    """Return flat list of {name, arguments} from expected_responses."""
    if isinstance(expected_responses_raw, str):
        messages = json.loads(expected_responses_raw)
    else:
        messages = expected_responses_raw

    calls = []
    for msg in messages:
        if not isinstance(msg, dict):
            continue
        if msg.get("role") == "assistant" and msg.get("tool_calls"):
            tc = msg["tool_calls"]
            if isinstance(tc, str):
                tc = json.loads(tc)
            for t in tc:
                fn = t.get("function", {})
                calls.append({
                    "name": fn.get("name", ""),
                    "arguments": fn.get("arguments", {}),
                })
    return calls


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--dags", nargs="+", default=ALL_DAGS,
        help="DAG types to include",
    )
    parser.add_argument("--output", default=str(DIR / "input_flat.jsonl"))
    args = parser.parse_args()

    records = []
    for dag in args.dags:
        ds = load_dataset("ServiceNow-AI/BFCL_agentic_judge_bench", dag, split="train")
        print(f"  {dag}: {len(ds)} records")
        for row in ds:
            raw_id = row.get("id", "") or ""
            expected_tool_calls = extract_expected_tool_calls(row["expected_responses"])

            # Skip records with no expected tool calls — nothing to ground rewrites to
            if not expected_tool_calls:
                continue

            records.append({
                "id":                  f"{dag}_{raw_id}",
                "dag_type":            dag,
                "user_message":        row["user_message"],
                "expected_tool_calls": json.dumps(expected_tool_calls),
                "available_tools":     (
                    row["available_tools"]
                    if isinstance(row["available_tools"], str)
                    else json.dumps(row["available_tools"])
                ),
                "system_prompt":       row.get("system_prompt", "") or "",
                "expected_responses":  (
                    row["expected_responses"]
                    if isinstance(row["expected_responses"], str)
                    else json.dumps(row["expected_responses"])
                ),
            })

    Path(args.output).write_text("\n".join(json.dumps(r) for r in records) + "\n")
    print(f"\nWritten {len(records)} records → {args.output}")


if __name__ == "__main__":
    main()
