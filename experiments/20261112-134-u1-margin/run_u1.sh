#!/usr/bin/env bash
# Registered job (PREREG.md). Run under: flock <bigmem.lock> fp-heavy.sh taskset -c 6-11 bash run_u1.sh <scratch>
# 1. logs the slot grant, 2. waits for MemAvailable >= 10 GB, 3. fixture (debug, aborts on failure),
# 4. registered run; if the grant is after 2026-11-12T18:05Z, starts from <X16> (PREREG fallback),
# all under a watchdog that kills by pid at the compute hard stop 2026-11-12T18:50:00Z.
# Usage: run_u1.sh <scratch> [<x16.npz for fallback>]
set -uo pipefail
cd "$(dirname "$0")"
S="$1"; X16="${2:-}"; R=runs; mkdir -p "$S" "$R"
now() { date -u +%FT%TZ; }
HS=$(date -u -d "2026-11-12T18:50:00Z" +%s)
FB=$(date -u -d "2026-11-12T18:05:00Z" +%s)
echo "slot granted $(now)" >> "$R/progress.log"
while [ "$(awk '/MemAvailable/{print $2}' /proc/meminfo)" -lt 10485760 ]; do
  if [ "$(date -u +%s)" -ge "$HS" ]; then echo "hard stop reached waiting for memory $(now)" >> "$R/progress.log"; exit 4; fi
  echo "waiting MemAvailable $(awk '/MemAvailable/{print $2}' /proc/meminfo) kB $(now)" >> "$R/progress.log"; sleep 30
done
echo "MemAvailable ok $(awk '/MemAvailable/{print $2}' /proc/meminfo) kB $(now)" >> "$R/progress.log"
export OMP_NUM_THREADS=6 OPENBLAS_NUM_THREADS=6 MKL_NUM_THREADS=6
watch() { # $1 pid
  while kill -0 "$1" 2>/dev/null; do
    if [ "$(date -u +%s)" -ge "$HS" ]; then echo "HARD STOP kill $1 $(now)" >> "$R/progress.log"; kill "$1"; fi
    sleep 20; done; }
python3 u1_margin.py fixture "$S/fixture" "$S/fixture.json" > "$S/fixture.log" 2>&1 &
p=$!; watch "$p" & w=$!; wait "$p"; rc=$?; kill "$w" 2>/dev/null
echo "fixture rc=$rc $(now)" >> "$R/progress.log"
if [ "$rc" -ne 0 ]; then exit 3; fi
ARG=""
if [ "$(date -u +%s)" -ge "$FB" ] && [ -n "$X16" ]; then ARG="$X16"; echo "fallback: start from external x16 $(now)" >> "$R/progress.log"; fi
echo "registered run start $(now)" >> "$R/progress.log"
/usr/bin/time -v python3 u1_margin.py run "$S/run" "$R" $ARG >> "$R/run.log" 2>> "$R/run.time" &
p=$!; watch "$p" & w=$!; wait "$p"; rc=$?; kill "$w" 2>/dev/null
echo "end rc=$rc $(now)" >> "$R/progress.log"
exit $rc
