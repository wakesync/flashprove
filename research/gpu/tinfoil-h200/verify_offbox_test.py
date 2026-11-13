#!/usr/bin/env python3
"""CPU test of verify_offbox.py (RUNBOOK.md step 8) with a mocked cp_verify (verify_offbox_test_mocks/).

Builds results trees the way run_job.sh exports them (<run>/bundle/{config,ivk,in,out}, <run>/cp_commit.log,
<run>.exit and <run>.verdict, steps.tsv, withheld.txt for a run the on-box verifier did not accept,
results/calib-plan.txt, results/SHA256SUMS) and checks that the helper: verifies every expected response of
every batch (r01..rNN per calibration run, `example` for the #43 runs); fails closed on a missing run, a
withheld out/, a missing or rejected response anywhere in the batch (an early failure is not hidden by
later YES), a response file the plan did not expect, a missing commitment ID, a crashing verifier; runs the
five registered mutations and fails if one is accepted; takes the expected coverage only from the
registered --plan / --no-calibration and --repeats, never from the archive: a missing, empty or differing
calib-plan.txt, a run the registration did not name (directory, steps.tsv row or run file), a --repeats
that differs from the job's, a missing steps.tsv and a missing or wrong SHA256SUMS all FAIL; refuses usage
errors (no mode, both modes, no --repeats, empty, duplicate or malformed plan, nothing expected) with exit 2.

The "registration" cases are the round-2 reviewers' reproductions on PR #141 (both families), each of
which returned PASS before this change.

The "boundary" cases are the round-3 reproductions (astra: a file or directory symbolic link in the
archive, followed by the check and written through by its mutation copies, while the report said PASS;
opus: a byte copy of a run, a linked run directory). Each hostile tree must FAIL as a structural
archive problem with no run checked, and every outside target's sha256 must be the same before and
after: file links (proof, answer, request, ivk, cp_commit.log; left out of or listed in SHA256SUMS),
directory links (out/, a run, a bundle), a link to an outside sibling, a relative link inside the tree,
a hard link, a fifo, isk/, --results itself a link, a SHA256SUMS path outside results/, the full 17-run
/ 227-response plan, and the tar -xzf round trip of the RUNBOOK (which, like sha256sum -c, accepts the
links). The intact control passes and its bytes are unchanged.

Round 4 (astra): a linked extraction root (`--results h200-x/results` with h200-x a link; also as an
absolute path, two levels down, and absolute outside the working directory) FAILs with no run checked;
a `..` in --results is a usage error; the working directory itself reached through a link (trusted)
and the same tree through real directories PASS. A verifier that writes its inputs (all three files,
the request only, or a new file in its working directory) FAILs after invocation: one run checked, no
further run, archive and outside bytes unchanged. A byte-copied run (C3-2 = C3-1, rep1 = quickstart)
FAILs in the preflight with no run checked.

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
import tarfile
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
TOOL = os.path.join(HERE, "verify_offbox.py")
MOCK = os.path.join(HERE, "verify_offbox_test_mocks", "cp_verify")
REGISTERED = "C2:8:4:3:300 C3:64:10:3:900"  # experiments/20261112-7-h200-dense-calibration/PREREG.md, Amendment 1


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
    # the job's per-run files in results/ and its steps.tsv row (run_job.sh one_run/calib_one)
    with open(os.path.join(results, run + ".exit"), "w") as f:
        f.write("0\n")
    with open(os.path.join(results, run + ".verdict"), "w") as f:
        f.write("YES\n" if accepted else "NO\n")
    st = os.path.join(results, "steps.tsv")
    if not os.path.exists(st):
        with open(st, "w") as f:
            f.write("step\texit\tseconds\ttimed_out\n")
    with open(st, "a") as f:
        f.write("%s\t0\t1\tno\n" % run)
    return top


def make_tree(base, plan=REGISTERED, repeats=2, cold="quickstart"):
    res = os.path.join(base, "results")
    os.makedirs(res)
    with open(os.path.join(res, "steps.tsv"), "w") as f:
        f.write("step\texit\tseconds\ttimed_out\nenv-gpu-query\t0\t1\tno\ncc_probe\t0\t1\tno\n")
    if cold != "none":
        make_run(res, cold, ["example"])
    for i in range(1, repeats + 1):
        make_run(res, "rep%d" % i, ["example"])
    for e in plan.split():
        with open(os.path.join(res, "steps.tsv"), "a") as f:
            f.write("plan-%s\t0\t1\tno\n" % e.split(":")[0])
    for e in plan.split():
        cid, n, _k, r, _t = e.split(":")
        for j in range(1, int(r) + 1):
            make_run(res, "%s-%d" % (cid, j), ["r%02d" % i for i in range(1, int(n) + 1)])
    if plan:
        with open(os.path.join(res, "calib-plan.txt"), "w") as f:
            f.write(plan + "\n")
    return res


def seal(res, links="follow"):
    """SHA256SUMS as run_job.sh's finalisation writes it: every regular file but itself, ./name paths.
    links: "follow" hashes a file link's target under the link's name (what sha256sum -c then checks),
    "skip" leaves file links out (what the round-3 checksum walk did). Directory links are never
    descended into (os.walk), so a linked directory's content is never listed either way."""
    lines = []
    for d, _dirs, files in os.walk(res):
        for fn in files:
            p = os.path.join(d, fn)
            rel = os.path.relpath(p, res)
            if rel == "SHA256SUMS" or (links == "skip" and os.path.islink(p)) or not os.path.isfile(p):
                continue
            with open(p, "rb") as f:
                lines.append((rel, hashlib.sha256(f.read()).hexdigest()))
    with open(os.path.join(res, "SHA256SUMS"), "w") as f:
        for rel, h in sorted(lines):
            f.write("%s  ./%s\n" % (h, rel))


