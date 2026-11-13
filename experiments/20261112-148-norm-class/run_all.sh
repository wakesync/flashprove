#!/usr/bin/env bash
# PREREG Amendment A-1: the remaining fixture debug and the registered run as ONE job under one heavy-slot grant.
#   flock <planning>/locks/bigmem.lock <planning>/fp-heavy.sh taskset -c 6-11 bash run_all.sh <scratch>
# 1. logs the slot grant (the 80 minute budget counts from here, so the fixture's minutes count against it);
# 2. runs the registered fixture debug (fixture tokens only, stock layers 0..3); if it is not ok the job ends and the
#    registered run does NOT start;
# 3. picks the layer set by decide_set.py (rule fixed in A-1), logged;
# 4. hands over to run_norm.sh (the registered run), which keeps the first grant time.
# After a lost session, resume the registered run with run_norm.sh directly and the logged layer set.
set -uo pipefail
cd "$(dirname "$0")"
X="$1"; R=runs; mkdir -p "$X" "$R/debug"
now() { date -u +%FT%TZ; }
G=$(now)
echo "slot granted $G set=pending (run_all.sh: fixture debug first, PREREG A-1)" >> "$R/progress.log"
freeb=$(df -B1 --output=avail "$X" | tail -1 | tr -d ' ')
if [ "$freeb" -lt 21000000000 ]; then echo "REFUSED (fixture): free disk under 21 GB (decimal) $(now)" >> "$R/progress.log"; exit 4; fi
avail=$(awk '/MemAvailable/ {print $2}' /proc/meminfo)
if [ "$avail" -lt 10485760 ]; then echo "REFUSED (fixture): MemAvailable under 10 GB $(now)" >> "$R/progress.log"; exit 3; fi
OMP_NUM_THREADS=6 OPENBLAS_NUM_THREADS=6 MKL_NUM_THREADS=6 python3 norm_class.py fixture "$X/fixture3" "$X/fixture3.json" > "$X/fixture3.stdout" 2> "$X/fixture3.stderr"
rc=$?
echo "fixture end rc=$rc $(now)" >> "$R/progress.log"
if [ "$rc" -ne 0 ]; then echo "registered run NOT started (fixture failed) $(now)" >> "$R/progress.log"; exit 5; fi
cp "$X/fixture3.json" "$R/debug/fixture-2.json"
SET=$(python3 decide_set.py "$X/fixture3.json" "$G" "$R/progress.log")
rc=$?
if [ "$rc" -ne 0 ]; then echo "registered run NOT started (decide_set rc=$rc) $(now)" >> "$R/progress.log"; exit 6; fi
exec bash run_norm.sh "$X/run" "$SET"
