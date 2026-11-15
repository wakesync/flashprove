#!/usr/bin/env python3
"""T8 completion run of experiment 20261114-195-dq-ne-d-admission (PREREG, Amendment 4, item 1).

usage: run_existing_rounds.py run <repo> <base cp_verify> <patched cp_verify> <private parent folder> <output folder>
                                  <budget seconds> <hard stop, UTC, HH:MM> [--dry]
       run_existing_rounds.py summarise <repo> <output folder>

run: rounds 2 to 5 of the existing rows, by the committed run_existing.py, which is called and not
changed. One binary at a time; base first in rounds 3 and 5, patched first in rounds 2 and 4 (the
rule of run_planning.py). Each (round, binary) gets a new work folder of mode 0700 below the private
parent folder, with umask 077, which is what examples/rejected-proofs/try_altered_copies.py asks
for. The budget counts from the moment this script starts (start it through the heavy-job gate: it
then starts when the gate grants the slot). Before each call it reads the clock: past the budget or
the hard stop it starts nothing more and writes how far it came. With --dry it prints the calls and
makes none.

summarise: per round and row, compares base with patched and both with round 1 as committed in
runs/existing/existing-summary.json. Exit status 0: four complete rounds, every counted row in
agreement. 3: a row's status or normalised hash differs between base and patched (stop rule 1 of
the design). 1: anything else (rounds missing, a row that fails or differs from round 1 on both
binaries alike).
"""
import datetime
import json
import os
import pathlib
import subprocess
import sys
import tempfile

GROUPS = "ABCDE"
ROUNDS = (2, 3, 4, 5)


def now():
    return datetime.datetime.now(datetime.timezone.utc)


def stamp():
    return now().strftime("%Y-%m-%dT%H:%M:%SZ")


def order(rnd):
    return ("base", "patched") if rnd % 2 else ("patched", "base")


def run(a):
    dry = "--dry" in a
    a = [x for x in a if x != "--dry"]
    if len(a) != 7:
        sys.exit(__doc__)
    repo, parent, out = pathlib.Path(a[0]).resolve(), pathlib.Path(a[3]).resolve(), pathlib.Path(a[4]).resolve()
    binary = {"base": str(pathlib.Path(a[1]).resolve()), "patched": str(pathlib.Path(a[2]).resolve())}
    budget = float(a[5])
    hh, mm = a[6].split(":")
    start = now()
    hard = start.replace(hour=int(hh), minute=int(mm), second=0, microsecond=0)
    here = pathlib.Path(__file__).resolve().parent
    if dry:
        for rnd in ROUNDS:
            for which in order(rnd):
                for g in GROUPS:
                    print("would call: run_existing.py <repo> %s <%s cp_verify> <new work folder> <output folder> %d %s" % (which, which, rnd, g))
        print("run_existing_rounds.py: dry: %d calls listed, none made; budget %.0f s, hard stop %s" % (len(ROUNDS) * 2 * len(GROUPS), budget, hard.strftime("%H:%MZ")))
        return 0
    os.umask(0o077)
    if out.exists() and any(out.iterdir()):
        sys.exit("run_existing_rounds.py: the output folder is not empty: nothing was run")
    out.mkdir(parents=True, exist_ok=True)
    log = open(out / "progress.txt", "a")

    def say(text):
        line = "%s %s" % (stamp(), text)
        print(line, flush=True)
        log.write(line + "\n")
        log.flush()

    say("slot granted, start; budget %.0f s, hard stop %s; order: base first in rounds 3 and 5, patched first in rounds 2 and 4; one binary at a time" % (budget, hard.strftime("%H:%MZ")))
    rounds, stopped = [], ""
    for rnd in ROUNDS:
        calls = []
        for which in order(rnd):
            work = tempfile.mkdtemp(prefix="t8-round-%d-%s-" % (rnd, which), dir=str(parent))
            for g in GROUPS:
                t = now()
                if (t - start).total_seconds() > budget or t > hard:
                    stopped = "stopped before round %d, %s, group %s: %s" % (rnd, which, g, "budget" if (t - start).total_seconds() > budget else "hard stop")
                    break
                p = subprocess.run([sys.executable, "-B", str(here / "run_existing.py"), str(repo), which, binary[which], work, str(out), str(rnd), g],
                                   stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, errors="replace")
                text = p.stdout.replace(work, "<work>").replace(binary[which], "<cp_verify>").replace(str(repo), "<repo>").replace(str(parent), "<private>")
                calls.append({"binary": which, "group": g, "status": p.returncode, "started": t.strftime("%Y-%m-%dT%H:%M:%SZ"), "ended": stamp(), "output": text.splitlines()})
                say("round %d %s group %s: status %d" % (rnd, which, g, p.returncode))
            if stopped:
                break
        rounds.append({"round": rnd, "order": list(order(rnd)), "calls": calls, "complete": len(calls) == 2 * len(GROUPS)})
        if stopped:
            say(stopped)
            break
    done = [r["round"] for r in rounds if r["complete"]]
    say("end: complete rounds %s of %s%s" % (done, list(ROUNDS), "; " + stopped if stopped else ""))
    (out / "rounds-run.json").write_text(json.dumps({"started": start.strftime("%Y-%m-%dT%H:%M:%SZ"), "ended": stamp(), "budget_seconds": budget, "hard_stop_utc": hard.strftime("%H:%MZ"),
                                                    "complete_rounds": done, "stopped": stopped, "rounds": rounds}, indent=1) + "\n")
    return 0


