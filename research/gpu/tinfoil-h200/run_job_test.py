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
# run_target_example.sh <kit> <work dir>; MOCK_EXAMPLE: yes | no | crash | sleep
MOCK_EXAMPLE = """#!/bin/bash
w=$2
mkdir -p "$w"/config "$w"/ivk "$w"/in "$w"/out "$w"/isk
echo "public config" >"$w/config/c"
echo 284 >"$w/out/example.y"
echo "%s" >"$w/isk/seed"
echo "commitment ID: mock" >"$w/cp_commit.log"
case ${MOCK_EXAMPLE:-yes} in
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
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


def http(port, path):
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}{path}", timeout=5) as r:
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

        # 3. Review item 2: one repeat rejected by the verifier -> that run classed failed, job DONE.
        if want("repeat-rejected"):
            c = Case(base, runner, "repeat-rejected", onbox=0, repeats=1, example="no")
            p = c.run_job()
            check(c.name, "cold run NO -> job FAILED, exit 1", p.returncode == 1 and c.exists("FAILED") and not c.exists("DONE"))
            check(c.name, "cold classed NO", (c.read("cold.verdict") or "").startswith("NO"))
            check(c.name, "failed run's files exported", c.exists("cold/bundle/out/example.y") and c.exists("cold/cp_verify.log"))
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
                check(c.name, "partial quickstart evidence exported and served", "quickstart/cp_commit.log" in paths and "quickstart/bundle/out/example.y" in paths)
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
            check(c.name, "the interrupted run was exported", c.exists("cold/bundle/out/example.y"))
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
