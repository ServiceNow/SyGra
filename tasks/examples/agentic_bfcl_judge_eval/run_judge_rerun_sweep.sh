#!/usr/bin/env bash
set -u
cd /Users/abhigya.verma/git/SyGra
DIR=tasks/examples/agentic_bfcl_judge_eval
MASTER="$DIR/sweep_progress.log"
WORKER="$DIR/run_judge_rerun_worker.sh"
LISTS="$DIR/rerun_lists"

WAVE1=(gpt_5_4 claude_large reranker_gemini)   # share llmproxy
WAVE2=(qwq_32b gpt_oss_20b)                     # separate vLLM hosts

: > "$MASTER"
{
  echo "=== rerun sweep started $(date) ==="
  echo "wave 1 (llmproxy, 3 parallel): ${WAVE1[*]}"
  echo "wave 2 (vLLM,    2 parallel): ${WAVE2[*]}"
  total=0
  for j in "${WAVE1[@]}" "${WAVE2[@]}"; do
    n=$(wc -l < "$LISTS/$j.txt" | tr -d ' ')
    echo "  $j: $n cells"
    total=$((total + n))
  done
  echo "total cells: $total"
  echo "duration guard: abort worker if any cell ends < 120s"
  echo
} >> "$MASTER"

run_wave() {
  local name=$1; shift
  local judges=("$@")
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] WAVE_START $name (${judges[*]})" >> "$MASTER"
  local pids=()
  for j in "${judges[@]}"; do
    "$WORKER" "$j" "$LISTS/$j.txt" &
    pids+=($!)
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] JUDGE_LAUNCH $j pid=$!" >> "$MASTER"
  done
  wait "${pids[@]}"
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] WAVE_END $name" >> "$MASTER"
}

run_wave "wave1" "${WAVE1[@]}"
run_wave "wave2" "${WAVE2[@]}"

echo "=== rerun sweep finished $(date) ===" >> "$MASTER"
