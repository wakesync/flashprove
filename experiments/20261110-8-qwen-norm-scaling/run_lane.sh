#!/usr/bin/env bash
# The whole lane in one heavy slot, in PREREG order: step 1 (reproduce PR #68 F = 12 rows, stop on mismatch),
# then localisation arms, then candidate arms, then summaries and cost. Run via fp-heavy.sh. Pinned to cores 0-5.
# Usage: run_lane.sh <cache_dir> <scratch_dir> [stage...]   stages: repro local cand  (default: all three)
set -euo pipefail
cd "$(dirname "$0")"
C="$1"; X="$2"; shift 2
STAGES="${*:-repro local cand}"
SRC=../20261109-8-qwen-real-weights
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
mkdir -p runs "$X"
for st in $STAGES; do
  case $st in
  repro)
    pids=()
    for ck in stock abl; do
      ( /usr/bin/time -v taskset -c 0-5 env OMP_NUM_THREADS=3 OPENBLAS_NUM_THREADS=3 python3 "$SRC/real_head.py" run "$C" "$ck" "runs/repro-real-$ck.jsonl" --F 12 \
          > "runs/repro-real-$ck.log" 2> "runs/repro-real-$ck.time" ) & pids+=($!)
    done
    for p in "${pids[@]}"; do wait "$p"; done
    if ! python3 repro_check.py rows > runs/repro-rows.out; then echo "STEP 1 MISMATCH: stop" > runs/STOP; exit 3; fi
    ;;
  local)
    rm -f runs/local-stock.jsonl
    /usr/bin/time -v taskset -c 0-5 python3 scaled_head.py run "$C" stock arms-local.json runs/local-stock.jsonl --jobs 6 --scratch "$X" \
      > runs/local-stock.log 2> runs/local-stock.time
    python3 summarise.py runs/local-stock.jsonl > runs/local-stock.table.md
    ;;
  cand)
    rm -f runs/cand-stock.jsonl
    /usr/bin/time -v taskset -c 0-5 python3 scaled_head.py run "$C" stock arms-cand.json runs/cand-stock.jsonl --jobs 6 --scratch "$X" \
      > runs/cand-stock.log 2> runs/cand-stock.time
    python3 summarise.py runs/cand-stock.jsonl > runs/cand-stock.table.md
    ;;
  esac
  echo "$st done $(date -u +%FT%TZ)" >> runs/lane.progress
done
