#!/usr/bin/env python3
"""Off-box verification of an H200 job's results (RUNBOOK.md step 8), on CPU, after restore.

Checks EVERY response that the job was expected to produce, against the run's own commitment ID,
with a cp_verify built by the operator from the pinned commit, and fails closed:

  * the expected runs come from the plan, not from what is in the archive: the #43 cold run
    (`quickstart` with FP_ONBOX_BUILD=1, `cold` with 0, or none), the warm repeats rep1..repN
    (each one response, `example`), and every calibration run <id>-1..<id>-<repeats> of the
    FP_CALIB plan (each <requests> responses r01..rNN). The plan is read from results/calib-plan.txt
    (the job writes it) or given with --plan; if both exist they must be equal.
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
  * the overall verdict is PASS only if every expected run passed and at least one run was expected.

Exit status: 0 PASS, 1 FAIL, 2 usage error (nothing checked). A JSON report goes to --report.
It never contacts any host. It does not check SHA256SUMS (RUNBOOK.md step 5's tar/sha256sum lines do).

usage: python3 verify_offbox.py --cp-verify PATH --results DIR [--plan FP_CALIB] [--repeats N]
                                [--cold quickstart|cold|none] [--mutations first|all|none]
                                [--timeout S] [--report FILE]
"""
import argparse
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


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--cp-verify", required=True)
    ap.add_argument("--results", required=True)
    ap.add_argument("--plan")
    ap.add_argument("--repeats", type=int, default=10)
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
        on_disk = None
        pf = os.path.join(a.results, "calib-plan.txt")
        if os.path.exists(pf):
            with open(pf) as f:
                on_disk = f.read()
        if a.plan is not None and on_disk is not None and a.plan.split() != on_disk.split():
            raise Usage("--plan differs from results/calib-plan.txt")
        plan_text = a.plan if a.plan is not None else (on_disk or "")
        if plan_text.strip() == "" and plan_text != "":
            raise Usage("whitespace-only plan")
        plan = parse_plan(plan_text)
        runs = expected_runs(plan, a.repeats, a.cold)
        if not runs:
            raise Usage("nothing expected: refusing to pass an empty check")
    except Usage as e:
        print("verify_offbox: usage error: %s" % e, file=sys.stderr)
        return 2
    reports = []
    with tempfile.TemporaryDirectory(prefix="fp-verify-offbox-") as tmp:
        for run, names in runs:
            rep = check_run(cp_verify, os.path.abspath(a.results), run, names, a.mutations, a.timeout, tmp)
            reports.append(rep)
            print("%s %s (%d responses)%s" % (rep["verdict"], run, len(names),
                                               "" if rep["verdict"] == "PASS" else ": " + "; ".join(rep["problems"])))
    ok = all(r["verdict"] == "PASS" for r in reports) and a.mutations != "none"
    summary = {"verdict": "PASS" if ok else "FAIL", "runs_expected": len(runs),
               "runs_passed": sum(r["verdict"] == "PASS" for r in reports),
               "responses_expected": sum(len(n) for _, n in runs), "mutations": a.mutations,
               "plan": plan_text.strip(), "repeats": a.repeats, "cold": a.cold, "runs": reports}
    if a.mutations == "none":
        print("mutation checks skipped: the PREREG requires them, so the overall verdict is FAIL")
    print("OVERALL %s: %d of %d runs passed" % (summary["verdict"], summary["runs_passed"], len(runs)))
    if a.report:
        with open(a.report, "w") as f:
            json.dump(summary, f, indent=1)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
