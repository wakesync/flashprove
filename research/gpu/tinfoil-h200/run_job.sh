#!/bin/bash
# run_job.sh: the H200 baseline job inside the prover container. Phase 1: written and checked with
# bash -n and shellcheck; NOT run on an H200.
#
#   run_job.sh serve   container entrypoint: starts the results server, then the job, once
#   run_job.sh job     the job alone (as in the container, but in the foreground)
#
# The job follows the H100 receipts' protocol (research/gpu/README.md, research/gpu/replication-1/),
# as registered in experiments/20261110-43-h200-bringup/PREREG.md:
#   0. environment record: nvidia-smi, conf-compute state, cgroup limits, toolkit, cc_probe
#   1. the GPU compiler check by value (compiler_sample), on this GPU
#   2. one cold run: examples/quickstart-gpu.sh, unmodified, in a writable copy of the pinned checkout
#      (FP_ONBOX_BUILD=1, the default). With FP_ONBOX_BUILD=0 the image's prebuilt programs are used
#      and the cold run is run_target_example.sh alone (a deviation from the PREREG; record it).
#   3. FP_REPEATS (default 10) warm runs of run_target_example.sh target_small_f2_roomy, each in a new
#      work directory with a new commitment, cp_commit and cp_prove under /usr/bin/time (GPU_RUN)
#   4. export: for each run, only the public bundle (config/, ivk/, in/, out/) and the logs. isk/
#      (the provider's secret side) is never exported and is removed with the work directory.
# A GPU sampler (nvidia-smi, 500 ms) runs for the whole job. Results go to $FP_WORK/results, which
# serve.py offers read-only; DONE or FAILED marks the end.
set -uo pipefail
FP_REPO=${FP_REPO:-/opt/flashprove}
FP_WORK=${FP_WORK:-/work}
FP_REPEATS=${FP_REPEATS:-10}
FP_ONBOX_BUILD=${FP_ONBOX_BUILD:-1}
HERE=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
R=$FP_WORK/results
KIT=target_small_f2_roomy
RUN_REPO=$FP_REPO # the checkout whose run_target_example.sh the repeats use; set in job()

stage() { printf '%s STAGE %s\n' "$(date -u +%FT%TZ)" "$*" | tee -a "$R/stages.log"; }
fail() {
  stage "FAILED: $*"
  printf '%s\n' "$*" >"$R/FAILED"
  exit 1
}

