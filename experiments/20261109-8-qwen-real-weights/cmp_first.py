#!/usr/bin/env python3
"""Check that the rerun (with the layer-level fields added) reproduces every per-head number of the first run.
Usage: cmp_first.py"""
import json
from pathlib import Path
R = Path(__file__).resolve().parent / "runs"
tot = bad = 0
for f in sorted((R / "first-run").glob("real-*.jsonl")):
    a = [json.loads(l) for l in open(f)]; b = [json.loads(l) for l in open(R / f.name)]
    assert len(a) == len(b), f
    for x, y in zip(a, b):
        y = {k: v for k, v in y.items() if k in x}
        tot += 1; bad += x != y
    print(f.name, len(a))
print("rows", tot, "differ", bad)
