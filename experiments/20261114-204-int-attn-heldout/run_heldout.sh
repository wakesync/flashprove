#!/usr/bin/env bash
# Registered run (PREREG): 75 min from the slot grant, compute hard stop 2026-11-14T07:40:00Z, 14 GB (decimal) tree RSS,
# MemAvailable >= 12 GB (decimal). Run through the heavy gate, cores 8-13. usage: run_heldout.sh <scratch>
set -eu
D="$(cd "$(dirname "$0")" && pwd)"
S="$1"
mkdir -p "$S/run" "$D/runs"
export OPENBLAS_NUM_THREADS=6 OMP_NUM_THREADS=6 MKL_NUM_THREADS=6
python3 "$D/watchdog.py" "$D/runs/progress.log" 75 2026-11-14T07:40:00Z 14 12 -- \
  python3 "$D/heldout.py" run "$S/run" "$D/runs"
