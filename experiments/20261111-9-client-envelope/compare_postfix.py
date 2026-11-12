#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Compare the post-registration re-run (runs/postfix/, fixed client) with the registered run
(runs/registered/, pre-fix client at fb63aa8), step by step. Post-registration check, no threshold.

  python3 experiments/20261111-9-client-envelope/compare_postfix.py

For every (run, vector, step) it compares exit code, last line, release and state change, and the
reject check. Writes runs/postfix/compare.json and prints a summary. Exit 0 only if every step has
the same verdict in both runs.
"""

import json
import pathlib
import statistics
import sys

HERE = pathlib.Path(__file__).resolve().parent


def rows(name):
    out = {}
    for line in (HERE / "runs" / name / "rows.jsonl").read_text().splitlines():
        r = json.loads(line)
        out[(r["run"], r["vector"], r["step"])] = r
    return out


def describe(xs):
    return {"n": len(xs), "median": statistics.median(xs), "sd": statistics.stdev(xs),
            "min": min(xs), "max": max(xs)}


def main():
    reg, post = rows("registered"), rows("postfix")
    keys = ("exit", "last", "released", "state_changed", "pass")
    diffs = []
    for k in sorted(set(reg) | set(post)):
        a, b = reg.get(k), post.get(k)
        if a is None or b is None or any(a[x] != b[x] for x in keys):
            diffs.append({"key": list(k), "registered": a and {x: a[x] for x in keys},
                          "postfix": b and {x: b[x] for x in keys}})
    rej = [r for r in post.values() if r["expect"] != "RELEASE"]
    acc = [r for r in post.values() if r["expect"] == "RELEASE"]
    rel = [r for r in acc if r["cp_verify_s"]]
    summary = {
        "note": "post-registration check of the fixed client, no threshold; registered numbers "
                "are the ones in runs/registered (pre-fix client, fb63aa8)",
        "steps_registered": len(reg), "steps_postfix": len(post),
        "steps_same_verdict": len(set(reg) & set(post)) - sum(1 for d in diffs
                                                            if d["registered"] and d["postfix"]),
        "steps_differing": len(diffs), "differences": diffs,
        "postfix_reject_steps_at_registered_check": sum(r["pass"] for r in rej),
        "postfix_reject_steps": len(rej),
        "postfix_reject_released": sum(r["released"] for r in rej),
        "postfix_reject_state_changed": sum(r["state_changed"] for r in rej),
        "postfix_accept_steps_released": sum(r["pass"] for r in acc),
        "postfix_accept_steps": len(acc),
        "postfix_reach_cp_verify_reject_vectors": sorted({r["vector"] for r in rej
                                                          if r["cp_verify"] and
                                                          not r["cp_verify"].startswith("exit=None")}),
        "postfix_release_cp_verify_s_diagnostic": describe([r["cp_verify_s"] for r in rel]),
        "postfix_release_overhead_s_diagnostic": describe([r["client_s"] - r["cp_verify_s"]
                                                          for r in rel]),
    }
    (HERE / "runs" / "postfix" / "compare.json").write_text(json.dumps(summary, indent=1,
                                                                       sort_keys=True) + "\n")
    print("steps registered %d postfix %d differing %d" % (len(reg), len(post), len(diffs)))
    print("postfix reject %d/%d at registered check, released %d, state changed %d; accept %d/%d"
          % (summary["postfix_reject_steps_at_registered_check"], len(rej),
             summary["postfix_reject_released"], summary["postfix_reject_state_changed"],
             summary["postfix_accept_steps_released"], len(acc)))
    print("reject vectors reaching cp_verify:", summary["postfix_reach_cp_verify_reject_vectors"])
    print("cp_verify on released steps (diagnostic):",
          json.dumps(summary["postfix_release_cp_verify_s_diagnostic"]))
    print("client overhead on released steps (diagnostic):",
          json.dumps(summary["postfix_release_overhead_s_diagnostic"]))
    return 0 if not diffs else 1


if __name__ == "__main__":
    sys.exit(main())
