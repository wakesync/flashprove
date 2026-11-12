#!/usr/bin/env python3
"""CPU test of run_job.sh's calibration step (issue #140, experiments/20261112-7-h200-dense-calibration).

Uses run_job_test.py's harness (its Case class and mocks of nvidia-smi, GNU time, compiler_sample and
the example), runs the REAL calib_run.sh and stamp.sh, and puts the mocks in calib_test_mocks/ in
place of cp_commit, cp_prove and cp_verify. It tests the runner, not the prover: order (warm repeats,
then each configuration smallest first), that every response of a batch is exported only when every
one was accepted (duty 6), that isk/ never is, the per-run windows of cp_commit and cp_prove, the
sampler interval, step and job timeouts during a calibration run, a cp_commit refusal (not replaced),
and that a malformed FP_CALIB ends the job FAILED before any GPU step. With FP_CALIB empty the job
is the #43 job (run_job_test.py's 87 checks test that).

usage: python3 run_job_calib_test.py [--runner PATH_TO_run_job.sh] [--only NAME]   (exit 0 = all passed)
"""
import argparse
import os
import shutil
import stat
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import run_job_test as rj  # noqa: E402

MOCKS = os.path.join(HERE, "calib_test_mocks")
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))


def calib_case(base, runner, name, calib, env=None, repeats=1):
    e = {"FP_CALIB": calib}
    e.update(env or {})
    c = rj.Case(base, runner, name, onbox=0, repeats=repeats, env=e)
    for p in ("cp_commit", "cp_prove", "cp_verify"):
        dst = os.path.join(c.repo, "prover", "build", "hc", p)
        shutil.copy(os.path.join(MOCKS, p), dst)
        os.chmod(dst, os.stat(dst).st_mode | stat.S_IXUSR)
    os.makedirs(os.path.join(c.repo, "prover", "tools"))
    shutil.copy(os.path.join(ROOT, "prover", "tools", "make_request.py"), os.path.join(c.repo, "prover", "tools"))
    cal = os.path.join(c.root, "calib")
    for cid, lt in (("C1", 6), ("C2", 7)):
        d = os.path.join(cal, cid)
        os.makedirs(d)
        with open(os.path.join(d, "policy.txt"), "w") as f:
            f.write("version H821\nlt %d\nV 512\n" % lt)
        for x in ("KL.bin", "layout.txt"):
            open(os.path.join(d, x), "w").close()
    c.env["FP_CALIB_DIR"] = cal
    c.env["FP_CALIB_RUNNER"] = os.path.join(HERE, "calib_run.sh")
    c.env["FP_STAMP"] = os.path.join(HERE, "stamp.sh")
    return c


