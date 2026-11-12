#!/usr/bin/env python3
"""CPU test of run_job.sh's control flow with mocked GPU programs. No GPU, no network, no container.

The mocks stand in for nvidia-smi, compiler_sample, the quickstart, run_target_example.sh and the three
prover programs. They test the runner, not the prover: what is classed as success or failure, what is
exported (and that isk/ never is), that the results stay served after a failed job, that the
checksums verify after finalisation, and that the step and job timeouts end the job with its results.

usage: python3 run_job_test.py [--runner PATH_TO_run_job.sh] [--only NAME]   (exit 0 = all passed)
Needs bash, GNU coreutils (timeout, env -C, sha256sum), findutils, diffutils, git and python3.
"""
import argparse
import json
import os
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
SECRET = "SECRET-isk-must-never-be-exported"

MOCK_NVIDIA_SMI = """#!/bin/bash
case " $* " in
  *" -lms "*) while :; do echo "t, 1, 1, 0"; sleep 0.5; done ;;
  *) echo "mock nvidia-smi $*" ;;
esac
"""
# A stand-in for GNU time: drops its options (-v, -o F, -a, -f FMT) and runs the command.
MOCK_TIME = """#!/bin/bash
while [ $# -gt 0 ]; do
  case $1 in
    -o|-f) shift 2 ;;
    -*) shift ;;
    *) break ;;
  esac
done
exec "$@"
"""
COMPILER_OK = '#!/bin/bash\necho "values are the same on the GPU and on the CPU"\n'
COMPILER_FAIL = '#!/bin/bash\necho "values differ"\nexit 1\n'
# run_target_example.sh <kit> <work dir>; MOCK_EXAMPLE: yes | no | crash | sleep, for every run;
# MOCK_EXAMPLE_REP1 overrides it for the first warm repeat only (a real warm-repeat case).
MOCK_EXAMPLE = """#!/bin/bash
w=$2
mode=${MOCK_EXAMPLE:-yes}
case $w in */rep1/*) mode=${MOCK_EXAMPLE_REP1:-$mode} ;; esac
mkdir -p "$w"/config "$w"/ivk "$w"/in "$w"/out "$w"/isk
echo "public config" >"$w/config/c"
echo 284 >"$w/out/example.y"
echo "%s" >"$w/isk/seed"
echo "commitment ID: mock" >"$w/cp_commit.log"
case $mode in
  yes) echo "covered: mock" >"$w/cp_verify.log"; echo YES >>"$w/cp_verify.log" ;;
  no) echo "NO: mock rejection" >"$w/cp_verify.log"; exit 1 ;;
  crash) echo "cudaHostRegister failed (mock)" >"$w/cp_commit.log"; exit 1 ;;
  sleep) sleep 600 ;;
esac
exit 0
""" % SECRET
# The quickstart: builds (mock) programs, then runs the example in a new directory under TMPDIR.
MOCK_QUICKSTART = """#!/bin/bash
mkdir -p prover/build/hc bin
for p in cp_commit cp_prove cp_verify; do printf '#!/bin/bash\\n' >"prover/build/hc/$p"; chmod +x "prover/build/hc/$p"; done
cp prover/build/hc/cp_verify bin/cp_verify
w=$(mktemp -d "$TMPDIR/quick.XXXXXX")/example
echo "WORK=$w"
prover/examples/run_target_example.sh target_small_f2_roomy "$w"
"""


