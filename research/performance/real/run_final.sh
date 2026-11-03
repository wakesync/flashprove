#!/bin/bash
# The final source (inline limbs + the read-once test switch), built with the stock flags
# (build-variants/cand2): differential against stock, then a confirmatory 10-round timing.
set -euo pipefail
top=$(cd "$(dirname "$0")/../../.." && pwd -P)
cd "$top"
B=build-variants
R=research/performance/real/results
python3 research/performance/real/differential.py $R/differential-final --cpu "${CPU:-15}" stock=$B/stock/cp_verify cand-final=$B/cand2/cp_verify
uptime
python3 research/performance/real/bench.py $R/single-final --cpu "${CPU:-15}" --reps "${REPS:-10}" stock=$B/stock/cp_verify cand-final=$B/cand2/cp_verify
uptime
