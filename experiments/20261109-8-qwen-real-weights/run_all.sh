#!/usr/bin/env bash
# Q3/Q4 runs: registered arm (F = 12, 14, 16, conv taps at 2^12) for both checkpoints, then the registered
# ablation (taps at 2^F) and the secondary q-unscaled arm (unregistered, Amendment). Usage: run_all.sh <cache_dir>
set -euo pipefail
cd "$(dirname "$0")"
C="$1"
for ck in stock abl; do
  /usr/bin/time -v taskset -c 0-5 python3 real_head.py run "$C" "$ck" "runs/real-$ck.jsonl" --F 12,14,16 > "runs/real-$ck.log" 2> "runs/real-$ck.time"
done
for ck in stock abl; do
  taskset -c 0-5 python3 real_head.py run "$C" "$ck" "runs/real-$ck-tapF.jsonl" --F 12,16 --tap-eq-F > "runs/real-$ck-tapF.log" 2>&1
  taskset -c 0-5 python3 real_head.py run "$C" "$ck" "runs/real-$ck-qunscaled.jsonl" --F 12,16 --q-unscaled > "runs/real-$ck-qunscaled.log" 2>&1
done
echo done > runs/run_all.done
