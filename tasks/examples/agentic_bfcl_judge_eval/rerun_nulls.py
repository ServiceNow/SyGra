#!/usr/bin/env python3
"""
Audit all completed judge runs for null alignment scores, create filtered input
JSONLs for the null records, and launch reruns via run_judge.py --input.

A run is "complete" when its output record count matches the generator JSONL size.
Only complete runs are eligible for null rerun (in-progress runs are skipped).

Usage:
    python rerun_nulls.py              # dry-run: print audit only
    python rerun_nulls.py --launch     # also write subset JSONLs and launch reruns
    python rerun_nulls.py --config graph_config_nogt_05.yaml --launch  # C2 only
    python rerun_nulls.py --merge      # merge rerun outputs back into originals
"""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from collections import defaultdict

DIR = Path(__file__).parent
RERUN_DIR = DIR / "null_rerun_inputs"

# ── judge → (config, suffix) ──────────────────────────────────────────────────
JUDGE_CONFIG = {
    # C1 judges
    "claude_large":      "graph_config.yaml",
    "gpt_5_4":           "graph_config.yaml",
    "gpt_oss_20b":       "graph_config.yaml",
    "qwq_32b":           "graph_config.yaml",
    "reranker_gemini":   "graph_config.yaml",
    "gpt_oss_120b":      "graph_config.yaml",
    # C2 nogt_05 judges
    "claude_large_nogt_05":    "graph_config_nogt_05.yaml",
    "gpt_5_4_nogt_05":         "graph_config_nogt_05.yaml",
    "gpt_oss_20b_nogt_05":     "graph_config_nogt_05.yaml",
    "qwq_32b_nogt_05":         "graph_config_nogt_05.yaml",
    "reranker_gemini_nogt_05": "graph_config_nogt_05.yaml",
    "gpt_oss_120b_nogt_05":    "graph_config_nogt_05.yaml",
}

# ── expected record counts per generator/difficulty ───────────────────────────
def get_expected(generator: str, diff: str) -> int:
    jsonl = DIR / generator / f"{diff}.jsonl"
    if not jsonl.exists():
        return 0
    with open(jsonl) as f:
        return sum(1 for line in f if line.strip())

# ── load the latest output file for a (judge, generator, diff) ───────────────
def find_output(generator: str, judge: str, diff: str):
    out_dir = DIR / generator / f"judged_by_{judge}"
    if not out_dir.is_dir():
        return None, None
    # pick the largest primary file (best proxy for most complete run)
    # exclude nullrerun files so the audit always reads the primary output
    candidates = sorted(
        [f for f in out_dir.glob(f"*_{diff}_output_*.json")
         if f.name != "metadata" and "nullrerun" not in f.name],
        key=lambda f: f.stat().st_size
    )
    return (candidates[-1], out_dir) if candidates else (None, None)

# ── null check ────────────────────────────────────────────────────────────────
def null_ids(records):
    # Null records have ALL fields as None (pure ghost placeholders) — id is also None.
    # Instead, compute missing IDs by set-difference: JSONL IDs minus successfully-judged IDs.
    return None  # not used directly

def successful_ids(records):
    return {r["id"] for r in records
            if r.get("id") is not None and r.get("overall_llm_alignment_percentage") is not None}

def load_jsonl_index(generator: str, diff: str) -> dict:
    jsonl = DIR / generator / f"{diff}.jsonl"
    idx = {}
    with open(jsonl) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            idx[rec["id"]] = rec
    return idx

# ── main audit ────────────────────────────────────────────────────────────────
def audit(config_filter=None):
    generators = [
        "gpt_5_4",
        "llama_3_1_8b_instruct",
        "llama_3_3_70b_instruct",
        "qwen3_32b",
        "smollm3_3b",
    ]
    diffs = ["easy", "medium", "hard"]

    results = []  # (judge, generator, diff, total, expected, n_null, out_file, out_dir)

    for judge, cfg in JUDGE_CONFIG.items():
        if config_filter and cfg != config_filter:
            continue
        for gen in generators:
            jsonl = DIR / gen / f"easy.jsonl"  # existence check
            if not jsonl.parent.exists():
                continue
            for diff in diffs:
                expected = get_expected(gen, diff)
                if expected == 0:
                    continue
                out_file, out_dir = find_output(gen, judge, diff)
                if out_file is None:
                    results.append((judge, gen, diff, 0, expected, 0, None, None))
                    continue
                with open(out_file) as f:
                    records = json.load(f)
                total = len(records)
                n_null = sum(1 for r in records if r.get("id") is None or r.get("overall_llm_alignment_percentage") is None)
                results.append((judge, gen, diff, total, expected, n_null, out_file, out_dir))

    return results

