#!/usr/bin/env python3
"""
Prepare corrupted-GT JSONL files for C3 ablation.

For each record, replaces expected_responses with the GT from a DIFFERENT
record of the SAME dag_type (random permutation within group, no self-match).
The true GT is preserved in true_expected_responses so the programmatic judge
can still compute correct alignment scores.

Usage:
    python prepare_corrupted_gt.py                          # all 3 diffs for llama_3_3_70b_instruct
    python prepare_corrupted_gt.py --generator gpt_5_4     # different generator
    python prepare_corrupted_gt.py --seed 42                # reproducible shuffle
"""

import argparse
import json
import random
from collections import defaultdict
from pathlib import Path

DIR = Path(__file__).parent


def corrupt_jsonl(generator: str, diff: str, seed: int) -> Path:
    src = DIR / generator / f"{diff}.jsonl"
    dst = DIR / generator / f"{diff}_corrupted_gt.jsonl"

    records = []
    with open(src) as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))

    # group indices by dag_type
    by_type: dict[str, list[int]] = defaultdict(list)
    for i, rec in enumerate(records):
        by_type[rec["dag_type"]].append(i)

    rng = random.Random(seed)

    # for each dag_type group, build a derangement (no record maps to itself)
    swap_target = [None] * len(records)
    for dag_type, indices in by_type.items():
        if len(indices) == 1:
            # can't swap a singleton — use itself (unavoidable)
            swap_target[indices[0]] = indices[0]
            continue
        shuffled = indices[:]
        # keep shuffling until it's a valid derangement
        for _ in range(1000):
            rng.shuffle(shuffled)
            if all(shuffled[i] != indices[i] for i in range(len(indices))):
                break
        for orig_idx, corrupt_src_idx in zip(indices, shuffled):
            swap_target[orig_idx] = corrupt_src_idx

    corrupted = []
    for i, rec in enumerate(records):
        src_idx = swap_target[i]
        new_rec = dict(rec)
        new_rec["true_expected_responses"] = rec["expected_responses"]
        new_rec["corrupted_expected_responses"] = records[src_idx]["expected_responses"]
        corrupted.append(new_rec)

    with open(dst, "w") as f:
        for rec in corrupted:
            f.write(json.dumps(rec) + "\n")

    singletons = sum(1 for dag_type, idx in by_type.items() if len(idx) == 1)
    print(f"  {generator}/{diff}: {len(corrupted)} records → {dst.name}"
          f"  ({singletons} singleton dag_types used self-swap)")
    return dst


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--generator", default="llama_3_3_70b_instruct")
    parser.add_argument("--difficulties", nargs="+", default=["easy", "medium", "hard"])
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args()

    print(f"Preparing corrupted-GT JSONLs for {args.generator} ...")
    for diff in args.difficulties:
        corrupt_jsonl(args.generator, diff, args.seed)
    print("Done.")
