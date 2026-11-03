#!/bin/bash
# Differential correctness: the unchanged stock build is the reference; every measured arm must
# match it on the honest example and the eight negative cases (see differential.py).
set -euo pipefail
top=$(cd "$(dirname "$0")/../../.." && pwd -P)
cd "$top"
B=build-variants
python3 research/performance/real/differential.py research/performance/real/results/differential --cpu "${CPU:-15}" \
  stock=$B/stock/cp_verify cand=$B/cand/cp_verify cand-pgo=$B/cand-pgouse/cp_verify \
  stock-o3=$B/o3/cp_verify stock-v3=$B/v3/cp_verify stock-pgo=$B/stock-pgo/use/cp_verify
