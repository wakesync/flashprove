#!/usr/bin/env python3
"""Diagnose a step-1 row mismatch: per field, the largest relative difference between PR #68's committed F = 12 rows
and this lane's rerun; and whether every integer field (max, min_exact) is identical.
Usage: repro_diff.py <new_jsonl> <ckpt> <out.json>"""
import json, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
OLD = HERE.parent / "20261109-8-qwen-real-weights" / "runs"

def flat(d, pre=""):
    for k, v in d.items():
        if isinstance(v, dict): yield from flat(v, pre + k + ".")
        else: yield pre + k, v

new, ck, out = sys.argv[1], sys.argv[2], sys.argv[3]
o = {(r["prompt"], r["head"]): r for r in map(json.loads, open(OLD / f"real-{ck}.jsonl")) if r["F"] == 12}
n = {(r["prompt"], r["head"]): r for r in map(json.loads, open(new))}
worst = {}; int_equal = True; int_fields = 0
for k in o:
    a, b = dict(flat(o[k])), dict(flat(n[k]))
    for f in a:
        if f.startswith("max.") or f.startswith("min_exact."):
            int_fields += 1
            if a[f] != b[f]: int_equal = False
            continue
        if isinstance(a[f], float):
            d = abs(a[f] - b[f]) / max(abs(a[f]), 1e-300)
            if d > worst.get(f, (0,))[0]: worst[f] = (d, k)
res = dict(ckpt=ck, rows=len(o), integer_fields_compared=int_fields, integer_fields_all_equal=int_equal,
           worst_rel_diff={f: dict(rel=v[0], at=list(v[1])) for f, v in sorted(worst.items(), key=lambda x: -x[1][0])})
Path(out).write_text(json.dumps(res, indent=1) + "\n"); print(json.dumps(res, indent=1)[:2500])
