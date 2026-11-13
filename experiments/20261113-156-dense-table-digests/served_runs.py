#!/usr/bin/env python3
"""Registered served-form runs of PREREG.md (#156): metrics 1 and 2.

usage: served_runs.py <main cp_verify> <main tree> <head cp_verify> <head tree> <new run folder> [--rounds N]

1. Runs verifier/tests/served_form_test.py on prover/tests/configurations/pinned_no_proof_of_work,
   N times per tree (default 5), alternating main, head: main's test file with the main binary, the
   head tree's test file with the head binary. Each run's output is kept as <tree>-<round>.log.
   Every run of one tree must print the same case lines.
2. Compares the two trees case by case and with the results registered in the PREREG, and prints a
   Markdown table (also written to table.md).
3. Gives the three files of every case of the group routed-experts, as the head tree's first run
   wrote them, to both binaries by the test's own planning call, and records for each the exit
   status, the refusal or the unmet conditions, the printed configuration= and the statement line
   (dense-files.tsv). The parameter files of these cases are copied to dense-files/<case>.policy.txt
   and the SHA-256 of all three files is in dense-files/sha256.tsv.

Writes summary.json. Exit 0 if everything is as registered, 1 otherwise. No timing is reported.
Run it from anywhere; the trees are entered with cwd so that no output names a path of the host.
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
CASE = re.compile(r"^([a-z-]+\.[A-Za-z0-9-]+): (.*): (status \d+, .*?); expected: (.*): (as expected|not as expected)$")
MET = "status 4, not met: (), the one-time files: ('a record', 'a record')"
ONLY = "status 4, not met: ('table-digests',), the one-time files: ('a record', 'a record')"


def no(name):
    return "status 1, ['%s']" % name


# The results registered for head (PREREG.md, "Acceptance threshold"). Every other case: as on main.
REGISTERED = {
    "routed-experts.dense": ONLY,
    "routed-experts.dense-with-digests": MET,
    "routed-experts.dense-with-sigmoid-digest": no("policy-tables"),
    "routed-experts.dense-sigmoid-one-bit": no("policy-tables"),
    "routed-experts.dense-partial-digests": no("policy-tables"),
    "routed-experts.dense-silu-altered": no("table-digest-silu"),
    "routed-experts.dense-rope-altered": no("table-digest-rope"),
    "routed-experts.dense-exp-altered": no("table-digest-exp"),
    "routed-experts.dense-silu-table-moved": no("table-digest-silu"),
    "routed-experts.dense-rope-table-moved": no("table-digest-rope"),
    "routed-experts.dense-exp-table-moved": no("table-digest-exp"),
    "routed-experts.dense-with-gcl": no("policy-gcl"),
    "routed-experts.dense-with-rcl": no("policy-rcl"),
    "routed-experts.NE-0": no("header-absent-class"),
}
# What the main binary is registered to give on the head tree's dense files (metric 2).
ON_MAIN = {
    "routed-experts.dense": "met",
    "routed-experts.dense-with-gcl": "NO: policy-gcl",
    "routed-experts.dense-with-rcl": "NO: policy-rcl",
    "routed-experts.NE-0": "NO: header-absent-class",
}  # every other dense case has digest lines: NO: policy-tables
LINE = re.compile(r"^plan: not the standard parameter form \((.*)\): no run with these public inputs can be a verification \(at best status 14\)$", re.M)


def cases(text):
    got = {}
    for line in text.splitlines():
        m = CASE.match(line)
        if m:
            got[m.group(1)] = (m.group(3), m.group(5))
    return got


def planned(binary, work, case):
    """(status, result, configuration, statement line) of the test's planning call on a case's files."""
    folder = os.path.join(work, case)
    words = [binary, "-plan", "request", os.path.join(folder, "policy.txt"), os.path.join(folder, "KL.bin"), "0"]
    if os.path.exists(os.path.join(folder, "layout.txt")):
        words += ["-layout", os.path.join(folder, "layout.txt")]
    words += ["-prompt", os.path.join(work, "request.bin"), "-reply", os.path.join(work, "y.bin"), "-q"]
    p = subprocess.run(words, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, errors="replace", check=False)
    lines = p.stdout.splitlines()
    refused = [x for x in lines if x.startswith("NO: ")]
    unmet = LINE.findall(p.stdout)
    result = refused[0] if refused else ("not met: " + unmet[0] if unmet else ("met" if p.returncode == 4 else "?"))
    configuration = ([x[len("configuration=") :] for x in lines if x.startswith("configuration=")] or ["-"])[0]
    statement = ([x for x in lines if x.startswith("statement: ")] or ["-"])[0]
    tables = ([x for x in lines if x.startswith("plan: this program's ")] or ["-"])[0]
    return p.returncode, result, configuration, statement, tables


def sha(path):
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def main():
    a = sys.argv[1:]
    rounds = 5
    if len(a) == 7 and a[5] == "--rounds":
        rounds = int(a[6])
        a = a[:5]
    if len(a) != 5:
        print(__doc__.split("\n\n")[1], file=sys.stderr)
        return 2
    binary = {"main": os.path.abspath(a[0]), "head": os.path.abspath(a[2])}
    tree = {"main": os.path.abspath(a[1]), "head": os.path.abspath(a[3])}
    folder = os.path.abspath(a[4])
    os.makedirs(os.path.join(folder, "dense-files"))
    work = os.path.join(folder, "work")
    bad, runs, rows = [], {"main": [], "head": []}, []
    for r in range(rounds):
        for which in ("main", "head"):
            w = os.path.join(work, "%s-%d" % (which, r))
            p = subprocess.run([sys.executable, "-B", TEST, binary[which], KIT, w], cwd=tree[which], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, errors="replace", check=False)
            with open(os.path.join(folder, "%s-%d.log" % (which, r + 1)), "w", encoding="utf-8") as f:
                f.write(p.stdout)
            got = cases(p.stdout)
            last = p.stdout.rstrip("\n").split("\n")[-1]
            runs[which].append(got)
            rows.append("\t".join([which, str(r + 1), str(p.returncode), str(len(got)), str(sum(v[1] != "as expected" for v in got.values())), last]))
            print("%s round %d: status %d, %d cases, %s" % (which, r + 1, p.returncode, len(got), last), flush=True)
            if p.returncode != 0 or last != "served_form_test.py: all as expected":
                bad.append("%s round %d: the test did not end 'all as expected' with status 0" % (which, r + 1))
            if got != runs[which][0]:
                bad.append("%s round %d: case lines differ from round 1 of the same tree" % (which, r + 1))
    with open(os.path.join(folder, "runs.tsv"), "w", encoding="utf-8") as f:
        f.write("tree\tround\tstatus\tcases\tnot_as_expected\tlast_line\n" + "\n".join(rows) + "\n")
    on_main, on_head = runs["main"][0], runs["head"][0]
    table, changed, new = ["| case | main | head | |", "|---|---|---|---|"], [], []
    for name in list(on_main) + [n for n in on_head if n not in on_main]:
        m, h = on_main.get(name, ("(no such case on main)",))[0], on_head.get(name, ("(no such case on head)",))[0]
        if name not in on_main:
            new.append(name)
            note = "new"
        elif m != h:
            changed.append(name)
            note = "**changed**"
        else:
            note = "same"
        if name in REGISTERED and h != REGISTERED[name]:
            bad.append("%s: head gives %s, registered %s" % (name, h, REGISTERED[name]))
        if name not in REGISTERED and m != h:
            bad.append("%s: not registered to change, main %s, head %s" % (name, m, h))
        table.append("| `%s` | %s | %s | %s |" % (name, m, h, note))
    missing = [n for n in on_main if n not in on_head] + [n for n in REGISTERED if n not in on_head]
    if missing:
        bad.append("cases missing on head: %s" % ", ".join(sorted(set(missing))))
    if sorted(changed) != ["routed-experts.dense", "routed-experts.dense-with-digests"]:
        bad.append("changed between main and head: %s; registered: dense and dense-with-digests" % (", ".join(changed) or "none"))
    with open(os.path.join(folder, "table.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(table) + "\n")
    print("\n".join(table))

    # Metric 2: the head tree's dense files under both binaries.
    first = os.path.join(work, "head-0")
    dense = sorted(x for x in os.listdir(first) if x.startswith("routed-experts.") and not x.endswith(".plan"))
    out, hashes, seen = [], [], {}
    for case in dense:
        for which in ("main", "head"):
            status, result, configuration, statement, tables = planned(binary[which], first, case)
            seen[(case, which)] = (status, result, configuration, statement)
            out.append("\t".join([case, which, str(status), result, configuration, statement, tables]))
        shutil.copyfile(os.path.join(first, case, "policy.txt"), os.path.join(folder, "dense-files", case + ".policy.txt"))
        for name in ("policy.txt", "KL.bin", "layout.txt"):
            path = os.path.join(first, case, name)
            hashes.append("\t".join([case, name, sha(path) if os.path.exists(path) else "-"]))
        want = ON_MAIN.get(case, "NO: policy-tables")
        if seen[(case, "main")][1] != want:
            bad.append("%s under the main binary: %s, registered %s" % (case, seen[(case, "main")][1], want))
    with open(os.path.join(folder, "dense-files.tsv"), "w", encoding="utf-8") as f:
        f.write("case\tbinary\tstatus\tresult\tconfiguration\tstatement\ttables_line\n" + "\n".join(out) + "\n")
    with open(os.path.join(folder, "dense-files", "sha256.tsv"), "w", encoding="utf-8") as f:
        f.write("case\tfile\tsha256\n" + "\n".join(hashes) + "\n")
    plain, lines = seen.get(("routed-experts.dense", "head")), seen.get(("routed-experts.dense-with-digests", "head"))
    if not plain or not lines or plain[2] == lines[2] or "-" in (plain[2], lines[2]):
        bad.append("the configuration digests of dense and dense-with-digests are not two different digests")
    if not plain or not lines or plain[3] != lines[3] or plain[3] == "-":
        bad.append("the statement lines of dense and dense-with-digests differ or are absent")
    shutil.rmtree(work)
    summary = {
        "rounds_per_tree": rounds,
        "cases_main": len(on_main),
        "cases_head": len(on_head),
        "changed": sorted(changed),
        "new_on_head": new,
        "same_main_head": len(on_main) - len(changed),
        "dense_cases_under_both_binaries": len(dense),
        "configuration_dense": plain[2] if plain else None,
        "configuration_dense_with_digests": lines[2] if lines else None,
        "statement_dense": plain[3] if plain else None,
        "statement_dense_with_digests": lines[3] if lines else None,
        "not_as_registered": bad,
    }
    with open(os.path.join(folder, "summary.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=1)
    print()
    print("served_runs.py: %d cases on main, %d on head; changed: %s; new: %d; %d rounds per tree; %s"
          % (len(on_main), len(on_head), ", ".join(sorted(changed)) or "none", len(new), rounds, "as registered" if not bad else "NOT as registered: " + "; ".join(bad)))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
