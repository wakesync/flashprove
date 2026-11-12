#!/usr/bin/env bash
# Issue #149 run (experiments/20261112-149-leaf-v2). CPU only. HASH LEVEL, NOT A PROOF.
# From the top of the tree: bash research/weight-binding/run_leafv2.sh <outdir> [--reverse] [--budget-s S]
# Fetches the 78 registered tensors of each pin by range request (memory only), converts by wb_int's
# matrix rule, writes blocks.jsonl; then, if all 78 completed, builds the leaf-v2 trees and runs the
# hostile suite twice. Logs the start time (the moment the heavy-job gate granted the slot).
set -euo pipefail
OUT=${1:?outdir}
shift
mkdir -p "$OUT"
W=research/weight-binding
echo "slot_granted_utc $(date -u +%Y-%m-%dT%H:%M:%SZ)" | tee "$OUT/slot.txt"
python3 --version > "$OUT/python.txt"
python3 -c "import numpy; print('numpy', numpy.__version__)" >> "$OUT/python.txt"
/usr/bin/time -v python3 $W/wb_leafv2.py run "$OUT" "$@" > "$OUT/run.log" 2> "$OUT/run.time"
N=$(wc -l < "$OUT/blocks.jsonl")
echo "blocks $N" | tee -a "$OUT/slot.txt"
if [ "$N" -eq 78 ]; then
  python3 $W/wb_leafv2.py tree "$OUT" | tee "$OUT/tree.log"
  python3 $W/test_wb_leafv2.py "$OUT" "$OUT/tests-1.json" > "$OUT/tests-1.log" || true
  python3 $W/test_wb_leafv2.py "$OUT" "$OUT/tests-2.json" > "$OUT/tests-2.log" || true
  tail -1 "$OUT/tests-1.log"
  tail -1 "$OUT/tests-2.log"
  sha256sum "$OUT/tests-1.json" "$OUT/tests-2.json" "$OUT/leaves-v2.json" | sed "s#$OUT/##" | tee "$OUT/sha256.txt"
fi
echo "finished_utc $(date -u +%Y-%m-%dT%H:%M:%SZ)" | tee -a "$OUT/slot.txt"
