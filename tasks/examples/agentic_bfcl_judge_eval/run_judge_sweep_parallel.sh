#!/usr/bin/env bash
set -u
cd /Users/abhigya.verma/git/SyGra
DIR=tasks/examples/agentic_bfcl_judge_eval
MASTER="$DIR/sweep_progress.log"
JUDGES=(gpt_5_4 claude_large reranker_gemini qwq_32b gpt_oss_20b)

{
  echo "=== parallel sweep started $(date) ==="
  echo "judges (each runs 9 cells serially): ${JUDGES[*]}"
  echo "total runs: $(( 5 * 9 ))"
  echo "strategy: 5 judges in parallel, each serializing its own 3 generators x 3 difficulties"
  echo
} > "$MASTER"

pids=()
for judge in "${JUDGES[@]}"; do
  "$DIR/run_judge_for_one.sh" "$judge" &
  pids+=($!)
  printf '[%s] JUDGE_LAUNCH %s pid=%d\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$judge" "$!" >> "$MASTER"
done

wait "${pids[@]}"
echo "=== parallel sweep finished $(date) ===" >> "$MASTER"
