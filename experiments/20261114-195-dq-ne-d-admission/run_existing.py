#!/usr/bin/env python3
"""T8 of experiment 20261114-195-dq-ne-d-admission: existing verifier rows, on one binary.

usage: run_existing.py <repo> <base|patched> <cp_verify> <work folder> <output folder> <round> <group>
       run_existing.py compare <output folder>

<group> is one of A, B, C, D (GROUPS below): one call runs one group on one binary, so that no
single command needs more than two minutes of CPU. The work folder is made if it is missing.

Runs, with the given binary, the existing tests and stored-proof calls named in the PREREG (their
commands are SUITE.md's, with the binary's path in place of ${S}/bin-target-f2/cp_verify). Each
row's whole output is kept, normalised (N, PREREG Amendment 1 item 4), under <output folder>/raw/,
with its exit status, the registered line it must print, its SHA-256 after N, and its CPU seconds.
compare: per row, the statuses and hashes of all rounds of both binaries must be one value.
"""
import hashlib
import json
import os
import pathlib
import re
import resource
import subprocess
import sys

PINNED = "prover/tests/configurations/pinned_no_proof_of_work"
EX, GAP = "examples/accepted-proof", "examples/accepted-proof-clipped-gap"


def rows(v, w, repo):
    # Every command runs with the repository's top as its working directory; ID.txt is read from there.
    whole = lambda d: [v, d + "/config", d + "/ivk", d + "/example.req", d + "/example.y", d + "/example.proof", "-id", open(os.path.join(repo, d, "ID.txt")).read().strip()]
    sh = ("mkdir -p {w}/la && sed 's/^la 8$/la 6/' {k}/policy.txt > {w}/la/policy.txt && grep -q '^la 6$' {w}/la/policy.txt && head -c 264 /dev/zero > {w}/la/a.req && "
          "head -c 4 /dev/zero > {w}/la/y.bin && {v} -plan request {w}/la/policy.txt {k}/KL.bin 0 -layout {k}/layout.txt -prompt {w}/la/a.req -reply {w}/la/y.bin").format(w=w, k=PINNED, v=v)
    return [
        ("example_kits", ["python3", "-B", "verifier/tests/example_kits_test.py", v, w + "/example_kits", "2"], 0, r"^example_kits_test\.py: 7 parameter files \(1 bare, 5 work, 1 yes\), 12 plays with a line changed; 0 not as expected$"),
        ("served_form", ["python3", "-B", "verifier/tests/served_form_test.py", v, PINNED, w + "/served_form"], 0, r"^served_form_test.py: all as expected$"),
        ("plan_tau", ["python3", "-B", "verifier/tests/plan_tau_test.py", v, PINNED, w + "/plan_tau"], 0, r"^plan_tau_test\.py: 13 cases: all as expected$"),
        ("kit_rounds", ["python3", "-B", "verifier/tests/kit_rounds_test.py", v, w + "/kit_rounds", "2"], 0, r"^kit_rounds_test\.py: 3 kits, [1-9]\d* kinds of rounds; 0 kits not as stored$"),
        ("la_equals_lt", ["/bin/sh", "-c", sh], 1, r"^NO: shape-la$"),
        ("whole_accepted_proof", whole(EX), 0, r"^YES$"),
        # As first run: without the option -policy, which this example needs (its README). Both binaries then
        # answer NO: policy before reading the proof. Kept as run; not counted (PREREG, Amendment 2, item 1).
        ("whole_clipped_gap", whole(GAP), 0, r"^WITHIN LIMITS: clipped-gap C="),
        ("whole_clipped_gap_with_policy", whole(GAP) + ["-policy", "clipped-gap,9244130,323343,1,16,8"], 0, r"^WITHIN LIMITS: clipped-gap C="),
        ("rejected_proofs_accepted", ["python3", "-B", "-u", "examples/rejected-proofs/try_altered_copies.py", v, w + "/rej-a", "--example", "accepted-proof"], 0, r"^10 altered sets: all rejected$"),
        ("rejected_proofs_gap", ["python3", "-B", "-u", "examples/rejected-proofs/try_altered_copies.py", v, w + "/rej-g", "--example", "accepted-proof-clipped-gap"], 0, r"^10 altered sets: all rejected$"),
        ("call_accounting", ["python3", "-B", "verifier/tests/call_accounting_test.py", v, EX + "/config", "128", w + "/whole_accepted_proof.raw.txt", EX + "/example.req"], 0,
         r"^call_accounting_test\.py: [1-9]\d* lines of the plan's accounting, 0 not as in the call$"),
    ]


def normalise(text, repo, work, binary, touched):
    out = []
    for line in text.replace(work, "<work>").replace(binary, "<cp_verify>").replace(repo, "<repo>").split("\n"):
        if line.lstrip().startswith("seconds:"):
            touched.add("removed: a line beginning 'seconds:'")
            continue
        new = re.sub(r"build=[0-9a-f]{64}", "build=<source digest>", line)
        if new != line:
            touched.add("masked: build=<64 hex>")
        new2 = re.sub(r"\d+\.\d+ s\b", "<t> s", new)
        if new2 != new:
            touched.add("masked: <digits>.<digits> s in: " + re.sub(r"\d+", "N", new2)[:70])
        out.append(new2)
    return "\n".join(out)


