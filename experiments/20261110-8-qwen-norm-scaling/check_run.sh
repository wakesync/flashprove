#!/usr/bin/env bash
# Engine checks 2(a) and 2(b): one process, one core, BLAS single-threaded. Usage: check_run.sh <cache_dir> <scratch_dir>
set -euo pipefail
cd "$(dirname "$0")"
mkdir -p "$2"
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
/usr/bin/time -v taskset -c 5 python3 scaled_head.py check "$1" stock runs/engine-check.json --scratch "$2" > runs/engine-check.log 2> runs/engine-check.time
