#!/usr/bin/env bash
# Master ablation launcher — runs all ablation workers in parallel (background).
# A1: temperature sweep (t0 baseline already done; run t0.3, t0.7, t1.0)
# A3: judge size — qwen3_1_7b
# A5: prompt format — qwen3_32b with free-form graph config
# E6: reasoning on vs off — qwq_32b_no_thinking (qwq_32b thinking=on already done)
set -u
cd /Users/abhigya.verma/git/SyGra
DIR=tasks/examples/agentic_bfcl_judge_eval
WORKER="$DIR/run_judge_rerun_worker.sh"
LISTS="$DIR/rerun_lists"
MASTER="$DIR/sweep_progress.log"

log() { printf '[%s] %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*" | tee -a "$MASTER"; }

log "=== ABLATIONS START ==="
log "A1: qwen3_32b @ t=0.3, 0.7, 1.0  |  A3: qwen3_1_7b  |  A5: qwen3_32b_freeform  |  E6: qwq_32b_no_thinking"

# A1 — temperature ablation (3 workers, one per temp level)
bash "$WORKER" qwen3_32b_t0.3 "$LISTS/ablation_a1_t0.3.txt" &
PID_A1_03=$!
log "A1_t0.3 launched (pid=$PID_A1_03)"

bash "$WORKER" qwen3_32b_t0.7 "$LISTS/ablation_a1_t0.7.txt" &
PID_A1_07=$!
log "A1_t0.7 launched (pid=$PID_A1_07)"

bash "$WORKER" qwen3_32b_t1.0 "$LISTS/ablation_a1_t1.0.txt" &
PID_A1_10=$!
log "A1_t1.0 launched (pid=$PID_A1_10)"

# A3 — size ablation (qwen3_1_7b judge)
bash "$WORKER" qwen3_1_7b "$LISTS/ablation_a3_qwen3_1_7b.txt" &
PID_A3=$!
log "A3_qwen3_1_7b launched (pid=$PID_A3)"

# A5 — prompt format ablation (free-form graph config)
bash "$WORKER" qwen3_32b_freeform "$LISTS/ablation_a5_freeform.txt" graph_config_freeform.yaml &
PID_A5=$!
log "A5_freeform launched (pid=$PID_A5)"

# E6 — reasoning: thinking off (12 cells, same GPU as qwq_32b thinking=on)
bash "$WORKER" qwq_32b_no_thinking "$LISTS/ablation_e6_no_thinking.txt" &
PID_E6=$!
log "E6_qwq_no_thinking launched (pid=$PID_E6)"

log "All 6 workers launched. Waiting..."

wait $PID_A1_03; log "A1_t0.3 done"
wait $PID_A1_07; log "A1_t0.7 done"
wait $PID_A1_10; log "A1_t1.0 done"
wait $PID_A3;    log "A3_qwen3_1_7b done"
wait $PID_A5;    log "A5_freeform done"
wait $PID_E6;    log "E6_qwq_no_thinking done"

log "=== ABLATIONS COMPLETE ==="
