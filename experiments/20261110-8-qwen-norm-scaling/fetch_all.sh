#!/usr/bin/env bash
# Step 1 fetch: PR #68's fetch.py, unchanged, for both checkpoints, plus layer-0 out_proj (descriptive residual question).
# fetch.py writes its manifest into ../20261109-8-qwen-real-weights/runs/fetch-<ckpt>.json; this script moves the new
# manifest into runs/ here and restores PR #68's committed file, so the two can be compared.
# Usage: fetch_all.sh <cache_dir>
set -euo pipefail
cd "$(dirname "$0")"
C="$1"; mkdir -p runs
SRC=../20261109-8-qwen-real-weights
for ck in stock abl; do
  ( cd "$SRC" && python3 fetch.py "$ck" "$C" model.language_model.layers.0.linear_attn.out_proj.weight ) > "runs/fetch-$ck.log" 2>&1
  mv "$SRC/runs/fetch-$ck.json" "runs/fetch-$ck.json"
  git checkout -- "$SRC/runs/fetch-$ck.json"
done
echo done > runs/fetch.done
