#!/usr/bin/env python3
"""CPU test of verify_offbox.py (RUNBOOK.md step 8) with a mocked cp_verify (verify_offbox_test_mocks/).

Builds results trees the way run_job.sh exports them (<run>/bundle/{config,ivk,in,out}, <run>/cp_commit.log,
withheld.txt for a run the on-box verifier did not accept, results/calib-plan.txt) and checks that the
helper: verifies every expected response of every batch (r01..rNN per calibration run, `example` for the
#43 runs); fails closed on a missing run, a withheld out/, a missing or rejected response anywhere in
the batch (an early failure is not hidden by later YES), a response file the plan did not expect, a
missing commitment ID, a crashing verifier; runs the five registered mutations and fails if one is
accepted; refuses usage errors (empty, whitespace-only, duplicate or mismatching plan) with exit 2.

usage: python3 verify_offbox_test.py [--only NAME]   (exit 0 = all passed)
"""
import argparse
import hashlib
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
TOOL = os.path.join(HERE, "verify_offbox.py")
MOCK = os.path.join(HERE, "verify_offbox_test_mocks", "cp_verify")


def make_run(results, run, names, cid=None, accepted=True):
    cid = cid or hashlib.sha256(run.encode()).hexdigest()
    top = os.path.join(results, run)
    b = os.path.join(top, "bundle")
    for part in ("config", "ivk", "in") + (("out",) if accepted else ()):
        os.makedirs(os.path.join(b, part))
    with open(os.path.join(b, "config", "policy.txt"), "w") as f:
        f.write("version H821\n")
    key = ("key of " + run).encode()
    with open(os.path.join(b, "ivk", "key.bin"), "wb") as f:
        f.write(key)
    with open(os.path.join(top, "cp_commit.log"), "w") as f:
        f.write("making the commitment\ncommitment ID: %s\n" % cid)
    for n in names:
        req = ("request %s %s" % (run, n)).encode()
        y = ("answer %s" % n).encode()
        with open(os.path.join(b, "in", n + ".req"), "wb") as f:
            f.write(req)
        if accepted:
            with open(os.path.join(b, "out", n + ".y"), "wb") as f:
                f.write(y)
            with open(os.path.join(b, "out", n + ".proof"), "wb") as f:
                f.write(hashlib.sha256(cid.encode() + req + y + key).hexdigest().encode())
    if not accepted:
        with open(os.path.join(top, "withheld.txt"), "w") as f:
            f.write("out/ (cp_verify did not accept this run: docs/limits.md, duty 6)\n")
    return top


def make_tree(base, plan="C2:8:4:3:300 C3:64:10:3:900", repeats=2, cold="quickstart"):
    res = os.path.join(base, "results")
    os.makedirs(res)
    if cold != "none":
        make_run(res, cold, ["example"])
    for i in range(1, repeats + 1):
        make_run(res, "rep%d" % i, ["example"])
    for e in plan.split():
        cid, n, _k, r, _t = e.split(":")
        for j in range(1, int(r) + 1):
            make_run(res, "%s-%d" % (cid, j), ["r%02d" % i for i in range(1, int(n) + 1)])
    if plan:
        with open(os.path.join(res, "calib-plan.txt"), "w") as f:
            f.write(plan + "\n")
    return res


def run_tool(res, *extra, env=None):
    rep = os.path.join(os.path.dirname(res), "report-%d.json" % len(os.listdir(os.path.dirname(res))))
    e = dict(os.environ)
    e.update(env or {})
    p = subprocess.run([sys.executable, TOOL, "--cp-verify", MOCK, "--results", res, "--report", rep] + list(extra),
                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=e, timeout=600)
    data = None
    if os.path.exists(rep):
        with open(rep) as f:
            data = json.load(f)
    return p.returncode, p.stdout.decode(errors="replace"), data


