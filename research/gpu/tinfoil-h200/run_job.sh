#!/bin/bash
# run_job.sh: the H200 baseline job inside the prover container. Untested draft: its control flow is
# tested on CPU with mocked GPU programs (run_job_test.py); it has NOT been run on an H200.
#
#   run_job.sh serve   container entrypoint: starts the results server, runs the job once, finalises
#                      the results (success or failure), and keeps serving them until stopped
#   run_job.sh job     the job and its finalisation alone, in the foreground (exit status = the job's)
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
# A GPU sampler (nvidia-smi, 500 ms) runs for the whole job.
#
# Process structure: the job runs as its own process under `timeout` (FP_JOB_TIMEOUT), and every
# step under its own `timeout`. A failing step ends the job process only, never this shell, so in
# serve mode the results server outlives the job. When the job process has ended, for any reason
# (success, failure, timeout, signal), this shell finalises $FP_WORK/results in this order:
#   stop the sampler; export what a run still holds; record cgroup memory.peak; write the marker
#   (DONE or FAILED, written to a temporary name then renamed); append the last stages.log line;
#   write SHA256SUMS last (temporary name, then rename). Nothing in results/ changes after that.
# serve.py reports "finalising" until SHA256SUMS exists. Per-step exit status, seconds and whether
# the step timed out are in results/steps.tsv.
set -uo pipefail
FP_REPO=${FP_REPO:-/opt/flashprove}
FP_WORK=${FP_WORK:-/work}
FP_REPEATS=${FP_REPEATS:-10}
FP_ONBOX_BUILD=${FP_ONBOX_BUILD:-1}
FP_PORT=${FP_PORT:-8080}
FP_TIME=${FP_TIME:-/usr/bin/time}
FP_CC_PROBE=${FP_CC_PROBE:-/opt/fp-h200/cc_probe}
FP_ENV_DIR=${FP_ENV_DIR:-/opt/env}
FP_CGROUP=${FP_CGROUP:-/sys/fs/cgroup}
# Timeouts in seconds. FP_JOB_TIMEOUT bounds the whole job; the operator sets it so that the job
# ends before the restore cut-off of the approved window (RUNBOOK.md, "Window sheet").
FP_JOB_TIMEOUT=${FP_JOB_TIMEOUT:-3600}
FP_TIMEOUT_ENV=${FP_TIMEOUT_ENV:-120}
FP_TIMEOUT_COMPILER=${FP_TIMEOUT_COMPILER:-600}
FP_TIMEOUT_QUICKSTART=${FP_TIMEOUT_QUICKSTART:-2700}
FP_TIMEOUT_RUN=${FP_TIMEOUT_RUN:-600}
FP_KILL_GRACE=${FP_KILL_GRACE:-30}
HERE=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
SELF=$HERE/$(basename -- "${BASH_SOURCE[0]}")
R=$FP_WORK/results
ST=$FP_WORK/.runner # runner bookkeeping, never served (outside results/)
KIT=target_small_f2_roomy
RUN_REPO=$FP_REPO # the checkout whose run_target_example.sh the repeats use; set in job()

stage() { printf '%s STAGE %s\n' "$(date -u +%FT%TZ)" "$*" | tee -a "$R/stages.log"; }
fail() {
  stage "FAILED: $*"
  printf '%s\n' "$*" >"$ST/fail-reason"
  exit 1
}

# step <name> <timeout s> <command...>: runs an external command under timeout and records
# name, exit status, seconds and timed-out (yes/no) in steps.tsv. Returns the command's status.
# Each step's timeout runs in its own process group (GNU timeout does setpgid); its pid, which is
# that group's id, is kept in $ST/step.pgid so that finalise can stop the step's whole group if the
# job process itself is stopped while the step runs.
step() {
  local name=$1 t=$2 start=$SECONDS rc to=no pid
  shift 2
  timeout -k "$FP_KILL_GRACE" "$t" "$@" &
  pid=$!
  echo "$pid" >"$ST/step.pgid"
  wait "$pid"
  rc=$?
  rm -f "$ST/step.pgid"
  if [ "$rc" = 124 ] || [ "$rc" = 137 ]; then to=yes; fi
  printf '%s\t%s\t%s\t%s\n' "$name" "$rc" "$((SECONDS - start))" "$to" >>"$R/steps.tsv"
  return "$rc"
}

