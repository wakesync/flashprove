#!/usr/bin/env python3
# Prints markdown tables from numbers.json (analyze.py). usage: table.py numbers.json [label ...]
import json
import sys

d = json.load(open(sys.argv[1]))
agg = d["aggregate"]
labels = sys.argv[2:] or [
    "C=exact theta=256 cap=0",
    "C=shipped theta=shipped cap=1",
    "C=shipped theta=shipped cap=0",
    "C=p99.9 theta=p100 cap=0",
    "C=p99.9 theta=p100 cap=1",
    "C=p99.5 theta=p99 cap=1",
    "C=p99 theta=p95 cap=2",
]
cols = ["honest", "fp2nd-1", "int2nd-1", "fp2nd-2", "int2nd-2", "fp2nd-4", "int2nd-4", "fp2nd-8", "int2nd-8",
        "fp2nd-16", "int2nd-16", "rand-1", "rand-2", "rand-4", "rand-8", "rand-16", "rand-reply", "other-prompt",
        "trunc-half", "trunc-1"] + [c for c in d.get("exploratory_classes", []) if c in d["classes"]]


def cell(s):
    if s is None:
        return "-"
    m, lo, hi = 100 * s["median"], 100 * s["min"], 100 * s["max"]
    return "%.0f (%.0f-%.0f)" % (m, lo, hi) if lo != hi else "%.0f" % m


print("| class | " + " | ".join("`%s`" % l for l in labels) + " |")
print("|---|" + "---|" * len(labels))
for c in cols:
    print("| %s | " % (c + (" (exploratory)" if c in d.get("exploratory_classes", []) else "")) + " | ".join(cell(agg[l]["acceptance"][c]) for l in labels) + " |")
print("| **FRR** | " + " | ".join(cell(agg[l]["frr"]) for l in labels) + " |")
print()
print("| point | " + " | ".join("seed %s" % s for s in d["seeds"]) + " |")
print("|---|" + "---|" * len(d["seeds"]))
for l in labels:
    v = agg[l]["values_per_seed"]
    print("| `%s` | " % l + " | ".join("%d / %d / %d" % tuple(v[str(s)] if str(s) in v else v[s]) for s in d["seeds"]) + " |")
