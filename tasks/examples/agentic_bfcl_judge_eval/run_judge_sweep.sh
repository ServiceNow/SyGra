#!/usr/bin/env bash
# Sweep: 3 generators × 5 judges × 3 difficulties = 45 runs, serial.
set -u
cd /Users/abhigya.verma/git/SyGra
PY=.venv/bin/python
DIR=tasks/examples/agentic_bfcl_judge_eval
MASTER="$DIR/sweep_progress.log"

GENS=(llama_3_1_8b_instruct qwen3_32b smollm3_3b)
JUDGES=(gpt_5_4 claude_large reranker_gemini qwq_32b gpt_oss_20b)
DIFFS=(easy medium hard)

{
  echo "=== sweep started $(date) ==="
  echo "generators: ${GENS[*]}"
  echo "judges:     ${JUDGES[*]}"
  echo "difficulties: ${DIFFS[*]}"
  echo "total runs: $(( ${#GENS[@]} * ${#JUDGES[@]} * ${#DIFFS[@]} ))"
  echo
} > "$MASTER"

i=0
total=$(( ${#GENS[@]} * ${#JUDGES[@]} * ${#DIFFS[@]} ))
for gen in "${GENS[@]}"; do
  for judge in "${JUDGES[@]}"; do
    for diff in "${DIFFS[@]}"; do
      i=$((i + 1))
      tag="${gen}_${judge}_${diff}"
      log="$DIR/run_judge_${tag}.log"
      printf '[%s] [%d/%d] START %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$i" "$total" "$tag" | tee -a "$MASTER"
      t0=$(date +%s)
      "$PY" "$DIR/run_judge.py" --generator "$gen" --judge_model "$judge" --difficulty "$diff" > "$log" 2>&1
      rc=$?
      dur=$(( $(date +%s) - t0 ))
      printf '[%s] [%d/%d] END   %s rc=%d dur=%ds\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$i" "$total" "$tag" "$rc" "$dur" | tee -a "$MASTER"
    done
  done
done

echo "=== sweep finished $(date) ===" | tee -a "$MASTER"
