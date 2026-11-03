#!/usr/bin/env bash
# Independent review replication of the committed public bundle.
# Usage: research/gpu/review/replicate.sh <cp_verify> <out dir>
#   <cp_verify>: a verifier built from a clean checkout of the pinned commit
#                9e2bdd8ff5bf9c62f18263d7dac189b0400b260c (verifier/build.sh).
#   <out dir>:   scratch directory; every corrupted case runs on its own copy.
# Prints one line per case: name, exit status, wall seconds, verifier's last line.
# The originals are checked against SHA256SUMS before and after.
set -u
V=$(realpath "$1"); W=$(realpath -m "$2")
G=$(cd "$(dirname "$0")/.." && pwd)
B=$G/bundle
ID=5259d3dffde81fcf7b08634bfaca2bb217aa12286ef2aacd321648572660968c
rm -rf "$W"; mkdir -p "$W"
(cd "$G" && sha256sum -c --quiet SHA256SUMS) || { echo "SHA256SUMS mismatch before run"; exit 2; }
mk(){ rm -rf "$W/$1"; cp -a "$B" "$W/$1"; }
flip(){ # file byte-offset bit-mask(decimal): xor one byte in place
  local cur; cur=$(od -An -tu1 -j "$2" -N1 "$1" | tr -d ' ')
  printf "\\$(printf '%03o' $(( cur ^ $3 )))" | dd of="$1" bs=1 seek="$2" conv=notrunc status=none; }
run(){ # name dir [request y proof]
  local d=$2 req=${3:-in/example.req} y=${4:-out/example.y} pf=${5:-out/example.proof} t0 t1 rc
  t0=$(date +%s.%N); (cd "$d" && "$V" config ivk "$req" "$y" "$pf" -id "$ID") > "$W/$1.log" 2>&1; rc=$?
  t1=$(date +%s.%N); printf '%s\texit=%s\t%.3fs\t%s\n' "$1" "$rc" "$(echo "$t1 - $t0" | bc)" "$(tail -1 "$W/$1.log")"; }
P=out/example.proof; SZ=$(stat -c %s "$B/$P")
for i in 1 2 3 4 5 6 7; do run "honest-$i" "$B"; done
mk c1;  flip "$W/c1/$P" 1000003 8;          run proof-bit3-at-1000003 "$W/c1"
mk c2;  flip "$W/c2/$P" $((SZ-17)) 1;       run proof-bit0-at-size-minus-17 "$W/c2"
mk c3;  flip "$W/c3/$P" 9 128;              run proof-bit7-at-9-header "$W/c3"
mk c4;  printf '\000' >> "$W/c4/$P";        run proof-append-zero-byte "$W/c4"
mk c5;  printf 'A' >> "$W/c5/in/example.req"; run request-append-byte "$W/c5"
mk c6;                                      run swap-request-and-y "$W/c6" out/example.y in/example.req
mk c7;  dd if=/dev/zero of="$W/c7/$P" bs=1 count=32 conv=notrunc status=none; run proof-zero-header-32B "$W/c7"
mk c8;  dd if=/dev/zero of="$W/c8/$P" bs=1 count=8 conv=notrunc status=none;  run proof-zero-magic-8B "$W/c8"
mk c9;  flip "$W/c9/ivk/key.bin" 500000 16; run key-bit4-at-500000 "$W/c9"
mk c10; flip "$W/c10/ivk/leaf/0.bin" 1234 2; run leaf-bit1-at-1234 "$W/c10"
mk c11; printf '\035\001\000\000' > "$W/c11/out/example.y"; run y-token-285-not-284 "$W/c11"
(cd "$G" && sha256sum -c --quiet SHA256SUMS) && echo "originals unchanged (SHA256SUMS ok)"
