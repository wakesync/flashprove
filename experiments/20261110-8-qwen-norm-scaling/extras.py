#!/usr/bin/env python3
"""Descriptive extras from rows already run (no new arithmetic on weights): per arm, how many of the 480 pairs meet
rel_y <= 0.01 and <= 0.05, the worst pair, and the mixer-output error relative to the float mixer output
(||W_o (y_int - y_f)|| / ||W_o y_f|| per prompt, n = 10). Writes runs/extras.json. Usage: extras.py"""
import json
from pathlib import Path
import numpy as np
R = Path(__file__).resolve().parent / "runs"
out = {}
for f in ("cand-stock.jsonl", "local-stock.jsonl"):
    if not (R / f).exists(): continue
    rows = [json.loads(l) for l in open(R / f)]
    for a in dict.fromkeys(r["arm"] for r in rows):
        rs = [r for r in rows if r["arm"] == a and "error" not in r]
        if len(rs) != 480: continue
        y = np.array([r["rel_y"] for r in rs]); w = max(rs, key=lambda r: r["rel_y"])
        lay = [r["layer"] for r in rs if "layer" in r]
        rel_out = [l["resid"]["frob"] / l["mixer_over_resid"]["frob"] for l in lay]
        bf_out = [l["resid_bf16"]["frob"] / l["mixer_over_resid"]["frob"] for l in lay]
        out[f"{f.split('-')[0]}:{a}"] = dict(
            n=480, pairs_rel_y_le_0_01=int((y <= 0.01).sum()), pairs_rel_y_le_0_05=int((y <= 0.05).sum()),
            rel_y_p90=float(np.percentile(y, 90)), worst_pair=dict(prompt=w["prompt"], head=w["head"], rel_y=w["rel_y"], rel_S=w["rel_S"]),
            heads_with_any_pair_over_0_05=sorted({r["head"] for r in rs if r["rel_y"] > 0.05}),
            out_rel=dict(n=len(rel_out), median=float(np.median(rel_out)), min=float(min(rel_out)), max=float(max(rel_out))),
            out_rel_bf16=dict(n=len(bf_out), median=float(np.median(bf_out)), min=float(min(bf_out)), max=float(max(bf_out))))
(R / "extras.json").write_text(json.dumps(out, indent=1) + "\n")
print("| arm | pairs rel_y <= 0.01 | pairs rel_y <= 0.05 | p90 rel_y | worst pair | mixer-output error / float mixer output, median (min / max), n = 10 |")
print("|---|---|---|---|---|---|")
for k, d in out.items():
    w = d["worst_pair"]; o = d["out_rel"]
    print(f"| {k} | {d['pairs_rel_y_le_0_01']} / 480 | {d['pairs_rel_y_le_0_05']} / 480 | {d['rel_y_p90']:.3g} | {w['prompt']} head {w['head']} ({w['rel_y']:.3g}) | {o['median']:.3g} ({o['min']:.3g} / {o['max']:.3g}) |")
b = next(iter(out.values()))["out_rel_bf16"]
print(f"| BF16 emulation | | | | | {b['median']:.3g} ({b['min']:.3g} / {b['max']:.3g}) |")
for k in ("cand:X3", "cand:C4P"):
    if k in out: print(k, "heads with a pair over 0.05:", out[k]["heads_with_any_pair_over_0_05"])
