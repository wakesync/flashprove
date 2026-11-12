#!/usr/bin/env python3
"""Off-box verification of an H200 job's results (RUNBOOK.md step 8), on CPU, after restore.

Checks EVERY response that the job was registered to produce, against the run's own commitment ID,
with a cp_verify built by the operator from the pinned commit, and fails closed:

  * the expected runs come from the REGISTERED plan given on the command line, never from the archive:
    `--plan '<FP_CALIB>'` (calibration mode; the #140 window passes the PREREG's value) or
    `--no-calibration` (the #43 job alone), one of the two is required, and `--repeats N` is required.
    Expected: the #43 cold run (`quickstart` with FP_ONBOX_BUILD=1, `cold` with 0, or none), the warm
    repeats rep1..repN (each one response, `example`), and every calibration run <id>-1..<id>-<repeats>
    of the plan (each <requests> responses r01..rNN).
  * the archive's own metadata is only cross-checked, never used to choose what is expected: in
    calibration mode results/calib-plan.txt (the job writes it) must exist, be non-empty and name the
    same plan; with --no-calibration it must be absent. results/steps.tsv must exist. Otherwise FAIL.
  * the archive must not hold a run the registration did not name: any directory in results/ that is
    not an expected run, and any run-shaped step row in steps.tsv or run file (<run>.exit, .verdict,
    .stdout, .time, .windows) of a run not expected (an extra repeat, C2-4, C3-4, rep11), is a FAIL.
    So is a --repeats smaller than the job's (its extra repeats are unexpected runs) or larger
    (missing runs).
  * results/SHA256SUMS must exist, list every regular file of results/ but itself, and match each one.
  * a run passes only if its cp_commit.log has one commitment ID, every expected response has its
    request, answer and proof in the bundle, cp_verify exits 0 with the last line YES on each of them,
    and the bundle has no response that the plan did not expect (a mixed tree is a failure).
  * a missing run, a withheld out/ (the on-box verifier did not accept it), a missing or rejected
    response, a cp_verify timeout, or a response the plan did not expect: that run FAILS. An early
    failure is never hidden by later YES: every response is checked and reported.
  * the registered mutation cases (research/gpu/local-verify: proof bit flip, answer bit flip,
    request bit flip, proof truncated by one byte, wrong commitment ID) on the first response of
    every run that passed (--mutations first, the default; `all` for every response; `none` to skip,
    which makes the overall verdict FAIL, since the PREREG requires them): each must make cp_verify
    exit nonzero with a last line starting NO. One accepted mutation fails the run.
  * the overall verdict is PASS only if every expected run passed, the archive checks above found
    nothing, and at least one run was expected.

Exit status: 0 PASS, 1 FAIL, 2 usage error (nothing checked). A JSON report goes to --report.
It never contacts any host. SHA256SUMS checks the archive's integrity only; it does not show that the
producer ran the registered plan (that is what --plan, --repeats and the unexpected-run check are for).

usage: python3 verify_offbox.py --cp-verify PATH --results DIR (--plan FP_CALIB | --no-calibration)
                                --repeats N [--cold quickstart|cold|none] [--mutations first|all|none]
                                [--timeout S] [--report FILE]
"""
import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

ENTRY = re.compile(r"^([A-Za-z0-9_]{1,16}):([1-9][0-9]?):([1-9][0-9]?):([1-9][0-9]?):([1-9][0-9]{0,4})$")
ID_LINE = re.compile(r"^commitment ID: *([0-9a-f]{64}) *$")
RESP = re.compile(r"^(.+)\.(req|y|proof)$")
MUTATIONS = ("proof-bitflip", "answer-bitflip", "request-bitflip", "proof-truncated", "wrong-id")
# names run_job.sh gives to runs: the cold run, the warm repeats, the calibration runs <id>-<j>
RUN_NAME = re.compile(r"^(quickstart|cold|rep[0-9]+|[A-Za-z0-9_]{1,16}-[0-9]+)$")
RUN_FILE = re.compile(r"^(.+)\.(exit|verdict|stdout|time|windows)$")
SUM_LINE = re.compile(r"^([0-9a-f]{64}) [ *]\./(.+)$")


class Usage(Exception):
    pass


