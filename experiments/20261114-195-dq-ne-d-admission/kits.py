#!/usr/bin/env python3
"""Kit helper of experiment 20261114-195-dq-ne-d-admission (issue #195).

Makes a configuration folder (policy.txt, KL.bin, then layout.txt) for another shape from a
committed kit, and makes planning calls on it. It reads no proof and makes none.

  kits.py selfcheck <repo>
      the iota formula below must give the committed kits' own lines iota_0..7 and iotaH_0..5
  kits.py make <repo> <base kit folder> <new folder> key=value ..
      writes policy.txt (the named lines changed, iota lines recomputed, table digests recomputed
      by scales/policy_tables.py if the kit has them) and copies KL.bin
  kits.py plan <repo> <cp_verify> <kit folder> <label>
      -plan arrays, prover/tools/pack_layout.py, -plan accounting; prints one JSON object

Every call of cp_verify runs under an address-space limit of 4 GiB.
"""
import json
import os
import pathlib
import re
import resource
import shutil
import subprocess
import sys

AS_LIMIT = 4 << 30


def clog2(n):
    return max(0, (n - 1).bit_length())


def words(text):
    """The value lines 'name number' of a parameter file, and its call lines by kind."""
    val, calls = {}, {"call": [], "callA": [], "callH": []}
    for line in text.splitlines():
        w = line.split(" ")
        if w[0] in calls:
            calls[w[0]].append(w[1:])
        elif len(w) == 2 and w[1].isdigit():
            val[w[0]] = int(w[1])
    return val, calls


def iota(text):
    """iota_0..7 and iotaH_0..5 as layout() and the output head derive them (cp_verify.cpp: place(),
    c.n = ll + lJ + lt, dT = min(lidb, least n), iota = n - dT). Written from the source's rules;
    selfcheck() compares it with the committed kits' lines."""
    v, calls = words(text)
    lt, ll, d, f, NE = v["lt"], v["ll"], v["d"], v["f"], v["NE"]
    dq, dkv = v["H"] * v["dh"], v["G"] * v["dh"]
    nqk = dq + dkv
    lidb = v.get("lidb", 22)
    row = (99 if v.get("xl", 4) == 5 else 74)
    seg = {"G": f, "U": f, "UT": f, "QK": nqk, "QKH": nqk, "N1": d, "N1H": d, "N2": d, "N2H": d, "O": d, "D": d, "V": dkv,
           "XR": d, "LR": NE, "LT": NE, "DD": NE, "GH": f, "UH": f, "OH": d, "DH": d, "VH": dkv, "ROW": row * 2,
           "LH": NE, "SEL": NE, "L3": NE, "G0": f, "CN1": d, "CN2": d, "CQK": nqk, "CV": dkv, "CLR": NE, "MR": 1, "CG": f, "F": f}
    floor = max(0, v["nmin"] - ll - lt)
    n = [ll + max(clog2(sum(seg[s] for s in c[2:])), floor) + lt for c in calls["call"]]
    dT = min([lidb] + n)
    out = {"iota_%d" % q: (n[q] - dT if q < len(n) else 0) for q in range(8)}
    S2 = 1 << (v["la"] - lt)
    JV = (v["V"] + S2 - 1) // S2 * S2
    JVa = 1 << (clog2(JV) - 1)
    segH = {"NF": d, "NFH": d, "HD0": JV, "HD1": JV, "ROW": row + 21, "HD2": JV, "CNF": d, "HE0": JVa, "HE1": JV - JVa}
    nminH = v.get("nminH", v["nmin"])
    floorH = max(0, nminH - lt)
    nH = [max(clog2(sum(segH[s] for s in c[2:])), floorH) + lt for c in calls["callH"]]
    dTH = min([lidb] + nH)
    out.update({"iotaH_%d" % q: (nH[q] - dTH if q < len(nH) else 0) for q in range(6)})
    return out


def selfcheck(repo):
    bad = 0
    kits = sorted(pathlib.Path(repo, "prover", "examples").glob("*/policy.txt")) + [pathlib.Path(repo, "prover/tests/configurations/pinned_no_proof_of_work/policy.txt")]
    for p in kits:
        text = p.read_text()
        v, _ = words(text)
        mine = iota(text)
        differ = sorted(k for k in mine if mine[k] != v.get(k))
        bad += bool(differ)
        print("selfcheck %s/%s: %s" % (p.parent.name, p.name, "iota lines reproduced" if not differ else "DIFFER at " + ",".join(differ)))
    print("selfcheck: %d kits, %d not reproduced" % (len(kits), bad))
    return 1 if bad else 0


