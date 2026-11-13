#!/bin/bash
# calib_run.sh <configuration dir> <new work dir> <requests> <in-step>: one calibration run of
# experiments/20261112-7-h200-dense-calibration (issue #140). Untested on a GPU: its control flow is
# tested on CPU with mocked programs (run_job_test.py, calibration cases).
#
#   1. config/ := the configuration's policy.txt, KL.bin, layout.txt
#   2. cp_commit -weights made-up-blocks -config config -M 1 -ivk ivk -isk isk     (a fresh commitment)
#   3. <requests> request files in/rNN.req, made by prover/tools/make_request.py from pseudo-random
#      tokens (seed = the request's index, recorded in requests.txt), r = T - 1, e = T (next token)
#   4. cp_prove -isk isk -in in -out out -in-step <in-step>                          (one batch)
#   5. cp_verify on every response; cp_verify.log gets every call's output, and as its LAST line
#      YES only if every call exited 0 with YES, else the first rejecting call's last line.
# cp_commit and cp_prove run under ${GPU_RUN} (run_job.sh: stamp.sh + /usr/bin/time), as
# run_target_example.sh runs them. BUILD names the directory of the three programs; FP_REPO the
# checkout (for make_request.py). Exit status: 0 if every response was accepted, else nonzero.
# Like run_target_example.sh, it never hands anything out: run_job.sh's export_run decides what
# leaves (out/ and cp_verify.log only if accepted, duty 6; isk/ never).
set -uo pipefail
cfg=$1 work=$2 n=$3 k=$4
: "${BUILD:?}" "${FP_REPO:?}"
read -r -a gpu_run < <(printf '%s\n' "${GPU_RUN:-}")
case $n in '' | *[!0-9]*) echo "calib_run.sh: requests must be a number" >&2; exit 2 ;; esac
case $k in '' | *[!0-9]*) echo "calib_run.sh: in-step must be a number" >&2; exit 2 ;; esac
if [ "$n" -lt 1 ] || [ "$n" -gt 64 ] || [ "$k" -lt 1 ] || [ "$k" -gt 16 ]; then
  echo "calib_run.sh: requests 1 to 64, in-step 1 to 16" >&2
  exit 2
fi
for f in policy.txt KL.bin layout.txt; do
  [ -r "$cfg/$f" ] || { echo "calib_run.sh: $cfg/$f is missing" >&2; exit 2; }
done
mkdir -m 700 "$work" || exit 2
cd "$work" || exit 2
mkdir config in home tmp || exit 2
cp "$cfg/policy.txt" "$cfg/KL.bin" "$cfg/layout.txt" config/ || exit 2
echo "WORK=$work"
${gpu_run[@]+"${gpu_run[@]}"} "$BUILD/cp_commit" -weights made-up-blocks -config config -M 1 -ivk ivk -isk isk >cp_commit.log 2>&1 || {
  echo "calib_run.sh: cp_commit failed with status $?" >&2
  tail -n 5 cp_commit.log >&2
  exit 1
}
id=$(sed -n 's/^commitment ID: //p' cp_commit.log | tr -d ' ')
[[ $id =~ ^[0-9a-f]{64}$ ]] || { echo "calib_run.sh: no commitment ID in cp_commit.log" >&2; exit 1; }
lt=$(awk '$1 == "lt" { print $2 }' config/policy.txt)
V=$(awk '$1 == "V" { print $2 }' config/policy.txt)
T=$((1 << lt))
: >requests.txt
for i in $(seq 1 "$n"); do
  name=$(printf 'r%02d' "$i")
  python3 -I -B -c 'import random, struct, sys
i, T, V, out = int(sys.argv[1]), int(sys.argv[2]), int(sys.argv[3]), sys.argv[4]
g = random.Random(i)
open(out, "wb").write(struct.pack("<%dI" % T, *[g.randrange(V) for _ in range(T)]))' "$i" "$T" "$V" "tmp/$name.tokens" || exit 1
  python3 -I -B "$FP_REPO/prover/tools/make_request.py" config/policy.txt "in/$name.req" "tmp/$name.tokens" $((T - 1)) "$T" >/dev/null || exit 1
  printf '%s seed=%s T=%s r=%s e=%s\n' "$name" "$i" "$T" $((T - 1)) "$T" >>requests.txt
done
cat requests.txt # into the run's stdout, which run_job.sh keeps as <run>.stdout
${gpu_run[@]+"${gpu_run[@]}"} env HOME="$work/home" TMPDIR="$work/tmp" "$BUILD/cp_prove" -isk "$work/isk" -in "$work/in" -out "$work/out" -in-step "$k" >cp_prove.log 2>&1
prc=$?
[ "$prc" = 0 ] || echo "calib_run.sh: cp_prove ended with status $prc" >&2
first_no='' all=yes
: >cp_verify.log
for i in $(seq 1 "$n"); do
  name=$(printf 'r%02d' "$i")
  printf '== %s\n' "$name" >>cp_verify.log
  if [ -f "out/$name.proof" ] && [ -f "out/$name.y" ]; then
    vs=0
    "$BUILD/cp_verify" config ivk "in/$name.req" "out/$name.y" "out/$name.proof" -id "$id" >"tmp/$name.verify" 2>&1 || vs=$?
    cat "tmp/$name.verify" >>cp_verify.log
    last=$(tail -n 1 "tmp/$name.verify")
    if [ "$vs" != 0 ] || [ "$last" != YES ]; then
      all=no
      [ -n "$first_no" ] || first_no="$name: ${last:-no output} (exit $vs)"
    fi
  else
    all=no
    echo "no response" >>cp_verify.log
    [ -n "$first_no" ] || first_no="$name: no response"
  fi
done
if [ "$prc" = 0 ] && [ "$all" = yes ]; then
  echo YES >>cp_verify.log
  exit 0
fi
printf 'NO: %s\n' "${first_no:-cp_prove ended with status $prc}" >>cp_verify.log
exit 1
