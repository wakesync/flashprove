#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Run the client envelope vectors (PREREG.md) through research/envelope/client_verify.py.

  run_suite.py --registered --cp-verify bin/cp_verify --runs 5 --out runs/registered
  run_suite.py --debug --out <tmp dir>          (debug vector set, STUB verifier; not a run)

Each vector runs in a fresh copy of its directory: the client's context and state, the envelope
bytes and the reply bytes. The proof bytes come from the stored example named in steps.json, with
the named transform (`none`, `cut1`). A step passes only if:
  RELEASE expected: exit 0, last line RELEASE, release file == reply bytes, state changed, the
                    `tee:` line starts `tee: none` or `tee: MOCK`.
  REJECT expected:  exit 1, last line exactly the registered `REJECT: <check>`, no release file,
                    state file byte-identical to before the step.
Rows go to <out>/rows.jsonl, one per step and run; the summary to <out>/summary.json.
"""

import argparse
import hashlib
import json
import os
import pathlib
import shutil
import statistics
import subprocess
import sys
import tempfile
import time

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parent.parent
CLIENT = REPO / "research" / "envelope" / "client_verify.py"
MAKE = REPO / "research" / "envelope" / "make_vectors.py"
STUB = REPO / "research" / "envelope" / "stub_cp_verify.py"
REGISTERED = REPO / "research" / "envelope" / "vectors"
EXAMPLE_DIRS = {"exact": "examples/accepted-proof", "clipped": "examples/accepted-proof-clipped-gap"}
HARD_STOP = "2026-11-12T01:00:00Z"
BUDGET_S = 30 * 60


def sha(data):
    return hashlib.sha256(data).hexdigest()


def proof_bytes(spec):
    data = (REPO / EXAMPLE_DIRS[spec["example"]] / "example.proof").read_bytes()
    if spec["transform"] == "none":
        return data
    if spec["transform"] == "cut1":
        return data[:-1]
    raise SystemExit("unknown transform %r" % spec["transform"])


def stop_epoch():
    return time.mktime(time.strptime(HARD_STOP, "%Y-%m-%dT%H:%M:%SZ")) - time.timezone


def run_vector(vdir, cp_verify, run, work_root):
    meta = json.loads((vdir / "steps.json").read_text())
    work = pathlib.Path(tempfile.mkdtemp(prefix=meta["name"] + "-", dir=work_root))
    for name in ("context.json", "state.json"):
        shutil.copyfile(vdir / name, work / name)
    rows = []
    for i, st in enumerate(meta["steps"]):
        pfile = work / ("proof-%d.bin" % i)
        pdata = proof_bytes(st["proof"])
        pfile.write_bytes(pdata)
        release = work / ("release-%d.bin" % i)
        before = (work / "state.json").read_bytes()
        env = (vdir / st["envelope"]).read_bytes()
        reply = (vdir / st["reply"]).read_bytes()
        words = [sys.executable, "-I", str(CLIENT), "deliver", "--context",
                 str(work / "context.json"), "--state", str(work / "state.json"),
                 "--root", str(REPO), "--deliver", st["deliver"],
                 "--envelope", str(vdir / st["envelope"]), "--reply", str(vdir / st["reply"]),
                 "--proof", str(pfile), "--now", str(st["now"]), "--release", str(release),
                 "--cp-verify", str(cp_verify)]
        t0 = time.perf_counter()
        done = subprocess.run(words, capture_output=True, text=True, timeout=900)
        wall = time.perf_counter() - t0
        lines = done.stdout.rstrip("\n").split("\n")
        after = (work / "state.json").read_bytes()
        released = release.exists()
        out = {k: next((ln[len(k) + 2:] for ln in lines if ln.startswith(k + ": ")), None)
               for k in ("signature", "tee", "proof", "cp_verify", "client", "why")}
        last = lines[-1] if lines else ""
        if st["expect"] == "RELEASE":
            ok = (done.returncode == 0 and last == "RELEASE" and released
                  and release.read_bytes() == reply and after != before
                  and (out["tee"] or "").startswith(("none", "MOCK"))
                  and (meta["name"] != "A6" or out["tee"].startswith("MOCK (not evidence")))
        else:
            ok = (done.returncode == 1 and last == st["expect"] and not released
                  and after == before)
        cp_s = None
        if out["cp_verify"] and "seconds=" in out["cp_verify"]:
            cp_s = float(out["cp_verify"].split("seconds=")[1].split(" ")[0])
        rows.append({"run": run, "vector": meta["name"], "kind": meta["kind"], "step": i,
                     "expect": st["expect"], "exit": done.returncode, "last": last, "pass": ok,
                     "released": released, "state_changed": after != before,
                     "signature": out["signature"], "tee": out["tee"], "proof": out["proof"],
                     "cp_verify": out["cp_verify"], "why": out["why"], "wall_s": wall,
                     "cp_verify_s": cp_s, "client_s": float(out["client"].split("=")[1])
                     if out["client"] else None,
                     "sha256": {"envelope": sha(env), "reply": sha(reply), "proof": sha(pdata),
                                "state_before": sha(before)},
                     "stderr_tail": done.stderr[-400:]})
    shutil.rmtree(work)
    return rows


def describe(xs):
    xs = [x for x in xs if x is not None]
    if not xs:
        return None
    return {"n": len(xs), "median": statistics.median(xs),
            "sd": statistics.stdev(xs) if len(xs) > 1 else 0.0, "min": min(xs), "max": max(xs)}


def main():
    ap = argparse.ArgumentParser()
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--registered", action="store_true")
    mode.add_argument("--debug", action="store_true")
    ap.add_argument("--cp-verify")
    ap.add_argument("--runs", type=int, default=5)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    out = pathlib.Path(a.out).resolve()
    if out.exists():
        raise SystemExit("refusing: %s exists (committed run files are never rewritten)" % out)
    granted = time.time()
    if a.debug:
        tmp = pathlib.Path(tempfile.mkdtemp(prefix="fp-envelope-debug-"))
        vectors = tmp / "vectors"
        stub_build = hashlib.sha256(b"flashprove-envelope-v1 STUB cp_verify, not a verifier"
                                    ).hexdigest()
        subprocess.run([sys.executable, str(MAKE), "--out", str(vectors), "--label", "debug",
                        "--build", stub_build], check=True)
        cp_verify = STUB
    else:
        if not a.cp_verify:
            raise SystemExit("--registered needs --cp-verify")
        vectors = REGISTERED
        cp_verify = pathlib.Path(a.cp_verify).resolve()
        if time.time() >= stop_epoch():
            raise SystemExit("past the lane hard stop %s" % HARD_STOP)
    out.mkdir(parents=True)
    names = sorted(json.loads((vectors / "INDEX.json").read_text())["vectors"])
    log = {"mode": "debug" if a.debug else "registered", "granted_unix": granted,
           "granted_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(granted)),
           "budget_s": BUDGET_S, "hard_stop": HARD_STOP, "cp_verify": cp_verify.name,
           "cp_verify_sha256": sha(cp_verify.read_bytes()), "vectors": len(names),
           "vector_sums_sha256": sha((vectors / "SHA256SUMS").read_bytes()),
           "affinity": sorted(os.sched_getaffinity(0)), "runs_planned": a.runs}
    print(json.dumps(log), flush=True)
    rows, killed = [], None
    work_root = pathlib.Path(tempfile.mkdtemp(prefix="fp-envelope-work-"))
    with open(out / "rows.jsonl", "w") as f:
        for run in range(1, a.runs + 1):
            order = names if run % 2 else list(reversed(names))
            for name in order:
                if time.time() - granted > BUDGET_S or (not a.debug and time.time() >= stop_epoch()):
                    killed = "budget or hard stop reached in run %d before %s" % (run, name)
                    break
                for row in run_vector(vectors / name, cp_verify, run, work_root):
                    rows.append(row)
                    f.write(json.dumps(row, sort_keys=True) + "\n")
                    f.flush()
            if killed:
                break
    shutil.rmtree(work_root, ignore_errors=True)
    per = {}
    for r in rows:
        per.setdefault(r["vector"], []).append(r)
    vec_summary = {}
    for name in names:
        rs = per.get(name, [])
        runs_done = sorted({r["run"] for r in rs})
        lasts = sorted({(r["step"], r["last"]) for r in rs})
        vec_summary[name] = {
            "kind": rs[0]["kind"] if rs else None, "runs": len(runs_done),
            "steps_passed": sum(r["pass"] for r in rs), "steps": len(rs),
            "all_pass": bool(rs) and all(r["pass"] for r in rs) and len(runs_done) == a.runs,
            "expect": sorted({r["expect"] for r in rs}), "last_lines": [x[1] for x in lasts],
            "released_any_reject": any(r["released"] for r in rs if r["expect"] != "RELEASE"),
            "wall_s": describe([r["wall_s"] for r in rs]),
            "cp_verify_s": describe([r["cp_verify_s"] for r in rs if r["cp_verify_s"]]),
            "client_s": describe([r["client_s"] for r in rs]),
            "client_minus_cp_verify_s": describe([r["client_s"] - (r["cp_verify_s"] or 0.0)
                                                  for r in rs if r["client_s"] is not None])}
    reject = [n for n, v in vec_summary.items() if v["kind"] == "reject"]
    accept = [n for n, v in vec_summary.items() if v["kind"] != "reject"]
    rel = [r for r in rows if r["expect"] == "RELEASE" and r["cp_verify_s"]]
    summary = dict(log, killed=killed, finished_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                   elapsed_s=time.time() - granted, rows=len(rows),
                   reject_vectors=len(reject), accept_vectors=len(accept),
                   reject_all_pass=sum(vec_summary[n]["all_pass"] for n in reject),
                   accept_all_pass=sum(vec_summary[n]["all_pass"] for n in accept),
                   reject_released=sum(vec_summary[n]["released_any_reject"] for n in reject),
                   reject_steps_passed=sum(r["pass"] for r in rows if r["expect"] != "RELEASE"),
                   reject_steps=sum(1 for r in rows if r["expect"] != "RELEASE"),
                   accept_steps_passed=sum(r["pass"] for r in rows if r["expect"] == "RELEASE"),
                   accept_steps=sum(1 for r in rows if r["expect"] == "RELEASE"),
                   release_cp_verify_s=describe([r["cp_verify_s"] for r in rel]),
                   release_overhead_s=describe([r["client_s"] - r["cp_verify_s"] for r in rel]),
                   verdict="PASS" if (not killed and all(v["all_pass"] for v in
                                                         vec_summary.values())) else
                   ("KILLED" if killed else "FAIL"),
                   per_vector=vec_summary)
    (out / "summary.json").write_text(json.dumps(summary, indent=1, sort_keys=True) + "\n")
    print("verdict=%s reject %d/%d accept %d/%d rows=%d killed=%s" % (
        summary["verdict"], summary["reject_all_pass"], len(reject), summary["accept_all_pass"],
        len(accept), len(rows), killed))
    for n, v in vec_summary.items():
        if not v["all_pass"]:
            print("NOT PASS %s %s %s" % (n, v["expect"], v["last_lines"]))
    return 0 if summary["verdict"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