def print_audit(results):
    print(f"\n{'JUDGE':<30} {'GEN':<25} {'DIFF':<6} {'TOTAL':>6} {'EXP':>6} {'NULLS':>6} {'STATUS'}")
    print("-" * 100)
    total_nulls = 0
    for judge, gen, diff, total, expected, n_null, out_file, out_dir in sorted(results):
        if total == 0:
            status = "❌ MISSING"
        elif total < expected:
            status = f"⏳ {total}/{expected}"
        elif n_null == 0:
            status = "✅ CLEAN"
        else:
            pct = round(n_null * 100 / total)
            status = f"⚠️  {n_null} nulls ({pct}%)"
            total_nulls += n_null
        print(f"{judge:<30} {gen:<25} {diff:<6} {total:>6} {expected:>6} {n_null:>6}  {status}")
    print(f"\nTotal null records across complete runs: {total_nulls:,}")

def needs_rerun(judge, gen, diff, total, expected, n_null, out_file, out_dir):
    return total == expected and n_null > 0 and out_file is not None

def launch_reruns(results, dry_run=True):
    RERUN_DIR.mkdir(exist_ok=True)
    cmds = []
    for judge, gen, diff, total, expected, n_null, out_file, out_dir in results:
        if not needs_rerun(judge, gen, diff, total, expected, n_null, out_file, out_dir):
            continue
        cfg = JUDGE_CONFIG[judge]

        # Find missing IDs: JSONL IDs that were never successfully judged
        with open(out_file) as f:
            records = json.load(f)
        succeeded = successful_ids(records)
        jsonl_idx = load_jsonl_index(gen, diff)
        missing_ids = set(jsonl_idx.keys()) - succeeded
        subset = [jsonl_idx[rid] for rid in missing_ids]

        if not subset:
            print(f"  SKIP {judge}/{gen}/{diff}: null IDs not found in generator JSONL")
            continue

        subset_path = RERUN_DIR / f"{judge}__{gen}__{diff}__nulls.jsonl"
        if not dry_run:
            with open(subset_path, "w") as f:
                for rec in subset:
                    f.write(json.dumps(rec) + "\n")

        cmd = [
            ".venv/bin/python",
            "tasks/examples/agentic_bfcl_judge_eval/run_judge.py",
            "--generator", gen,
            "--judge_model", judge,
            "--difficulty", diff,
            "--config", cfg,
            "--input", str(subset_path),
            "--run_name", f"nullrerun_{judge}_{gen}_{diff}",
        ]
        cmds.append((judge, gen, diff, n_null, cmd, subset_path))
        print(f"  {'[DRY]' if dry_run else '[LAUNCH]'} {judge}/{gen}/{diff}: {n_null} nulls → {subset_path.name}")

    if not dry_run and cmds:
        # Group by judge and launch one worker per judge (sequential within judge)
        by_judge = defaultdict(list)
        for judge, gen, diff, n_null, cmd, subset_path in cmds:
            by_judge[judge].append((gen, diff, n_null, cmd, subset_path))

        cells_dir = RERUN_DIR / "cells"
        cells_dir.mkdir(exist_ok=True)
        for judge, cells in by_judge.items():
            cells_file = cells_dir / f"{judge}_nulls.txt"
            with open(cells_file, "w") as f:
                for gen, diff, n_null, cmd, subset_path in cells:
                    f.write(f"{gen} {diff}\n")
            # Write a small per-judge launcher that uses --input
            launcher = cells_dir / f"launch_{judge}.sh"
            with open(launcher, "w") as f:
                f.write("#!/usr/bin/env bash\nset -u\ncd /Users/abhigya.verma/git/SyGra\n")
                for gen, diff, n_null, cmd, subset_path in cells:
                    cfg = JUDGE_CONFIG[judge]
                    f.write(
                        f".venv/bin/python tasks/examples/agentic_bfcl_judge_eval/run_judge.py"
                        f" --generator {gen} --judge_model {judge} --difficulty {diff}"
                        f" --config {cfg} --input {subset_path}"
                        f" --run_name nullrerun_{judge}_{gen}_{diff}"
                        f" >> {cells_dir}/nullrerun_{judge}.log 2>&1\n"
                    )
            os.chmod(launcher, 0o755)
            subprocess.Popen(["bash", str(launcher)], start_new_session=True)
            print(f"  Launched worker for {judge} ({len(cells)} cells) → PID launched")

    return cmds

