#!/usr/bin/env bash
# Run from the repository root. Builds CPU-only experiments, never invokes CUDA.
set -euo pipefail
exp=experiments/20261103-7-cpu-commit
work=${1:?usage: build.sh NEW_SCRATCH_DIRECTORY}
mkdir "$work"
mkdir "$work/base" "$work/candidate"
git archive 29907e5fbe648b9ec246cebf9d757511a751fca2 blocks | tar -x -C "$work/base"
cp -a "$work/base/blocks" "$work/candidate/"
patch -s -d "$work/candidate" -p1 < "$exp/candidate.patch"
flags=(-O2 -fno-ipa-modref -std=c++17 -pthread -DBLK_FIELD=2 -D_GLIBCXX_ASSERTIONS)
for arm in A B; do
  tree=base; [[ $arm == A ]] || tree=candidate
  g++-13 "${flags[@]}" -I"$work/$tree/blocks" "$exp/reference.cpp" -o "$work/reference-$arm"
done
g++-13 "${flags[@]}" -I"$work/base/blocks" -pg -DPROFILE_GENERATION "$exp/reference.cpp" -o "$work/reference-gen-prof"
# Match prover/build.sh's verifier_unit isolation, so C++ names cannot coalesce.
export LC_ALL=C
word=$({ (cd verifier/src && sha256sum * ../../prover/*/plan_rounds.h ../../prover/hiding/token_plan.h); (cd "$work/base/blocks" && find . -type f -name '*.h' ! -path '*/tests/*' | sort | xargs sha256sum); } | sha256sum | cut -c1-64)
g++-13 -O2 -fno-ipa-modref -std=c++17 -pthread -Iverifier/src -I"$work/base/blocks" -Iprover -DBLK_FIELD=2 -DSERVING_BUILD=1 -DDIGEST_WORDS=8 -DVF_SOURCE_DIGEST="\"$word\"" -DCP_VERIFY_AS_A_UNIT -fno-gnu-unique -pg -c verifier/src/cp_verify.cpp -o "$work/configured-compiled.o"
door=$(nm "$work/configured-compiled.o" | awk '$2 == "T" && $3 ~ /^_Z18cp_with_configured/ {print $3}')
[[ $door =~ ^[A-Za-z0-9_]+$ ]]
ld -r --force-group-allocation -o "$work/configured-piece.o" "$work/configured-compiled.o"
objcopy --keep-global-symbol="$door" "$work/configured-piece.o" "$work/configured.o"
g++-13 -O2 -fno-ipa-modref -std=c++17 -pthread -DBLK_FIELD=2 -I"$work/base/blocks" -Iverifier/src -pg "$exp/configure.cpp" "$work/configured.o" -o "$work/configure-prof"
