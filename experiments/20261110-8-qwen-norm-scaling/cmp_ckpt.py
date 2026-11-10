#!/usr/bin/env python3
"""Identity check: rows of runs/cand-abl.jsonl against the same arms in runs/cand-stock.jsonl (everything but ckpt and
the timing field). Also the engine's C0 against PR #68's committed F = 12 rows (rel_y, rel_S largest relative
difference; integer maxima S, M, delta, o, w equal). Writes runs/cmp-ckpt.json."""
import json
from pathlib import Path
HERE = Path(__file__).resolve().parent
R = HERE / "runs"
def load(f):
    out = {}
    for l in open(f):
        r = json.loads(l)
        if "error" in r: out[(r["arm"], r["prompt"], -1)] = r; continue
        r = dict(r); r.pop("ckpt")
        if "layer" in r: r["layer"] = {k: v for k, v in r["layer"].items() if k != "seconds"}
        out[(r["arm"], r["prompt"], r["head"])] = r
    return out
s, a = load(R / "cand-stock.jsonl"), load(R / "cand-abl.jsonl")
arms = sorted({k[0] for k in a})
res = dict(arms=arms, rows_compared=len(a), rows_identical=sum(a[k] == s.get(k) for k in a))
old = {(r["prompt"], r["head"]): r for r in map(json.loads, open(HERE.parent / "20261109-8-qwen-real-weights" / "runs" / "real-stock.jsonl")) if r["F"] == 12}
wy = ws = 0.0; ints = True
for (arm, p, h), r in s.items():
    if arm != "C0" or h < 0: continue
    o = old[(p, h)]
    wy = max(wy, abs(r["rel_y"] - o["rel_y"]) / o["rel_y"]); ws = max(ws, abs(r["rel_S"] - o["rel_S"]) / o["rel_S"])
    ints &= all(int(r["max"][k]) == o["max"][k] for k in ("S", "M", "delta", "o", "w", "v", "k_hat", "q_hat", "xin", "ar", "br", "z", "cg", "y", "sigma", "Vx"))
res["engine_C0_vs_pr68"] = dict(rows=480, max_rel_diff_rel_y=wy, max_rel_diff_rel_S=ws, integer_maxima_equal=bool(ints))
(R / "cmp-ckpt.json").write_text(json.dumps(res, indent=1) + "\n"); print(json.dumps(res, indent=1))