job() {
  umask 077
  stage job-start
  printf 'step\texit\tseconds\ttimed_out\n' >"$R/steps.tsv"
  # ---- 0. environment
  {
    step env-gpu-query "$FP_TIMEOUT_ENV" nvidia-smi --query-gpu=name,compute_cap,driver_version,memory.total,memory.used,mig.mode.current,power.limit,persistence_mode --format=csv
    step env-conf-compute-f "$FP_TIMEOUT_ENV" nvidia-smi conf-compute -f
    step env-conf-compute-grs "$FP_TIMEOUT_ENV" nvidia-smi conf-compute -grs
    timeout "$FP_TIMEOUT_ENV" nvidia-smi -q | grep -i -A3 'confidential\|conf compute'
  } >"$R/gpu-env.txt" 2>&1
  {
    echo "nproc $(nproc)"
    for f in cpu.max memory.max; do printf '%s: ' "$f"; cat "$FP_CGROUP/$f" 2>/dev/null || echo unavailable; done
    grep -m1 'model name' /proc/cpuinfo
    grep -m1 -ow sha_ni /proc/cpuinfo || echo 'no sha_ni'
    uname -r
    grep -E '^(NAME|VERSION)=' /etc/os-release
  } >"$R/host-env.txt" 2>&1
  cp "$FP_ENV_DIR"/* "$R/" 2>/dev/null
  step cc_probe "$FP_TIMEOUT_ENV" "$FP_CC_PROBE" >"$R/cc_probe.json" 2>&1
  stage env-recorded
  # The sampler: time, used MiB, power W, utilization %, for the whole job.
  nvidia-smi --query-gpu=timestamp,memory.used,power.draw,utilization.gpu --format=csv,noheader,nounits -lms 500 \
    >"$R/gpu-samples.csv" 2>/dev/null &
  sampler=$!
  echo "$sampler" >"$ST/sampler.pid"
  trap 'kill "$sampler" 2>/dev/null; wait "$sampler" 2>/dev/null' EXIT

  # ---- 1. the compiler check by value on this GPU
  step compiler_sample "$FP_TIMEOUT_COMPILER" env -C "$FP_REPO/prover/build" ./compiler_sample >"$R/compiler_sample.txt" 2>&1 ||
    fail "compiler_sample failed or timed out on this GPU (see compiler_sample.txt, steps.tsv): do not use these programs"
  grep -q 'values are the same on the GPU and on the CPU' "$R/compiler_sample.txt" ||
    fail "compiler_sample did not report equal values"
  stage compiler-sample-ok

  # ---- 2. the cold run
  local src=$FP_WORK/src build qrc qtop
  if [ "$FP_ONBOX_BUILD" = 1 ]; then
    mkdir -m 700 "$src" || fail "cannot create $src"
    cp -a "$FP_REPO/." "$src/" || fail "cannot copy the checkout"
    rm -rf "${src:?}/bin" "${src:?}/prover/build" # the quickstart builds them itself, as on the H100
    git -C "$src" status --porcelain >"$R/git-status-before.txt" 2>&1
    stage quickstart-start
    step quickstart "$FP_TIMEOUT_QUICKSTART" env -C "$src" TMPDIR="$FP_WORK" "$FP_TIME" -v bash examples/quickstart-gpu.sh \
      >"$R/quickstart.stdout" 2>"$R/whole-run.time"
    qrc=$?
    echo "$qrc" >"$R/quickstart.exit"
    stage "quickstart-exit $qrc"
    git -C "$src" status --porcelain >"$R/git-status-after.txt" 2>&1
    # The quickstart's own work directory: export its public bundle and logs BEFORE judging the
    # exit status, so that a failed quickstart's partial evidence is kept.
    qtop=$(sed -n 's/^WORK=//p' "$R/quickstart.stdout" | head -n 1)
    if [ -n "$qtop" ]; then
      printf 'quickstart\t%s\n' "$qtop" >"$ST/current"
      export_run quickstart "$qtop" || stage "quickstart export incomplete (work directory kept, not served)"
      rm -f "$ST/current"
    fi
    [ "$qrc" = 0 ] || fail "the quickstart did not end with exit 0 (quickstart.stdout, quickstart/)"
    build=$src/prover/build/hc RUN_REPO=$src
    sha256sum "$build/cp_commit" "$build/cp_prove" "$build/cp_verify" "$src/bin/cp_verify" >"$R/binaries.sha256"
  else
    build=$FP_REPO/prover/build/hc RUN_REPO=$FP_REPO
    sha256sum "$build/cp_commit" "$build/cp_prove" "$build/cp_verify" >"$R/binaries.sha256"
    echo "deviation: FP_ONBOX_BUILD=0, the image's prebuilt programs were used; no quickstart" >"$R/DEVIATION"
    one_run cold "$build" || fail "the cold run did not end with YES"
  fi

  # ---- 3. warm repeats
  local i
  for i in $(seq 1 "$FP_REPEATS"); do
    one_run "rep$i" "$build" || stage "rep$i did not end with YES (kept, reported)"
  done
  stage job-steps-finished
}

# one_run <name> <dir with the three programs>: one run of the small example under /usr/bin/time.
# The verdict is read from the work directory BEFORE export_run removes it.
one_run() {
  local name=$1 build=$2 top=$FP_WORK/$1 rc verdict
  mkdir -m 700 "$top" || return 1
  printf '%s\t%s\n' "$name" "$top/example" >"$ST/current"
  stage "$name-start"
  # GPU_RUN puts /usr/bin/time before cp_commit and cp_prove (prover/examples/run_target_example.sh).
  step "$name" "$FP_TIMEOUT_RUN" env -C "$RUN_REPO" BUILD="$build" GPU_RUN="$FP_TIME -o $R/$name.time -a -f %e|%M|%x|%U|%S|%C" \
    prover/examples/run_target_example.sh "$KIT" "$top/example" >"$R/$name.stdout" 2>&1
  rc=$?
  verdict=$(tail -n 1 "$top/example/cp_verify.log" 2>/dev/null)
  echo "$rc" >"$R/$name.exit"
  export_run "$name" "$top/example" || stage "$name export incomplete (work directory kept, not served)"
  rm -f "$ST/current"
  rmdir "$top" 2>/dev/null
  if [ "$rc" = 0 ] && [ "$verdict" = YES ]; then
    echo YES >"$R/$name.verdict"
    stage "$name-exit 0 YES"
    return 0
  fi
  printf '%s\n' "${verdict:-no cp_verify.log}" >"$R/$name.verdict"
  stage "$name-exit $rc ${verdict:-no cp_verify.log}"
  return 1
}

# export_run <name> <work dir>: copies the public files and logs, checks every copy, and only then
# removes the work directory, isk/ with it. Nothing below isk/ is ever copied. If a copy fails or
# differs, the work directory is kept (it is outside results/, so it is not served) and 1 returned.
export_run() {
  local name=$1 w=$2 d=$R/$1 ok=0 part log
  [ -d "$w" ] || return 0
  mkdir -p "$d/bundle" || return 1
  for part in config ivk in out; do
    [ -d "$w/$part" ] || continue
    cp -a "$w/$part" "$d/bundle/" && diff -r --no-dereference "$w/$part" "$d/bundle/$part" >/dev/null || ok=1
  done
  for log in cp_commit.log cp_prove.log cp_verify.log; do
    [ -f "$w/$log" ] || continue
    cp "$w/$log" "$d/" && cmp -s "$w/$log" "$d/$log" || ok=1
  done
  (cd "$w" && find . -maxdepth 3 -printf '%TY-%Tm-%TdT%TH:%TM:%TS %p\n' | sort) >"$d/file-times.txt" || ok=1
  [ "$ok" = 0 ] || return 1
  rm -rf "$w"
}

# finalise <job exit status>: see the header. Idempotent: does nothing once SHA256SUMS exists.
finalise() {
  local rc=$1 pid name w marker reason n
  [ -e "$R/SHA256SUMS" ] && return 0
  # A step still running in its own process group (the job process was stopped mid-step): stop the
  # group, TERM then KILL after FP_KILL_GRACE, and wait until it is gone, so nothing writes to
  # results/ after the checksums. The pid is checked to still be a timeout process first.
  if [ -s "$ST/step.pgid" ]; then
    pid=$(cat "$ST/step.pgid")
    if grep -qa timeout "/proc/$pid/cmdline" 2>/dev/null; then
      kill -TERM -- "-$pid" 2>/dev/null
      n=0
      while kill -0 -- "-$pid" 2>/dev/null && [ "$n" -lt "$FP_KILL_GRACE" ]; do sleep 1; n=$((n + 1)); done
      kill -KILL -- "-$pid" 2>/dev/null
      sleep 1 # SIGKILL is not deferred; this leaves time for the exits (zombies would still answer kill -0)
      stage "a step was still running at finalisation; its process group was stopped"
    fi
    rm -f "$ST/step.pgid"
  fi
  if [ -s "$ST/sampler.pid" ]; then
    pid=$(cat "$ST/sampler.pid")
    if grep -qa nvidia-smi "/proc/$pid/cmdline" 2>/dev/null; then kill "$pid" 2>/dev/null; fi
  fi
  if [ -s "$ST/current" ]; then # a run the job did not get to export (timeout or signal)
    IFS=$'\t' read -r name w <"$ST/current"
    if [ -n "${name:-}" ] && [ -d "${w:-}" ]; then
      export_run "$name" "$w" || stage "$name export incomplete at finalisation (work directory kept, not served)"
    fi
    rm -f "$ST/current"
  fi
  {
    for f in memory.peak memory.max memory.events cpu.max cpu.stat; do
      printf '== %s\n' "$f"
      cat "$FP_CGROUP/$f" 2>/dev/null || echo unavailable
    done
  } >"$R/cgroup-final.txt" 2>&1
  printf 'job\t%s\t%s\t%s\n' "$rc" "$SECONDS" "$([ "$rc" = 124 ] || [ "$rc" = 137 ] && echo yes || echo no)" >>"$R/steps.tsv"
  if [ "$rc" = 0 ]; then
    marker=DONE reason="job finished; per-run verdicts in <run>.verdict and steps.tsv"
  else
    marker=FAILED
    if [ -s "$ST/fail-reason" ]; then
      reason=$(cat "$ST/fail-reason")
    elif [ "$rc" = 124 ] || [ "$rc" = 137 ]; then
      reason="the job exceeded FP_JOB_TIMEOUT=${FP_JOB_TIMEOUT}s and was stopped"
    else
      reason="the job process ended with status $rc"
    fi
  fi
  [ -f "$FP_WORK/job.log" ] && cp "$FP_WORK/job.log" "$R/job.log" # snapshot; the live log is not served
  printf '%s\n' "$reason" >"$ST/marker.tmp" && mv "$ST/marker.tmp" "$R/$marker"
  if [ "$marker" = DONE ]; then stage job-done; else stage "job-failed (status $rc): $reason"; fi
  # Last: the checksums, over every regular file, written outside results/ and renamed in.
  (cd "$R" && find . -type f ! -name SHA256SUMS -print0 | sort -z | xargs -0 -r sha256sum) >"$ST/SHA256SUMS.tmp" &&
    mv "$ST/SHA256SUMS.tmp" "$R/SHA256SUMS"
}

# run_and_finalise: runs the job in its own process under FP_JOB_TIMEOUT, then finalises.
jobpid=
terminated=0
on_term() {
  terminated=1
  [ -n "$jobpid" ] && kill -TERM "$jobpid" 2>/dev/null
}
run_and_finalise() {
  local rc
  mkdir -p "$R" "$ST" || return 2
  chmod 700 "$ST"
  if [ -e "$R/DONE" ] || [ -e "$R/FAILED" ] || [ -e "$R/SHA256SUMS" ]; then
    echo "run_job: $R already holds a finished job" >&2
    return 2
  fi
  timeout -k "$FP_KILL_GRACE" "$FP_JOB_TIMEOUT" bash "$SELF" _job &
  jobpid=$!
  wait "$jobpid"
  rc=$?
  if [ "$terminated" = 1 ]; then # wait was interrupted by the signal: reap the job for real
    wait "$jobpid"
    rc=$?
    printf 'stopped by a signal to the runner\n' >"$ST/fail-reason"
    [ "$rc" = 0 ] && rc=143
  fi
  jobpid=
  finalise "$rc"
  return "$rc"
}

case "${1:-}" in
  serve)
    mkdir -p "$R" "$FP_WORK"
    python3 "$HERE/serve.py" "$R" "$FP_PORT" 2>"$FP_WORK/serve.log" &
    server=$!
    trap on_term TERM INT
    run_and_finalise >"$FP_WORK/job.log" 2>&1
    echo "run_job: job ended with status $?; results final, serving until stopped" >&2
    if [ "$terminated" = 1 ]; then
      kill "$server" 2>/dev/null
      exit 143
    fi
    trap 'kill "$server" 2>/dev/null; exit 143' TERM INT
    wait "$server"
    ;;
  job)
    trap on_term TERM INT
    run_and_finalise
    exit $?
    ;;
  _job) # internal: the job process itself
    mkdir -p "$R" "$ST"
    job
    ;;
  *)
    echo "usage: run_job.sh serve|job" >&2
    exit 2
    ;;
esac
