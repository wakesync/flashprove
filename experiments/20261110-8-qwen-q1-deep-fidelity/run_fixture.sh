#!/usr/bin/env bash
# Debug run on the fixture (not in the registered suite), as PREREG "Debug before the registered run". Run via fp-heavy.sh.
# Usage: run_fixture.sh <scratch>
set -euo pipefail
cd "$(dirname "$0")"
X="$1"; mkdir -p "$X"
export OMP_NUM_THREADS=6 OPENBLAS_NUM_THREADS=6
echo "fixture slot $(date -u +%FT%TZ)" >> "$X/fixture.progress"
/usr/bin/time -v taskset -c 0-5 python3 q1_forward.py fixture "$X" "$X" > "$X/fixture.log" 2> "$X/fixture.time"
echo "fixture done $(date -u +%FT%TZ)" >> "$X/fixture.progress"
