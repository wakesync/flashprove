#!/usr/bin/env bash
# Registered job (PREREG.md). Run under:
#   flock <bigmem.lock> fp-heavy.sh taskset -c 10-15 /usr/bin/time -v bash run_p03.sh <scratch>
# Logs the slot grant, waits for MemAvailable >= 10 GB, then run 1 (registered) and run 2 (repeat, determinism) of
# u1_p03.py, each under a watchdog that kills by pid at the compute hard stop 2026-11-13T04:40:00Z, or if free disk
# drops under 21 GB, or MemAvailable under 2 GB.
set -uo pipefail
cd "$(dirname "$0")"
S="$1"; R=runs; mkdir -p "$S" "$R"
now() { date -u +%FT%TZ; }
HS=$(date -u -d "2026-11-13T04:40:00Z" +%s)
echo "slot granted $(now)" >> "$R/progress.log"
while [ "$(awk '/MemAvailable/{print $2}' /proc/meminfo)" -lt 10485760 ]; do
  if [ "$(date -u +%s)" -ge "$HS" ]; then echo "hard stop reached waiting for memory $(now)" >> "$R/progress.log"; exit 4; fi
  echo "waiting MemAvailable $(awk '/MemAvailable/{print $2}' /proc/meminfo) kB $(now)" >> "$R/progress.log"; sleep 20
done
export OMP_NUM_THREADS=6 OPENBLAS_NUM_THREADS=6 MKL_NUM_THREADS=6
for k in 1 2; do
  mkdir -p "$R/run$k"
  echo "run$k start MemAvailable $(awk '/MemAvailable/{print $2}' /proc/meminfo) kB free_disk_kB $(df -k --output=avail / | tail -n 1) $(now)" >> "$R/progress.log"
  /usr/bin/time -v python3 u1_p03.py run "$S/run$k" "$R/run$k" >> "$R/run$k/run.log" 2>> "$R/run$k/run.time" &
  p=$!
  ( while kill -0 "$p" 2>/dev/null; do
      if [ "$(date -u +%s)" -ge "$HS" ]; then echo "HARD STOP kill $p $(now)" >> "$R/progress.log"; kill "$p"; fi
      if [ "$(df -k --output=avail / | tail -n 1)" -lt 22020096 ]; then echo "DISK under 21 GB kill $p $(now)" >> "$R/progress.log"; kill "$p"; fi
      if [ "$(awk '/MemAvailable/{print $2}' /proc/meminfo)" -lt 2097152 ]; then echo "MemAvailable under 2 GB kill $p $(now)" >> "$R/progress.log"; kill "$p"; fi
      sleep 15; done ) &
  w=$!
  wait "$p"; rc=$?
  kill "$w" 2>/dev/null
  echo "run$k end rc=$rc $(now)" >> "$R/progress.log"
  if [ "$rc" -ne 0 ]; then exit "$rc"; fi
done
exit 0
