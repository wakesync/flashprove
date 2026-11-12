#!/usr/bin/env bash
# The registered run (PREREG.md). Run as:
#   flock <planning>/locks/bigmem.lock <planning>/fp-heavy.sh taskset -c 6-11 bash run_mlp.sh <scratch>
# Logs the slot grant first, picks the prompt set from the FIRST grant time (full if granted at or before
# 2026-11-12T17:25Z, else reduced), refuses to start under 10 GB MemAvailable, and kills the job by pid at the
# registered compute hard stop 2026-11-12T18:25Z. A rerun after a lost session resumes from <scratch>/ckpt.npz.
set -uo pipefail
cd "$(dirname "$0")"
X="$1"; R=runs; mkdir -p "$X" "$R"
now() { date -u +%FT%TZ; }
echo "slot granted $(now)" >> "$R/progress.log"
first=$(grep -m1 '^slot granted' "$R/progress.log" | awk '{print $3}')
CUT=$(date -u -d "2026-11-12T17:25:00Z" +%s)
HS=$(date -u -d "2026-11-12T18:25:00Z" +%s)
if [ "$(date -u -d "$first" +%s)" -le "$CUT" ]; then SET=full; else SET=reduced; fi
avail=$(awk '/MemAvailable/ {print $2}' /proc/meminfo)
echo "prompt set $SET (first grant $first); hard stop 2026-11-12T18:25:00Z; MemAvailable ${avail} kB" >> "$R/progress.log"
if [ "$avail" -lt 10485760 ]; then echo "REFUSED: MemAvailable under 10 GB $(now)" >> "$R/progress.log"; exit 3; fi
OMP_NUM_THREADS=6 OPENBLAS_NUM_THREADS=6 MKL_NUM_THREADS=6 /usr/bin/time -v python3 mlp_e2e.py run "$X" "$R" "$SET" >> "$R/run.log" 2>> "$R/run.time" &
pid=$!
( while kill -0 "$pid" 2>/dev/null; do
    if [ "$(date -u +%s)" -ge "$HS" ]; then
      kids=$(pgrep -P "$pid" | tr '\n' ' ')
      echo "HARD STOP kill $pid and its children $kids $(now)" >> "$R/progress.log"
      kill $kids "$pid"
    fi
    sleep 20; done ) &
w=$!
wait "$pid"; rc=$?
kill "$w" 2>/dev/null
echo "end rc=$rc $(now)" >> "$R/progress.log"
exit $rc
