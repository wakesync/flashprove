#!/usr/bin/env python3
"""Negative tests N1 to N3 of PREREG.md: complete honest proofs of another statement, given to the
application-level checks that should stop them.

N1  commitment substitution: the clipped-gap example's own files under the exact-match example's ID.
N2  policy substitution: the clipped-gap example under its own ID, (a) without -policy, (b) with an
    exact-match -policy.
N3  coverage substitution: the exact-match example (range 60:64) given to integrations/check_proof.py by a
    client that expects 59:64. Also recorded: bin/cp_verify alone on those files.

Each arm runs 5 times; odd repetitions run the control first, even ones the attack first. Output: one
JSON file with input SHA-256s, commands (repository-relative), exit codes, last lines and the line that
names the check. Paths of the checkout are replaced by "<repo>".

Usage (from anywhere):
  python3 experiments/20261110-6-coverage-inventory/negative.py --dry-run
  python3 experiments/20261110-6-coverage-inventory/negative.py --out runs/negative-registered.json
Run the registered call under fp-heavy.sh, pinned to cores 0-5. Budget: 15 minutes from the start of
this process (the moment the gate granted its slot), after which it stops and marks the file partial.
"""
import argparse
import hashlib
import json
import os
import platform
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
VERIFY = "bin/cp_verify"
EXACT = "examples/accepted-proof"
GAP = "examples/accepted-proof-clipped-gap"
EXACT_ID = "79a5a2bc7a469b40df73dedf40abeb740671e8ae8077738bd3743897aeb22183"
GAP_ID = "8df714349b76202d6f302bb80b33d6d0798bd81d987b9e387038b7fd24c55ae6"
GAP_POLICY = "clipped-gap,9244130,323343,1,16,8"
EXACT_POLICY = "exact-match,256,256,0,16,8"
REPS = 5
BUDGET_S = 15 * 60


def files_of(ex):
    return [ex + "/config", ex + "/ivk", ex + "/example.req", ex + "/example.y", ex + "/example.proof"]


def cpv(ex, ident, policy=None):
    cmd = [VERIFY] + files_of(ex) + ["-id", ident, "-j", "1", "-q"]
    if policy:
        cmd += ["-policy", policy]
    return cmd


def checkp(rng):
    return [
        sys.executable, "integrations/check_proof.py", EXACT + "/example.proof", EXACT + "/example.req",
        "--public-key-dir", EXACT + "/ivk", "--parameter-file", EXACT + "/config/policy.txt",
        "--scales-file", EXACT + "/config/KL.bin", "--commitment-id", EXACT_ID,
        "--range", rng, "--next-token", "199", "--end-token", "none", "--threads", "1",
    ]


# name, command, expected exit, expected last line (prefix), reason line that must be present (substring)
CASES = {
    "N1": {
        "intended_check": "ID comparison in the key stage, refuse(\"model-statement\") in verifier/src/cp_verify.cpp",
        "control": ("own ID, own -policy", cpv(GAP, GAP_ID, GAP_POLICY), 0, "WITHIN LIMITS:", None),
        "attacks": [
            ("clipped-gap example's complete files under the exact-match example's ID",
             cpv(GAP, EXACT_ID, GAP_POLICY), 1, "NO: model-statement",
             "id: these are not the files of the commitment that you named"),
        ],
    },
    "N2": {
        "intended_check": "cpPolicyHeld in verifier/src/cp_verify.cpp (NO: policy, with the reason line policy: ...)",
        "control": ("own ID, own -policy", cpv(GAP, GAP_ID, GAP_POLICY), 0, "WITHIN LIMITS:", None),
        "attacks": [
            ("N2a: own ID, no -policy (a client that expects exact match)",
             cpv(GAP, GAP_ID), 1, "NO: policy",
             "policy: the request covers more than the output token, the parameter file sets another policy than exact-match, and the call has no -policy"),
            ("N2b: own ID, -policy exact-match",
             cpv(GAP, GAP_ID, EXACT_POLICY), 1, "NO: policy",
             "policy: the option -policy names another kind of policy"),
        ],
    },
    "N3": {
        "intended_check": "integrations/check_proof.py Request.__init__ range comparison",
        "control": ("check_proof.py --range 60:64 (the proof's own range)", checkp("60:64"), 0, "check_proof: verified", None),
        "attacks": [
            ("check_proof.py --range 59:64 (client expects one more checked token)",
             checkp("59:64"), 1, "check_proof: rejected",
             "the request file's checked range is 60:64, but you expect 59:64"),
        ],
        "also": ("bin/cp_verify alone on the same files: the proof part accepts", cpv(EXACT, EXACT_ID), 0, "YES", None),
    },
}


