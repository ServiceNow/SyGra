#!/usr/bin/env bash
# Live terminal dashboard for the judge sweep.
# Usage: watch_sweep.sh [refresh_seconds]  (default 30)
cd /Users/abhigya.verma/git/SyGra
DIR=tasks/examples/agentic_bfcl_judge_eval
REFRESH="${1:-30}"
TOTAL=31

render() {
  clear
  started=$(grep -c ' START ' "$DIR/sweep_progress.log" 2>/dev/null); [ -z "$started" ] && started=0
  ended=$(grep -c ' END '   "$DIR/sweep_progress.log" 2>/dev/null); [ -z "$ended" ] && ended=0
  aborted=$(grep -c ' ABORT ' "$DIR/sweep_progress.log" 2>/dev/null); [ -z "$aborted" ] && aborted=0
  workers=$(pgrep -f 'run_judge_rerun_worker\.sh [a-z]' 2>/dev/null | wc -l | tr -d ' ')
  first_ts=$(grep -m1 ' START ' "$DIR/sweep_progress.log" 2>/dev/null | awk '{print $2}' | tr -d ']')
  if [ -n "$first_ts" ]; then
    elapsed_min=$(( ($(date +%s) - $(date -j -f '%H:%M:%S' "$first_ts" +%s 2>/dev/null || echo 0)) / 60 ))
  else
    elapsed_min=0
  fi

  printf '═══ JUDGE SWEEP · %s · refresh %ss ═══\n' "$(date '+%H:%M:%S')" "$REFRESH"
  printf 'ended=%s/%s  started=%s/%s  aborted=%s  workers=%s  elapsed=%sm\n\n' \
    "$ended" "$TOTAL" "$started" "$TOTAL" "$aborted" "$workers" "$elapsed_min"

  printf '%-18s %-5s %-52s %6s %-12s %s\n' 'JUDGE' 'CELL' 'ACTIVE_TAG' 'PCT' 'RECORDS' 'RATE'
  printf '%s\n' '─────────────────────────────────────────────────────────────────────────────────────────────────────────────'
  for judge in gpt_5_4 claude_large reranker_gemini qwq_32b gpt_oss_20b; do
    cells_total=$(wc -l < "$DIR/rerun_lists/${judge}.txt" 2>/dev/null | tr -d ' ')
    cells_done=$(grep -cE " END .*_${judge}_" "$DIR/sweep_progress.log" 2>/dev/null)
    alive=$(pgrep -f "run_judge_rerun_worker\.sh ${judge} " > /dev/null && echo yes || echo no)
    if [ "$alive" = "no" ]; then
      if [ "$cells_done" = "$cells_total" ] && [ "$cells_done" != "0" ]; then
        printf '%-18s %s/%-3s %-52s %6s %-12s %s\n' "$judge" "$cells_done" "$cells_total" 'DONE' '-' '-' '-'
      else
        printf '%-18s %s/%-3s %-52s %6s %-12s %s\n' "$judge" "$cells_done" "$cells_total" 'STOPPED/NOT STARTED' '-' '-' '-'
      fi
      continue
    fi
    active=$(grep " START .*_${judge}_" "$DIR/sweep_progress.log" | tail -1 | awk '{print $NF}')
    log="$DIR/run_judge_${active}.log"
    pct=$(grep -oE '[0-9]+%\|' "$log" 2>/dev/null | tail -1 | tr -d '%|')
    records=$(grep -oE '[0-9]+/[0-9]+ \[' "$log" 2>/dev/null | tail -1 | tr -d ' [')
    rate=$(grep -oE '[0-9.]+it/s' "$log" 2>/dev/null | tail -1)
    printf '%-18s %s/%-3s %-52s %5s%% %-12s %s\n' \
      "$judge" "$((cells_done+1))" "$cells_total" "$active" "${pct:-?}" "${records:-?}" "${rate:-?}"
  done

  printf '\n── RECENT END EVENTS ──────────────────────────────────────────\n'
  grep ' END ' "$DIR/sweep_progress.log" | tail -6

  printf '\n(Ctrl-C to quit)\n'
}

while true; do
  render
  sleep "$REFRESH"
done
