#!/bin/bash
# blocks/tests/TESTS through blocks/Makefile `test`, setting f2h1, on the final candidate source.
# usage: run_blocks_tests_final.sh <work dir>
set -uo pipefail
here=$(cd "$(dirname "$0")" && pwd -P)
top=$(cd "$here/../../.." && pwd -P)
work=$1; mkdir -p "$work"; work=$(cd "$work" && pwd -P)
list=$(grep -v '^#' "$top/blocks/tests/TESTS" | grep . | sed "s#\.cpp\$#.ran#; s#^#$work/final/f2h1/#" | tr '\n' ' ')
(cd "$top/blocks" && make -k -j 12 OUT="$work/final" SETTINGS=f2h1 $list > "$work/final.make.log" 2>&1; echo "make exit $?" >> "$work/final.make.log")
grep '^f2h1 ' "$work/final.make.log" | sed 's/[0-9.]* s\b/<t> s/g' | sort > "$work/final.results"
echo "$(wc -l < "$work/final.results") result lines; $(find "$work/final/f2h1" -name '*.ran' | wc -l) .ran files; $(tail -n 1 "$work/final.make.log")"
