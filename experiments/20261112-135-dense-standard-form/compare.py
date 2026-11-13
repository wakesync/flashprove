#!/usr/bin/env python3
"""Main-vs-head comparison registered in PREREG.md (#135).

usage: compare.py <main cp_verify> <head cp_verify> <repo root> <new run folder> [--rounds N]

For every registered stored-proof call (whole call, the same with -q, the planning call) on the four
stored sets, runs main and head alternately (main, head, main, head, ...) and records for each run the
exit status, the last line, and the SHA-256 of the combined output after normalisation N (the 64 hex
digits after build= replaced by <build>; lines that begin "seconds:" removed). Writes runs.tsv (one row
per run) and summary.json into the run folder, and the normalised outputs of the first round under
outputs/. Exit 0 if every call agrees between main and head and within each binary; 1 otherwise.
No timing is reported.
"""

import hashlib
import json
import os
import re
import subprocess
import sys

SETS = {
    "full-size": None,
    "full-size-clipped-gap": "clipped-gap,25856,512,1,15,8",
    "accepted-proof": None,
    "accepted-proof-clipped-gap": "clipped-gap,9244130,323343,1,16,8",
}
BUILD = re.compile(r"build=[0-9a-f]{64}")


def normalise(text):
    text = BUILD.sub("build=<build>", text)
    return "".join(x for x in text.splitlines(True) if not x.startswith("seconds:"))


def calls(root):
    out = []
    for name, policy in SETS.items():
        d = os.path.join(root, "examples", name)
        with open(os.path.join(d, "ID.txt"), encoding="ascii") as f:
            ident = f.read().strip()
        whole = [os.path.join(d, "config"), os.path.join(d, "ivk"), os.path.join(d, "example.req"),
                 os.path.join(d, "example.y"), os.path.join(d, "example.proof"), "-id", ident]
        if policy:
            whole += ["-policy", policy]
        out.append((name + ".whole", whole))
        out.append((name + ".whole-q", whole + ["-q"]))
        c = os.path.join(d, "config")
        out.append((name + ".plan-request", ["-plan", "request", os.path.join(c, "policy.txt"), os.path.join(c, "KL.bin"), "128",
                                             "-layout", os.path.join(c, "layout.txt"), "-prompt", os.path.join(d, "example.req"),
                                             "-reply", os.path.join(d, "example.y"), "-q"]))
    return out


def main():
    a = sys.argv[1:]
    rounds = 2
    if len(a) == 6 and a[4] == "--rounds":
        rounds = int(a[5])
        a = a[:4]
    if len(a) != 4:
        print(__doc__.split("\n\n")[1], file=sys.stderr)
        return 2
    binaries = {"main": os.path.abspath(a[0]), "head": os.path.abspath(a[1])}
    root, folder = a[2], a[3]  # root as given: run from the repository with "." so that no output names a host path
    os.makedirs(os.path.join(folder, "outputs"))
    rows, summary, bad = [], {}, 0
    for name, words in calls(root):
        seen = {"main": [], "head": []}
        for r in range(rounds):
            for which in ("main", "head"):
                p = subprocess.run([binaries[which]] + words, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False)
                text = normalise(p.stdout.decode("utf-8", "replace"))
                last = text.rstrip("\n").split("\n")[-1] if text.strip() else ""
                digest = hashlib.sha256(text.encode()).hexdigest()
                seen[which].append((p.returncode, last, digest))
                rows.append("\t".join([name, which, str(r), str(p.returncode), digest, last]))
                if r == 0:
                    with open(os.path.join(folder, "outputs", "%s.%s.txt" % (name, which)), "w", encoding="utf-8") as f:
                        f.write(text)
                print("%s %s round %d: status %d, %s, %s" % (name, which, r, p.returncode, digest[:16], last[:60]), flush=True)
        same = len(set(seen["main"] + seen["head"])) == 1
        bad += not same
        summary[name] = {"same": same, "main": sorted(set(seen["main"])), "head": sorted(set(seen["head"]))}
    with open(os.path.join(folder, "runs.tsv"), "w", encoding="utf-8") as f:
        f.write("call\tbinary\tround\tstatus\tsha256_normalised\tlast_line\n" + "\n".join(rows) + "\n")
    with open(os.path.join(folder, "summary.json"), "w", encoding="utf-8") as f:
        json.dump({"rounds": rounds, "calls": summary, "differ": bad}, f, indent=1)
    print("compare.py: %d calls, %d rounds per binary: %d differ" % (len(summary), rounds, bad))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
