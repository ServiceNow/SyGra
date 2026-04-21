"""
Splits bfcl_agentic_rewritten.jsonl into three per-difficulty input files
for the judge eval pipeline.

For each difficulty the user_message field is replaced with the appropriate
query variant; all other fields (available_tools, expected_responses,
system_prompt, expected_tool_calls, dag_type, id) are preserved unchanged.

Output files (written next to this script):
    input_easy.jsonl    — user_message = original user_message
    input_medium.jsonl  — user_message = query_medium
    input_hard.jsonl    — user_message = query_hard

Usage:
    python tasks/examples/agentic_bfcl_judge_eval/prepare_difficulty_inputs.py
    python tasks/examples/agentic_bfcl_judge_eval/prepare_difficulty_inputs.py \\
        --source tasks/examples/agentic_bfcl_query_rewrite/bfcl_agentic_rewritten.jsonl
"""

import argparse
import json
from pathlib import Path

DEFAULT_SOURCE = (
    Path(__file__).parent.parent
    / "agentic_bfcl_query_rewrite"
    / "bfcl_agentic_rewritten.jsonl"
)
OUT_DIR = Path(__file__).parent

DIFFICULTY_MAP = {
    "easy":   "user_message",
    "medium": "query_medium",
    "hard":   "query_hard",
}

KEEP_FIELDS = [
    "id", "dag_type", "user_message",
    "system_prompt", "available_tools",
    "expected_responses", "expected_tool_calls",
]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", default=str(DEFAULT_SOURCE),
                        help="Path to bfcl_agentic_rewritten.jsonl")
    args = parser.parse_args()

    source = Path(args.source)
    records = [json.loads(line) for line in source.read_text().splitlines() if line.strip()]
    print(f"Loaded {len(records)} records from {source}")

    for difficulty, query_field in DIFFICULTY_MAP.items():
        out_path = OUT_DIR / f"input_{difficulty}.jsonl"
        skipped = 0
        with out_path.open("w") as f:
            for rec in records:
                query = rec.get(query_field, "").strip()
                if not query:
                    skipped += 1
                    query = rec["user_message"]  # fallback to original
                row = {k: rec[k] for k in KEEP_FIELDS if k in rec}
                row["user_message"] = query
                row["difficulty"] = difficulty
                f.write(json.dumps(row) + "\n")
        print(f"  {difficulty:6s} → {out_path}  ({len(records) - skipped}/{len(records)} records with valid rewrite)")

    print("\nDone. Run the judge sweep with:")
    for difficulty in DIFFICULTY_MAP:
        print(
            f"  python run_judge_sweep.py --judge_model <model> "
            f"--task tasks.examples.agentic_bfcl_judge_eval "
            f"--input_file tasks/examples/agentic_bfcl_judge_eval/input_{difficulty}.jsonl "
            f"--output_dir tasks/examples/agentic_bfcl_judge_eval/results/{difficulty} "
            f"-n 3808 -b 25"
        )


if __name__ == "__main__":
    main()