def make(repo, base, out, changes):
    base, out = pathlib.Path(base), pathlib.Path(out)
    text = (base / "policy.txt").read_text()

    def put(text, key, value):
        text, n = re.subn(r"(?m)^%s \d+$" % re.escape(key), "%s %d" % (key, value), text)
        if n != 1:
            sys.exit("kits.py: the base file has %d lines '%s'" % (n, key))
        return text

    for key, value in changes.items():
        if "," in str(value):  # a line of several numbers, such as table=8,26,7864320,524287,0,14
            text, n = re.subn(r"(?m)^%s( \d+)+$" % re.escape(key), "%s %s" % (key, " ".join(str(int(x)) for x in value.split(","))), text)
            if n != 1:
                sys.exit("kits.py: the base file has %d lines '%s'" % (n, key))
            continue
        text = put(text, key, int(value))
    for key, value in iota(text).items():
        text = put(text, key, value)
    out.mkdir(parents=True)
    (out / "policy.txt").write_text(text)
    if re.search(r"(?m)^trope0 \d+$", text):
        r = subprocess.run([sys.executable, "-B", str(pathlib.Path(repo, "scales/policy_tables.py")), str(out / "policy.txt")], capture_output=True, text=True)
        if r.returncode != 0:
            sys.exit("kits.py: policy_tables.py refused the file: " + r.stderr.strip())
        (out / "policy.txt").write_text(r.stdout)
    shutil.copyfile(base / "KL.bin", out / "KL.bin")
    print("made %s: %s" % (out.name, " ".join("%s=%s" % kv for kv in sorted(changes.items()))))
    return 0


def call(args):
    """One cp_verify call under the address-space limit: status, lines, peak resident KiB."""
    before = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss
    p = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, errors="replace",
                         preexec_fn=lambda: resource.setrlimit(resource.RLIMIT_AS, (AS_LIMIT, AS_LIMIT)))
    try:
        text, _ = p.communicate(timeout=110)
    except subprocess.TimeoutExpired:
        p.kill()
        text, _ = p.communicate()
        return {"status": "timeout", "last": "", "lines": [], "maxrss_kib_children_so_far": None}
    lines = text.splitlines()
    after = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss
    return {"status": p.returncode, "last": lines[-1] if lines else "", "lines": lines, "maxrss_kib_children_so_far": max(before, after)}


def plan(repo, verifier, kit, label, keep=None):
    kit = pathlib.Path(kit)
    out = {"label": label, "kit": kit.name}
    if (kit / "layout.txt").exists():
        os.remove(kit / "layout.txt")
    a = call([verifier, "-plan", "arrays", str(kit), "128"])
    out["arrays"] = {"status": a["status"], "last": a["last"], "array_lines": sum(l.startswith("array:") for l in a["lines"])}
    if a["status"] == 4 and out["arrays"]["array_lines"]:
        l = next(line.split()[4] for line in (kit / "policy.txt").read_text().splitlines() if line.startswith("group link "))
        r = subprocess.run([sys.executable, "-B", str(pathlib.Path(repo, "prover/tools/pack_layout.py")), "--arrays", "-", l, "4"],
                           input="\n".join(a["lines"]) + "\n", capture_output=True, text=True)
        out["pack_layout"] = {"status": r.returncode, "stderr": r.stderr.strip()[:200]}
        if r.returncode == 0:
            (kit / "layout.txt").write_text(r.stdout)
    c = call([verifier, "-plan", "accounting", str(kit), "128"])
    out["accounting"] = {"status": c["status"], "last": c["last"],
                         "rounds_hold_lines": sum(l.startswith("accounting: THE ROUNDS: HOLD") for l in c["lines"]),
                         "internal_lines": sum("internal-" in l for l in c["lines"]),
                         "not_standard_form": [l[:160] for l in c["lines"] if l.startswith("plan: not the standard parameter form")],
                         "maxrss_kib_children_so_far": c["maxrss_kib_children_so_far"]}
    out["planned"] = c["status"] == 4 and c["last"] == "PLAN ONLY: no proof was checked" and out["accounting"]["rounds_hold_lines"] == 1 and not out["accounting"]["internal_lines"]
    if keep:
        pathlib.Path(keep).write_text("\n".join(c["lines"]) + "\n")
    print(json.dumps(out))
    return out


def main():
    a = sys.argv[1:]
    if a[:1] == ["selfcheck"] and len(a) == 2:
        return selfcheck(a[1])
    if a[:1] == ["make"] and len(a) >= 4:
        return make(a[1], a[2], a[3], dict(x.split("=") for x in a[4:]))
    if a[:1] == ["plan"] and len(a) == 5:
        plan(a[1], a[2], a[3], a[4])
        return 0
    sys.exit(__doc__)


if __name__ == "__main__":
    sys.exit(main())
