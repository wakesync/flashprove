#!/usr/bin/env bash
# Light test (matmuls only, one process at a time, cores 6-11): in_proj hashes of all 10 prompts under 1, 3, 6 BLAS
# threads and with the variable unset (PR #68's setting). Usage: blas_threads_test.sh <cache>
set -euo pipefail
cd "$(dirname "$0")"
: > runs/blas-threads.jsonl
for n in 1 3 6; do
  OPENBLAS_NUM_THREADS=$n OMP_NUM_THREADS=$n taskset -c 6-11 python3 blas_threads_test.py "$1" >> runs/blas-threads.jsonl
done
env -u OPENBLAS_NUM_THREADS -u OMP_NUM_THREADS taskset -c 6-11 python3 blas_threads_test.py "$1" >> runs/blas-threads.jsonl
python3 blas_threads_cmp.py
