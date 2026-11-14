#!/usr/bin/env bash
# Registered forward (PREREG "Kill criterion"). Run under:
#   flock <bigmem.lock> fp-heavy.sh taskset -c 10-15 /usr/bin/time -v bash run177.sh <scratch> <served-ids-private.json> <private_out.json>
# Logs the slot grant; waits for MemAvailable >= 12 GB but not past the registered start-by 2026-11-13T17:45:00Z;
# hard stop = grant + 70 min, never later than 2026-11-13T18:20:00Z. Watchdog polls every 5 s and kills the Python pid
# (by pid) at RSS > 14 GB, free disk < 21 GB or the hard stop. One run (deterministic float64, PREREG "Runs").
set -uo pipefail
cd "$(dirname "$0")"
S="$1"; IDS="$2"; OUT="$3"; R=runs; mkdir -p "$S" "$R"
now() { date -u +%FT%TZ; }
G=$(date -u +%s)
echo "slot granted $(now)" >> "$R/progress.log"
HS=$(( G + 70 * 60 )); CAP=$(date -u -d "2026-11-13T18:20:00Z" +%s); if [ "$HS" -gt "$CAP" ]; then HS=$CAP; fi
SB=$(date -u -d "2026-11-13T17:45:00Z" +%s)
echo "hard stop $(date -u -d @$HS +%FT%TZ)" >> "$R/progress.log"
while [ "$(awk '/MemAvailable/{print $2}' /proc/meminfo)" -lt 12582912 ]; do
  if [ "$(date -u +%s)" -ge "$SB" ]; then echo "start-by 2026-11-13T17:45:00Z reached waiting for memory, forward not started $(now)" >> "$R/progress.log"; exit 4; fi
  echo "waiting MemAvailable $(awk '/MemAvailable/{print $2}' /proc/meminfo) kB $(now)" >> "$R/progress.log"; sleep 20
done
if [ "$(date -u +%s)" -ge "$SB" ]; then echo "start-by reached, forward not started $(now)" >> "$R/progress.log"; exit 4; fi
export OMP_NUM_THREADS=6 OPENBLAS_NUM_THREADS=6 MKL_NUM_THREADS=6
echo "run start MemAvailable $(awk '/MemAvailable/{print $2}' /proc/meminfo) kB free_disk_kB $(df -k --output=avail / | tail -n 1) $(now)" >> "$R/progress.log"
python3 forward177.py run "$S" "$R" "$IDS" "$OUT" >> "$S/run.log" 2>&1 &
p=$!
( peak=0
  while kill -0 "$p" 2>/dev/null; do
    rss=$(awk '/VmRSS/{print $2}' /proc/$p/status 2>/dev/null || echo 0); rss=${rss:-0}
    if [ "$rss" -gt "$peak" ]; then peak=$rss; echo "$peak" > "$S/watchdog-peak-kB"; fi
    if [ "$rss" -gt 14680064 ]; then echo "RSS over 14 GB ($rss kB) kill $p $(now)" >> "$R/progress.log"; kill "$p"; fi
    if [ "$(date -u +%s)" -ge "$HS" ]; then echo "HARD STOP kill $p $(now)" >> "$R/progress.log"; kill "$p"; fi
    if [ "$(df -k --output=avail / | tail -n 1)" -lt 22020096 ]; then echo "DISK under 21 GB kill $p $(now)" >> "$R/progress.log"; kill "$p"; fi
    sleep 5; done ) &
w=$!
wait "$p"; rc=$?
kill "$w" 2>/dev/null
echo "run end rc=$rc watchdog_peak_rss_kB $(cat "$S/watchdog-peak-kB" 2>/dev/null) $(now)" >> "$R/progress.log"
exit $rc
