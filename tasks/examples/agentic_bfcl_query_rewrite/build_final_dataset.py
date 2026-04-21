"""
Merges the SyGra rewrite output back with the original records to produce
a final JSONL dataset with all three query difficulty levels.

Each output record contains:
  - id, dag_type
  - user_message       (original — "easy")
  - query_medium       (medium difficulty rewrite)
  - query_hard         (hard difficulty rewrite)
  - available_tools, system_prompt, expected_responses, expected_tool_calls
  - rewrite_medium_status, rewrite_hard_status  ("OK" or "FAILED")

Usage:
    python build_final_dataset.py
    python build_final_dataset.py \
        --rewrites output_<timestamp>.json \
        --output   bfcl_agentic_rewritten.jsonl
"""

import argparse
import json
from pathlib import Path

DIR = Path(__file__).parent


def find_latest_output() -> Path:
    outputs = sorted(DIR.glob("*output_*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not outputs:
        raise FileNotFoundError(f"No output_*.json found in {DIR}")
    return outputs[0]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--rewrites", default=None,
        help="SyGra output JSON (defaults to latest output_*.json in task dir)",
    )
    parser.add_argument(
        "--output", default=str(DIR / "bfcl_agentic_rewritten.jsonl"),
    )
    args = parser.parse_args()

    rewrite_path = Path(args.rewrites) if args.rewrites else find_latest_output()
    print(f"Loading rewrites from: {rewrite_path}")

    raw = rewrite_path.read_text().strip()
    rewrites = json.loads(raw) if raw.startswith("[") else [json.loads(l) for l in raw.splitlines() if l.strip()]
    print(f"  {len(rewrites)} rewritten records")

    # Stats
    med_ok   = sum(1 for r in rewrites if r.get("rewrite_medium_status") == "OK")
    hard_ok  = sum(1 for r in rewrites if r.get("rewrite_hard_status")   == "OK")
    print(f"  Medium OK: {med_ok}/{len(rewrites)} ({med_ok/len(rewrites)*100:.1f}%)")
    print(f"  Hard   OK: {hard_ok}/{len(rewrites)} ({hard_ok/len(rewrites)*100:.1f}%)")

    # DAG type breakdown
    from collections import Counter
    dag_counts = Counter(r.get("dag_type", "unknown") for r in rewrites)
    print("  DAG breakdown:", dict(dag_counts))

    # Build final records — preserve all original fields, add rewrites
    final = []
    for r in rewrites:
        final.append({
            "id":                    r["id"],
            "dag_type":              r.get("dag_type", ""),
            "user_message":          r["user_message"],       # original (easy)
            "query_medium":          r.get("query_medium", r["user_message"]),
            "query_hard":            r.get("query_hard",   r["user_message"]),
            "rewrite_medium_status": r.get("rewrite_medium_status", "UNKNOWN"),
            "rewrite_hard_status":   r.get("rewrite_hard_status",   "UNKNOWN"),
            "system_prompt":         r.get("system_prompt", ""),
            "available_tools":       r.get("available_tools", ""),
            "expected_responses":    r.get("expected_responses", ""),
            "expected_tool_calls":   r.get("expected_tool_calls", ""),
        })

    Path(args.output).write_text("\n".join(json.dumps(r) for r in final) + "\n")
    print(f"\nWritten {len(final)} records → {args.output}")


if __name__ == "__main__":
    main()