def sha(path):
    p = os.path.join(ROOT, path)
    if os.path.isdir(p):
        h = hashlib.sha256()
        for dp, dn, fn in sorted(os.walk(p)):
            dn.sort()
            for f in sorted(fn):
                q = os.path.join(dp, f)
                h.update(os.path.relpath(q, p).encode() + b"\0")
                with open(q, "rb") as x:
                    h.update(hashlib.sha256(x.read()).digest())
        return "dir:" + h.hexdigest()
    with open(p, "rb") as x:
        return hashlib.sha256(x.read()).hexdigest()


def clean(text):
    return text.replace(ROOT, "<repo>").replace(sys.executable, "python3")


def run(cmd):
    t0 = time.time()
    p = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, timeout=600)
    out = clean(p.stdout + p.stderr)
    lines = [l for l in out.splitlines() if l.strip()]
    return {"exit": p.returncode, "last_line": lines[-1] if lines else "", "tail": lines[-8:],
            "seconds": round(time.time() - t0, 3), "_all": lines}


def judge(res, exp_exit, exp_last, reason):
    ok = res["exit"] == exp_exit and res["last_line"].startswith(exp_last)
    if reason is not None:
        hit = [l for l in res["_all"] if reason in l]
        res["reason_line"] = hit[0] if hit else None
        ok = ok and bool(hit)
    res["as_expected"] = ok
    del res["_all"]
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--out", default="runs/negative-registered.json")
    a = ap.parse_args()
    start = time.time()
    inputs = {p: sha(p) for p in [VERIFY, "integrations/check_proof.py"] + files_of(EXACT) + files_of(GAP)}
    doc = {
        "experiment": "20261110-6-coverage-inventory", "arms": "N1, N2 (a, b), N3",
        "started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(start)),
        "note_start": "start = the moment fp-heavy.sh granted the slot (this process starts inside the gate)",
        "budget_seconds": BUDGET_S, "reps": REPS, "order": "odd rep: control then attacks; even rep: attacks then control",
        "inputs_sha256": inputs, "python": platform.python_version(), "affinity": sorted(os.sched_getaffinity(0)),
        "dry_run": a.dry_run, "cases": {}, "partial": False,
    }
    for name, c in CASES.items():
        doc["cases"][name] = {"intended_check": c["intended_check"], "reps": []}
    if a.dry_run:
        for name, c in CASES.items():
            arms = [c["control"]] + c["attacks"] + ([c["also"]] if "also" in c else [])
            doc["cases"][name]["commands"] = [" ".join(x[1]).replace(sys.executable, "python3") for x in arms]
        print(json.dumps(doc, indent=1))
        return 0
    for rep in range(1, REPS + 1):
        for name, c in CASES.items():
            if time.time() - start > BUDGET_S:
                doc["partial"] = True
                break
            arms = [("control",) + c["control"]] + [("attack",) + x for x in c["attacks"]]
            if rep % 2 == 0:
                arms = arms[1:] + arms[:1]
            if "also" in c:
                arms.append(("also",) + c["also"])
            got = []
            for role, desc, cmd, ee, el, reason in arms:
                r = judge(run(cmd), ee, el, reason)
                r.update({"role": role, "desc": desc,
                          "cmd": " ".join(cmd).replace(sys.executable, "python3")})
                got.append(r)
            doc["cases"][name]["reps"].append({"rep": rep, "arms": got})
        if doc["partial"]:
            break
    summary = {}
    for name, c in doc["cases"].items():
        reps = c["reps"]
        att = [x for r in reps for x in r["arms"] if x["role"] == "attack"]
        ctl = [x for r in reps for x in r["arms"] if x["role"] == "control"]
        also = [x for r in reps for x in r["arms"] if x["role"] == "also"]
        summary[name] = {
            "reps_done": len(reps),
            "attacks_rejected_for_intended_check": sum(x["as_expected"] for x in att), "attacks": len(att),
            "attacks_accepted": sum(x["exit"] == 0 for x in att),
            "controls_accepted": sum(x["as_expected"] for x in ctl), "controls": len(ctl),
            "also_as_expected": sum(x["as_expected"] for x in also), "also": len(also),
        }
        secs = sorted(x["seconds"] for r in reps for x in r["arms"])
        summary[name]["seconds_min_median_max"] = [secs[0], secs[len(secs) // 2], secs[-1]] if secs else None
        summary[name]["pass"] = (len(reps) == REPS and summary[name]["attacks_rejected_for_intended_check"] == len(att)
                                 and summary[name]["controls_accepted"] == len(ctl) and summary[name]["also_as_expected"] == len(also))
    doc["summary"] = summary
    doc["finished_utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    doc["elapsed_seconds"] = round(time.time() - start, 1)
    out = os.path.join(HERE, a.out)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    if os.path.exists(out):
        print("refusing to overwrite " + a.out)
        return 2
    with open(out, "w") as h:
        json.dump(doc, h, indent=1, sort_keys=True)
        h.write("\n")
    print(json.dumps(summary, indent=1, sort_keys=True))
    return 0 if all(s["pass"] for s in summary.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
