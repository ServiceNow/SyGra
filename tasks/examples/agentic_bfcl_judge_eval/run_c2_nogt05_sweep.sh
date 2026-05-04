#!/usr/bin/env bash
# C2: 0.5-default no-GT ablation sweep
# 4 generators × 6 judges × 3 difficulties = 72 runs (6 workers in parallel)
set -u
cd /Users/abhigya.verma/git/SyGra
DIR=tasks/examples/agentic_bfcl_judge_eval
WORKER="$DIR/run_judge_rerun_worker.sh"
CELLS="$DIR/rerun_lists/r2_nogt05_gpt54.txt"
CONFIG="graph_config_nogt_05.yaml"
MASTER="$DIR/sweep_progress.log"

log() { printf '[%s] %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*" | tee -a "$MASTER"; }

log "=== C2 nogt-05 sweep START (72 cells, 6 parallel workers) ==="

bash "$WORKER" gpt_5_4_nogt_05         "$CELLS" "$CONFIG" &
PID1=$!; log "gpt_5_4_nogt_05 launched (pid=$PID1)"

bash "$WORKER" claude_large_nogt_05    "$CELLS" "$CONFIG" &
PID2=$!; log "claude_large_nogt_05 launched (pid=$PID2)"

bash "$WORKER" reranker_gemini_nogt_05 "$CELLS" "$CONFIG" &
PID3=$!; log "reranker_gemini_nogt_05 launched (pid=$PID3)"

bash "$WORKER" qwq_32b_nogt_05         "$CELLS" "$CONFIG" &
PID4=$!; log "qwq_32b_nogt_05 launched (pid=$PID4)"

bash "$WORKER" gpt_oss_20b_nogt_05     "$CELLS" "$CONFIG" &
PID5=$!; log "gpt_oss_20b_nogt_05 launched (pid=$PID5)"

bash "$WORKER" gpt_oss_120b_nogt_05    "$CELLS" "$CONFIG" &
PID6=$!; log "gpt_oss_120b_nogt_05 launched (pid=$PID6)"

log "All 6 workers launched. Waiting for completion..."

wait $PID1; log "gpt_5_4_nogt_05 done"
wait $PID2; log "claude_large_nogt_05 done"
wait $PID3; log "reranker_gemini_nogt_05 done"
wait $PID4; log "qwq_32b_nogt_05 done"
wait $PID5; log "gpt_oss_20b_nogt_05 done"
wait $PID6; log "gpt_oss_120b_nogt_05 done"

log "=== C2 nogt-05 sweep COMPLETE ==="
