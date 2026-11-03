#!/bin/bash
# PGO use build of the candidate sources, from the profile of two honest verifications of the
# example by cand-pgogen. gcc looks the profile up under the output's own path, so the .gcda is
# copied to the name that the use build expects. Research harness only.
set -euo pipefail
top=$(cd "$(dirname "$0")/../../.." && pwd -P)
cd "$top"
d=build-variants/pgo-data
mkdir -p "$d$top/build-variants/cand-pgouse"
cp "$d$top/build-variants/cand-pgogen/cp_verify.gcda" "$d$top/build-variants/cand-pgouse/cp_verify.gcda"
research/performance/real/build_variant.sh build-variants/cand-pgouse -fprofile-use="$top/$d" -fprofile-correction -Wmissing-profile > build-variants/cand-pgouse.log 2>&1
tail -n 1 build-variants/cand-pgouse.log