def run_tool(res, *extra, env=None, sealed=True, cwd=None, given=None):
    """sealed=True (re)writes SHA256SUMS first: a producer who edits the archive can rewrite it too, so the
    registration cases must fail without help from the checksums. The tool runs as RUNBOOK step 8 says:
    from the directory that holds the tree (cwd, default res's parent), with a relative --results (given,
    default res's name)."""
    if sealed:
        seal(res)
    cwd = cwd or os.path.dirname(res)
    given = given or os.path.basename(res)
    rep = os.path.join(cwd, "report-%d.json" % len(os.listdir(cwd)))
    e = dict(os.environ)
    e.update(env or {})
    p = subprocess.run([sys.executable, TOOL, "--cp-verify", MOCK, "--results", given, "--report", rep] + list(extra),
                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=e, timeout=600, cwd=cwd)
    data = None
    if os.path.exists(rep):
        with open(rep) as f:
            data = json.load(f)
    return p.returncode, p.stdout.decode(errors="replace"), data


def sha_tree(top):
    """{relative path: sha256} of every regular file under top (links not followed), the outside
    targets' fingerprint before and after a check."""
    out = {}
    for d, _dirs, files in os.walk(top):
        for fn in files:
            p = os.path.join(d, fn)
            if os.path.islink(p) or not os.path.isfile(p):
                continue
            with open(p, "rb") as f:
                out[os.path.relpath(p, top)] = hashlib.sha256(f.read()).hexdigest()
    return out


def move_out(res, rel, outside):
    """Moves results/rel (a file or a directory) to outside/ and leaves a symbolic link in its place,
    the hostile archive of the round-3 review. Returns the outside path."""
    src = os.path.join(res, rel)
    os.makedirs(outside, exist_ok=True)
    dst = os.path.join(outside, rel.replace("/", "__"))
    is_dir = os.path.isdir(src)
    shutil.move(src, dst)
    os.symlink(dst, src, target_is_directory=is_dir)
    return dst


def run_of(data, name):
    for r in data["runs"]:
        if r["run"] == name:
            return r
    return None


def archive_has(data, text):
    return bool(data) and any(text in p for p in data["archive_problems"])