job() {
  umask 077
  mkdir -p "$R" || exit 2
  [ ! -e "$R/DONE" ] && [ ! -e "$R/FAILED" ] || { echo "run_job: $R already holds a finished job" >&2; exit 2; }
  stage job-start
  # ---- 0. environment
  {
    nvidia-smi --query-gpu=name,compute_cap,driver_version,memory.total,memory.used,mig.mode.current,power.limit,persistence_mode --format=csv
    nvidia-smi conf-compute -f 2>&1 || true
    nvidia-smi conf-compute -grs 2>&1 || true
    nvidia-smi -q 2>&1 | grep -i -A3 'confidential\|conf compute' || true
  } >"$R/gpu-env.txt" 2>&1
  {
    echo "nproc $(nproc)"
    cat /sys/fs/cgroup/cpu.max /sys/fs/cgroup/memory.max 2>/dev/null
    grep -m1 'model name' /proc/cpuinfo
    grep -m1 -ow sha_ni /proc/cpuinfo || echo 'no sha_ni'
    uname -r
    cat /etc/os-release | grep -E '^(NAME|VERSION)='
  } >"$R/host-env.txt" 2>&1
  cp /opt/env/* "$R/" 2>/dev/null
  /opt/fp-h200/cc_probe >"$R/cc_probe.json" 2>&1 || true
  stage env-recorded
  # The sampler: time, used MiB, power W, utilization %, for the whole job.
  nvidia-smi --query-gpu=timestamp,memory.used,power.draw,utilization.gpu --format=csv,noheader,nounits -lms 500 \
    >"$R/gpu-samples.csv" 2>/dev/null &
  sampler=$!
  trap 'kill "$sampler" 2>/dev/null' EXIT

  # ---- 1. the compiler check by value on this GPU
  (cd "$FP_REPO/prover/build" && ./compiler_sample) >"$R/compiler_sample.txt" 2>&1 ||
    fail "compiler_sample failed on this GPU (see compiler_sample.txt): do not use these programs"
  grep -q 'values are the same on the GPU and on the CPU' "$R/compiler_sample.txt" ||
    fail "compiler_sample did not report equal values"
  stage compiler-sample-ok

  # ---- 2. the cold run
  local src=$FP_WORK/src build
  if [ "$FP_ONBOX_BUILD" = 1 ]; then
    mkdir -m 700 "$src" || fail "cannot create $src"
    cp -a "$FP_REPO/." "$src/" || fail "cannot copy the checkout"
    rm -rf "${src:?}/bin" "${src:?}/prover/build" # the quickstart builds them itself, as on the H100
    git -C "$src" status --porcelain >"$R/git-status-before.txt" 2>&1
    stage quickstart-start
    (cd "$src" && TMPDIR=$FP_WORK /usr/bin/time -v bash examples/quickstart-gpu.sh) \
      >"$R/quickstart.stdout" 2>"$R/whole-run.time"
    echo $? >"$R/quickstart.exit"
    stage "quickstart-exit $(cat "$R/quickstart.exit")"
    git -C "$src" status --porcelain >"$R/git-status-after.txt" 2>&1
    [ "$(cat "$R/quickstart.exit")" = 0 ] || fail "the quickstart did not end with exit 0 (quickstart.stdout)"
    build=$src/prover/build/hc RUN_REPO=$src
    sha256sum "$build/cp_commit" "$build/cp_prove" "$build/cp_verify" "$src/bin/cp_verify" >"$R/binaries.sha256"
    # The quickstart's own work directory: export its public bundle like the repeats'.
    local qtop
    qtop=$(sed -n 's/^WORK=//p' "$R/quickstart.stdout" | head -n 1)
    [ -n "$qtop" ] && export_run quickstart "$qtop"
  else
    build=$FP_REPO/prover/build/hc RUN_REPO=$FP_REPO
    sha256sum "$build/cp_commit" "$build/cp_prove" "$build/cp_verify" >"$R/binaries.sha256"
    echo "deviation: FP_ONBOX_BUILD=0, the image's prebuilt programs were used; no quickstart" >"$R/DEVIATION"
    one_run cold "$build" || fail "the cold run failed"
  fi

  # ---- 3. warm repeats
  local i
  for i in $(seq 1 "$FP_REPEATS"); do
    one_run "rep$i" "$build" || stage "rep$i did not end with YES (kept, reported)"
  done
  kill "$sampler" 2>/dev/null
  # shellcheck disable=SC2094 # find skips both names, so the list never reads the file being written
  (cd "$R" && find . -type f ! -name SHA256SUMS ! -name SHA256SUMS.tmp -print0 | sort -z | xargs -0 sha256sum >SHA256SUMS.tmp && mv SHA256SUMS.tmp SHA256SUMS)
  stage job-done
  touch "$R/DONE"
}

# one_run <name> <dir with the three programs>: one run of the small example under /usr/bin/time.
one_run() {
  local name=$1 build=$2 top=$FP_WORK/$1 rc
  mkdir -m 700 "$top" || return 1
  stage "$name-start"
  # GPU_RUN puts /usr/bin/time before cp_commit and cp_prove (prover/examples/run_target_example.sh).
  (cd "$RUN_REPO" && BUILD=$build GPU_RUN="/usr/bin/time -o $R/$name.time -a -f %e|%M|%x|%U|%S|%C" \
    prover/examples/run_target_example.sh "$KIT" "$top/example") >"$R/$name.stdout" 2>&1
  rc=$?
  echo "$rc" >"$R/$name.exit"
  stage "$name-exit $rc"
  export_run "$name" "$top/example"
  [ "$rc" = 0 ] && [ "$(tail -n 1 "$top/example/cp_verify.log" 2>/dev/null)" = YES ]
}

# export_run <name> <work dir>: keeps the public files and logs, then removes the work directory,
# isk/ with it. Nothing below isk/ is ever copied.
export_run() {
  local name=$1 w=$2 d=$R/$1
  [ -d "$w" ] || return 0
  mkdir -p "$d/bundle"
  for part in config ivk in out; do [ -d "$w/$part" ] && cp -a "$w/$part" "$d/bundle/"; done
  for log in cp_commit.log cp_prove.log cp_verify.log; do [ -f "$w/$log" ] && cp "$w/$log" "$d/"; done
  (cd "$w" && find . -maxdepth 3 -printf '%TY-%Tm-%TdT%TH:%TM:%TS %p\n' | sort) >"$d/file-times.txt"
  rm -rf "$w"
}

case "${1:-}" in
  serve)
    mkdir -p "$R"
    python3 "$HERE/serve.py" "$R" &
    job >"$FP_WORK/job.log" 2>&1
    wait
    ;;
  job) job ;;
  *)
    echo "usage: run_job.sh serve|job" >&2
    exit 2
    ;;
esac
