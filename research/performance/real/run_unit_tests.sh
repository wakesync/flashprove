#!/bin/bash
# Library tests for the candidate (this checkout) and the unchanged base, the same way:
#  1. blocks/Makefile `test` (setting f2h1) on exactly the sources listed in blocks/tests/TESTS, the
#     list of SUITE.md row blocks.tests; 8 jobs.
#  2. numbers_test (the targeted test of blocks/numbers, incl. real.h) under ASan + UBSan, with
#     _GLIBCXX_ASSERTIONS, for the candidate's new limb storage.
# usage: run_unit_tests.sh <unchanged base checkout> <work dir>
set -uo pipefail
here=$(cd "$(dirname "$0")" && pwd -P)
cand=$(cd "$here/../../.." && pwd -P)
base=$(cd "$1" && pwd -P)
work=$2; mkdir -p "$work"; work=$(cd "$work" && pwd -P)
for side in cand base; do
  src=$cand; [ $side = base ] && src=$base
  list=$(grep -v '^#' "$src/blocks/tests/TESTS" | grep . | sed "s#\.cpp\$#.ran#; s#^#$work/$side/f2h1/#" | tr '\n' ' ')
  (cd "$src/blocks" && make -k -j 8 OUT="$work/$side" SETTINGS=f2h1 $list > "$work/$side.make.log" 2>&1; echo "make exit $?" >> "$work/$side.make.log") &
done
wait
for side in cand base; do
  echo "== $side: $(grep -c ': ' "$work/$side.make.log") result lines; $(ls "$work/$side/f2h1" -R 2>/dev/null | grep -c '\.ran$') .ran files; $(tail -n 1 "$work/$side.make.log")"
done
cd "$cand"
g++ -O1 -g -fno-ipa-modref -std=c++17 -DBLK_FIELD=2 -D_GLIBCXX_ASSERTIONS -fsanitize=address,undefined -fno-sanitize-recover=all \
  -Iblocks blocks/numbers/tests/numbers_test.cpp -o "$work/numbers_test_asan" > "$work/numbers_test_asan.build.log" 2>&1
echo "asan build exit $?"
"$work/numbers_test_asan" > "$work/numbers_test_asan.log" 2>&1
echo "asan numbers_test exit $?: $(tail -n 1 "$work/numbers_test_asan.log")"
