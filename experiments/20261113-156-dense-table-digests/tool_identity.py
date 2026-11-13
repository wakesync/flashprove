#!/usr/bin/env python3
"""Registered check of PREREG.md (#156): scales/policy_tables.py prints the same bytes on head as on
main for every parameter file with NE above 0.

usage: tool_identity.py <main tree> <head tree> <dense policy.txt> <new run folder>

For every parameter file under prover/examples/ and prover/tests/configurations/ of the head tree
(the files themselves must be byte-identical in the two trees), runs each tree's
scales/policy_tables.py in its three modes (default, --check, --strip) and records the exit status
and the SHA-256 of standard output and of standard error. Then runs both tools on the dense file
given (a file with NE 0 and its digest lines, as the served-form test writes it): there the two
tools are registered to differ (main rejects the file, head prints it unchanged and --check passes).

Writes runs.tsv and summary.json. Exit 0 if every file with NE above 0 gives the same status and
bytes under both tools in all three modes, no file with NE 0 is among the tree's files, and the
dense file behaves as registered; 1 otherwise. Paths in the outputs are relative to the trees.
"""

import glob
import hashlib
import json
import os
import subprocess
import sys

MODES = ((), ("--check",), ("--strip",))


def run(tree, mode, path):
    p = subprocess.run([sys.executable, "-B", os.path.join("scales", "policy_tables.py"), *mode, path], cwd=tree, capture_output=True, check=False)
    return p.returncode, hashlib.sha256(p.stdout).hexdigest(), hashlib.sha256(p.stderr).hexdigest(), p.stdout


def experts(path):
    with open(path, encoding="ascii") as f:
        values = [x.split(" ")[1] for x in f.read().split("\n") if x.startswith("NE ")]
    return len(values) == 1 and values[0] != "0"


def main():
    a = sys.argv[1:]
    if len(a) != 4:
        print(__doc__.split("\n\n")[1], file=sys.stderr)
        return 2
    main_tree, head_tree, dense, folder = (os.path.abspath(x) for x in a)
    os.makedirs(folder)
    files = sorted(glob.glob(os.path.join(head_tree, "prover", "examples", "*", "policy*.txt")) + glob.glob(os.path.join(head_tree, "prover", "tests", "configurations", "*", "policy*.txt")))
    rows, bad, same = [], [], 0
    for path in files:
        rel = os.path.relpath(path, head_tree)
        with open(path, "rb") as f, open(os.path.join(main_tree, rel), "rb") as g:
            if f.read() != g.read():
                bad.append("%s differs between the two trees" % rel)
        if not experts(path):
            bad.append("%s has NE 0: not registered" % rel)
        for mode in MODES:
            m, h = run(main_tree, mode, rel), run(head_tree, mode, rel)
            ok = m[:3] == h[:3]
            same += ok
            if not ok:
                bad.append("%s %s: main and head differ" % (rel, " ".join(mode) or "default"))
            rows.append("\t".join([rel, " ".join(mode) or "default", str(m[0]), str(h[0]), m[1], h[1], m[2], h[2], "same" if ok else "DIFFER"]))
            print("%s %s: main status %d, head status %d: %s" % (rel, " ".join(mode) or "default", m[0], h[0], "same" if ok else "DIFFER"), flush=True)
    with open(dense, "rb") as f:
        dense_bytes = f.read()
    seen = {}
    for mode in MODES[:2]:
        m, h = run(main_tree, mode, dense), run(head_tree, mode, dense)
        seen[" ".join(mode) or "default"] = {"main_status": m[0], "head_status": h[0], "head_prints_the_file_unchanged": h[3] == dense_bytes}
        rows.append("\t".join(["<the dense file>", " ".join(mode) or "default", str(m[0]), str(h[0]), m[1], h[1], m[2], h[2], "registered to differ"]))
    if seen["default"]["main_status"] != 2 or seen["default"]["head_status"] != 0 or not seen["default"]["head_prints_the_file_unchanged"]:
        bad.append("the dense file, default mode: not (main rejects, head prints it unchanged)")
    if seen["--check"]["main_status"] != 2 or seen["--check"]["head_status"] != 0:
        bad.append("the dense file, --check: not (main rejects, head passes)")
    with open(os.path.join(folder, "runs.tsv"), "w", encoding="utf-8") as f:
        f.write("file\tmode\tmain_status\thead_status\tmain_stdout_sha256\thead_stdout_sha256\tmain_stderr_sha256\thead_stderr_sha256\tverdict\n" + "\n".join(rows) + "\n")
    summary = {"files_with_experts": len(files), "modes": len(MODES), "runs_per_tool": len(files) * len(MODES), "same": same, "dense_file": seen,
               "dense_file_sha256": hashlib.sha256(dense_bytes).hexdigest(), "not_as_registered": bad}  # fmt: skip
    with open(os.path.join(folder, "summary.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=1)
    print("tool_identity.py: %d files, %d modes: %d of %d the same on main and head; the dense file: %s; %s"
          % (len(files), len(MODES), same, len(files) * len(MODES), seen, "as registered" if not bad else "NOT as registered: " + "; ".join(bad)))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
