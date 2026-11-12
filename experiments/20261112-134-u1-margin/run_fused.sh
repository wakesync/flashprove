#!/usr/bin/env bash
# Registered job (PREREG.md Amendment A-1). Run under:
#   flock <bigmem.lock> fp-heavy.sh taskset -c 6-11 bash run_fused.sh <scratch> <x16.npz>
# Logs the slot grant, picks the prompt tier from the grant time (A-1), waits for MemAvailable >= 10 GB,
# runs u1_fused.py under a watchdog that kills by pid at the compute hard stop 2026-11-12T18:50:00Z.
set -uo pipefail
cd "$(dirname "$0")"
S="$1"; X16="$2"; R=runs; mkdir -p "$S" "$R"
now() { date -u +%FT%TZ; }
HS=$(date -u -d "2026-11-12T18:50:00Z" +%s)
G=$(date -u +%s)
echo "slot granted $(now)" >> "$R/progress.log"
FULL="p01-ordinary-short,p07-chat-ordinary,p08-chat-refusal,p09-multilingual,p02-ordinary-paragraph,p04-repeat-punct,p05-code,p03-repeat-word,p06a-digits-256,p11-chat-long"
T2="p01-ordinary-short,p07-chat-ordinary,p08-chat-refusal,p09-multilingual,p02-ordinary-paragraph,p04-repeat-punct,p05-code,p06a-digits-256,p11-chat-long"
T3="p01-ordinary-short,p07-chat-ordinary,p08-chat-refusal,p09-multilingual,p06a-digits-256,p11-chat-long"
if   [ "$G" -le "$(date -u -d 2026-11-12T18:15:00Z +%s)" ]; then IDS="$FULL"; TIER=1
elif [ "$G" -le "$(date -u -d 2026-11-12T18:28:00Z +%s)" ]; then IDS="$T2"; TIER=2
elif [ "$G" -le "$(date -u -d 2026-11-12T18:35:00Z +%s)" ]; then IDS="$T3"; TIER=3
else echo "grant after 18:35Z: not run (A-1) $(now)" >> "$R/progress.log"; exit 5; fi
echo "tier $TIER prompts $IDS" >> "$R/progress.log"
while [ "$(awk '/MemAvailable/{print $2}' /proc/meminfo)" -lt 10485760 ]; do
  if [ "$(date -u +%s)" -ge "$HS" ]; then echo "hard stop reached waiting for memory $(now)" >> "$R/progress.log"; exit 4; fi
  echo "waiting MemAvailable $(awk '/MemAvailable/{print $2}' /proc/meminfo) kB $(now)" >> "$R/progress.log"; sleep 20
done
echo "MemAvailable ok $(awk '/MemAvailable/{print $2}' /proc/meminfo) kB; registered run start $(now)" >> "$R/progress.log"
export OMP_NUM_THREADS=6 OPENBLAS_NUM_THREADS=6 MKL_NUM_THREADS=6
/usr/bin/time -v python3 u1_fused.py run "$S/run" "$R" "$X16" "$IDS" >> "$R/run.log" 2>> "$R/run.time" &
p=$!
( while kill -0 "$p" 2>/dev/null; do
    if [ "$(date -u +%s)" -ge "$HS" ]; then echo "HARD STOP kill $p $(now)" >> "$R/progress.log"; kill "$p"; fi
    sleep 15; done ) &
w=$!
wait "$p"; rc=$?
kill "$w" 2>/dev/null
echo "end rc=$rc $(now)" >> "$R/progress.log"
exit $rc
