#!/bin/bash
# Builds cp_verify exactly as verifier/build.sh does (same sources, same digest, same hardening and
# -fno-ipa-modref, same -D switches) but with extra compiler flags appended, into a named directory.
# usage: [BASE_OPT=-O3] build_variant.sh <output dir> [extra g++ flags...]
# Research harness only: the shipped build stays verifier/build.sh. Without extra flags and with the
# default BASE_OPT it reproduces the stock binary byte for byte (checked: see README).
set -euo pipefail
out=$1; shift
top=$(cd "$(dirname "$0")/../../.." && pwd -P)
mkdir -p "$out"; out=$(cd "$out" && pwd -P)
cd "$top/verifier/src"
export LC_ALL=C
build_word=$({ sha256sum * ../../prover/*/plan_rounds.h ../../prover/hiding/token_plan.h; cd ../../blocks && find . -type f -name '*.h' ! -path '*/tests/*' | sort | xargs sha256sum; } | sha256sum | cut -c1-64)
harden=(-D_GLIBCXX_ASSERTIONS -U_FORTIFY_SOURCE -D_FORTIFY_SOURCE=3 -fstack-protector-strong -fstack-clash-protection
  -ftrivial-auto-var-init=zero -fPIE -pie -Wl,-z,relro,-z,now,-z,noexecstack -fcf-protection=full)
base=${BASE_OPT:--O2}
echo "build=$build_word flags: $base -fno-ipa-modref ${harden[*]} $*" | tee "$out/flags.txt"
export TMPDIR=$out
g++ $base -fno-ipa-modref "${harden[@]}" -std=c++17 -Wall -Wextra -Wuninitialized -Werror=unused-result \
  -Wno-misleading-indentation -pthread -I. -I../../blocks -I../../prover -DBLK_FIELD=2 -DBLK_COUNT_HASH_CALLS=1 \
  -DSERVING_BUILD=1 -DDIGEST_WORDS=8 -DVF_SOURCE_DIGEST="\"$build_word\"" "$@" -o "$out/cp_verify" cp_verify.cpp
echo "BUILT $out/cp_verify"
