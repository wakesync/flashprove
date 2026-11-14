#!/usr/bin/env bash
# Registered run (PREREG): 75 min from the slot grant, hard stop 2026-11-13T17:40:00Z, 14 GB tree RSS, MemAvailable >= 12 GB.
# Run through the heavy gate, cores 10-15. usage: run_attn.sh <scratch>
set -eu
D="$(cd "$(dirname "$0")" && pwd)"
S="$1"
mkdir -p "$S/run" "$D/runs"
export OPENBLAS_NUM_THREADS=6 OMP_NUM_THREADS=6 MKL_NUM_THREADS=6
python3 "$D/watchdog.py" "$D/runs/progress.log" 75 2026-11-13T17:40:00Z 14 12 -- \
  python3 "$D/int_attn.py" run "$S/run" "$D/runs"