def drop_run(res, run):
    """Removes a run completely: its directory, its files in results/ and its steps.tsv row."""
    shutil.rmtree(os.path.join(res, run))
    for ext in ("exit", "verdict"):
        os.remove(os.path.join(res, "%s.%s" % (run, ext)))
    st = os.path.join(res, "steps.tsv")
    with open(st) as f:
        rows = [line for line in f if line.split("\t", 1)[0] != run]
    with open(st, "w") as f:
        f.writelines(rows)


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

    reg = ("--plan", REGISTERED)

    with tempfile.TemporaryDirectory(prefix="fp-verify-offbox-test-") as tmp:
        def fresh(name):
            d = os.path.join(tmp, name)
            os.makedirs(d)
            return d

        if want("all-good"):
            res = make_tree(fresh("all-good"))
            rc, out, d = run_tool(res, *reg, "--repeats", "2")
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
            check("all-good", "plan is the registered --plan, no archive problems",
                  d and d["plan"] == REGISTERED and d["mode"] == "calibration" and d["archive_problems"] == [])

        if want("early-reject"):
            res = make_tree(fresh("early-reject"), plan="C2:8:4:1:300", repeats=0)
            with open(os.path.join(res, "C2-1", "bundle", "out", "r01.proof"), "wb") as f:
                f.write(b"forged")
            rc, out, d = run_tool(res, "--plan", "C2:8:4:1:300", "--repeats", "0")
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
            rc, out, d = run_tool(res, "--plan", "C2:8:4:1:300", "--repeats", "0")
            r = d and run_of(d, "C2-1")
            check("missing-response", "a missing proof and a missing answer: FAIL, exit 1",
                  rc == 1 and r["verdict"] == "FAIL" and "missing" in r["responses"]["r03"]["why"]
                  and "missing" in r["responses"]["r08"]["why"])

        if want("missing-run"):
            res = make_tree(fresh("missing-run"), plan="C2:8:4:3:300", repeats=0)
            shutil.rmtree(os.path.join(res, "C2-3"))
            rc, out, d = run_tool(res, "--plan", "C2:8:4:3:300", "--repeats", "0")
            r = d and run_of(d, "C2-3")
            check("missing-run", "a run of the plan absent from the archive: FAIL, its 8 responses FAIL",
                  rc == 1 and r and r["verdict"] == "FAIL" and len(r["responses"]) == 8
                  and all(v["verdict"] == "FAIL" for v in r["responses"].values()))

        if want("withheld"):
            res = make_tree(fresh("withheld"), plan="", repeats=1)
            make_run(res, "rep2", ["example"], accepted=False)
            rc, out, d = run_tool(res, "--no-calibration", "--repeats", "2")
            r = d and run_of(d, "rep2")
            check("withheld", "out/ withheld on the box: FAIL, reason recorded",
                  rc == 1 and r and r["verdict"] == "FAIL" and "withheld" in r["problems"][0])

        if want("unexpected-file"):
            res = make_tree(fresh("unexpected-file"), plan="C2:2:1:1:30", repeats=0)
            for sub, ext in (("in", "req"), ("out", "y"), ("out", "proof")):
                shutil.copy(os.path.join(res, "C2-1", "bundle", sub, "r01." + ext),
                            os.path.join(res, "C2-1", "bundle", sub, "r03." + ext))
            rc, out, d = run_tool(res, "--plan", "C2:2:1:1:30", "--repeats", "0")
            r = d and run_of(d, "C2-1")
            check("unexpected-file", "a stale r03 beside the expected r01, r02 (mixed tree): FAIL",
                  rc == 1 and r and r["verdict"] == "FAIL" and any("unexpected" in p for p in r["problems"]))

        if want("no-id"):
            res = make_tree(fresh("no-id"), plan="", repeats=1, cold="none")
            with open(os.path.join(res, "rep1", "cp_commit.log"), "w") as f:
                f.write("cudaHostRegister failed\n")
            rc, out, d = run_tool(res, "--no-calibration", "--repeats", "1", "--cold", "none")
            check("no-id", "no commitment ID: FAIL", rc == 1 and run_of(d, "rep1")["verdict"] == "FAIL")
            res2 = make_tree(fresh("two-ids"), plan="", repeats=1, cold="none")
            with open(os.path.join(res2, "rep1", "cp_commit.log"), "a") as f:
                f.write("commitment ID: %s\n" % ("0" * 64))
            rc, out, d = run_tool(res2, "--no-calibration", "--repeats", "1", "--cold", "none")
            check("no-id", "two different commitment IDs: FAIL", rc == 1 and run_of(d, "rep1")["verdict"] == "FAIL")

        if want("broken-verifier"):
            res = make_tree(fresh("broken-verifier"), plan="C2:2:1:1:30", repeats=0, cold="none")
            args = ("--plan", "C2:2:1:1:30", "--repeats", "0", "--cold", "none")
            rc, out, d = run_tool(res, *args, env={"MOCK_VERIFY": "accept-all"})
            r = d and run_of(d, "C2-1")
            check("broken-verifier", "a verifier that accepts every mutation: FAIL by the mutation checks",
                  rc == 1 and r["verdict"] == "FAIL" and all(not m["rejected"] for m in r["mutations"].values()))
            rc, out, d = run_tool(res, *args, env={"MOCK_VERIFY": "crash"})
            check("broken-verifier", "a verifier that crashes with no output: FAIL",
                  rc == 1 and d["verdict"] == "FAIL")

        if want("mutations-none"):
            res = make_tree(fresh("mutations-none"), plan="C2:2:1:1:30", repeats=0, cold="none")
            args = ("--plan", "C2:2:1:1:30", "--repeats", "0", "--cold", "none")
            rc, out, d = run_tool(res, *args, "--mutations", "none")
            check("mutations-none", "skipping the registered mutations: overall FAIL", rc == 1 and d["verdict"] == "FAIL")
            rc, out, d = run_tool(res, *args, "--mutations", "all")
            check("mutations-none", "--mutations all: 2 responses x 5, PASS",
                  rc == 0 and len(run_of(d, "C2-1")["mutations"]) == 10)

        if want("usage"):
            res = make_tree(fresh("usage"), plan="C2:2:1:1:30", repeats=0, cold="none")
            cases = [
                ("neither --plan nor --no-calibration", ["--repeats", "0", "--cold", "none"]),
                ("both --plan and --no-calibration", ["--plan", "C2:2:1:1:30", "--no-calibration", "--repeats", "0", "--cold", "none"]),
                ("no --repeats", ["--plan", "C2:2:1:1:30", "--cold", "none"]),
                ("empty --plan", ["--plan", "", "--repeats", "0", "--cold", "none"]),
                ("whitespace-only --plan", ["--plan", "   ", "--repeats", "0", "--cold", "none"]),
                ("duplicate id in --plan", ["--plan", "C2:2:1:1:30 C2:2:1:1:30", "--repeats", "0", "--cold", "none"]),
                ("malformed --plan", ["--plan", "C2:2:3:1:30", "--repeats", "0", "--cold", "none"]),
                ("nothing expected", ["--no-calibration", "--repeats", "0", "--cold", "none"]),
            ]
            for label, extra in cases:
                rc, out, d = run_tool(res, *extra)
                check("usage", "%s: exit 2, nothing checked" % label, rc == 2 and d is None)
            rc, out, d = run_tool(res, "--plan", "C2:2:1:2:30", "--repeats", "0", "--cold", "none")
            check("usage", "--plan differs from calib-plan.txt: FAIL (exit 1), not a smaller check",
                  rc == 1 and archive_has(d, "differs from the registered --plan"))

        if want("cold-runs"):
            res = make_tree(fresh("cold-runs"), plan="", repeats=1, cold="cold")
            rc, out, d = run_tool(res, "--no-calibration", "--repeats", "1", "--cold", "cold")
            check("cold-runs", "FP_ONBOX_BUILD=0 layout (cold + rep1), --no-calibration: PASS",
                  rc == 0 and d["runs_expected"] == 2 and d["mode"] == "no-calibration")
            rc, out, d = run_tool(res, "--no-calibration", "--repeats", "1")
            check("cold-runs", "default --cold quickstart on that tree: quickstart missing, cold unexpected, FAIL",
                  rc == 1 and run_of(d, "quickstart")["verdict"] == "FAIL" and archive_has(d, "unexpected run directory cold"))

        # ---- the round-2 reviewers' reproductions (both families): each was exit 0 PASS before
        if want("registration"):
            def full(name):
                return make_tree(fresh(name), repeats=10)

            res = full("reg-intact")
            rc, out, d = run_tool(res, *reg, "--repeats", "10")
            check("registration", "intact registered job, --plan <registered> --repeats 10: PASS, 17 runs, 227 responses",
                  rc == 0 and d["verdict"] == "PASS" and d["runs_expected"] == 17 and d["responses_expected"] == 227)

            res = full("reg-missing-plan")
            os.remove(os.path.join(res, "calib-plan.txt"))
            rc, out, d = run_tool(res, *reg, "--repeats", "10")
            check("registration", "calib-plan.txt missing: FAIL, still 17 runs expected",
                  rc == 1 and archive_has(d, "calib-plan.txt missing") and d["runs_expected"] == 17)

            res = full("reg-empty-plan")
            open(os.path.join(res, "calib-plan.txt"), "w").close()
            rc, out, d = run_tool(res, *reg, "--repeats", "10")
            check("registration", "calib-plan.txt zero bytes: FAIL", rc == 1 and archive_has(d, "calib-plan.txt is empty"))
            with open(os.path.join(res, "calib-plan.txt"), "w") as f:
                f.write(" \n\t\n")
            rc, out, d = run_tool(res, *reg, "--repeats", "10")
            check("registration", "calib-plan.txt whitespace only: FAIL", rc == 1 and archive_has(d, "calib-plan.txt is empty"))

            res = full("reg-no-calibration-at-all")
            os.remove(os.path.join(res, "calib-plan.txt"))
            for run in ["C2-%d" % j for j in (1, 2, 3)] + ["C3-%d" % j for j in (1, 2, 3)]:
                drop_run(res, run)
            rc, out, d = run_tool(res, *reg, "--repeats", "10")
            check("registration", "calib-plan.txt and every C2/C3 run gone (empty FP_CALIB job): FAIL, 6 runs FAIL",
                  rc == 1 and sum(r["verdict"] == "FAIL" for r in d["runs"]) == 6
                  and all(run_of(d, x)["verdict"] == "FAIL" for x in ("C2-1", "C3-3")))

            res = full("reg-c2-only-forged-c3")
            with open(os.path.join(res, "calib-plan.txt"), "w") as f:
                f.write("C2:8:4:3:300\n")
            with open(os.path.join(res, "C3-2", "bundle", "out", "r40.proof"), "wb") as f:
                f.write(b"forged")
            rc, out, d = run_tool(res, *reg, "--repeats", "10")
            check("registration", "calib-plan.txt says C2 only, C3-2 r40 forged: FAIL, plan mismatch and C3-2 r40 rejected",
                  rc == 1 and archive_has(d, "differs from the registered --plan")
                  and run_of(d, "C3-2")["responses"]["r40"]["verdict"] == "FAIL")
            rc, out, d = run_tool(res, "--plan", "C2:8:4:3:300", "--repeats", "10")
            check("registration", "same archive, operator passes the C2-only plan: FAIL, C3 runs unexpected",
                  rc == 1 and archive_has(d, "unexpected run directory C3-2"))

            res = full("reg-repeats-reduced")
            with open(os.path.join(res, "calib-plan.txt"), "w") as f:
                f.write("C2:8:4:1:300 C3:64:10:3:900\n")
            rc, out, d = run_tool(res, *reg, "--repeats", "10")
            check("registration", "calib-plan.txt with C2 repeats 3 -> 1: FAIL, C2-2 and C2-3 still checked",
                  rc == 1 and archive_has(d, "differs") and run_of(d, "C2-3")["verdict"] == "PASS")

            res = full("reg-extra-c3-4")
            shutil.copytree(os.path.join(res, "C3-1"), os.path.join(res, "C3-4"))
            with open(os.path.join(res, "C3-4", "bundle", "out", "r01.proof"), "wb") as f:
                f.write(b"mutated")
            rc, out, d = run_tool(res, *reg, "--repeats", "10")
            check("registration", "extra failing C3-4 bundle: FAIL", rc == 1 and archive_has(d, "unexpected run directory C3-4"))

            res = full("reg-extra-c2-4")
            make_run(res, "C2-4", ["r%02d" % i for i in range(1, 9)])
            rc, out, d = run_tool(res, *reg, "--repeats", "10")
            check("registration", "extra valid C2-4 beyond 3 repeats: FAIL (dir, files and steps.tsv row)",
                  rc == 1 and archive_has(d, "unexpected run directory C2-4") and archive_has(d, "unexpected run file C2-4.exit")
                  and archive_has(d, "steps.tsv has a step C2-4"))

            res = full("reg-extra-rep11")
            make_run(res, "rep11", ["example"])
            with open(os.path.join(res, "rep11", "bundle", "out", "example.proof"), "wb") as f:
                f.write(b"forged")
            rc, out, d = run_tool(res, *reg, "--repeats", "10")
            check("registration", "extra rep11 with a forged proof: FAIL", rc == 1 and archive_has(d, "unexpected run directory rep11"))

            res = full("reg-repeats-5")
            with open(os.path.join(res, "rep7", "bundle", "out", "example.proof"), "wb") as f:
                f.write(b"forged")
            rc, out, d = run_tool(res, *reg, "--repeats", "5")
            check("registration", "--repeats 5 on a 10-repeat job, rep7 forged: FAIL, rep6..rep10 unexpected",
                  rc == 1 and all(archive_has(d, "unexpected run directory rep%d" % i) for i in range(6, 11)))

            res = full("reg-repeats-12")
            rc, out, d = run_tool(res, *reg, "--repeats", "12")
            check("registration", "--repeats 12 on a 10-repeat job: FAIL, rep11 and rep12 missing",
                  rc == 1 and run_of(d, "rep11")["verdict"] == "FAIL" and run_of(d, "rep12")["verdict"] == "FAIL")

            res = full("reg-step-row-only")
            with open(os.path.join(res, "steps.tsv"), "a") as f:
                f.write("rep11\t1\t30\tno\nC3-4\tinterrupted\t5\tyes\n")
            rc, out, d = run_tool(res, *reg, "--repeats", "10")
            check("registration", "a run removed but its steps.tsv rows kept (rep11, C3-4): FAIL",
                  rc == 1 and archive_has(d, "steps.tsv has a step rep11") and archive_has(d, "steps.tsv has a step C3-4"))

            res = full("reg-run-file-only")
            with open(os.path.join(res, "C3-4.verdict"), "w") as f:
                f.write("NO: proof-refused\n")
            rc, out, d = run_tool(res, *reg, "--repeats", "10")
            check("registration", "a run removed but its C3-4.verdict kept: FAIL",
                  rc == 1 and archive_has(d, "unexpected run file C3-4.verdict"))

            res = full("reg-no-calib-flag-on-calib-job")
            rc, out, d = run_tool(res, "--no-calibration", "--repeats", "10")
            check("registration", "--no-calibration on a calibration archive: FAIL (calib-plan.txt, C2/C3 unexpected)",
                  rc == 1 and archive_has(d, "calib-plan.txt present") and archive_has(d, "unexpected run directory C3-1"))

            res = make_tree(fresh("reg-43-only"), plan="", repeats=10)
            rc, out, d = run_tool(res, "--no-calibration", "--repeats", "10")
            check("registration", "#43 job alone, --no-calibration --repeats 10: PASS, 11 runs",
                  rc == 0 and d["runs_expected"] == 11 and d["mode"] == "no-calibration")

        if want("archive"):
            res = make_tree(fresh("archive-sums"), plan="C2:2:1:1:30", repeats=1)
            args = ("--plan", "C2:2:1:1:30", "--repeats", "1")
            rc, out, d = run_tool(res, *args)
            check("archive", "sealed intact tree: PASS", rc == 0)
            os.remove(os.path.join(res, "SHA256SUMS"))
            rc, out, d = run_tool(res, *args, sealed=False)
            check("archive", "SHA256SUMS missing: FAIL", rc == 1 and archive_has(d, "SHA256SUMS missing"))
            seal(res)
            with open(os.path.join(res, "rep1.verdict"), "a") as f:
                f.write("edited after sealing\n")
            rc, out, d = run_tool(res, *args, sealed=False)
            check("archive", "a file changed after sealing: FAIL", rc == 1 and archive_has(d, "mismatch: rep1.verdict"))
            seal(res)
            with open(os.path.join(res, "notes.txt"), "w") as f:
                f.write("added after sealing\n")
            rc, out, d = run_tool(res, *args, sealed=False)
            check("archive", "a file added after sealing: FAIL", rc == 1 and archive_has(d, "does not list notes.txt"))
            seal(res)
            os.remove(os.path.join(res, "notes.txt"))
            rc, out, d = run_tool(res, *args, sealed=False)
            check("archive", "a listed file removed: FAIL", rc == 1 and archive_has(d, "lists notes.txt"))
            os.remove(os.path.join(res, "steps.tsv"))
            rc, out, d = run_tool(res, *args)
            check("archive", "steps.tsv missing: FAIL", rc == 1 and archive_has(d, "steps.tsv missing"))

        # ---- the round-3 review (astra): the archive's file boundary. Each hostile tree must FAIL as an
        # archive problem before any run is checked, and an outside target's bytes must not change.
        if want("boundary"):
            def full(name):
                return make_tree(fresh(name), repeats=10)

            def hostile(label, res, outside, links="follow", extra=reg + ("--repeats", "10")):
                seal(res, links=links)
                before = sha_tree(outside)
                rc, out, d = run_tool(res, *extra, sealed=False)
                after = sha_tree(outside)
                check("boundary", "%s: FAIL (exit 1) as a structural archive problem, no run checked" % label,
                      rc == 1 and d and d["verdict"] == "FAIL" and d["structural_problems"] and d["runs"] == []
                      and "no run was verified" in out)
                check("boundary", "%s: outside target unchanged (sha256 before = after, %d files)" % (label, len(before)),
                      before and before == after)
                return d

            res = full("bnd-intact")
            outside = os.path.join(os.path.dirname(res), "outside")
            os.makedirs(outside)
            with open(os.path.join(outside, "bystander"), "wb") as f:
                f.write(b"not part of the archive\n")
            seal(res)
            sums_before = sha_tree(res)
            rc, out, d = run_tool(res, *reg, "--repeats", "10", sealed=False)
            check("boundary", "intact control, 17 runs / 227 responses: PASS",
                  rc == 0 and d["verdict"] == "PASS" and d["runs_expected"] == 17 and d["responses_expected"] == 227
                  and d["structural_problems"] == [])
            check("boundary", "intact control: archive bytes unchanged by the check", sha_tree(res) == sums_before)

            # file links: proof (the full-plan 17-run / 227-response probe), answer, request
            for label, rel in (("proof file link (17 runs / 227 responses)", "quickstart/bundle/out/example.proof"),
                               ("answer file link", "C2-1/bundle/out/r01.y"),
                               ("request file link", "C3-3/bundle/in/r64.req"),
                               ("ivk file link", "rep4/bundle/ivk/key.bin"),
                               ("cp_commit.log link", "rep1/cp_commit.log")):
                for links in ("skip", "follow"):
                    res = full("bnd-%s-%s" % (rel.replace("/", "_"), links))
                    outside = os.path.join(os.path.dirname(res), "outside")
                    move_out(res, rel, outside)
                    d = hostile("%s, link %s by SHA256SUMS" % (label, "left out" if links == "skip" else "listed"),
                                res, outside, links=links)
                    check("boundary", "%s: the link is named" % label,
                          d and any(rel in p and "symbolic link" in p for p in d["structural_problems"]))
            # directory links: out/, a whole run, a whole bundle
            for label, rel in (("out/ directory link", "C2-2/bundle/out"),
                               ("run directory link", "C3-1"),
                               ("bundle directory link", "rep2/bundle")):
                res = full("bnd-dir-%s" % rel.replace("/", "_"))
                outside = os.path.join(os.path.dirname(res), "outside")
                move_out(res, rel, outside)
                hostile(label, res, outside)
            # a link to a sibling outside the archive that the archive never had (an extra, unlisted file)
            res = full("bnd-sibling")
            outside = os.path.join(os.path.dirname(res), "outside")
            os.makedirs(outside)
            with open(os.path.join(outside, "secret.txt"), "wb") as f:
                f.write(b"outside the archive\n")
            os.symlink(os.path.join(outside, "secret.txt"), os.path.join(res, "notes.txt"))
            hostile("link to an outside sibling", res, outside)
            # a link that stays inside the tree is refused too (only directories and regular files)
            res = full("bnd-inside-link")
            outside = os.path.join(os.path.dirname(res), "outside")
            os.makedirs(outside)
            with open(os.path.join(outside, "bystander"), "wb") as f:
                f.write(b"x\n")
            p = os.path.join(res, "C2-3", "bundle", "out", "r02.proof")
            os.remove(p)
            os.symlink(os.path.join("..", "..", "..", "C2-1", "bundle", "out", "r02.proof"), p)
            hostile("relative link inside the tree", res, outside)
            # a hard link to a file outside the tree (same file system)
            res = full("bnd-hardlink")
            outside = os.path.join(os.path.dirname(res), "outside")
            os.makedirs(outside)
            p = os.path.join(res, "C3-2", "bundle", "out", "r10.proof")
            os.link(p, os.path.join(outside, "r10.proof"))
            d = hostile("hard-linked proof (st_nlink 2)", res, outside)
            check("boundary", "hard link named", d and any("hard-linked" in x for x in d["structural_problems"]))
            # a fifo (reading it would block) and an isk/ directory
            res = full("bnd-fifo")
            outside = os.path.join(os.path.dirname(res), "outside")
            os.makedirs(outside)
            with open(os.path.join(outside, "bystander"), "wb") as f:
                f.write(b"x\n")
            os.mkfifo(os.path.join(res, "rep3", "bundle", "in", "pipe"))
            hostile("fifo in the tree", res, outside)
            res = full("bnd-isk")
            os.makedirs(os.path.join(res, "rep5", "bundle", "isk"))
            with open(os.path.join(res, "rep5", "bundle", "isk", "k"), "wb") as f:
                f.write(b"k")
            hostile("isk/ in the tree", res, outside)
            # the results directory itself given as a link
            res = full("bnd-root-link")
            seal(res)
            alias = os.path.join(os.path.dirname(res), "results-alias")
            os.symlink(res, alias, target_is_directory=True)
            rc, out, d = run_tool(alias, *reg, "--repeats", "10", sealed=False)
            check("boundary", "--results given as a symbolic link: FAIL, no run checked",
                  rc == 1 and d and d["runs"] == [] and any("symbolic link" in x for x in d["structural_problems"]))
            # SHA256SUMS naming a path outside results/
            res = full("bnd-sums-outside")
            seal(res)
            with open(os.path.join(res, "SHA256SUMS"), "a") as f:
                f.write("%s  ./../outside/bystander\n" % ("0" * 64))
            rc, out, d = run_tool(res, *reg, "--repeats", "10", sealed=False)
            check("boundary", "SHA256SUMS lists ./../outside/...: FAIL, no run checked",
                  rc == 1 and d and d["runs"] == [] and any("outside results" in x for x in d["structural_problems"]))
            # the round-3 tar route: links packed into a tar.gz and unpacked with the RUNBOOK's tar -xzf
            res = full("bnd-tar")
            base = os.path.dirname(res)
            outside = os.path.join(base, "outside")
            move_out(res, "quickstart/bundle/out/example.proof", outside)
            move_out(res, "C2-2/bundle/out", outside)
            seal(res, links="skip")
            tgz = os.path.join(base, "hostile.tar.gz")
            with tarfile.open(tgz, "w:gz", dereference=False) as t:
                t.add(res, arcname="results")
            dest = os.path.join(base, "extracted")
            os.makedirs(dest)
            before = sha_tree(outside)
            x = subprocess.run(["tar", "-xzf", tgz, "-C", dest], capture_output=True)
            s = subprocess.run(["sha256sum", "-c", "--quiet", "SHA256SUMS"], cwd=os.path.join(dest, "results"),
                               capture_output=True)
            rc, out, d = run_tool(os.path.join(dest, "results"), *reg, "--repeats", "10", sealed=False)
            check("boundary", "tar -xzf + sha256sum -c of a linked archive both exit 0 (they are not the boundary)",
                  x.returncode == 0 and s.returncode == 0)
            check("boundary", "the same extracted tree: FAIL, no run checked, outside unchanged",
                  rc == 1 and d and d["runs"] == [] and sha_tree(outside) == before)
            # ---- round 4 (astra): a linked extraction root, a verifier that writes its inputs, a
            # duplicate commitment ID. The extraction root (h200-x in RUNBOOK step 5) linked to an
            # outside sibling: --results h200-x/results from the working directory must FAIL, no run.
            res = full("bnd-extract-root-link")
            base = os.path.dirname(res)
            outside = os.path.join(base, "outside")
            os.makedirs(outside)
            os.makedirs(os.path.join(base, "work"))
            shutil.move(res, os.path.join(outside, "results"))
            seal(os.path.join(outside, "results"))
            os.symlink(outside, os.path.join(base, "work", "h200-x"), target_is_directory=True)
            before = sha_tree(outside)
            rc, out, d = run_tool(os.path.join(base, "work", "h200-x", "results"), *reg, "--repeats", "10",
                                  sealed=False, cwd=os.path.join(base, "work"), given="h200-x/results")
            check("boundary", "round 4: extraction root h200-x a link, --results h200-x/results: FAIL, no run checked",
                  rc == 1 and d and d["runs"] == [] and "no run was verified" in out
                  and any("h200-x" in x and "symbolic link" in x for x in d["structural_problems"]))
            check("boundary", "round 4: linked extraction root: outside target unchanged (%d files)" % len(before),
                  before and sha_tree(outside) == before)
            # the same through an absolute --results below the working directory, and a deeper link
            rc, out, d = run_tool(os.path.join(base, "work", "h200-x", "results"), *reg, "--repeats", "10",
                                  sealed=False, cwd=os.path.join(base, "work"),
                                  given=os.path.join(os.path.realpath(os.path.join(base, "work")), "h200-x", "results"))
            check("boundary", "round 4: the same given as an absolute path below the working directory: FAIL, no run checked",
                  rc == 1 and d and d["runs"] == [] and any("symbolic link" in x for x in d["structural_problems"]))
            os.makedirs(os.path.join(base, "work", "deep"))
            os.symlink(outside, os.path.join(base, "work", "deep", "x"), target_is_directory=True)
            rc, out, d = run_tool(os.path.join(base, "work", "deep", "x", "results"), *reg, "--repeats", "10",
                                  sealed=False, cwd=os.path.join(base, "work"), given="deep/x/results")
            check("boundary", "round 4: a linked parent two levels down (deep/x/results): FAIL, no run checked",
                  rc == 1 and d and d["runs"] == [] and any("deep/x" in x and "symbolic link" in x for x in d["structural_problems"]))
            # absolute --results outside the working directory: only / is trusted, so a link anywhere fails
            rc, out, d = run_tool(os.path.join(base, "work", "h200-x", "results"), *reg, "--repeats", "10",
                                  sealed=False, cwd=outside,
                                  given=os.path.join(os.path.realpath(base), "work", "h200-x", "results"))
            check("boundary", "round 4: absolute --results outside the working directory through a link: FAIL, no run checked",
                  rc == 1 and d and d["runs"] == [] and any("symbolic link" in x for x in d["structural_problems"]))
            # '..' in --results: usage error, nothing checked
            rc, out, d = run_tool(os.path.join(outside, "results"), *reg, "--repeats", "10", sealed=False,
                                  cwd=os.path.join(base, "work"), given="../outside/results")
            check("boundary", "round 4: --results with a '..' component: usage error (exit 2), nothing checked",
                  rc == 2 and d is None)
            # the trusted side: the working directory itself reached through a link is the operator's
            # (its parents are trusted), and the same tree without the linked component PASSes
            os.symlink(outside, os.path.join(base, "operator-link"), target_is_directory=True)
            rc, out, d = run_tool(os.path.join(outside, "results"), *reg, "--repeats", "10", sealed=False,
                                  cwd=os.path.join(base, "operator-link"), given="results")
            check("boundary", "round 4: working directory entered through a link (trusted), --results results: PASS, 17 runs",
                  rc == 0 and d and d["verdict"] == "PASS" and d["runs_passed"] == 17)
            rc, out, d = run_tool(os.path.join(outside, "results"), *reg, "--repeats", "10", sealed=False,
                                  cwd=base, given="outside/results")
            check("boundary", "round 4: the same tree through real directories (outside/results): PASS, 17 runs",
                  rc == 0 and d and d["verdict"] == "PASS" and d["runs_passed"] == 17)
            # a verifier that writes its inputs: noticed after the call, FAIL, no further run verified;
            # the archive and everything outside the private copy unchanged
            for mode in ("scribble", "scribble-request", "litter"):
                res = full("bnd-%s" % mode)
                outside = os.path.join(os.path.dirname(res), "outside")
                os.makedirs(outside)
                with open(os.path.join(outside, "bystander"), "wb") as f:
                    f.write(b"x\n")
                seal(res)
                before, before_out = sha_tree(res), sha_tree(outside)
                rc, out, d = run_tool(res, *reg, "--repeats", "10", env={"MOCK_VERIFY": mode}, sealed=False)
                check("boundary", "round 4: verifier %s: FAIL after invocation (input_written), one run checked, "
                      "no further run" % mode,
                      rc == 1 and d and d["verdict"] == "FAIL" and d["input_written"] and len(d["runs"]) == 1
                      and d["runs"][0]["verdict"] == "FAIL" and d["structural_problems"] == []
                      and archive_has(d, "wrote its private input copy"))
                check("boundary", "round 4: verifier %s: archive and outside bytes unchanged" % mode,
                      sha_tree(res) == before and sha_tree(outside) == before_out
                      and subprocess.run(["sha256sum", "-c", "--quiet", "SHA256SUMS"], cwd=res,
                                         capture_output=True).returncode == 0)
            # one commitment per run, checked BEFORE any run (opus round 3, astra round 4)
            res = full("bnd-duplicate-run")
            shutil.rmtree(os.path.join(res, "C3-2"))
            shutil.copytree(os.path.join(res, "C3-1"), os.path.join(res, "C3-2"))
            rc, out, d = run_tool(res, *reg, "--repeats", "10")
            check("boundary", "C3-2 a byte copy of C3-1 (same commitment ID): FAIL, no run checked",
                  rc == 1 and d["runs"] == [] and "no run was verified" in out
                  and any("C3-1 C3-2 share one commitment ID" in x for x in d["structural_problems"]))
            res = full("bnd-duplicate-across-kinds")
            shutil.rmtree(os.path.join(res, "rep1"))
            shutil.copytree(os.path.join(res, "quickstart"), os.path.join(res, "rep1"))
            rc, out, d = run_tool(res, *reg, "--repeats", "10")
            check("boundary", "round 4: rep1 a byte copy of quickstart: FAIL, no run checked",
                  rc == 1 and d["runs"] == []
                  and any("quickstart rep1 share one commitment ID" in x for x in d["structural_problems"]))

    for name, ok in results:
        print(("PASS " if ok else "FAIL ") + name)
    print("%d of %d checks passed" % (sum(ok for _, ok in results), len(results)))
    return 0 if results and all(ok for _, ok in results) else 1


if __name__ == "__main__":
    sys.exit(main())
