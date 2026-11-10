#!/usr/bin/env bash
# Step 1, second attempt (PREREG amendment A-1): PR #68's own command line for the registered arm, F = 12 only:
# taskset -c 0-5, BLAS thread variables unset, checkpoints one after the other. Idempotent and locked, so it can be
# called twice: the first caller runs it, the second sees the result. Run via fp-heavy.sh. On a match it caches the
# in_proj outputs (same thread setting) and continues into pipeline.sh in the same slot.
# Writes runs/repro.done (every row of both checkpoints equal) or runs/STOP. Usage: repro_run2.sh <cache_dir>
set -euo pipefail
cd "$(dirname "$0")"
unset OMP_NUM_THREADS OPENBLAS_NUM_THREADS MKL_NUM_THREADS || true
C="$1"; SRC=../20261109-8-qwen-real-weights
exec 9> runs/.repro.lock
flock 9
if [ -e runs/attempt2.ran ]; then exit 0; fi
mkdir -p runs/attempt1-threads3
mv -f runs/repro-real-*.jsonl runs/repro-real-*.log runs/repro-real-*.time runs/repro-rows.json runs/repro-rows.out runs/attempt1-threads3/ 2>/dev/null || true
mv -f runs/STOP runs/attempt1-threads3/STOP 2>/dev/null || true
date -u +%FT%TZ > runs/attempt2.start
for ck in stock abl; do
  /usr/bin/time -v taskset -c 0-5 python3 "$SRC/real_head.py" run "$C" "$ck" "runs/repro-real-$ck.jsonl" --F 12 > "runs/repro-real-$ck.log" 2> "runs/repro-real-$ck.time"
done
if python3 repro_check.py rows > runs/repro-rows.out; then
  # same slot, same thread setting as PR #68: cache x and the per-head in_proj outputs of every prompt for the engine
  P="$C/../prep"
  for ck in stock abl; do taskset -c 0-5 python3 scaled_head.py prep "$C" "$ck" "$P" >> runs/prep.log 2>&1; done
  echo ok > runs/repro.done
else
  echo "STEP 1 MISMATCH (attempt 2)" > runs/STOP
fi
date -u +%FT%TZ > runs/attempt2.ran
# PREREG amendment A-2: the arms run in this same heavy slot, and only if step 1 matched
if [ -e runs/repro.done ]; then ./pipeline.sh "$C" "$C/.." || true; fi
