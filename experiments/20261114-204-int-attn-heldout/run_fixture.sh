#!/usr/bin/env bash
# Debug only (PREREG (e)): PR #88's fixture, stock layers 0..3, frozen layer-3 scales. Not a registered prompt.
# Run through the heavy gate, cores 8-13. usage: run_fixture.sh <scratch>
set -eu
D="$(cd "$(dirname "$0")" && pwd)"
S="$1"
mkdir -p "$S/fixture" "$D/runs/debug-fixture"
export OPENBLAS_NUM_THREADS=6 OMP_NUM_THREADS=6 MKL_NUM_THREADS=6
python3 "$D/watchdog.py" "$D/runs/debug-fixture/watchdog.log" 10 2026-11-14T07:40:00Z 14 6 -- \
  python3 "$D/heldout.py" fixture "$S/fixture" "$D/runs/debug-fixture"
