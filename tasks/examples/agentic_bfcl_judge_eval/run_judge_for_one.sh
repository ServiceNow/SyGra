#!/usr/bin/env bash
# Worker: runs all (generator × difficulty) cells for ONE judge, serially.
# Args: $1 = judge name
set -u
cd /Users/abhigya.verma/git/SyGra
PY=.venv/bin/python
DIR=tasks/examples/agentic_bfcl_judge_eval
MASTER="$DIR/sweep_progress.log"
JUDGE="$1"
GENS=(llama_3_1_8b_instruct qwen3_32b smollm3_3b)
DIFFS=(easy medium hard)

for gen in "${GENS[@]}"; do
  for diff in "${DIFFS[@]}"; do
    tag="${gen}_${JUDGE}_${diff}"
    log="$DIR/run_judge_${tag}.log"
    printf '[%s] START %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$tag" >> "$MASTER"
    t0=$(date +%s)
    "$PY" "$DIR/run_judge.py" --generator "$gen" --judge_model "$JUDGE" --difficulty "$diff" > "$log" 2>&1
    rc=$?
    dur=$(( $(date +%s) - t0 ))
    printf '[%s] END   %s rc=%d dur=%ds\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$tag" "$rc" "$dur" >> "$MASTER"
  done
done
printf '[%s] JUDGE_DONE %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$JUDGE" >> "$MASTER"
