#!/usr/bin/env python3
"""rel_y per (prompt, head) bucketed by the head's median float o RMS in integer units (the norm's input resolution).
Writes runs/buckets.json. Usage: buckets.py"""
import json
from pathlib import Path
import numpy as np
R = Path(__file__).resolve().parent / "runs"
out = {}
for fn, arm in (("real-stock.jsonl", "registered"), ("real-stock-qunscaled.jsonl", "q_unscaled")):
    rows = [json.loads(l) for l in open(R / fn)]
    for F in sorted({r["F"] for r in rows}):
        rs = [r for r in rows if r["F"] == F]
        o = np.array([r["o_rms_int_median"] for r in rs]); y = np.array([r["rel_y"] for r in rs])
        b = {}
        for lo, hi in ((0, 16), (16, 128), (128, 1024), (1024, 8192), (8192, 1e12)):
            m = (o >= lo) & (o < hi)
            if m.any(): b[f"[{lo},{hi:g})"] = dict(n=int(m.sum()), median_rel_y=float(np.median(y[m])), max_rel_y=float(y[m].max()))
        out[f"{arm}/F{F}"] = dict(n=len(rs), pairs_rel_y_le_0_05=int((y <= 0.05).sum()), pairs_rel_y_le_0_01=int((y <= 0.01).sum()), buckets=b)
(R / "buckets.json").write_text(json.dumps(out, indent=1) + "\n")
for k, v in out.items():
    print(k, "n", v["n"], "rel_y<=0.05:", v["pairs_rel_y_le_0_05"], "<=0.01:", v["pairs_rel_y_le_0_01"])
    for bk, bv in v["buckets"].items(): print("   o_rms_int", bk, bv)
