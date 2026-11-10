#!/usr/bin/env bash
# Offline reproduction of numbers.json from the committed rental-2 session logs (added 2026-11-10).
#
# analyze_r2.py (unchanged since d6ef23dd) expects log basenames session-<NAME>.log, while the committed
# logs carry a hardware prefix (h100-session-CA1.log, h200-session-TB1.log). This script copies the two logs,
# unchanged, to the expected names in a temporary directory outside the run directory, runs the analyzer
# with the rounded box prices 4.8185 (H100, 2-GPU box) and 5.5402 (H200, 1-GPU box), and compares its output
# with the committed numbers.json. No committed file is written.
#
# usage: bash experiments/20261104-43-h200-memory-lever/reproduce_r2.sh
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
cp "$here/rental2/h100-session-CA1.log" "$tmp/session-CA1.log"
cp "$here/rental2/h200-session-TB1.log" "$tmp/session-TB1.log"
python3 "$here/analyze_r2.py" "$tmp/numbers.json" 4.8185 5.5402 "$tmp/session-CA1.log" "$tmp/session-TB1.log" >/dev/null
if cmp -s "$tmp/numbers.json" "$here/numbers.json"; then
  echo "reproduce_r2: numbers.json reproduced byte for byte"
else
  echo "reproduce_r2: output differs from the committed numbers.json" >&2
  diff "$tmp/numbers.json" "$here/numbers.json" >&2 || true
  exit 1
fi
