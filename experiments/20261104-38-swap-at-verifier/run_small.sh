#!/bin/bash
# As runner, after runner.sh BUILD. One fresh commitment on a small kit, then cp_prove on every in-*/ folder of
# requests and a whole cp_verify call on every response that has a proof.
# usage: small.sh <tag> <config dir with policy.txt KL.bin layout.txt> <requests root holding in-*/> <cp_verify -policy string>
# Writes $HOME/art-<tag>/ : commit.log, ID.txt, prove-<k>.log, results.tsv (name, prover, exit, last line), proofs.sha256, DONE.
set -uo pipefail
umask 022
TAG=$1 CFG=$2 REQ=$3 POL=$4
export PATH="$HOME/cuda-13.2.86/nvidia/cu13/bin:$PATH"
P=$HOME/flashprove/prover/build/hc
A=$HOME/art-$TAG W=$HOME/s-$TAG
mkdir -m 700 $A $W $W/home $W/tmp $W/config || exit 2
cp $CFG/policy.txt $CFG/KL.bin $CFG/layout.txt $W/config/
GPU=$(nvidia-smi --query-gpu=uuid --format=csv,noheader | sed -n "$(( ${SMALL_GPU:-0} + 1 ))p")
ts() { date -u +%FT%TZ; }
echo "$(ts) commit-start $TAG" >> $A/stages.log
cd $W && HOME=$W/home TMPDIR=$W/tmp CUDA_VISIBLE_DEVICES=$GPU $P/cp_commit -weights made-up-blocks -config config -M 1 -ivk ivk -isk $W/isk > $A/commit.log 2>&1
echo "$(ts) commit-exit $?" >> $A/stages.log
sed -n 's/^commitment ID: //p' $A/commit.log | tr -d ' ' | head -1 > $A/ID.txt
ID=$(cat $A/ID.txt)
[ -n "$ID" ] || { echo "FAIL commit" > $A/DONE; exit 1; }
printf 'name\tprover\texit\tlast_line\n' > $A/results.tsv
for d in $REQ/in-*; do
  k=$(basename $d)
  mkdir -m 700 $W/$k && cp $d/*.req $W/$k/
  echo "$(ts) prove-start $k $(ls $W/$k | wc -l)" >> $A/stages.log
  HOME=$W/home TMPDIR=$W/tmp CUDA_VISIBLE_DEVICES=$GPU $P/cp_prove -isk $W/isk -in $W/$k -out $W/out-$k > $A/prove-$k.log 2>&1
  echo "$(ts) prove-exit $k $?" >> $A/stages.log
  for r in $W/$k/*.req; do
    n=$(basename $r .req)
    if [ -f $W/out-$k/$n.proof ]; then
      out=$($P/cp_verify $W/config $W/ivk $r $W/out-$k/$n.y $W/out-$k/$n.proof -id $ID -policy $POL -q 2>&1); ec=$?
      printf '%s\tproof\t%s\t%s\n' "$n" "$ec" "$(printf '%s\n' "$out" | grep -v '^$' | tail -1)" >> $A/results.tsv
      printf '%s\n' "$out" | grep '^result-v1' | sed "s/^/$n /" >> $A/result-v1.txt
    elif [ -f $W/out-$k/$n.failed ]; then
      printf '%s\tfailed\t-\t-\n' "$n" >> $A/results.tsv
    else
      printf '%s\tnone\t-\t-\n' "$n" >> $A/results.tsv
    fi
  done
  (cd $W/out-$k 2>/dev/null && sha256sum *.proof 2>/dev/null) >> $A/proofs.sha256
done
echo "$(ts) all-done" >> $A/stages.log
echo "DONE 0" > $A/DONE
