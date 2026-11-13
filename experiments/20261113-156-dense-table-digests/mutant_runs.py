#!/usr/bin/env python3
"""Secondary runs of PREREG.md (#156), metric 6: verifiers whose own table differs in one entry.

usage: mutant_runs.py <head tree> <sha256.tsv of the registered served run> <new run folder> <name>=<cp_verify> ...

Each <name>=<cp_verify> is a build of the head sources: "head" (unchanged), and "silu", "rope",
"exp", each built with the patch of that name in mutants/ applied (one entry of that table moved by
1, as a floating-point library that rounds the entry differently would give it).

The script writes the dense case files again with the head tree's served_form_test.py and the
binary named "head" (group routed-experts on prover/tests/configurations/pinned_no_proof_of_work),
checks that the three files of the cases dense and dense-with-digests have the SHA-256 that the
registered served run recorded, and gives both cases to every binary by the test's planning call.

Registered: on dense-with-digests, head is met; silu, rope, exp end NO: table-digest-silu,
-rope, -exp. Reported as it comes, not registered: what each binary says of the case dense (no
digest lines), where there is nothing to compare a table with.

Writes runs.tsv and summary.json. Exit 0 if the registered results hold, 1 otherwise.
"""

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys

KIT = os.path.join("prover", "tests", "configurations", "pinned_no_proof_of_work")
TEST = os.path.join("verifier", "tests", "served_form_test.py")
LINE = re.compile(r"^plan: not the standard parameter form \((.*)\): no run with these public inputs can be a verification \(at best status 14\)$", re.M)
CASES = ("routed-experts.dense-with-digests", "routed-experts.dense")
REGISTERED = {"head": "met", "silu": "NO: table-digest-silu", "rope": "NO: table-digest-rope", "exp": "NO: table-digest-exp"}


def planned(binary, work, case):
    folder = os.path.join(work, case)
    words = [binary, "-plan", "request", os.path.join(folder, "policy.txt"), os.path.join(folder, "KL.bin"), "0", "-layout", os.path.join(folder, "layout.txt"),
             "-prompt", os.path.join(work, "request.bin"), "-reply", os.path.join(work, "y.bin"), "-q"]  # fmt: skip
    p = subprocess.run(words, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, errors="replace", check=False)
    refused = [x for x in p.stdout.splitlines() if x.startswith("NO: ")]
    unmet = LINE.findall(p.stdout)
    build = re.findall(r"build=([0-9a-f]{64})", p.stdout)
    return p.returncode, refused[0] if refused else ("not met: " + unmet[0] if unmet else ("met" if p.returncode == 4 else "?")), build[0] if build else "-"


def sha(path):
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def main():
    a = sys.argv[1:]
    if len(a) < 4 or any("=" not in x for x in a[3:]):
        print(__doc__.split("\n\n")[1], file=sys.stderr)
        return 2
    tree, recorded, folder = os.path.abspath(a[0]), os.path.abspath(a[1]), os.path.abspath(a[2])
    binaries = {x.split("=", 1)[0]: os.path.abspath(x.split("=", 1)[1]) for x in a[3:]}
    os.makedirs(folder)
    work = os.path.join(folder, "work")
    p = subprocess.run([sys.executable, "-B", TEST, binaries["head"], KIT, work, "--condition", "routed-experts"], cwd=tree, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, check=False)
    bad = []
    if p.returncode != 0:
        bad.append("served_form_test.py on the group routed-experts: status %d" % p.returncode)
    with open(recorded, encoding="utf-8") as f:
        want = {(x.split("\t")[0], x.split("\t")[1]): x.split("\t")[2] for x in f.read().splitlines()[1:]}
    files = 0
    for case in CASES:
        for name in ("policy.txt", "KL.bin", "layout.txt"):
            files += 1
            if sha(os.path.join(work, case, name)) != want.get((case, name)):
                bad.append("%s/%s is not the file of the registered served run" % (case, name))
    rows, seen = [], {}
    for case in CASES:
        for which, binary in binaries.items():
            status, result, build = planned(binary, work, case)
            seen[which + " on " + case.split(".", 1)[1]] = result
            rows.append("\t".join([case, which, sha(binary), str(status), result]))
            print("%s, %s: status %d, %s" % (case, which, status, result), flush=True)
            if case == CASES[0] and result != REGISTERED.get(which, result):
                bad.append("%s on %s: %s, registered %s" % (which, case, result, REGISTERED[which]))
    if len({sha(b) for b in binaries.values()}) != len(binaries):
        bad.append("two of the binaries are the same file")
    shutil.rmtree(work)
    with open(os.path.join(folder, "runs.tsv"), "w", encoding="utf-8") as f:
        f.write("case\tbinary\tbinary_sha256\tstatus\tresult\n" + "\n".join(rows) + "\n")
    with open(os.path.join(folder, "summary.json"), "w", encoding="utf-8") as f:
        json.dump({"binaries": sorted(binaries), "case_files_checked_against_the_registered_run": files, "results": seen, "not_as_registered": bad}, f, indent=1)
    print("mutant_runs.py: %d binaries, %d cases: %s" % (len(binaries), len(CASES), "as registered" if not bad else "NOT as registered: " + "; ".join(bad)))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