def merge_reruns(results):
    """Patch null records in original output files with rerun results."""
    RERUN_DIR.mkdir(exist_ok=True)
    for judge, gen, diff, total, expected, n_null, out_file, out_dir in results:
        if not needs_rerun(judge, gen, diff, total, expected, n_null, out_file, out_dir):
            continue
        # Find all rerun output files; pick the one with most successes (fewest nulls)
        rerun_candidates = list(out_dir.glob(f"*nullrerun*{diff}*output*.json"))
        if not rerun_candidates:
            print(f"  No rerun output yet for {judge}/{gen}/{diff}")
            continue
        def rerun_quality(f):
            try:
                recs = json.load(open(f))
                return sum(1 for r in recs if r.get("overall_llm_alignment_percentage") is not None)
            except Exception:
                return -1
        rerun_file = max(rerun_candidates, key=rerun_quality)
        with open(rerun_file) as f:
            rerun_records = json.load(f)
        with open(out_file) as f:
            orig_records = json.load(f)

        # Build a lookup of the best result per ID from ALL sources:
        # primary non-null > rerun non-null > ghost (keep as null placeholder)
        best_by_id: dict = {}
        # Index primary non-null records
        for r in orig_records:
            rid = r.get("id")
            if rid is not None and r.get("overall_llm_alignment_percentage") is not None:
                best_by_id[rid] = r
        # Index rerun good records (only fill gaps, don't overwrite primary good)
        added = 0
        for r in rerun_records:
            rid = r.get("id")
            if rid is not None and r.get("overall_llm_alignment_percentage") is not None:
                if rid not in best_by_id:
                    best_by_id[rid] = r
                    added += 1

        # Rebuild using canonical JSONL ID order; keep ghost for any still-missing ID
        jsonl_idx = load_jsonl_index(gen, diff)
        merged = []
        for rid, orig_input in jsonl_idx.items():
            if rid in best_by_id:
                merged.append(best_by_id[rid])
            else:
                # still null — keep one ghost placeholder
                merged.append({k: None for k in orig_records[0].keys()})

        remaining_nulls = sum(1 for r in merged if r.get("overall_llm_alignment_percentage") is None)
        with open(out_file, "w") as f:
            json.dump(merged, f, indent=2)
        print(f"  Merged {added} new records into {out_file.name} "
              f"({len(merged)} total, {remaining_nulls} nulls remaining)")


def launch_missing(dry_run=True):
    """Launch full runs for MISSING cells (no output file at all)."""
    generators = [
        "gpt_5_4", "llama_3_1_8b_instruct", "llama_3_3_70b_instruct",
        "qwen3_32b", "smollm3_3b",
    ]
    diffs = ["easy", "medium", "hard"]
    RESUME_DIR = DIR / "resume_inputs"
    if not dry_run:
        RESUME_DIR.mkdir(exist_ok=True)

    by_judge: dict = defaultdict(list)
    for judge, cfg in JUDGE_CONFIG.items():
        for gen in generators:
            if not (DIR / gen).is_dir():
                continue
            for diff in diffs:
                expected = get_expected(gen, diff)
                if expected == 0:
                    continue
                out_file, out_dir = find_output(gen, judge, diff)
                if out_file is None:
                    print(f"  {'[DRY]' if dry_run else '[LAUNCH]'} MISSING {judge}/{gen}/{diff} ({expected} records)")
                    by_judge[judge].append((gen, diff, cfg))

    if not dry_run and by_judge:
        cells_dir = DIR / "resume_inputs" / "cells"
        cells_dir.mkdir(exist_ok=True)
        for judge, cells in by_judge.items():
            launcher = cells_dir / f"launch_missing_{judge}.sh"
            with open(launcher, "w") as f:
                f.write("#!/usr/bin/env bash\nset -u\ncd /Users/abhigya.verma/git/SyGra\n")
                for gen, diff, cfg in cells:
                    log = cells_dir / f"missing_{judge}_{gen}_{diff}.log"
                    f.write(
                        f".venv/bin/python tasks/examples/agentic_bfcl_judge_eval/run_judge.py"
                        f" --generator {gen} --judge_model {judge} --difficulty {diff}"
                        f" --config {cfg}"
                        f" >> {log} 2>&1\n"
                    )
            os.chmod(launcher, 0o755)
            subprocess.Popen(["nohup", "bash", str(launcher)], start_new_session=True)
            print(f"  Launched missing-cell worker for {judge} ({len(cells)} cells)")

    return by_judge


