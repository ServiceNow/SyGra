#!/usr/bin/env python3
"""Audit C1/C2/C3 completeness, write missing-ID subset JSONLs, and launch reruns."""
import json, os, subprocess, sys
from pathlib import Path

DIR = Path(__file__).parent
SYGRA_ROOT = DIR.parent.parent.parent
VENV_PY = SYGRA_ROOT / ".venv/bin/python"
RUN_JUDGE = "tasks/examples/agentic_bfcl_judge_eval/run_judge.py"

GENS = ["gpt_5_4", "llama_3_1_8b_instruct", "llama_3_3_70b_instruct", "qwen3_32b", "smollm3_3b"]
DIFFS = ["easy", "medium", "hard"]
C1_JUDGES = ["claude_large", "gpt_5_4", "gpt_oss_120b", "gpt_oss_20b", "qwq_32b", "reranker_gemini"]
C2_BASE   = ["claude_large", "gpt_5_4", "gpt_oss_120b", "gpt_oss_20b", "qwq_32b", "reranker_gemini"]


def load_jsonl(path):
    return [json.loads(l) for l in open(path) if l.strip()]


def get_all_map(gen, diff, src=None):
    p = src or (DIR / gen / f"{diff}.jsonl")
    return {r["id"]: r for r in load_jsonl(p)}


def collect_good_ids(gen, jdir, diff, c3=False):
    base = DIR / gen / f"judged_by_{jdir}"
    if not base.exists():
        return set()
    if c3:
        files = list(base.glob(f"c3_corrupted_gt_{jdir}_{gen}_{diff}_output_*.json"))
    else:
        files = [f for f in base.glob(f"*_{diff}_output_*.json")
                 if "c3" not in f.name and "resume" not in f.name]
        files += list(base.glob(f"nullrerun_*_{diff}_output_*.json"))
        files += list(base.glob(f"resume_*_{diff}_output_*.json"))
    good = set()
    for f in files:
        try:
            for r in json.load(open(f)):
                if r.get("id") and r.get("overall_llm_alignment_percentage") is not None:
                    good.add(r["id"])
        except Exception:
            pass
    return good


# --- Build list of incomplete cells ---
cells = []

# C1
for gen in GENS:
    for judge in C1_JUDGES:
        for diff in DIFFS:
            all_map = get_all_map(gen, diff)
            good = collect_good_ids(gen, judge, diff)
            missing = set(all_map) - good
            if missing:
                cells.append(dict(
                    cond="C1", gen=gen, judge=judge, diff=diff,
                    missing=missing, all_map=all_map,
                    config="graph_config.yaml",
                    src_jsonl=str(DIR / gen / f"{diff}.jsonl"),
                ))

# C2
for gen in GENS:
    for jb in C2_BASE:
        jm = f"{jb}_nogt_05"
        for diff in DIFFS:
            all_map = get_all_map(gen, diff)
            good = collect_good_ids(gen, jm, diff)
            missing = set(all_map) - good
            if missing:
                cells.append(dict(
                    cond="C2", gen=gen, judge=jm, diff=diff,
                    missing=missing, all_map=all_map,
                    config="graph_config_nogt_05.yaml",
                    src_jsonl=str(DIR / gen / f"{diff}.jsonl"),
                ))

# C3
for judge in ["reranker_gemini", "qwq_32b"]:
    gen = "llama_3_3_70b_instruct"
    for diff in DIFFS:
        src = DIR / gen / f"{diff}_corrupted_gt.jsonl"
        all_map = get_all_map(gen, diff, src=src)
        good = collect_good_ids(gen, judge, diff, c3=True)
        missing = set(all_map) - good
        if missing:
            cells.append(dict(
                cond="C3", gen=gen, judge=judge, diff=diff,
                missing=missing, all_map=all_map,
                config="graph_config_corrupted_gt.yaml",
                src_jsonl=str(src),
            ))

print(f"Total incomplete cells: {len(cells)}")
for c in cells:
    print(f"  {c['cond']} | {c['gen'][:28]:28s} | {c['judge'][:28]:28s} | {c['diff']:6s} | missing={len(c['missing'])}")

# --- Write subset JSONLs ---
rerun_dir = DIR / "rerun_inputs_v2"
rerun_dir.mkdir(exist_ok=True)

for cell in cells:
    fname = f"{cell['cond']}_{cell['gen']}_{cell['judge']}_{cell['diff']}_missing.jsonl"
    out_path = rerun_dir / fname
    with open(out_path, "w") as f:
        for rid in sorted(cell["missing"]):
            if rid in cell["all_map"]:
                f.write(json.dumps(cell["all_map"][rid]) + "\n")
    cell["subset_jsonl"] = str(out_path)

print(f"\nWrote {len(cells)} subset JSONLs to {rerun_dir}/")

# --- Build launch commands ---
# Group by judge to enable sequential launches per judge
from collections import defaultdict
by_judge = defaultdict(list)
for cell in cells:
    by_judge[cell["judge"]].append(cell)

log_dir = DIR / "rerun_v2_logs"
log_dir.mkdir(exist_ok=True)

launch_scripts = []
for judge, judge_cells in by_judge.items():
    script_path = log_dir / f"rerun_{judge}.sh"
    with open(script_path, "w") as f:
        f.write("#!/usr/bin/env bash\nset -u\n")
        f.write(f"cd {SYGRA_ROOT}\n")
        for cell in sorted(judge_cells, key=lambda x: (x["cond"], x["gen"], x["diff"])):
            n = len(cell["missing"])
            run_name = f"rerun_{cell['cond']}_{cell['judge']}_{cell['gen']}_{cell['diff']}"
            log = log_dir / f"{run_name}.log"
            cmd = (
                f"{VENV_PY} {RUN_JUDGE} "
                f"--generator {cell['gen']} "
                f"--judge_model {cell['judge']} "
                f"--difficulty {cell['diff']} "
                f"--config {cell['config']} "
                f"--input {cell['subset_jsonl']} "
                f"--run_name {run_name}"
                f" >> {log} 2>&1\n"
            )
            f.write(f"# {cell['cond']} {cell['gen']} {cell['diff']} missing={n}\n")
            f.write(cmd)
    os.chmod(script_path, 0o755)
    launch_scripts.append(script_path)

print(f"\nWrote {len(launch_scripts)} per-judge launch scripts:")
for s in sorted(launch_scripts):
    print(f"  {s}")

# --- Launch all scripts in parallel ---
print("\nLaunching all reruns...")
procs = []
for script in sorted(launch_scripts):
    p = subprocess.Popen(
        ["nohup", "bash", str(script)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
        cwd=str(SYGRA_ROOT),
    )
    procs.append((script.name, p.pid))
    print(f"  Launched {script.name} (PID {p.pid})")

print(f"\nAll {len(procs)} rerun scripts launched.")
print("Monitor logs in:", log_dir)
