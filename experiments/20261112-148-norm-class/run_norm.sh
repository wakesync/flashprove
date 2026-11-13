#!/usr/bin/env bash
# The registered run (PREREG.md). Run through the shared heavy slot, pinned to 6 cores:
#   flock <planning>/locks/bigmem.lock <planning>/fp-heavy.sh taskset -c 6-11 bash run_norm.sh <scratch> <full|r33>
# Logs the slot grant first, refuses to start under 10 GB MemAvailable, and kills the job by pid at the earlier of
# (first grant + 80 min) and the registered compute hard stop 2026-11-13T00:05:00Z. A rerun after a lost session
# resumes from <scratch>/ckpt.npz and keeps the FIRST grant time and the first run's layer set.
set -uo pipefail
cd "$(dirname "$0")"
X="$1"; SET="$2"; R=runs; mkdir -p "$X" "$R"
now() { date -u +%FT%TZ; }
echo "slot granted $(now) set=$SET" >> "$R/progress.log"
first=$(grep -m1 '^slot granted' "$R/progress.log" | awk '{print $3}')
HS=$(date -u -d "2026-11-13T00:05:00Z" +%s)
B=$(( $(date -u -d "$first" +%s) + 4800 ))
if [ "$B" -lt "$HS" ]; then STOP=$B; else STOP=$HS; fi
avail=$(awk '/MemAvailable/ {print $2}' /proc/meminfo)
echo "first grant $first; stop at $(date -u -d "@$STOP" +%FT%TZ) (min of grant + 80 min and 2026-11-13T00:05:00Z); MemAvailable ${avail} kB" >> "$R/progress.log"
if [ "$avail" -lt 10485760 ]; then echo "REFUSED: MemAvailable under 10 GB $(now)" >> "$R/progress.log"; exit 3; fi
freeb=$(df -B1 --output=avail "$X" | tail -1 | tr -d ' ')
echo "free disk ${freeb} bytes" >> "$R/progress.log"
if [ "$freeb" -lt 21000000000 ]; then echo "REFUSED: free disk under 21 GB (decimal) $(now)" >> "$R/progress.log"; exit 4; fi
OMP_NUM_THREADS=6 OPENBLAS_NUM_THREADS=6 MKL_NUM_THREADS=6 /usr/bin/time -v python3 norm_class.py run "$X" "$R" "$SET" >> "$R/run.log" 2>> "$R/run.time" &
pid=$!
( while kill -0 "$pid" 2>/dev/null; do
    if [ "$(date -u +%s)" -ge "$STOP" ]; then
      kids=$(pgrep -P "$pid" | tr '\n' ' ')
      gkids=""; for k in $kids; do gkids="$gkids $(pgrep -P "$k" | tr '\n' ' ')"; done
      echo "HARD STOP kill $pid, children $kids, grandchildren $gkids $(now)" >> "$R/progress.log"
      kill $gkids $kids "$pid" 2>/dev/null
    fi
    sleep 15; done ) &
w=$!
wait "$pid"; rc=$?
kill "$w" 2>/dev/null
echo "end rc=$rc $(now)" >> "$R/progress.log"
exit $rc
