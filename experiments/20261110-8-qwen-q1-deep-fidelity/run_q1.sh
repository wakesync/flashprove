#!/usr/bin/env bash
# The registered run (PREREG.md), one heavy slot. Run via fp-heavy.sh. Cores 0-5.
# Stages: A stock forward 0..20 (+E paths), B abl 17..20, C arms on T16, T20s, T20a, D stock end to end, E abl end to end.
# Stop rule: grant time logged first; no new stage (and no new arm group inside C) after grant + 75 min; compute hard
# stop 23:00Z (a watchdog kills the running stage by pid). Stages not started are logged.
# Usage: run_q1.sh <scratch>
set -uo pipefail
cd "$(dirname "$0")"
X="$1"; R=runs; mkdir -p "$X" "$R"
prog() { echo "$1 $(date -u +%FT%TZ)" >> "$R/run.progress"; }
prog "slot granted"
DL=$(date -u -d "+75 minutes" +%H%M); HARD=2300
if [ "$DL" \> "$HARD" ]; then DL=$HARD; fi
prog "stage cut-off ${DL}Z, hard stop ${HARD}Z"
late() { [ "$(date -u +%H%M)" \> "$DL" ] || [ "$(date -u +%H%M)" = "$DL" ]; }
stage() {  # stage <name> <cmd...>
  local n="$1"; shift
  if late; then prog "NOT STARTED $n (cut-off)"; return 1; fi
  prog "start $n"
  "$@" &
  local pid=$!
  ( while kill -0 "$pid" 2>/dev/null; do
      if [ "$(date -u +%H%M)" \> "$HARD" ] || [ "$(date -u +%H%M)" = "$HARD" ]; then echo "HARD STOP kill $pid $(date -u +%FT%TZ)" >> "$R/run.progress"; kill "$pid"; fi
      sleep 20; done ) &
  local w=$!
  wait "$pid"; local rc=$?
  kill "$w" 2>/dev/null
  prog "end $n rc=$rc"
  return $rc
}
F64() { OMP_NUM_THREADS=6 OPENBLAS_NUM_THREADS=6 MKL_NUM_THREADS=6 /usr/bin/time -v taskset -c 0-5 python3 q1_forward.py "$@"; }
ARM() { OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 /usr/bin/time -v taskset -c 0-5 python3 q1_arms.py "$@"; }
stage A F64 stageA "$X" "$R" > "$R/stageA.log" 2> "$R/stageA.time" || { prog "stop after A"; exit 3; }
stage B F64 stageB "$X" "$R" > "$R/stageB.log" 2> "$R/stageB.time" || prog "B failed or not started"
stage C16 ARM "$X/prep-L16" stock-L16 "$X/Wo-stock-L16.npy" "$R/arms-T16.jsonl" "$X/fref-T16" "$DL" > "$R/arms-T16.log" 2> "$R/arms-T16.time"
stage C20s ARM "$X/prep-L20" stock-L20 "$X/Wo-stock-L20.npy" "$R/arms-T20s.jsonl" "$X/fref-T20s" "$DL" > "$R/arms-T20s.log" 2> "$R/arms-T20s.time"
stage C20a ARM "$X/prep-abl-L20" abl-L20 "$X/Wo-abl-L20.npy" "$R/arms-T20a.jsonl" "$X/fref-T20a" "$DL" > "$R/arms-T20a.log" 2> "$R/arms-T20a.time"
stage D F64 stageD "$X" "$R" > "$R/stageD.log" 2> "$R/stageD.time"
if ! grep -q '"sanity_pass": true' "$R/e2e-stock.json" 2>/dev/null; then prog "SANITY CHECK FAILED or D missing: E not run"; exit 4; fi
stage E F64 stageE "$X" "$R" > "$R/stageE.log" 2> "$R/stageE.time"
prog "run done"
