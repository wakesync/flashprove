#!/usr/bin/env bash
# Step 1, second attempt in PR #68's exact environment: run_all.sh's command line (taskset -c 0-5, sequential,
# no BLAS thread variables set). The first attempt (repro_run via run_lane.sh) set OPENBLAS_NUM_THREADS=3 and ran
# both checkpoints in parallel; its rows differ from PR #68's in float fields at <= 5e-13 relative, integer fields
# all equal (runs/repro-diff-threads3-*.json). Usage: repro_run2.sh <cache_dir>
set -euo pipefail
cd "$(dirname "$0")"
unset OMP_NUM_THREADS OPENBLAS_NUM_THREADS MKL_NUM_THREADS || true
C="$1"; SRC=../20261109-8-qwen-real-weights
mkdir -p runs/attempt1-threads3
mv -f runs/repro-real-*.jsonl runs/repro-real-*.log runs/repro-real-*.time runs/repro-rows.json runs/repro-rows.out runs/attempt1-threads3/ 2>/dev/null || true
rm -f runs/STOP
for ck in stock abl; do
  /usr/bin/time -v taskset -c 0-5 python3 "$SRC/real_head.py" run "$C" "$ck" "runs/repro-real-$ck.jsonl" --F 12 > "runs/repro-real-$ck.log" 2> "runs/repro-real-$ck.time"
done
if python3 repro_check.py rows > runs/repro-rows.out; then echo ok > runs/repro.done; else echo "STEP 1 MISMATCH (attempt 2)" > runs/STOP; fi