def launch_resume(results, dry_run=True):
    """For in-progress cells (total < expected), compute missing IDs and launch completion runs."""
    RESUME_DIR = DIR / "resume_inputs"
    if not dry_run:
        RESUME_DIR.mkdir(exist_ok=True)

    by_judge: dict = defaultdict(list)
    for judge, gen, diff, total, expected, n_null, out_file, out_dir in results:
        if total == 0 or total >= expected or out_file is None:
            continue
        cfg = JUDGE_CONFIG[judge]

        with open(out_file) as f:
            records = json.load(f)
        present_ids = {r["id"] for r in records if r.get("id") is not None}
        jsonl_idx = load_jsonl_index(gen, diff)
        missing_ids = set(jsonl_idx.keys()) - present_ids
        if not missing_ids:
            continue

        subset = [jsonl_idx[rid] for rid in missing_ids]
        subset_path = RESUME_DIR / f"{judge}__{gen}__{diff}__resume.jsonl"
        if not dry_run:
            with open(subset_path, "w") as f:
                for rec in subset:
                    f.write(json.dumps(rec) + "\n")

        n_missing = len(missing_ids)
        print(f"  {'[DRY]' if dry_run else '[LAUNCH]'} RESUME {judge}/{gen}/{diff}: "
              f"{total}/{expected} present, {n_missing} missing → {subset_path.name}")
        by_judge[judge].append((gen, diff, cfg, n_missing, subset_path))

    if not dry_run and by_judge:
        cells_dir = RESUME_DIR / "cells"
        cells_dir.mkdir(exist_ok=True)
        for judge, cells in by_judge.items():
            launcher = cells_dir / f"launch_resume_{judge}.sh"
            with open(launcher, "w") as f:
                f.write("#!/usr/bin/env bash\nset -u\ncd /Users/abhigya.verma/git/SyGra\n")
                for gen, diff, cfg, n_missing, subset_path in cells:
                    log = cells_dir / f"resume_{judge}_{gen}_{diff}.log"
                    f.write(
                        f".venv/bin/python tasks/examples/agentic_bfcl_judge_eval/run_judge.py"
                        f" --generator {gen} --judge_model {judge} --difficulty {diff}"
                        f" --config {cfg} --input {subset_path}"
                        f" --run_name resume_{judge}_{gen}_{diff}"
                        f" >> {log} 2>&1\n"
                    )
            os.chmod(launcher, 0o755)
            subprocess.Popen(["nohup", "bash", str(launcher)], start_new_session=True)
            print(f"  Launched resume worker for {judge} ({len(cells)} cells)")

    return by_judge


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--launch", action="store_true", help="Write subset JSONLs and launch null reruns")
    parser.add_argument("--resume", action="store_true", help="Launch completion runs for in-progress cells")
    parser.add_argument("--missing", action="store_true", help="Launch full runs for MISSING cells")
    parser.add_argument("--merge", action="store_true", help="Merge rerun outputs back into originals")
    parser.add_argument("--config", default=None, help="Filter to a specific graph config (e.g. graph_config_nogt_05.yaml)")
    parser.add_argument("--judge", default=None, help="Filter to a specific judge")
    args = parser.parse_args()

    print("=== NULL AUDIT ===")
    results = audit(config_filter=args.config)
    if args.judge:
        results = [r for r in results if r[0] == args.judge]
    print_audit(results)

    rerun_candidates = [r for r in results if needs_rerun(*r)]
    print(f"\n{len(rerun_candidates)} (judge, gen, diff) combos need null rerun")

    if args.merge:
        print("\n=== MERGING RERUN OUTPUTS ===")
        merge_reruns(results)
    elif args.resume:
        print("\n=== LAUNCHING RESUME RUNS (in-progress cells) ===")
        launch_resume(results, dry_run=False)
    elif args.missing:
        print("\n=== LAUNCHING MISSING CELLS ===")
        launch_missing(dry_run=False)
    elif args.launch:
        print("\n=== LAUNCHING NULL RERUNS ===")
        launch_reruns(results, dry_run=False)
    else:
        print("\n=== DRY-RUN PLAN ===")
        print("\n--- In-progress cells (need resume) ---")
        launch_resume(results, dry_run=True)
        print("\n--- Missing cells ---")
        launch_missing(dry_run=True)
        print("\n--- Null reruns (complete cells with nulls) ---")
        launch_reruns(results, dry_run=True)
        print("\nRe-run with --resume, --missing, or --launch to execute.")
