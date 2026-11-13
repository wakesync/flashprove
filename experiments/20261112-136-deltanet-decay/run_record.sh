#!/usr/bin/env bash
# Registered forward (PREREG "Kill criterion"): run inside the heavy gate; hard stop 2026-11-12T23:05:00Z.
# usage: run_record.sh <scratch> <S10|S7>    (from this directory; writes runs/)
set -u
SC="$1"; SET="$2"
HERE="$(cd "$(dirname "$0")" && pwd)"
mkdir -p "$HERE/runs"
STOP=$(date -u -d 2026-11-12T23:05:00Z +%s)
LEFT=$(( STOP - $(date -u +%s) ))
MEM=$(awk '/MemAvailable/ {print int($2/1048576)}' /proc/meminfo)
echo "{\"t\": \"$(date -u +%FT%TZ)\", \"slot_granted\": true, \"set\": \"$SET\", \"seconds_to_stop\": $LEFT, \"mem_available_gb\": $MEM}" >> "$HERE/runs/progress.log.jsonl"
if [ "$MEM" -lt 10 ]; then echo "MemAvailable ${MEM} GB < 10, not starting" >&2; exit 3; fi
if [ "$LEFT" -le 60 ]; then echo "past stop" >&2; exit 4; fi
cd "$HERE"
OPENBLAS_NUM_THREADS=6 OMP_NUM_THREADS=6 MKL_NUM_THREADS=6 /usr/bin/time -v -o runs/run.time \
  timeout --signal=TERM "$LEFT" python3 record.py run "$SC" runs "$SET"
RC=$?
echo "{\"t\": \"$(date -u +%FT%TZ)\", \"end_rc\": $RC}" >> "$HERE/runs/progress.log.jsonl"
exit $RC
