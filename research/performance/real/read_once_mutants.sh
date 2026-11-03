#!/bin/bash
# Does planners_read_once_test keep its power to detect a second read after the inline-limb change?
# The test fires a hook at one heap allocation at a time; Big no longer allocates for short numbers,
# so there are fewer allocations (119156 probed plans on the base, 4618 on the candidate). Mutation
# check: each `READ ONCE (plan.h)` copy in blocks/numbers/blocks.h is in turn replaced by a
# reference (`const T x = callers_x;` -> `const T &x = callers_x;`), in a scratch copy of blocks/,
# and the test is built and run on base and candidate. A mutant counts as detected if the test
# exits non-zero. The header of the test names four copies it cannot detect on the base.
# usage: read_once_mutants.sh <unchanged base checkout> <work dir>
set -uo pipefail
here=$(cd "$(dirname "$0")" && pwd -P)
cand=$(cd "$here/../../.." && pwd -P)
base=$(cd "$1" && pwd -P)
work=$2; mkdir -p "$work"; work=$(cd "$work" && pwd -P)
lines=$(grep -n 'READ ONCE (plan.h)' "$cand/blocks/numbers/blocks.h" | cut -d: -f1)
one() {  # side line
  local side=$1 line=$2 src=$cand
  [ "$side" = base ] && src=$base
  local d=$work/$side-$line
  rm -rf "$d"; mkdir -p "$d"; cp -r "$src/blocks" "$d/blocks"
  if [ "$line" != none ]; then
    sed -i "${line}s/^\(  const [A-Za-z:<>_]*\) \([a-z_]*\) = callers_/\1 \&\2 = callers_/; ${line}s/, \([a-z_]*\) = callers_/, \&\1 = callers_/" "$d/blocks/numbers/blocks.h"
    sed -n "${line}p" "$d/blocks/numbers/blocks.h" > "$d/mutated_line.txt"
    grep -q '&' "$d/mutated_line.txt" || { echo "$side $line NOT-MUTATED"; return; }
  fi
  if ! g++ -std=c++17 -O2 -Wall -Wextra -fno-ipa-modref -DBLK_FIELD=2 -DBLK_HASH=1 -I "$d/blocks" \
      "$d/blocks/numbers/tests/planners_read_once_test.cpp" -o "$d/t" > "$d/build.log" 2>&1; then
    echo "$side $line BUILD-FAILED"; return
  fi
  "$d/t" > "$d/run.log" 2>&1; local s=$?
  echo "$side $line exit=$s $( [ $s -ne 0 ] && echo DETECTED || echo missed ) | $(tail -n 1 "$d/run.log" | cut -c1-90) | $(cat "$d/mutated_line.txt" 2>/dev/null | sed 's/^ *//' | cut -c1-70)"
  rm -rf "$d/blocks" "$d/t"
}
export -f one; export cand base work
{ for l in none $lines; do echo "base $l"; echo "cand $l"; done; } | xargs -P 6 -n 2 bash -c 'one "$0" "$1"' | sort -k2,2 -k1,1
