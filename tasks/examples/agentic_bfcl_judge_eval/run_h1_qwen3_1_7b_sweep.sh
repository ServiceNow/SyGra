#!/usr/bin/env bash
# H1: complete qwen3_1_7b full factorial — 9 missing cells
# generators: llama_3_1_8b_instruct, qwen3_32b, smollm3_3b x {easy,medium,hard}
set -u
cd /Users/abhigya.verma/git/SyGra
PY=.venv/bin/python
DIR=tasks/examples/agentic_bfcl_judge_eval
LOG_DIR="$DIR/rerun_v2_logs"
mkdir -p "$LOG_DIR"

GENS=(llama_3_1_8b_instruct qwen3_32b smollm3_3b)
DIFFS=(easy medium hard)

for gen in "${GENS[@]}"; do
  for diff in "${DIFFS[@]}"; do
    tag="H1_qwen3_1_7b_${gen}_${diff}"
    log="$LOG_DIR/${tag}.log"
    echo "[$(date '+%H:%M:%S')] Launching $tag"
    "$PY" "$DIR/run_judge.py" --generator "$gen" --judge_model qwen3_1_7b --difficulty "$diff" > "$log" 2>&1 &
  done
done

echo "All 9 cells launched in background. PIDs:"
jobs -l
wait
echo "[$(date '+%H:%M:%S')] All done."
