#!/bin/bash
# After the test switch BLK_BIG_ON_THE_HEAP_FOR_A_TEST was added (real.h, fence.h,
# planners_read_once_test.cpp):
#  1. the production verifier is rebuilt with verifier/build.sh flags; its binary must not change
#     apart from the source digest it prints (real.h and fence.h are hashed sources);
#  2. the switch must not compile beside SERVING_BUILD (fence.h), and must leave the marker string
#     in a test build;
#  3. numbers_test, and the read-once test with its 14 mutants on candidate and base.
# usage: run_round4.sh <unchanged base checkout> <work dir>
set -uo pipefail
here=$(cd "$(dirname "$0")" && pwd -P)
top=$(cd "$here/../../.." && pwd -P)
base=$(cd "$1" && pwd -P)
work=$2; mkdir -p "$work"; work=$(cd "$work" && pwd -P)
cd "$top"
"$here/build_variant.sh" build-variants/cand2 > build-variants/cand2.log 2>&1 && echo "cand2 built: $(sha256sum build-variants/cand2/cp_verify | cut -c1-16)"
echo 'int main(){}' > "$work/fence_probe.cpp"
if g++ -std=c++17 -DBLK_FIELD=2 -DSERVING_BUILD=1 -DBLK_BIG_ON_THE_HEAP_FOR_A_TEST -include blocks/numbers/real.h -Iblocks "$work/fence_probe.cpp" -o "$work/fence_probe" > "$work/fence_probe.log" 2>&1; then
  echo "FENCE FAILED: the switch compiled under SERVING_BUILD"
else
  echo "fence: refused under SERVING_BUILD: $(grep -o 'error: #error.*' "$work/fence_probe.log" | head -n 1)"
fi
g++ -std=c++17 -DBLK_FIELD=2 -DBLK_BIG_ON_THE_HEAP_FOR_A_TEST -include blocks/numbers/real.h -Iblocks "$work/fence_probe.cpp" -o "$work/fence_probe_test" > /dev/null 2>&1 &&
  echo "fence: test build carries the marker: $(grep -c -a 'BLK-NOT-FOR-SERVING' "$work/fence_probe_test")"
g++ -O2 -fno-ipa-modref -std=c++17 -DBLK_FIELD=2 -D_GLIBCXX_ASSERTIONS -Wall -Wextra -Iblocks blocks/numbers/tests/numbers_test.cpp -o "$work/numbers_test" > "$work/numbers_test.build.log" 2>&1
"$work/numbers_test" | tail -n 1
"$here/read_once_mutants.sh" "$base" "$work/mutants"
