#!/bin/bash
# Builds the candidate (this checkout's sources) three ways, in parallel: plain stock flags, a PGO
# instrumented build, and the numbers unit test. Research harness only.
set -euo pipefail
top=$(cd "$(dirname "$0")/../../.." && pwd -P)
cd "$top"
mkdir -p build-variants/cand
nohup research/performance/real/build_variant.sh build-variants/cand > build-variants/cand.log 2>&1 &
nohup research/performance/real/build_variant.sh build-variants/cand-pgogen -fprofile-generate="$top/build-variants/pgo-data" -fprofile-update=atomic > build-variants/cand-pgogen.log 2>&1 &
nohup g++ -O2 -fno-ipa-modref -std=c++17 -DBLK_FIELD=2 -D_GLIBCXX_ASSERTIONS -Wall -Wextra -Iblocks blocks/numbers/tests/numbers_test.cpp -o build-variants/cand/numbers_test > build-variants/cand-numbers-build.log 2>&1 &
echo started
