#!/usr/bin/env bash
# Debug run 2 on the fixture (not in the registered suite): E-path code. Run via fp-heavy.sh. Usage: run_fixture2.sh <scratch>
set -euo pipefail
cd "$(dirname "$0")"
X="$1"; mkdir -p "$X"
export OMP_NUM_THREADS=6 OPENBLAS_NUM_THREADS=6
/usr/bin/time -v taskset -c 0-5 python3 q1_forward.py fixture2 "$X" "$X" > "$X/fixture2.log" 2> "$X/fixture2.time"