def run_of(data, name):
    for r in data["runs"]:
        if r["run"] == name:
            return r
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only")
    a = ap.parse_args()
    os.chmod(MOCK, os.stat(MOCK).st_mode | stat.S_IXUSR)
    results = []

    def check(case, label, ok):
        results.append(("%s: %s" % (case, label), bool(ok)))

    def want(n):
        return a.only is None or a.only == n

    with tempfile.TemporaryDirectory(prefix="fp-verify-offbox-test-") as tmp:
        def fresh(name):
            d = os.path.join(tmp, name)
            os.makedirs(d)
            return d

        if want("all-good"):
            res = make_tree(fresh("all-good"))
            rc, out, d = run_tool(res, "--repeats", "2")
            check("all-good", "registered plan: exit 0, PASS", rc == 0 and d and d["verdict"] == "PASS")
            check("all-good", "every expected run checked: quickstart + 2 reps + C2 x3 + C3 x3 = 9",
                  d and d["runs_expected"] == 9 and d["runs_passed"] == 9)
            check("all-good", "every response checked: 3 + 3x8 + 3x64 = 219",
                  d and d["responses_expected"] == 219
                  and sum(len(r["responses"]) for r in d["runs"]) == 219
                  and all(v["verdict"] == "YES" for r in d["runs"] for v in r["responses"].values()))
            c3 = d and run_of(d, "C3-3")
            check("all-good", "C3-3 has r01..r64, each YES",
                  c3 and sorted(c3["responses"]) == ["r%02d" % i for i in range(1, 65)])
            check("all-good", "5 mutations on the first response of every run, all rejected",
                  d and all(len(r["mutations"]) == 5 and all(m["rejected"] for m in r["mutations"].values())
                            for r in d["runs"]))
            check("all-good", "plan read from results/calib-plan.txt", d and d["plan"] == "C2:8:4:3:300 C3:64:10:3:900")

        if want("early-reject"):
            res = make_tree(fresh("early-reject"), plan="C2:8:4:1:300", repeats=0)
            with open(os.path.join(res, "C2-1", "bundle", "out", "r01.proof"), "wb") as f:
                f.write(b"forged")
            rc, out, d = run_tool(res, "--repeats", "0")
            r = d and run_of(d, "C2-1")
            check("early-reject", "r01 rejected, r02..r08 YES: run FAIL, overall FAIL, exit 1",
                  rc == 1 and d["verdict"] == "FAIL" and r["verdict"] == "FAIL"
                  and r["responses"]["r01"]["verdict"] == "FAIL"
                  and all(r["responses"]["r%02d" % i]["verdict"] == "YES" for i in range(2, 9)))
            check("early-reject", "the rejection's NO line is kept", r and r["responses"]["r01"]["last_line"] == "NO: proof-refused")
            check("early-reject", "printed OVERALL FAIL", "OVERALL FAIL" in out)

        if want("missing-response"):
            res = make_tree(fresh("missing-response"), plan="C2:8:4:1:300", repeats=0)
            os.remove(os.path.join(res, "C2-1", "bundle", "out", "r03.proof"))
            os.remove(os.path.join(res, "C2-1", "bundle", "out", "r08.y"))
            rc, out, d = run_tool(res, "--repeats", "0")
            r = d and run_of(d, "C2-1")
            check("missing-response", "a missing proof and a missing answer: FAIL, exit 1",
                  rc == 1 and r["verdict"] == "FAIL" and "missing" in r["responses"]["r03"]["why"]
                  and "missing" in r["responses"]["r08"]["why"])

        if want("missing-run"):
            res = make_tree(fresh("missing-run"), plan="C2:8:4:3:300", repeats=0)
            shutil.rmtree(os.path.join(res, "C2-3"))
            rc, out, d = run_tool(res, "--repeats", "0")
            r = d and run_of(d, "C2-3")
            check("missing-run", "a run of the plan absent from the archive: FAIL, its 8 responses FAIL",
                  rc == 1 and r and r["verdict"] == "FAIL" and len(r["responses"]) == 8
                  and all(v["verdict"] == "FAIL" for v in r["responses"].values()))

        if want("withheld"):
            res = make_tree(fresh("withheld"), plan="", repeats=1)
            make_run(res, "rep2", ["example"], accepted=False)
            rc, out, d = run_tool(res, "--repeats", "2")
            r = d and run_of(d, "rep2")
            check("withheld", "out/ withheld on the box: FAIL, reason recorded",
                  rc == 1 and r and r["verdict"] == "FAIL" and "withheld" in r["problems"][0])

        if want("unexpected-file"):
            res = make_tree(fresh("unexpected-file"), plan="C2:2:1:1:30", repeats=0)
            for sub, ext in (("in", "req"), ("out", "y"), ("out", "proof")):
                shutil.copy(os.path.join(res, "C2-1", "bundle", sub, "r01." + ext),
                            os.path.join(res, "C2-1", "bundle", sub, "r03." + ext))
            rc, out, d = run_tool(res, "--repeats", "0")
            r = d and run_of(d, "C2-1")
            check("unexpected-file", "a stale r03 beside the expected r01, r02 (mixed tree): FAIL",
                  rc == 1 and r and r["verdict"] == "FAIL" and any("unexpected" in p for p in r["problems"]))

        if want("no-id"):
            res = make_tree(fresh("no-id"), plan="", repeats=1, cold="none")
            with open(os.path.join(res, "rep1", "cp_commit.log"), "w") as f:
                f.write("cudaHostRegister failed\n")
            rc, out, d = run_tool(res, "--repeats", "1", "--cold", "none")
            check("no-id", "no commitment ID: FAIL", rc == 1 and run_of(d, "rep1")["verdict"] == "FAIL")
            res2 = make_tree(fresh("two-ids"), plan="", repeats=1, cold="none")
            with open(os.path.join(res2, "rep1", "cp_commit.log"), "a") as f:
                f.write("commitment ID: %s\n" % ("0" * 64))
            rc, out, d = run_tool(res2, "--repeats", "1", "--cold", "none")
            check("no-id", "two different commitment IDs: FAIL", rc == 1 and run_of(d, "rep1")["verdict"] == "FAIL")

        if want("broken-verifier"):
            res = make_tree(fresh("broken-verifier"), plan="C2:2:1:1:30", repeats=0, cold="none")
            rc, out, d = run_tool(res, "--repeats", "0", "--cold", "none", env={"MOCK_VERIFY": "accept-all"})
            r = d and run_of(d, "C2-1")
            check("broken-verifier", "a verifier that accepts every mutation: FAIL by the mutation checks",
                  rc == 1 and r["verdict"] == "FAIL" and all(not m["rejected"] for m in r["mutations"].values()))
            rc, out, d = run_tool(res, "--repeats", "0", "--cold", "none", env={"MOCK_VERIFY": "crash"})
            check("broken-verifier", "a verifier that crashes with no output: FAIL",
                  rc == 1 and d["verdict"] == "FAIL")

        if want("mutations-none"):
            res = make_tree(fresh("mutations-none"), plan="C2:2:1:1:30", repeats=0, cold="none")
            rc, out, d = run_tool(res, "--repeats", "0", "--cold", "none", "--mutations", "none")
            check("mutations-none", "skipping the registered mutations: overall FAIL", rc == 1 and d["verdict"] == "FAIL")
            rc, out, d = run_tool(res, "--repeats", "0", "--cold", "none", "--mutations", "all")
            check("mutations-none", "--mutations all: 2 responses x 5, PASS",
                  rc == 0 and len(run_of(d, "C2-1")["mutations"]) == 10)

        if want("usage"):
            res = make_tree(fresh("usage"), plan="C2:2:1:1:30", repeats=0, cold="none")
            cases = [
                ("--plan differs from calib-plan.txt", ["--plan", "C2:2:1:2:30"]),
                ("duplicate id in --plan", ["--plan", "C2:2:1:1:30 C2:2:1:1:30"]),
                ("malformed --plan", ["--plan", "C2:2:3:1:30"]),
            ]
            for label, extra in cases:
                rc, out, d = run_tool(res, "--repeats", "0", "--cold", "none", *extra)
                check("usage", "%s: exit 2, nothing checked" % label, rc == 2 and d is None)
            empty = os.path.join(fresh("usage-empty"), "results")
            os.makedirs(empty)
            rc, out, d = run_tool(empty, "--repeats", "0", "--cold", "none")
            check("usage", "nothing expected: exit 2, never PASS", rc == 2 and d is None)
            ws = os.path.join(fresh("usage-ws"), "results")
            os.makedirs(ws)
            with open(os.path.join(ws, "calib-plan.txt"), "w") as f:
                f.write("   \n")
            rc, out, d = run_tool(ws, "--repeats", "1", "--cold", "none")
            check("usage", "whitespace-only plan: exit 2", rc == 2 and d is None)

        if want("cold-runs"):
            res = make_tree(fresh("cold-runs"), plan="", repeats=1, cold="cold")
            rc, out, d = run_tool(res, "--repeats", "1", "--cold", "cold")
            check("cold-runs", "FP_ONBOX_BUILD=0 layout (cold + rep1): PASS", rc == 0 and d["runs_expected"] == 2)
            rc, out, d = run_tool(res, "--repeats", "1")
            check("cold-runs", "default --cold quickstart on that tree: quickstart missing, FAIL",
                  rc == 1 and run_of(d, "quickstart")["verdict"] == "FAIL")

    for name, ok in results:
        print(("PASS " if ok else "FAIL ") + name)
    print("%d of %d checks passed" % (sum(ok for _, ok in results), len(results)))
    return 0 if results and all(ok for _, ok in results) else 1


if __name__ == "__main__":
    sys.exit(main())
