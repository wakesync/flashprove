#!/bin/bash
# Short pilot (3 rounds) over every arm, to choose which arms get the full 10+ round comparison.
set -euo pipefail
top=$(cd "$(dirname "$0")/../../.." && pwd -P)
cd "$top"
B=build-variants
uptime
python3 research/performance/real/bench.py research/performance/real/results/pilot --cpu "${CPU:-15}" --reps 3 \
  stock=$B/stock/cp_verify cand=$B/cand/cp_verify o3=$B/o3/cp_verify v3=$B/v3/cp_verify pgo=$B/cand-pgouse/cp_verify
uptime