def script(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(text)
    os.chmod(path, 0o755)


def free_port():
    s = socket.socket()
    s.bind(("localhost", 0))
    p = s.getsockname()[1]
    s.close()
    return p


def http(port, path):
    try:
        with urllib.request.urlopen(f"http://localhost:{port}{path}", timeout=5) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()
    except OSError:
        return None, b""


class Case:
    def __init__(self, base, runner, name, onbox=0, repeats=2, compiler=COMPILER_OK, example="yes",
                 quickstart_exit=None, env=None):
        self.name, self.runner = name, runner
        self.root = os.path.join(base, name)
        self.repo = os.path.join(self.root, "repo")
        self.mock = os.path.join(self.root, "mock")
        self.work = os.path.join(self.root, "work")
        self.cg = os.path.join(self.root, "cgroup")
        os.makedirs(self.work)
        os.makedirs(self.cg)
        for f, v in (("memory.peak", "123456\n"), ("memory.max", "max\n"), ("cpu.max", "max 100000\n")):
            with open(os.path.join(self.cg, f), "w") as fh:
                fh.write(v)
        script(os.path.join(self.mock, "nvidia-smi"), MOCK_NVIDIA_SMI)
        script(os.path.join(self.mock, "time"), MOCK_TIME)
        # the compiler that FP_ONBOX_BUILD=1 needs (checked before any GPU step); a case can remove it
        script(os.path.join(self.mock, "nvcc"), "#!/bin/bash\necho mock nvcc\n")
        script(os.path.join(self.repo, "prover/build/compiler_sample"), compiler)
        for p in ("cp_commit", "cp_prove", "cp_verify"):
            script(os.path.join(self.repo, "prover/build/hc", p), "#!/bin/bash\n")
        script(os.path.join(self.repo, "prover/examples/run_target_example.sh"), MOCK_EXAMPLE)
        q = MOCK_QUICKSTART + ("exit %d\n" % quickstart_exit if quickstart_exit is not None else "")
        script(os.path.join(self.repo, "examples/quickstart-gpu.sh"), q)
        subprocess.run(["git", "init", "-q", self.repo], check=True)
        self.env = dict(os.environ)
        self.env.update({
            "PATH": self.mock + ":" + os.environ.get("PATH", "/usr/bin:/bin"),
            "FP_REPO": self.repo, "FP_WORK": self.work, "FP_REPEATS": str(repeats),
            "FP_ONBOX_BUILD": str(onbox), "FP_TIME": os.path.join(self.mock, "time"),
            "FP_CC_PROBE": os.path.join(self.mock, "no-cc-probe"), "FP_ENV_DIR": os.path.join(self.root, "no-env"),
            "FP_CGROUP": self.cg, "FP_KILL_GRACE": "2", "MOCK_EXAMPLE": example,
        })
        self.env.update(env or {})
        self.results = os.path.join(self.work, "results")

    def run_job(self, timeout=60):
        """Runs `run_job.sh job` in its own session; on the test's own deadline the whole session is
        killed (a runner without timeouts would otherwise hang the test) and returncode is None."""
        p = subprocess.Popen(["bash", self.runner, "job"], env=self.env, stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE, text=True, start_new_session=True)
        try:
            p.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            os.killpg(p.pid, signal.SIGKILL)  # the runner's own session only
            p.communicate()
            p.returncode = None
        return p

    def start_serve(self):
        self.port = free_port()
        self.env["FP_PORT"] = str(self.port)
        self.proc = subprocess.Popen(["bash", self.runner, "serve"], env=self.env, stdout=subprocess.DEVNULL,
                                     stderr=subprocess.DEVNULL, start_new_session=True)
        return self.proc

    def stop_serve(self):
        if self.proc.poll() is None:
            os.kill(self.proc.pid, signal.SIGTERM)  # by pid, the runner's own
            try:
                self.proc.wait(timeout=20)
            except subprocess.TimeoutExpired:
                pass
        try:  # anything the runner left behind in its own process group (e.g. an orphaned server)
            os.killpg(self.proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        self.proc.wait()

    def read(self, rel):
        p = os.path.join(self.results, rel)
        return open(p, errors="replace").read() if os.path.isfile(p) else None

    def exists(self, rel):
        return os.path.exists(os.path.join(self.results, rel))

    def sums_ok(self):
        if not self.exists("SHA256SUMS"):
            return False
        return subprocess.run(["sha256sum", "-c", "--quiet", "SHA256SUMS"], cwd=self.results,
                              capture_output=True).returncode == 0

    def no_secret(self):
        for base, dirs, names in os.walk(self.results):
            if "isk" in dirs:
                return False
            for n in names:
                with open(os.path.join(base, n), "rb") as f:
                    if SECRET.encode() in f.read():
                        return False
        return True

    def stages(self):
        return self.read("stages.log") or ""


def server_state(runner, results):
    """The state serve.py (next to the runner under test) reports for a results directory."""
    import importlib.util
    path = os.path.join(os.path.dirname(runner), "serve.py")
    spec = importlib.util.spec_from_file_location("serve_state_probe", path)
    argv = sys.argv
    sys.argv = [path, results, "0"]
    try:
        m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
        return m.state()
    finally:
        sys.argv = argv


# A sha256sum that fails when it is asked to hash the results (relative ./ paths), as when a file
# there cannot be read; anything else goes to the real one.
MOCK_SHA256SUM_FAIL = """#!/bin/bash
for a in "$@"; do case $a in ./*) echo "sha256sum: mock read error" >&2; exit 77 ;; esac; done
PATH=${PATH#*:} exec sha256sum "$@"
"""


def bounded(cmd, env, seconds):
    """Runs cmd in its own session; past the deadline that session is killed and returncode is None."""
    p = subprocess.Popen(cmd, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, start_new_session=True)
    try:
        p.stdout_text, p.stderr = p.communicate(timeout=seconds)
    except subprocess.TimeoutExpired:
        os.killpg(p.pid, signal.SIGKILL)  # this command's own session only
        p.stdout_text, p.stderr = p.communicate()
        p.returncode = None
    return p


def wait_for(pred, seconds):
    end = time.time() + seconds
    while time.time() < end:
        if pred():
            return True
        time.sleep(0.2)
    return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--runner", default=os.path.join(HERE, "run_job.sh"))
    ap.add_argument("--only")
    a = ap.parse_args()
    runner = os.path.abspath(a.runner)
    results = []

    def check(case, label, ok):
        results.append(("%s: %s" % (case, label), bool(ok)))

    with tempfile.TemporaryDirectory(prefix="fp-runjob-test-") as base:
        def want(n):
            return a.only is None or a.only == n

        # 1. Review item 2: prebuilt programs, cold run and 2 repeats succeed -> classed successful.
        if want("prebuilt-success"):
            c = Case(base, runner, "prebuilt-success", onbox=0, repeats=2)
            p = c.run_job()
            check(c.name, "job exits 0", p.returncode == 0)
            check(c.name, "DONE, no FAILED", c.exists("DONE") and not c.exists("FAILED"))
            check(c.name, "cold, rep1, rep2 classed YES", all((c.read(n + ".verdict") or "").strip() == "YES" for n in ("cold", "rep1", "rep2")))
            check(c.name, "no 'did not end with YES' stage", "did not end with YES" not in c.stages())
            check(c.name, "bundles exported", all(c.exists(n + "/bundle/out/example.y") and c.exists(n + "/cp_verify.log") for n in ("cold", "rep1", "rep2")))
            check(c.name, "SHA256SUMS verifies, stages.log included", c.sums_ok() and "./stages.log" in (c.read("SHA256SUMS") or ""))
            check(c.name, "job-done is the last stage line", c.stages().rstrip().splitlines()[-1].endswith("STAGE job-done"))
            check(c.name, "isk never exported", c.no_secret())
            check(c.name, "work dirs removed", not any(os.path.exists(os.path.join(c.work, n)) for n in ("cold", "rep1", "rep2")))
            check(c.name, "cgroup memory.peak recorded", "123456" in (c.read("cgroup-final.txt") or ""))
            steps = c.read("steps.tsv") or ""
            check(c.name, "steps.tsv has every step with status", all(("\n%s\t0\t" % s) in steps for s in ("compiler_sample", "cold", "rep1", "rep2", "job")))

        # 2. Review item 2: on-box quickstart then 2 repeats, all succeed.
        if want("quickstart-success"):
            c = Case(base, runner, "quickstart-success", onbox=1, repeats=2)
            p = c.run_job()
            check(c.name, "job exits 0 with DONE", p.returncode == 0 and c.exists("DONE"))
            check(c.name, "rep1, rep2 classed YES", all((c.read(n + ".verdict") or "").strip() == "YES" for n in ("rep1", "rep2")))
            check(c.name, "quickstart bundle exported", c.exists("quickstart/bundle/out/example.y"))
            check(c.name, "SHA256SUMS verifies", c.sums_ok())
            check(c.name, "isk never exported", c.no_secret())

        # 2b. PR #141 review round 1: a runtime-stage image (no compiler) started with FP_ONBOX_BUILD=1, or a
        # value other than 0/1, ends FAILED before any GPU step (here: FP_NVCC names no program, as in
        # the runtime image, where nvcc is absent).
        if want("onbox-no-compiler"):
            c = Case(base, runner, "onbox-no-compiler", onbox=1, repeats=1, env={"FP_NVCC": "fp-h200-no-such-nvcc"})
            p = c.run_job()
            steps = c.read("steps.tsv") or ""
            check(c.name, "FP_ONBOX_BUILD=1 without a compiler: FAILED, exit 1, reason names it",
                  p.returncode == 1 and c.exists("FAILED") and "FP_ONBOX_BUILD=1 needs the compiler" in (c.read("FAILED") or ""))
            check(c.name, "before any GPU step (no cc_probe, compiler_sample, quickstart)",
                  not any(s in steps for s in ("cc_probe", "compiler_sample", "quickstart")) and c.sums_ok())
            c = Case(base, runner, "onbox-bad-value", onbox=0, repeats=1, env={"FP_ONBOX_BUILD": "yes"})
            p = c.run_job()
            check(c.name, "FP_ONBOX_BUILD=yes refused before any GPU step",
                  p.returncode == 1 and "FP_ONBOX_BUILD must be 0 or 1" in (c.read("FAILED") or "")
                  and "compiler_sample" not in (c.read("steps.tsv") or ""))
            c = Case(base, runner, "onbox-0-no-compiler", onbox=0, repeats=1, env={"FP_NVCC": "fp-h200-no-such-nvcc"})
            p = c.run_job()
            check(c.name, "FP_ONBOX_BUILD=0 needs no compiler: DONE", p.returncode == 0 and c.exists("DONE"))

        # 3. Review item 2: one repeat rejected by the verifier -> that run classed failed, job DONE.
        if want("repeat-rejected"):
            c = Case(base, runner, "repeat-rejected", onbox=0, repeats=1, example="no")
            p = c.run_job()
            check(c.name, "cold run NO -> job FAILED, exit 1", p.returncode == 1 and c.exists("FAILED") and not c.exists("DONE"))
            check(c.name, "cold classed NO", (c.read("cold.verdict") or "").startswith("NO"))
            check(c.name, "failed run's public files and commit log exported", c.exists("cold/bundle/config/c") and c.exists("cold/cp_commit.log"))
            # fix2, duty 6: a response cp_verify did not accept is given to no one.
            check(c.name, "rejected run: out/ and cp_verify.log withheld, listed in withheld.txt",
                  not c.exists("cold/bundle/out") and not c.exists("cold/cp_verify.log") and "duty 6" in (c.read("cold/withheld.txt") or ""))
            check(c.name, "SHA256SUMS verifies", c.sums_ok())

        # 4. Review item 1: compiler failure in serve mode -> server stays up and serves the failure.
        if want("compiler-fail-serve"):
            c = Case(base, runner, "compiler-fail-serve", onbox=0, compiler=COMPILER_FAIL)
            c.start_serve()
            try:
                up = wait_for(lambda: c.exists("SHA256SUMS"), 30)
                time.sleep(1)
                check(c.name, "finalised (FAILED + SHA256SUMS)", up and c.exists("FAILED"))
                check(c.name, "runner still running after the job failed", c.proc.poll() is None)
                code, body = http(c.port, "/status")
                st = json.loads(body) if code == 200 else {}
                check(c.name, "/status says failed", st.get("state") == "failed")
                code, body = http(c.port, "/files")
                paths = [f["path"] for f in json.loads(body)] if code == 200 else []
                check(c.name, "/files lists the failure's logs", "compiler_sample.txt" in paths and "FAILED" in paths and "job.log" in paths)
                code, body = http(c.port, "/results.tar.gz")
                check(c.name, "/results.tar.gz served", code == 200 and len(body) > 0)
                check(c.name, "SHA256SUMS verifies", c.sums_ok())
            finally:
                c.stop_serve()

        # 5. Review item 1: failed quickstart (the predicted CC-On refusal path) in serve mode.
        if want("quickstart-fail-serve"):
            c = Case(base, runner, "quickstart-fail-serve", onbox=1, example="crash")
            c.start_serve()
            try:
                up = wait_for(lambda: c.exists("SHA256SUMS"), 30)
                time.sleep(1)
                check(c.name, "finalised FAILED", up and c.exists("FAILED"))
                check(c.name, "runner still running", c.proc.poll() is None)
                code, body = http(c.port, "/status")
                check(c.name, "/status says failed", code == 200 and json.loads(body)["state"] == "failed")
                code, body = http(c.port, "/files")
                paths = [f["path"] for f in json.loads(body)] if code == 200 else []
                check(c.name, "partial quickstart evidence exported and served", "quickstart/cp_commit.log" in paths and "quickstart/bundle/config/c" in paths)
                check(c.name, "failed quickstart: out/ withheld (duty 6)", not any(x.startswith("quickstart/bundle/out") for x in paths) and "quickstart/withheld.txt" in paths)
                check(c.name, "the failure's own log is served", "cudaHostRegister failed (mock)" in (c.read("quickstart/cp_commit.log") or ""))
                check(c.name, "isk never exported", c.no_secret())
                check(c.name, "SHA256SUMS verifies", c.sums_ok())
            finally:
                c.stop_serve()

        # 6. Step timeout: a hung repeat is stopped, recorded as timed out, and the job goes on.
        if want("step-timeout"):
            c = Case(base, runner, "step-timeout", onbox=0, repeats=1, example="sleep", env={"FP_TIMEOUT_RUN": "2"})
            p = c.run_job(timeout=30)
            steps = c.read("steps.tsv") or ""
            check(c.name, "cold run timed out -> FAILED", p.returncode == 1 and c.exists("FAILED"))
            check(c.name, "steps.tsv marks the timeout", "\ncold\t124\t" in steps and steps.split("\ncold\t", 1)[-1].split("\n", 1)[0].endswith("yes"))
            check(c.name, "SHA256SUMS verifies", c.sums_ok())
            check(c.name, "isk never exported", c.no_secret())

        # 7. Whole-job timeout: the job is stopped mid-step; finalisation still exports and seals.
        if want("job-timeout"):
            c = Case(base, runner, "job-timeout", onbox=0, repeats=1, example="sleep", env={"FP_JOB_TIMEOUT": "3"})
            t0 = time.time()
            p = c.run_job(timeout=30)
            check(c.name, "ended within the job timeout plus grace", p.returncode is not None and time.time() - t0 < 20)
            check(c.name, "FAILED with the timeout reason", c.exists("FAILED") and "FP_JOB_TIMEOUT" in (c.read("FAILED") or ""))
            check(c.name, "the interrupted run was exported", c.exists("cold/bundle/config/c") and c.exists("cold/cp_commit.log"))
            check(c.name, "the interrupted run's out/ withheld (never verified)", not c.exists("cold/bundle/out"))
            # fix2: the interrupted step gets its own row, written at finalisation.
            check(c.name, "steps.tsv records the interrupted step", "\ncold\tinterrupted\t" in (c.read("steps.tsv") or ""))
            check(c.name, "isk never exported", c.no_secret())
            time.sleep(1)
            check(c.name, "SHA256SUMS still verifies a second later", c.sums_ok())

        # 8. Signal to the runner in serve mode: finalises, then exits.
        if want("serve-sigterm"):
            c = Case(base, runner, "serve-sigterm", onbox=0, repeats=1, example="sleep")
            c.start_serve()
            try:
                wait_for(lambda: "cold-start" in c.stages(), 20)
                os.kill(c.proc.pid, signal.SIGTERM)
                try:
                    c.proc.wait(timeout=30)
                except subprocess.TimeoutExpired:
                    pass
                check(c.name, "runner exited after SIGTERM", c.proc.poll() is not None)
                check(c.name, "FAILED + SHA256SUMS written", c.exists("FAILED") and c.sums_ok())
                check(c.name, "isk never exported", c.no_secret())
            finally:
                c.stop_serve()

        # ---- fix2 cases (PR #69 second re-reviews) ----
        # astra 1: whole-job timeout DURING the default on-box quickstart; its partial evidence lives
        # outside results/ and must be exported at finalisation.
        if want("quickstart-job-timeout"):
            c = Case(base, runner, "quickstart-job-timeout", onbox=1, repeats=0, example="sleep", env={"FP_JOB_TIMEOUT": "3"})
            p = c.run_job(timeout=40)
            check(c.name, "job stopped by the timeout, FAILED", p.returncode == 124 and c.exists("FAILED") and not c.exists("DONE"))
            check(c.name, "quickstart's partial evidence exported", c.exists("quickstart/cp_commit.log") and c.exists("quickstart/bundle/config/c"))
            check(c.name, "its unverified out/ withheld", not c.exists("quickstart/bundle/out"))
            check(c.name, "steps.tsv records the interrupted quickstart", "\nquickstart\tinterrupted\t" in (c.read("steps.tsv") or ""))
            check(c.name, "isk never exported", c.no_secret())
            check(c.name, "SHA256SUMS verifies", c.sums_ok())

        # astra 2 / opus should-fix 1: finalisation failures must not end as DONE.
        if want("seal-hash-fails"):  # the final manifest's hashing fails
            c = Case(base, runner, "seal-hash-fails", onbox=0, repeats=0)
            script(os.path.join(c.mock, "sha256sum"), MOCK_SHA256SUM_FAIL)
            p = c.run_job()
            check(c.name, "job exits nonzero", p.returncode not in (0, None))
            check(c.name, "no DONE; FAILED and SEAL-FAILED written", not c.exists("DONE") and c.exists("FAILED") and c.exists("SEAL-FAILED"))
            check(c.name, "a stage line names the failed step", "finalisation failed at: checksums" in c.stages())
            check(c.name, "/status says failed, never done or finalising forever", server_state(runner, c.results) == "failed")
        if want("seal-unreadable-file"):  # opus: an unreadable file in results/
            mk = '#!/bin/bash\necho "values are the same on the GPU and on the CPU"\n: >"$FP_WORK/results/unreadable"; chmod 000 "$FP_WORK/results/unreadable"\n'
            c = Case(base, runner, "seal-unreadable-file", onbox=0, repeats=0, compiler=mk)
            p = c.run_job()
            if os.geteuid() == 0:
                check(c.name, "skipped as root (mode 000 is readable)", True)
            else:
                check(c.name, "job exits nonzero, no DONE, SEAL-FAILED", p.returncode not in (0, None) and not c.exists("DONE") and c.exists("SEAL-FAILED"))
                check(c.name, "/status says failed", server_state(runner, c.results) == "failed")
            os.chmod(os.path.join(c.results, "unreadable"), 0o600)
        if want("seal-write-fails"):  # the checksum file cannot be written
            mk = '#!/bin/bash\necho "values are the same on the GPU and on the CPU"\nmkdir -p "$FP_WORK/.runner/SHA256SUMS.tmp"\n'
            c = Case(base, runner, "seal-write-fails", onbox=0, repeats=0, compiler=mk)
            p = c.run_job()
            check(c.name, "job exits nonzero, no DONE, SEAL-FAILED", p.returncode not in (0, None) and not c.exists("DONE") and c.exists("SEAL-FAILED") and c.exists("FAILED"))
            check(c.name, "a stage line names the failed step", "finalisation failed at: checksums" in c.stages())
            check(c.name, "/status says failed", server_state(runner, c.results) == "failed")
        if want("marker-write-fails"):  # the marker cannot be put in place (a directory named DONE)
            mk = '#!/bin/bash\necho "values are the same on the GPU and on the CPU"\nmkdir -p "$FP_WORK/results/DONE"\n'
            c = Case(base, runner, "marker-write-fails", onbox=0, repeats=0, compiler=mk)
            p = c.run_job()
            check(c.name, "job exits nonzero", p.returncode not in (0, None))
            check(c.name, "FAILED and SEAL-FAILED written, stage line names the marker",
                  os.path.isfile(os.path.join(c.results, "FAILED")) and c.exists("SEAL-FAILED") and "finalisation failed at: marker" in c.stages())
            check(c.name, "/status says failed", server_state(runner, c.results) == "failed")
        if want("export-fails"):  # astra: results/cold/bundle is a regular file
            c = Case(base, runner, "export-fails", onbox=0, repeats=0)
            os.makedirs(os.path.join(c.results, "cold"))
            with open(os.path.join(c.results, "cold", "bundle"), "w") as fh:
                fh.write("collision")
            p = c.run_job()
            check(c.name, "job exits nonzero (3), FAILED, no DONE", p.returncode == 3 and c.exists("FAILED") and not c.exists("DONE"))
            check(c.name, "FAILED and a stage line name the export", "export" in (c.read("FAILED") or "") and "cold export failed" in c.stages())
            check(c.name, "source kept outside results/", os.path.exists(os.path.join(c.work, "cold", "example", "cp_commit.log")))
            check(c.name, "SHA256SUMS verifies; /status says failed", c.sums_ok() and server_state(runner, c.results) == "failed")

        # astra / opus should-fix 3: one job per work directory.
        if want("lock-second-job"):
            slow = '#!/bin/bash\nsleep 3\necho "values are the same on the GPU and on the CPU"\n'
            c = Case(base, runner, "lock-second-job", onbox=0, repeats=1, compiler=slow)
            first = subprocess.Popen(["bash", runner, "job"], env=c.env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
            try:
                wait_for(lambda: "job-start" in c.stages(), 20)
                before = sorted(os.listdir(c.results))
                second = bounded(["bash", runner, "job"], c.env, 20)
                serve2 = bounded(["bash", runner, "serve"], dict(c.env, FP_PORT=str(free_port())), 10)
                after = sorted(os.listdir(c.results))
                check(c.name, "second job refused, exit 2, clear message", second.returncode == 2 and "another job holds the lock" in second.stderr)
                check(c.name, "second serve refused, exit 2", serve2.returncode == 2 and "another job holds the lock" in serve2.stderr)
                check(c.name, "refusals touched nothing", before == after and c.stages().count("STAGE job-start") == 1)
                first.wait(timeout=60)
            finally:
                if first.poll() is None:
                    os.killpg(first.pid, signal.SIGKILL)
                    first.wait()
            check(c.name, "first job DONE, exit 0, no FAILED, one job row", first.returncode == 0 and c.exists("DONE") and not c.exists("FAILED")
                  and (c.read("steps.tsv") or "").count("\njob\t") == 1)
            check(c.name, "first job's SHA256SUMS verifies", c.sums_ok())

        # astra should-fix: real warm-repeat cases (the cold run succeeds, the first repeat does not).
        if want("warm-repeat-rejected"):
            c = Case(base, runner, "warm-repeat-rejected", onbox=0, repeats=2, env={"MOCK_EXAMPLE_REP1": "no"})
            p = c.run_job()
            check(c.name, "job DONE, exit 0 (a repeat's NO is reported, not fatal)", p.returncode == 0 and c.exists("DONE"))
            check(c.name, "cold and rep2 YES, rep1 NO", (c.read("cold.verdict") or "").strip() == "YES" and (c.read("rep2.verdict") or "").strip() == "YES"
                  and (c.read("rep1.verdict") or "").startswith("NO"))
            check(c.name, "rep1 stage says not YES", "rep1 did not end with YES" in c.stages())
            check(c.name, "rep1 out/ and cp_verify.log withheld, rep2's exported", not c.exists("rep1/bundle/out") and not c.exists("rep1/cp_verify.log")
                  and c.exists("rep2/bundle/out/example.y") and c.exists("rep2/cp_verify.log"))
            check(c.name, "SHA256SUMS verifies", c.sums_ok())
        if want("warm-repeat-timeout"):
            c = Case(base, runner, "warm-repeat-timeout", onbox=0, repeats=2, env={"MOCK_EXAMPLE_REP1": "sleep", "FP_TIMEOUT_RUN": "2"})
            p = c.run_job(timeout=40)
            steps = c.read("steps.tsv") or ""
            check(c.name, "job DONE, exit 0", p.returncode == 0 and c.exists("DONE"))
            check(c.name, "rep1 recorded 124 timed out, cold and rep2 exit 0", "\nrep1\t124\t" in steps and "\ncold\t0\t" in steps and "\nrep2\t0\t" in steps)
            check(c.name, "rep1 out/ withheld, its commit log exported", not c.exists("rep1/bundle/out") and c.exists("rep1/cp_commit.log"))
            check(c.name, "SHA256SUMS verifies, isk never exported", c.sums_ok() and c.no_secret())

        # A refusal to reuse a finished results directory.
        if want("no-reuse"):
            c = Case(base, runner, "no-reuse", onbox=0, repeats=0)
            c.run_job()
            p = c.run_job()
            check(c.name, "second run refused with exit 2", p.returncode == 2)
            check(c.name, "first run's checksums intact", c.sums_ok())

    for name, ok in results:
        print(("PASS " if ok else "FAIL ") + name)
    print("%d of %d checks passed" % (sum(ok for _, ok in results), len(results)))
    return 0 if results and all(ok for _, ok in results) else 1


if __name__ == "__main__":
    sys.exit(main())
