#!/usr/bin/env bash
# Debug fixture (PREREG "Runs"): 5 fixture tokens, stock layers 0..3. Run through the heavy gate, cores 10-15.
# usage: run_fixture.sh <scratch>
set -eu
D="$(cd "$(dirname "$0")" && pwd)"
S="$1"
mkdir -p "$S/fixture" "$D/runs/debug-fixture"
export OPENBLAS_NUM_THREADS=6 OMP_NUM_THREADS=6 MKL_NUM_THREADS=6
python3 "$D/watchdog.py" "$D/runs/debug-fixture/watchdog.log" 15 2026-11-13T17:40:00Z 14 12 -- \
  python3 "$D/int_attn.py" fixture "$S/fixture" "$D/runs/debug-fixture"