def windows(c, run):
    rows = [line.split() for line in (c.read(run + ".windows") or "").splitlines()]
    return [r[0] for r in rows if len(r) == 4 and float(r[2]) >= float(r[1])]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--runner", default=os.path.join(HERE, "run_job.sh"))
    ap.add_argument("--only")
    a = ap.parse_args()
    runner = os.path.abspath(a.runner)
    results = []

    def check(case, label, ok):
        results.append(("%s: %s" % (case, label), bool(ok)))

    with tempfile.TemporaryDirectory(prefix="fp-runjob-calib-test-") as base:
        def want(n):
            return a.only is None or a.only == n

        if want("calib-success"):
            c = calib_case(base, runner, "calib-success", "C1:2:2:2:30 C2:3:1:1:30", env={"FP_SAMPLE_MS": "100"})
            seen = os.path.join(c.root, "smi-args")
            rj.script(os.path.join(c.mock, "nvidia-smi"),
                      rj.MOCK_NVIDIA_SMI.replace("case ", 'echo "$*" >>%s\ncase ' % seen, 1))
            p = c.run_job()
            steps = c.read("steps.tsv") or ""
            check(c.name, "job exits 0 with DONE", p.returncode == 0 and c.exists("DONE") and not c.exists("FAILED"))
            check(c.name, "C1-1, C1-2, C2-1 classed YES",
                  all((c.read(n + ".verdict") or "").strip() == "YES" for n in ("C1-1", "C1-2", "C2-1")))
            check(c.name, "after the warm repeats, smallest first",
                  0 < steps.find("\nrep1\t") < steps.find("\nC1-1\t") < steps.find("\nC1-2\t") < steps.find("\nC2-1\t")
                  and "\nC2-1\t0\t" in steps)
            check(c.name, "every response of the batch exported (2 and 3 requests)",
                  c.exists("C1-1/bundle/out/r02.proof") and c.exists("C2-1/bundle/out/r03.y")
                  and not c.exists("C2-1/bundle/out/r04.y") and c.exists("C2-1/cp_verify.log"))
            check(c.name, "-in-step passed to cp_prove",
                  "in-step 2" in (c.read("C1-1/cp_prove.log") or "") and "in-step 1" in (c.read("C2-1/cp_prove.log") or ""))
            check(c.name, "cp_commit and cp_prove windows stamped per run",
                  windows(c, "C1-1") == ["cp_commit", "cp_prove"] and windows(c, "C2-1") == ["cp_commit", "cp_prove"])
            check(c.name, "the box's planner arrays and the plan recorded",
                  "PLAN ONLY" in (c.read("plan-C1.arrays.txt") or "") and "\nplan-C2\t4\t" in steps
                  and (c.read("calib-plan.txt") or "").strip() == "C1:2:2:2:30 C2:3:1:1:30")
            req = os.path.join(c.results, "C2-1", "bundle", "in", "r03.req")
            check(c.name, "requests recorded with seeds, T words + 2",
                  "r02 seed=2 T=64 r=63 e=64" in (c.read("C1-1.stdout") or "")
                  and "r03 seed=3 T=128 r=127 e=128" in (c.read("C2-1.stdout") or "")
                  and os.path.isfile(req) and os.path.getsize(req) == 4 * 130)
            check(c.name, "sampler at FP_SAMPLE_MS",
                  os.path.exists(seen) and "-lms 100" in open(seen).read())
            check(c.name, "SHA256SUMS verifies, isk never exported, work dirs removed",
                  c.sums_ok() and c.no_secret()
                  and not any(os.path.exists(os.path.join(c.work, n)) for n in ("C1-1", "C1-2", "C2-1")))

        if want("calib-off"):
            c = calib_case(base, runner, "calib-off", "")
            p = c.run_job()
            steps = c.read("steps.tsv") or ""
            check(c.name, "without FP_CALIB: DONE, no calibration step or plan file",
                  p.returncode == 0 and c.exists("DONE") and "plan-" not in steps
                  and not c.exists("calib-plan.txt") and "calibration-start" not in c.stages())

        if want("calib-rejected"):
            c = calib_case(base, runner, "calib-rejected", "C1:2:1:1:30", env={"MOCK_CALIB": "no"})
            p = c.run_job()
            check(c.name, "a rejected calibration run does not fail the job", p.returncode == 0 and c.exists("DONE"))
            check(c.name, "C1-1 classed NO with the first rejection",
                  (c.read("C1-1.verdict") or "").startswith("NO: r01: NO: mock rejection"))
            check(c.name, "out/ and cp_verify.log withheld (duty 6), commit log exported",
                  not c.exists("C1-1/bundle/out") and not c.exists("C1-1/cp_verify.log")
                  and c.exists("C1-1/cp_commit.log") and "duty 6" in (c.read("C1-1/withheld.txt") or ""))
            check(c.name, "SHA256SUMS verifies, isk never exported", c.sums_ok() and c.no_secret())

        if want("calib-crash"):
            c = calib_case(base, runner, "calib-crash", "C1:1:1:2:30 C2:1:1:1:30", env={"MOCK_CALIB": "crash"})
            p = c.run_job()
            steps = c.read("steps.tsv") or ""
            check(c.name, "cp_commit refusal: every run reported, none replaced, job DONE",
                  p.returncode == 0 and c.exists("DONE")
                  and all(("\n%s\t1\t" % n) in steps for n in ("C1-1", "C1-2", "C2-1")) and not c.exists("C1-3.verdict"))
            check(c.name, "the refusal's log is served", "cudaHostRegister failed (mock)" in (c.read("C1-1/cp_commit.log") or ""))
            check(c.name, "SHA256SUMS verifies", c.sums_ok())

        if want("calib-step-timeout"):
            c = calib_case(base, runner, "calib-step-timeout", "C1:1:1:1:2 C2:1:1:1:2", env={"MOCK_CALIB": "sleep"})
            p = c.run_job(timeout=60)
            steps = c.read("steps.tsv") or ""
            check(c.name, "both runs recorded 124 timed out, job DONE",
                  p.returncode == 0 and c.exists("DONE") and "\nC1-1\t124\t" in steps and "\nC2-1\t124\t" in steps)
            check(c.name, "timed-out run: out/ withheld, commit log exported",
                  not c.exists("C1-1/bundle/out") and c.exists("C1-1/cp_commit.log"))
            check(c.name, "SHA256SUMS verifies, isk never exported", c.sums_ok() and c.no_secret())

        if want("calib-job-timeout"):
            c = calib_case(base, runner, "calib-job-timeout", "C1:1:1:1:600 C2:1:1:1:600",
                           env={"MOCK_CALIB": "sleep", "FP_JOB_TIMEOUT": "6"})
            p = c.run_job(timeout=60)
            steps = c.read("steps.tsv") or ""
            check(c.name, "job stopped by FP_JOB_TIMEOUT: FAILED, exit 124",
                  p.returncode == 124 and c.exists("FAILED") and "FP_JOB_TIMEOUT" in (c.read("FAILED") or ""))
            check(c.name, "the running calibration step recorded interrupted, C2 never started",
                  "\nC1-1\tinterrupted\t" in steps and "C2-1" not in steps)
            check(c.name, "its partial evidence exported, out/ withheld",
                  c.exists("C1-1/cp_commit.log") and not c.exists("C1-1/bundle/out"))
            check(c.name, "SHA256SUMS verifies, isk never exported", c.sums_ok() and c.no_secret())

        if want("calib-malformed"):
            bads = ("C1:0:1:1:30", "C1:2:3:1:30", "C1:2:1:1:030", "ZZ:1:1:1:30", "C1:1:1:1", "../C1:1:1:1:30",
                    "C1:65:1:1:30", "C1:2:1:21:30")
            for i, bad in enumerate(bads):
                c = calib_case(base, runner, "calib-malformed-%d" % i, bad)
                p = c.run_job()
                check(c.name, "%r refused before any GPU step" % bad,
                      p.returncode == 1 and c.exists("FAILED") and "FP_CALIB" in (c.read("FAILED") or "")
                      and "compiler_sample" not in (c.read("steps.tsv") or "") and c.sums_ok())

    for name, ok in results:
        print(("PASS " if ok else "FAIL ") + name)
    print("%d of %d checks passed" % (sum(ok for _, ok in results), len(results)))
    return 0 if results and all(ok for _, ok in results) else 1


if __name__ == "__main__":
    sys.exit(main())
