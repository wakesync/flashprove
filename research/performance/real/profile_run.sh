#!/bin/bash
# Samples one complete stored-proof verification with sampler.so and writes per-process flat and
# inclusive profiles. usage: profile_run.sh <cp_verify built with frame pointers> <sampler.so> <out dir>
set -euo pipefail
bin=$(realpath "$1"); so=$(realpath "$2"); out=$3
here=$(cd "$(dirname "$0")" && pwd -P)
top=$(cd "$here/../../.." && pwd -P)
F=$top/examples/accepted-proof
mkdir -p "$out"; out=$(realpath "$out")
rm -f "$out"/samples.*.txt
SAMPLER_DIR=$out LD_PRELOAD=$so "$bin" "$F/config" "$F/ivk" "$F/example.req" "$F/example.y" "$F/example.proof" \
  -id "$(cat "$F/ID.txt")" -j 1 -show-stages > "$out/run.stdout" 2> "$out/run.stderr" || true
tail -1 "$out/run.stdout"
for s in "$out"/samples.*.txt; do
  python3 "$here/symbolize.py" "$bin" "$s" --top "${TOP:-60}" --match 'blk::(Big|Real|Bound)\b' \
    --match 'blk::configure\(' --match 'blk::sized\(' --match 'blk::check_proof\(' --match 'Tensor::' \
    --match 'Blake2bF' > "${s%.txt}.profile.txt"
  grep -E '^(==|-- stacks)' "${s%.txt}.profile.txt"
done
