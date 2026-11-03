#!/bin/bash
# PGO of the UNCHANGED upstream sources, so that the compiler-only win is reported apart from the
# source change. usage: build_stock_pgo.sh <unchanged checkout> <out dir>
# Trains on two honest verifications of the example, as for the candidate's PGO build.
set -euo pipefail
src=$(cd "$1" && pwd -P); out=$(mkdir -p "$2" && cd "$2" && pwd -P)
here=$(cd "$(dirname "$0")" && pwd -P)
mkdir -p "$src/research/performance/real"
cp "$here/build_variant.sh" "$src/research/performance/real/build_variant.sh"
bv=$src/research/performance/real/build_variant.sh
"$bv" "$out/gen" -fprofile-generate="$out/data" -fprofile-update=atomic > "$out/gen.log" 2>&1
F=$src/examples/accepted-proof
for i in 1 2; do
  "$out/gen/cp_verify" "$F/config" "$F/ivk" "$F/example.req" "$F/example.y" "$F/example.proof" -id "$(cat "$F/ID.txt")" -j 1 | tail -n 1
done
mkdir -p "$out/data$out/use"
cp "$out/data$out/gen/cp_verify.gcda" "$out/data$out/use/cp_verify.gcda"
"$bv" "$out/use" -fprofile-use="$out/data" -fprofile-correction > "$out/use.log" 2>&1
rm -rf "$src/research/performance/real"
tail -n 1 "$out/use.log"