def parse_plan(text):
    """FP_CALIB as run_job.sh's calib_ok accepts it, duplicates refused: [(id, requests, repeats)]."""
    out, seen = [], set()
    for e in text.split():
        m = ENTRY.match(e)
        if not m:
            raise Usage("malformed plan entry %r" % e)
        cid, n, k, r, t = m.group(1), int(m.group(2)), int(m.group(3)), int(m.group(4)), int(m.group(5))
        if n > 64 or k > 16 or k > n or r > 20 or t > 86400:
            raise Usage("plan entry out of range %r" % e)
        if cid in seen:
            raise Usage("plan names %s twice" % cid)
        seen.add(cid)
        out.append((cid, n, r))
    return out


def expected_runs(plan, repeats, cold):
    runs = []
    if cold != "none":
        runs.append((cold, ["example"]))
    runs += [("rep%d" % i, ["example"]) for i in range(1, repeats + 1)]
    for cid, n, r in plan:
        for j in range(1, r + 1):
            runs.append(("%s-%d" % (cid, j), ["r%02d" % i for i in range(1, n + 1)]))
    return runs


def commitment_id(path):
    try:
        with open(path, errors="replace") as f:
            ids = [m.group(1) for m in (ID_LINE.match(line.rstrip("\n")) for line in f) if m]
    except OSError:
        return None
    return ids[0] if len(set(ids)) == 1 else None


def call(cp_verify, cwd, name, cid, timeout):
    args = [cp_verify, "config", "ivk", "in/%s.req" % name, "out/%s.y" % name, "out/%s.proof" % name, "-id", cid]
    try:
        p = subprocess.run(args, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=timeout)
    except subprocess.TimeoutExpired:
        return {"exit": "timeout", "last_line": None}
    except OSError as e:
        return {"exit": "error", "last_line": str(e)}
    lines = p.stdout.decode(errors="replace").strip().splitlines()
    return {"exit": p.returncode, "last_line": lines[-1].strip() if lines else ""}


def flip(path, offset):
    with open(path, "r+b") as f:
        size = os.path.getsize(path)
        if size == 0:
            return False
        offset %= size
        f.seek(offset)
        b = f.read(1)[0]
        f.seek(offset)
        f.write(bytes([b ^ 1]))
    return True


