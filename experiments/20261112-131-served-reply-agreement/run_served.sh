#!/usr/bin/env bash
# The registered forward (PREREG.md). Run via the bigmem lock and fp-heavy.sh. Cores 0-5.
# Usage: run_served.sh <scratch>
# Logs the slot grant first; hard stop = grant + 100 min, never later than 2026-11-12T18:10Z; watchdog kills by pid.
set -uo pipefail
cd "$(dirname "$0")"
X="$1"; R=runs; mkdir -p "$X" "$R"
now() { date -u +%FT%TZ; }
echo "slot granted $(now)" >> "$R/progress.log"
first=$(grep -m1 '^slot granted' "$R/progress.log" | awk '{print $3}')
HS=$(( $(date -u -d "$first" +%s) + 100 * 60 ))
CAP=$(date -u -d "2026-11-12T18:10:00Z" +%s)
if [ "$HS" -gt "$CAP" ]; then HS=$CAP; fi
echo "hard stop $(date -u -d @$HS +%FT%TZ) (first grant $first)" >> "$R/progress.log"
OMP_NUM_THREADS=6 OPENBLAS_NUM_THREADS=6 MKL_NUM_THREADS=6 /usr/bin/time -v taskset -c 0-5 python3 served_e2e.py run "$X" "$R" "$R/served-ids.json" >> "$R/run.log" 2>> "$X/run.time" &
pid=$!
( while kill -0 "$pid" 2>/dev/null; do
    if [ "$(date -u +%s)" -ge "$HS" ]; then echo "HARD STOP kill $pid $(now)" >> "$R/progress.log"; kill "$pid"; fi
    sleep 20; done ) &
w=$!
wait "$pid"; rc=$?
kill "$w" 2>/dev/null
echo "end rc=$rc $(now)" >> "$R/progress.log"
exit $rc
