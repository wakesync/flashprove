#!/usr/bin/env python3
"""Main-vs-head comparison, second form (PREREG.md, Amendment 1): normalisation N2 and raw outputs kept.

usage: compare2.py <main cp_verify> <head cp_verify> <repo root> <new run folder> [--rounds N]

The calls are those of compare.py (imported from it). Runs alternate main, head, main, head, ...
For every run it keeps the raw output (raw/<call>.<binary>.<round>.txt), and records the exit status,
the last line, the SHA-256 of the raw output and the SHA-256 after normalisation N2:
  - the 64 hex digits after every build= replaced by <build>;
  - every line whose text, leading blanks removed, begins "seconds:" removed;
  - every number of the form <digits>.<digits> directly followed by " s" (a wall time) replaced by <t>.
Nothing else is changed. A second pass, N2-check, lists every line that N2 changed in any run, so a
reader can see that only wall times were touched (n2-touched.txt). Exit 0 if, for every call, all runs
of both binaries have one status, one last line and one N2 hash; 1 otherwise.
"""

import collections
import hashlib
import json
import os
import re
import subprocess
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from compare import calls  # noqa: E402

BUILD = re.compile(r"build=[0-9a-f]{64}")
TIME = re.compile(r"\b\d+\.\d+ s\b")


def n2(text):
    out = []
    for line in text.splitlines(True):
        if line.lstrip(" ").startswith("seconds:"):
            continue
        out.append(TIME.sub("<t> s", BUILD.sub("build=<build>", line)))
    return "".join(out)


def touched(text):
    """The lines that N2 removes or changes, with the wall times masked, so that equal shapes collapse."""
    got = []
    for line in text.splitlines():
        if line.lstrip(" ").startswith("seconds:"):
            got.append("removed: " + re.sub(r"\d+\.\d+", "<t>", line.strip())[:160])
        elif TIME.search(line):
            got.append("masked: " + TIME.sub("<t> s", line.strip())[:160])
    return got


def main():
    a = sys.argv[1:]
    rounds = 5
    if len(a) == 6 and a[4] == "--rounds":
        rounds = int(a[5])
        a = a[:4]
    if len(a) != 4:
        print(__doc__.split("\n\n")[1], file=sys.stderr)
        return 2
    binaries = {"main": os.path.abspath(a[0]), "head": os.path.abspath(a[1])}
    root, folder = a[2], a[3]
    os.makedirs(os.path.join(folder, "raw"))
    rows, summary, bad, shapes = [], {}, 0, collections.Counter()
    for name, words in calls(root):
        seen = {"main": [], "head": []}
        for r in range(rounds):
            for which in ("main", "head"):
                p = subprocess.run([binaries[which]] + words, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False)
                raw = p.stdout.decode("utf-8", "replace")
                with open(os.path.join(folder, "raw", "%s.%s.%d.txt" % (name, which, r)), "w", encoding="utf-8") as f:
                    f.write(raw)
                norm = n2(raw)
                last = norm.rstrip("\n").split("\n")[-1] if norm.strip() else ""
                h_raw = hashlib.sha256(raw.encode()).hexdigest()
                h_n2 = hashlib.sha256(norm.encode()).hexdigest()
                shapes.update(touched(raw))
                seen[which].append((p.returncode, last, h_n2))
                rows.append("\t".join([name, which, str(r), str(p.returncode), h_raw, h_n2, last]))
                print("%s %s round %d: status %d, n2 %s, %s" % (name, which, r, p.returncode, h_n2[:16], last[:60]), flush=True)
        same = len(set(seen["main"] + seen["head"])) == 1
        bad += not same
        summary[name] = {"same": same, "main": sorted(set(seen["main"])), "head": sorted(set(seen["head"]))}
    with open(os.path.join(folder, "runs.tsv"), "w", encoding="utf-8") as f:
        f.write("call\tbinary\tround\tstatus\tsha256_raw\tsha256_n2\tlast_line\n" + "\n".join(rows) + "\n")
    with open(os.path.join(folder, "n2-touched.txt"), "w", encoding="utf-8") as f:
        f.write("".join("%6d  %s\n" % (n, s) for s, n in sorted(shapes.items())))
    with open(os.path.join(folder, "summary.json"), "w", encoding="utf-8") as f:
        json.dump({"rounds": rounds, "normalisation": "N2", "calls": summary, "differ": bad}, f, indent=1)
    print("compare2.py: %d calls, %d rounds per binary: %d differ" % (len(summary), rounds, bad))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
