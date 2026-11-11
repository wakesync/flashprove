#!/usr/bin/env bash
# PR #87 review (opus item 2): rerun H1 and the count with COMMITTED code into a new directory.
# The original H1 outputs and counted.json were written before wb_manifest.py / wb_count.py were
# committed. This script is committed before it is run; it runs the verifier as FIXED in PR #87
# (canonical opening checks, astra item 3), and never touches runs/.
# Run from the top of the tree: research/weight-binding/rerun_pr87.sh
set -eu
E=experiments/20261110-36-weight-binding
R=experiments/20261109-8-qwen-real-weights/runs
O=$E/runs-rerun-pr87
mkdir -p "$O"
{
  echo "code commit: $(git rev-parse HEAD)"
  echo "start (UTC): $(date -u +%Y-%m-%dT%H:%M:%SZ)"
} > "$O/rerun.time"
python3 research/weight-binding/test_wb_manifest.py > "$O/test_wb_manifest.log"
python3 research/weight-binding/wb_manifest.py demo "$R/stream-stock.json" "$R/stream-abl.json" "$O/h1-manifest-demo.json" > "$O/h1.log"
python3 research/weight-binding/wb_manifest.py build "$R/stream-stock.json" "$O/manifest-stock.json" >> "$O/h1.log"
python3 research/weight-binding/wb_manifest.py build "$R/stream-abl.json" "$O/manifest-abl.json" >> "$O/h1.log"
python3 research/weight-binding/wb_count.py "$O/counted.json" > /dev/null
echo "finished (UTC): $(date -u +%Y-%m-%dT%H:%M:%SZ)" >> "$O/rerun.time"
python3 research/weight-binding/compare_rerun.py "$O/compare.json" > /dev/null
