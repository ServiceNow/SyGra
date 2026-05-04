#!/usr/bin/env bash
# C1: Judge sweep for GPT-5.4 generator outputs
# 1 generator × 6 judges × 3 difficulties = 18 runs (6 parallel workers)
set -u
cd /Users/abhigya.verma/git/SyGra
DIR=tasks/examples/agentic_bfcl_judge_eval
WORKER="$DIR/run_judge_rerun_worker.sh"
CELLS="$DIR/rerun_lists/c1_gpt54_generator.txt"
CONFIG="graph_config.yaml"
MASTER="$DIR/sweep_progress.log"

log() { printf '[%s] %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*" | tee -a "$MASTER"; }

log "=== C1 gpt_5_4 judge sweep START (18 cells, 6 parallel workers) ==="

bash "$WORKER" gpt_5_4         "$CELLS" "$CONFIG" &
PID1=$!; log "gpt_5_4 judge launched (pid=$PID1)"

bash "$WORKER" claude_large    "$CELLS" "$CONFIG" &
PID2=$!; log "claude_large judge launched (pid=$PID2)"

bash "$WORKER" reranker_gemini "$CELLS" "$CONFIG" &
PID3=$!; log "reranker_gemini judge launched (pid=$PID3)"

bash "$WORKER" qwq_32b         "$CELLS" "$CONFIG" &
PID4=$!; log "qwq_32b judge launched (pid=$PID4)"

bash "$WORKER" gpt_oss_20b     "$CELLS" "$CONFIG" &
PID5=$!; log "gpt_oss_20b judge launched (pid=$PID5)"

bash "$WORKER" gpt_oss_120b    "$CELLS" "$CONFIG" &
PID6=$!; log "gpt_oss_120b judge launched (pid=$PID6)"

log "All 6 workers launched. Waiting..."

wait $PID1; log "gpt_5_4 judge done"
wait $PID2; log "claude_large judge done"
wait $PID3; log "reranker_gemini judge done"
wait $PID4; log "qwq_32b judge done"
wait $PID5; log "gpt_oss_20b judge done"
wait $PID6; log "gpt_oss_120b judge done"

log "=== C1 gpt_5_4 judge sweep COMPLETE ==="
