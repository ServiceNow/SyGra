#!/usr/bin/env bash
# Worker: runs a pre-computed list of (generator, difficulty) cells for ONE judge.
# Aborts if any cell ends in < 120s (silent API-error cascade protection).
# Usage: run_judge_rerun_worker.sh <judge> <cells_file> [graph_config.yaml]
set -u
cd /Users/abhigya.verma/git/SyGra
PY=.venv/bin/python
DIR=tasks/examples/agentic_bfcl_judge_eval
MASTER="$DIR/sweep_progress.log"
JUDGE="$1"
CELLS_FILE="$2"
CONFIG="${3:-graph_config.yaml}"
MIN_DUR=120

while IFS=' ' read -r gen diff; do
  [ -z "${gen:-}" ] && continue
  tag="${gen}_${JUDGE}_${diff}"
  log="$DIR/run_judge_${tag}.log"
  printf '[%s] START %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$tag" >> "$MASTER"
  t0=$(date +%s)
  "$PY" "$DIR/run_judge.py" --generator "$gen" --judge_model "$JUDGE" --difficulty "$diff" --config "$CONFIG" > "$log" 2>&1
  rc=$?
  dur=$(( $(date +%s) - t0 ))
  if [ "$dur" -lt "$MIN_DUR" ] && [ "$rc" -eq 0 ]; then
    printf '[%s] ABORT %s dur=%ds (below %ds threshold, likely silent failure)\n' \
      "$(date '+%Y-%m-%d %H:%M:%S')" "$tag" "$dur" "$MIN_DUR" >> "$MASTER"
    printf '[%s] WORKER_EXIT %s (duration guard tripped)\n' \
      "$(date '+%Y-%m-%d %H:%M:%S')" "$JUDGE" >> "$MASTER"
    exit 2
  fi
  printf '[%s] END   %s rc=%d dur=%ds\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$tag" "$rc" "$dur" >> "$MASTER"
done < "$CELLS_FILE"

printf '[%s] JUDGE_DONE %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$JUDGE" >> "$MASTER"