def summarise(a):
    if len(a) != 2:
        sys.exit(__doc__)
    repo, out = pathlib.Path(a[0]).resolve(), pathlib.Path(a[1]).resolve()
    first = json.loads((repo / "experiments/20261114-195-dq-ne-d-admission/runs/existing/existing-summary.json").read_text())["rows"]
    records = []
    for f in sorted(out.glob("existing-*-round-*-*.json")):
        records += json.loads(f.read_text())["records"]
    ran = json.loads((out / "rounds-run.json").read_text())
    table, stop1, other, complete = {}, [], [], ran["complete_rounds"]
    for rnd in ROUNDS:
        if rnd not in complete:
            continue
        for row in sorted(first):
            one = {w: [r for r in records if r["row"] == row and r["round"] == rnd and r["binary"] == w] for w in ("base", "patched")}
            if any(len(v) != 1 for v in one.values()):
                other.append("round %d %s: %s records" % (rnd, row, {w: len(v) for w, v in one.items()}))
                continue
            b, p = one["base"][0], one["patched"][0]
            h1, s1 = first[row]["hashes"]["base"][0], first[row]["statuses"][0]
            same_bp = b["status"] == p["status"] and b["sha256_normalised"] == p["sha256_normalised"]
            same_1 = b["sha256_normalised"] == h1 and p["sha256_normalised"] == h1 and b["status"] == s1 and p["status"] == s1
            passes = b["passes"] and p["passes"]
            table["round %d %s" % (rnd, row)] = {"status_base": b["status"], "status_patched": p["status"], "sha256_base": b["sha256_normalised"], "sha256_patched": p["sha256_normalised"],
                                                 "sha256_round_1": h1, "passes_both": passes, "identical_base_patched": same_bp, "equal_to_round_1": same_1, "agreement": passes and same_bp and same_1}
            if not same_bp:
                stop1.append("round %d %s" % (rnd, row))
            elif not (passes and same_1):
                other.append("round %d %s: passes_both %s, equal_to_round_1 %s" % (rnd, row, passes, same_1))
    for rnd in ROUNDS:
        rows = [v for k, v in table.items() if k.startswith("round %d " % rnd)]
        print("round %d: %s" % (rnd, "not complete, not counted" if rnd not in complete else "%d rows, %d in agreement (pass, base = patched, = round 1)" % (len(rows), sum(v["agreement"] for v in rows))))
    verdict = "STOP RULE 1: base and patched differ" if stop1 else "all four rounds complete, every counted row in agreement" if len(complete) == len(ROUNDS) and not other and len(table) == len(ROUNDS) * len(first) else "PARTIAL"
    (out / "completion-summary.json").write_text(json.dumps({"rows_counted_per_round": sorted(first), "complete_rounds": complete, "rows": table, "base_patched_differ": stop1, "other_faults": other,
                                                            "not_counted": "whole_clipped_gap (called without -policy; PREREG Amendment 2 item 1)", "verdict": verdict}, indent=1) + "\n")
    print("run_existing_rounds.py summarise: complete rounds %s; %d row-rounds compared, %d in agreement; base/patched differences %d; other faults %d: %s"
          % (complete, len(table), sum(v["agreement"] for v in table.values()), len(stop1), len(other), verdict))
    return 3 if stop1 else 0 if verdict.startswith("all four") else 1


def main():
    a = sys.argv[1:]
    if a[:1] == ["run"]:
        return run(a[1:])
    if a[:1] == ["summarise"]:
        return summarise(a[1:])
    sys.exit(__doc__)


if __name__ == "__main__":
    sys.exit(main())
