#!/bin/bash
# The measured comparisons of PERF-REAL (see README.md here):
#   single: 12 alternating rounds, one CPU, -j 1, six arms (stock, compiler-only variants, candidate)
#   threads: 12 alternating rounds, four CPUs, -j 4, stock vs candidate (parallelism reported apart)
# Nothing else of this lane builds or runs meanwhile; the host's load is recorded around every call.
set -euo pipefail
top=$(cd "$(dirname "$0")/../../.." && pwd -P)
cd "$top"
B=build-variants
R=research/performance/real/results
uptime
python3 research/performance/real/bench.py $R/single --cpu "${CPU:-15}" --reps "${REPS:-12}" \
  stock=$B/stock/cp_verify stock-o3=$B/o3/cp_verify stock-v3=$B/v3/cp_verify stock-pgo=$B/stock-pgo/use/cp_verify \
  cand=$B/cand/cp_verify cand-pgo=$B/cand-pgouse/cp_verify
uptime
python3 research/performance/real/bench.py $R/threads4 --cpu "${CPUS:-12-15}" --threads 4 --reps "${REPS:-12}" \
  stock-j4=$B/stock/cp_verify cand-j4=$B/cand/cp_verify
uptime