GROUPS = {"A": ["example_kits"], "B": ["served_form", "plan_tau", "kit_rounds", "la_equals_lt"],
          "C": ["whole_accepted_proof", "whole_clipped_gap", "call_accounting"], "D": ["rejected_proofs_accepted", "rejected_proofs_gap"],
          "E": ["whole_clipped_gap_with_policy"]}
HARNESS_FAULT = {"whole_clipped_gap": "called without -policy: a fault of this harness (PREREG, Amendment 2, item 1); not counted"}


def run(repo, which, binary, work, outdir, rnd, group):
    os.makedirs(work, exist_ok=True)
    raw = outdir / "raw"
    raw.mkdir(parents=True, exist_ok=True)
    touched, records = set(), []
    for name, cmd, status_wanted, pattern in rows(binary, work, repo):
        if name not in GROUPS[group]:
            continue
        before = resource.getrusage(resource.RUSAGE_CHILDREN)
        p = subprocess.run(cmd, cwd=repo, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=600,
                           preexec_fn=lambda: resource.setrlimit(resource.RLIMIT_AS, (4 << 30, 4 << 30)))
        after = resource.getrusage(resource.RUSAGE_CHILDREN)
        text = p.stdout.decode(errors="replace")
        if name == "whole_accepted_proof":
            pathlib.Path(work, name + ".raw.txt").write_text(text)  # call_accounting reads the call's own output
        norm = normalise(text, repo, work, binary, touched)
        (raw / ("%s.%s.%d.txt" % (name, which, rnd))).write_text(norm)
        lines = text.splitlines()
        ok = p.returncode == status_wanted and any(re.search(pattern, l) for l in lines)
        records.append({"row": name, "binary": which, "round": rnd, "status": p.returncode, "status_wanted": status_wanted, "registered_line_found": any(re.search(pattern, l) for l in lines),
                        "passes": ok, "last": lines[-1][:160] if lines else "", "sha256_normalised": hashlib.sha256(norm.encode()).hexdigest(),
                        "cpu_seconds": round(after.ru_utime + after.ru_stime - before.ru_utime - before.ru_stime, 1), "peak_rss_kib_children_so_far": after.ru_maxrss})
        print("%-26s %-7s round %d: %s | status %d | %s | cpu %.1f s" % (name, which, rnd, "passes" if ok else "FAILS", p.returncode, records[-1]["sha256_normalised"][:12], records[-1]["cpu_seconds"]), flush=True)
    (outdir / ("existing-%s-round-%d-%s.json" % (which, rnd, group))).write_text(json.dumps({"binary": which, "round": rnd, "group": group, "touched_by_normalisation": sorted(touched), "records": records}, indent=1) + "\n")
    return 0 if all(r["passes"] for r in records) else 1


def compare(outdir):
    records, touched = [], set()
    files = sorted(outdir.glob("existing-*-round-*.json"))
    for f in files:
        d = json.loads(f.read_text())
        records += d["records"]
        touched |= set(d["touched_by_normalisation"])
    bad, table, faults = 0, {}, {}
    for name in sorted({r["row"] for r in records}):
        rs = [r for r in records if r["row"] == name]
        if name in HARNESS_FAULT:
            faults[name] = {"why": HARNESS_FAULT[name], "runs": [{k: r[k] for k in ("binary", "round", "status", "last", "sha256_normalised")} for r in rs]}
            print("%-30s NOT COUNTED: %s" % (name, HARNESS_FAULT[name]))
            continue
        hashes = {w: sorted({r["sha256_normalised"] for r in rs if r["binary"] == w}) for w in ("base", "patched")}
        same = len(set(hashes["base"]) | set(hashes["patched"])) == 1 and len({r["status"] for r in rs}) == 1 and all(r["passes"] for r in rs)
        bad += not same
        table[name] = {"runs_base": sum(r["binary"] == "base" for r in rs), "runs_patched": sum(r["binary"] == "patched" for r in rs), "statuses": sorted({r["status"] for r in rs}),
                       "all_pass": all(r["passes"] for r in rs), "hashes": hashes, "identical_base_patched": same, "cpu_seconds_max": max(r["cpu_seconds"] for r in rs)}
        print("%-26s base %d runs, patched %d runs | status %s | %s" % (name, table[name]["runs_base"], table[name]["runs_patched"], table[name]["statuses"], "IDENTICAL" if same else "DIFFERS OR FAILS"))
    (outdir / "existing-summary.json").write_text(json.dumps({"files": [f.name for f in files], "rows": table, "rows_not_identical": bad, "harness_faults_not_counted": faults,
                                                             "touched_by_normalisation": sorted(touched)}, indent=1) + "\n")
    print("run_existing.py compare: %d rows counted, %d not identical or failing; %d not counted (harness fault); %d round files" % (len(table), bad, len(faults), len(files)))
    return 1 if bad else 0


def main():
    a = sys.argv[1:]
    if len(a) == 2 and a[0] == "compare":
        return compare(pathlib.Path(a[1]).resolve())
    if len(a) != 7 or a[1] not in ("base", "patched") or a[6] not in GROUPS:
        sys.exit(__doc__)
    return run(str(pathlib.Path(a[0]).resolve()), a[1], str(pathlib.Path(a[2]).resolve()), str(pathlib.Path(a[3]).resolve()), pathlib.Path(a[4]).resolve(), int(a[5]), a[6])


if __name__ == "__main__":
    sys.exit(main())
