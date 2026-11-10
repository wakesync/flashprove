#!/usr/bin/env bash
# Step 1: PR #68's registered arm at F = 12, unchanged code, both checkpoints, from this lane's fresh fetch.
# Run through fp-heavy.sh; pinned to 6 cores. Usage: repro_run.sh <cache_dir>
set -euo pipefail
cd "$(dirname "$0")"
C="$1"; SRC=../20261109-8-qwen-real-weights
for ck in stock abl; do
  /usr/bin/time -v taskset -c 0-5 python3 "$SRC/real_head.py" run "$C" "$ck" "runs/repro-real-$ck.jsonl" --F 12 > "runs/repro-real-$ck.log" 2> "runs/repro-real-$ck.time"
done
python3 repro_check.py rows > runs/repro-rows.out
echo done > runs/repro.done