def mutate(bundle, name, cid, case, tmp):
    """Copy the bundle and apply one mutation; returns (copy dir, commitment ID to use)."""
    d = tempfile.mkdtemp(dir=tmp)
    for part in ("config", "ivk", "in", "out"):
        shutil.copytree(os.path.join(bundle, part), os.path.join(d, part), symlinks=True)
    if case == "proof-bitflip":
        p = os.path.join(d, "out", name + ".proof")
        flip(p, os.path.getsize(p) // 2)
    elif case == "answer-bitflip":
        flip(os.path.join(d, "out", name + ".y"), 0)
    elif case == "request-bitflip":
        p = os.path.join(d, "in", name + ".req")
        flip(p, os.path.getsize(p) - 1)
    elif case == "proof-truncated":
        p = os.path.join(d, "out", name + ".proof")
        with open(p, "r+b") as f:
            f.truncate(max(0, os.path.getsize(p) - 1))
    elif case == "wrong-id":
        cid = cid[:-1] + "%x" % (int(cid[-1], 16) ^ 1)
    return d, cid


def check_run(cp_verify, results, run, names, mutations, timeout, tmp):
    rep = {"run": run, "expected": len(names), "responses": {}, "mutations": {}, "problems": []}
    top = os.path.join(results, run)
    bundle = os.path.join(top, "bundle")
    if not os.path.isdir(top):
        rep["problems"].append("run directory missing")
    elif not os.path.isdir(os.path.join(bundle, "out")):
        why = "out/ withheld (on-box verifier did not accept)" if os.path.exists(os.path.join(top, "withheld.txt")) else "out/ missing"
        rep["problems"].append(why)
    cid = commitment_id(os.path.join(top, "cp_commit.log")) if os.path.isdir(top) else None
    if os.path.isdir(top) and cid is None:
        rep["problems"].append("no single commitment ID in cp_commit.log")
    for part in ("config", "ivk", "in"):
        if os.path.isdir(top) and not os.path.isdir(os.path.join(bundle, part)):
            rep["problems"].append("bundle/%s missing" % part)
    if rep["problems"]:
        for n in names:
            rep["responses"][n] = {"verdict": "FAIL", "why": "not checked: " + rep["problems"][0]}
        rep["verdict"] = "FAIL"
        return rep
    # responses present that the plan did not expect (a mixed tree, e.g. a stale r02 next to r01)
    for sub in ("in", "out"):
        for f in sorted(os.listdir(os.path.join(bundle, sub))):
            m = RESP.match(f)
            if m and m.group(1) not in names:
                rep["problems"].append("unexpected response file %s/%s" % (sub, f))
    for n in names:
        files = ["in/%s.req" % n, "out/%s.y" % n, "out/%s.proof" % n]
        missing = [f for f in files if not os.path.isfile(os.path.join(bundle, f))]
        if missing:
            rep["responses"][n] = {"verdict": "FAIL", "why": "missing " + ", ".join(missing)}
            continue
        r = call(cp_verify, bundle, n, cid, timeout)
        r["verdict"] = "YES" if r["exit"] == 0 and r["last_line"] == "YES" else "FAIL"
        rep["responses"][n] = r
    bad = [n for n in names if rep["responses"][n]["verdict"] != "YES"]
    if bad:
        rep["problems"].append("responses not accepted: " + " ".join(bad))
    if mutations != "none" and not bad:
        for n in (names if mutations == "all" else names[:1]):
            for case in MUTATIONS:
                d, mid = mutate(bundle, n, cid, case, tmp)
                r = call(cp_verify, d, n, mid, timeout)
                shutil.rmtree(d, ignore_errors=True)
                r["rejected"] = r["exit"] not in (0, "timeout", "error") and (r["last_line"] or "").startswith("NO")
                rep["mutations"]["%s/%s" % (n, case)] = r
                if not r["rejected"]:
                    rep["problems"].append("mutation %s of %s not rejected" % (case, n))
    rep["verdict"] = "PASS" if not rep["problems"] else "FAIL"
    return rep


def archive_problems(results, run_names, calibration, plan_text):
    """Cross-checks of the archive against the registration. Returns a list of problems (empty = ok)."""
    probs = []
    expected = set(run_names)
    pf = os.path.join(results, "calib-plan.txt")
    if calibration:
        if not os.path.isfile(pf):
            probs.append("results/calib-plan.txt missing (the job writes it whenever FP_CALIB is set)")
        else:
            with open(pf, errors="replace") as f:
                on_disk = f.read()
            if on_disk.strip() == "":
                probs.append("results/calib-plan.txt is empty")
            elif on_disk.split() != plan_text.split():
                probs.append("results/calib-plan.txt (%r) differs from the registered --plan" % on_disk.strip())
    elif os.path.lexists(pf):
        probs.append("results/calib-plan.txt present, but --no-calibration was given")
    for e in sorted(os.listdir(results)):
        p = os.path.join(results, e)
        if os.path.isdir(p) and e not in expected:
            probs.append("unexpected run directory %s (not in the registered plan/repeats)" % e)
        m = RUN_FILE.match(e)
        if m and RUN_NAME.match(m.group(1)) and m.group(1) not in expected:
            probs.append("unexpected run file %s (not in the registered plan/repeats)" % e)
    st = os.path.join(results, "steps.tsv")
    if not os.path.isfile(st):
        probs.append("results/steps.tsv missing")
    else:
        with open(st, errors="replace") as f:
            for line in f:
                name = line.split("\t", 1)[0].strip()
                if RUN_NAME.match(name) and name not in expected:
                    probs.append("steps.tsv has a step %s that is not in the registered plan/repeats" % name)
    probs += checksum_problems(results)
    return probs


def checksum_problems(results):
    """results/SHA256SUMS (run_job.sh's finalisation, `./name` paths) must list every regular file but
    itself and match each one."""
    sums = os.path.join(results, "SHA256SUMS")
    if not os.path.isfile(sums):
        return ["results/SHA256SUMS missing"]
    listed, probs = {}, []
    with open(sums, errors="replace") as f:
        for line in f:
            m = SUM_LINE.match(line.rstrip("\n"))
            if not m:
                probs.append("SHA256SUMS: unreadable line %r" % line[:80])
                continue
            listed[os.path.normpath(m.group(2))] = m.group(1)
    present = set()
    for d, dirs, files in os.walk(results):
        for fn in files:
            p = os.path.join(d, fn)
            rel = os.path.relpath(p, results)
            if rel == "SHA256SUMS" or os.path.islink(p) or not os.path.isfile(p):
                continue
            present.add(rel)
    for rel in sorted(present - set(listed)):
        probs.append("SHA256SUMS does not list %s" % rel)
    for rel in sorted(listed):
        p = os.path.join(results, rel)
        if rel not in present:
            probs.append("SHA256SUMS lists %s, which is not a regular file in results/" % rel)
            continue
        h = hashlib.sha256()
        with open(p, "rb") as f:
            for chunk in iter(lambda: f.read(1 << 20), b""):
                h.update(chunk)
        if h.hexdigest() != listed[rel]:
            probs.append("SHA256SUMS mismatch: %s" % rel)
    return probs


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--cp-verify", required=True)
    ap.add_argument("--results", required=True)
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--plan", help="the registered FP_CALIB (calibration mode)")
    mode.add_argument("--no-calibration", action="store_true", help="the #43 job alone, no FP_CALIB")
    ap.add_argument("--repeats", type=int, required=True, help="the registered FP_REPEATS")
    ap.add_argument("--cold", choices=("quickstart", "cold", "none"), default="quickstart")
    ap.add_argument("--mutations", choices=("first", "all", "none"), default="first")
    ap.add_argument("--timeout", type=float, default=900)
    ap.add_argument("--report")
    a = ap.parse_args(argv)
    try:
        if a.repeats < 0 or a.repeats > 100:
            raise Usage("--repeats 0 to 100")
        if not (os.path.isfile(a.cp_verify) and os.access(a.cp_verify, os.X_OK)):
            raise Usage("--cp-verify is not an executable file")
        if not os.path.isdir(a.results):
            raise Usage("--results is not a directory")
        cp_verify = os.path.abspath(a.cp_verify)
        calibration = a.plan is not None
        plan_text = a.plan if calibration else ""
        if calibration and plan_text.strip() == "":
            raise Usage("empty or whitespace-only --plan (for the #43 job alone use --no-calibration)")
        plan = parse_plan(plan_text)
        runs = expected_runs(plan, a.repeats, a.cold)
        if not runs:
            raise Usage("nothing expected: refusing to pass an empty check")
    except Usage as e:
        print("verify_offbox: usage error: %s" % e, file=sys.stderr)
        return 2
    results = os.path.abspath(a.results)
    archive = archive_problems(results, [r for r, _ in runs], calibration, plan_text)
    for p in archive:
        print("FAIL archive: %s" % p)
    reports = []
    with tempfile.TemporaryDirectory(prefix="fp-verify-offbox-") as tmp:
        for run, names in runs:
            rep = check_run(cp_verify, results, run, names, a.mutations, a.timeout, tmp)
            reports.append(rep)
            print("%s %s (%d responses)%s" % (rep["verdict"], run, len(names),
                                               "" if rep["verdict"] == "PASS" else ": " + "; ".join(rep["problems"])))
    ok = all(r["verdict"] == "PASS" for r in reports) and a.mutations != "none" and not archive
    summary = {"verdict": "PASS" if ok else "FAIL", "runs_expected": len(runs),
               "runs_passed": sum(r["verdict"] == "PASS" for r in reports),
               "responses_expected": sum(len(n) for _, n in runs), "mutations": a.mutations,
               "mode": "calibration" if calibration else "no-calibration",
               "plan": plan_text.strip(), "repeats": a.repeats, "cold": a.cold,
               "archive_problems": archive, "runs": reports}
    if a.mutations == "none":
        print("mutation checks skipped: the PREREG requires them, so the overall verdict is FAIL")
    print("OVERALL %s: %d of %d runs passed, %d archive problems" % (summary["verdict"], summary["runs_passed"],
                                                                  len(runs), len(archive)))
    if a.report:
        with open(a.report, "w") as f:
            json.dump(summary, f, indent=1)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
