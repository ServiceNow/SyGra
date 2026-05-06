"""
Aggregate per-record JSONL outputs from run_judge.py into per-cell mean alignment.
Reproduces Fig 3 / Table 1 / Table 3 cell values from the raw judging outputs.

Expects output paths produced by run_judge.py:
    <task_dir>/<generator>/judged_by_<judge>/<run_name_with_timestamp>/*.jsonl

Condition is inferred from the run_name prefix (set via run_judge.py --run_name):
    c1_/judge_  → c1_main           (Fig 3 main results)
    c2_/nogt05  → c2_nogt_05        (Table 3)
    c3_/corrupt → c3_corrupted_gt   (Table 1 cGT column)
    freeform_   → rq6_freeform      (Fig 7)

Usage:
    python tasks/agentic_bfcl_judge_eval/analyze_results.py
    python tasks/agentic_bfcl_judge_eval/analyze_results.py --output results.csv
    python tasks/agentic_bfcl_judge_eval/analyze_results.py --task_dir <dir>
"""

import argparse
import csv
import json
import re
import statistics
import sys
from collections import defaultdict
from pathlib import Path

CONDITION_PATTERNS = [
    (re.compile(r"^(c2_|nogt_?05)", re.I), "c2_nogt_05"),
    (re.compile(r"^(c3_|corrupt)",   re.I), "c3_corrupted_gt"),
    (re.compile(r"^freeform",        re.I), "rq6_freeform"),
    (re.compile(r"^(c1_|judge_)",    re.I), "c1_main"),
]
DIFFICULTY_RE = re.compile(r"\b(easy|medium|hard)\b", re.I)


def parse_run_dir(run_dir: str) -> tuple[str, str]:
    """Extract (condition, difficulty) from a run directory name."""
    condition = next(
        (label for pat, label in CONDITION_PATTERNS if pat.search(run_dir)),
        "c1_main",
    )
    diff_match = DIFFICULTY_RE.search(run_dir)
    difficulty = diff_match.group(1).lower() if diff_match else "unknown"
    return condition, difficulty


def aggregate(task_dir: Path) -> list[dict]:
    cells: dict[tuple, list[dict]] = defaultdict(list)
    for jsonl in task_dir.glob("*/judged_by_*/*/*.jsonl"):
        parts = jsonl.relative_to(task_dir).parts
        if len(parts) < 4 or not parts[1].startswith("judged_by_"):
            continue
        generator, judge_dir, run_dir = parts[0], parts[1], parts[2]
        judge = judge_dir[len("judged_by_"):]
        condition, difficulty = parse_run_dir(run_dir)
        with jsonl.open() as f:
            cells[(generator, judge, difficulty, condition)].extend(
                json.loads(line) for line in f if line.strip()
            )

    rows = []
    for (gen, judge, diff, cond), records in sorted(cells.items()):
        with_gt = [r["overall_llm_alignment_percentage"]
                   for r in records if r.get("overall_llm_alignment_percentage") is not None]
        without_gt = [r["overall_llm_alignment_percentage_no_gt"]
                      for r in records if r.get("overall_llm_alignment_percentage_no_gt") is not None]
        rows.append({
            "generator":  gen,
            "judge":      judge,
            "difficulty": diff,
            "condition":  cond,
            "n_records":  len(records),
            "n_with_gt":  len(with_gt),
            "n_without_gt": len(without_gt),
            "mean_alignment_with_gt":    round(statistics.mean(with_gt), 2) if with_gt else None,
            "mean_alignment_without_gt": round(statistics.mean(without_gt), 2) if without_gt else None,
        })
    return rows


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--task_dir", type=str, default=str(Path(__file__).parent),
                        help="Base task directory (default: directory containing this script)")
    parser.add_argument("--output", type=str, default=None,
                        help="Output CSV path (default: print to stdout)")
    args = parser.parse_args()

    rows = aggregate(Path(args.task_dir))
    if not rows:
        print(f"No JSONL outputs found under {args.task_dir}", file=sys.stderr)
        sys.exit(1)

    fieldnames = list(rows[0].keys())
    sink = open(args.output, "w") if args.output else sys.stdout
    writer = csv.DictWriter(sink, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows)
    if args.output:
        sink.close()
        print(f"Wrote {len(rows)} cells → {args.output}", file=sys.stderr)


if __name__ == "__main__":
    main()
