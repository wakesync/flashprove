#!/usr/bin/env bash
# Issue #91 runs. CPU only, seconds. From the top of the tree: bash research/weight-binding/run_wb91.sh <outdir>
# Builds both pins' conversion ids twice (H4), runs the hostile test suite twice (H1-H3), counts the
# key-file table cost (H5). Hash level and counts; NOT A PROOF.
set -euo pipefail
OUT=${1:?outdir}
mkdir -p "$OUT"
R68=experiments/20261109-8-qwen-real-weights/runs
R91=experiments/20261111-91-conversion-id/runs
W=research/weight-binding
for pin in stock abl; do
  for k in 1 2; do
    python3 $W/wb_conv.py build $R68/stream-$pin.json $R91/config-$pin.json "$OUT/conv-$pin-build$k.json" | tee -a "$OUT/build.log"
  done
done
sha256sum "$OUT"/conv-*-build*.json | sed "s#$OUT/##" | tee "$OUT/build-sha256.txt"
python3 $W/test_wb_conv.py "$OUT/tests-1.json" > "$OUT/tests-1.log"
python3 $W/test_wb_conv.py "$OUT/tests-2.json" > "$OUT/tests-2.log"
tail -1 "$OUT/tests-1.log"
tail -1 "$OUT/tests-2.log"
python3 $W/wb_keyfile_count.py $R68/stream-stock.json $R91/config-stock.json "$OUT/keyfile-count.json"
sha256sum $R91/config-stock.json $R91/config-abl.json | tee "$OUT/config-sha256.txt"
python3 --version > "$OUT/python.txt"
