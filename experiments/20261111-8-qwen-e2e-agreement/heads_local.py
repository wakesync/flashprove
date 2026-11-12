#!/usr/bin/env python3
"""Descriptive (registered, no threshold): where the closed-loop per-head errors over 0.05 sit, per checkpoint and prompt.
summary.json's `heads_local` reads each leg's own file only, so for stock it covers layers 17..63; the shared layers
0..16 (stock weights, identical inputs on both checkpoints) were logged once, in heads-abl.jsonl. This script counts
each checkpoint over all 48 DeltaNet layers: stock = heads-abl layers 0..16 + heads-stock 17..63; abl = heads-abl 0..63.
Writes runs/heads-local.json. Light."""
import json
from pathlib import Path
import numpy as np
HERE = Path(__file__).resolve().parent; R = HERE / "runs"
P = json.load(open(HERE / "prompts-e2e.json")); ORDER = [p["id"] for p in P["prompts"]]
ha = [json.loads(l) for l in open(R / "heads-abl.jsonl")]; hs = [json.loads(l) for l in open(R / "heads-stock.jsonl")]
rows = {"abl": ha, "stock": [r for r in ha if r["layer"] <= 16] + hs}
E = {leg: json.load(open(R / f"e2e-{leg}.json"))["prompts"] for leg in ("abl", "stock")}
out = {}
for leg, H in rows.items():
    for arm in ("XS18", "XS20"):
        for pid in ORDER:
            rr = [r for r in H if r["path"] == arm and r["prompt"] == pid]
            v = np.array([x for r in rr for x in r["rel_y"]])
            over = [(r["layer"], h, x) for r in rr for h, x in enumerate(r["rel_y"]) if x > 0.05]
            m = E[leg][pid]["paths"][arm]; kl = np.array(m["kl"])
            out.setdefault(leg, {}).setdefault(arm, {})[pid] = dict(
                layers=len({r["layer"] for r in rr}), pairs=int(v.size), rel_y_median=float(np.median(v)), rel_y_max=float(v.max()),
                over_0p05=len(over), share_over=float(len(over) / v.size), layers_with_over=sorted({l for l, _, _ in over}),
                worst=[dict(layer=l, head=h, rel_y=round(x, 4)) for l, h, x in sorted(over, key=lambda t: -t[2])[:3]],
                top1_agree=int(sum(m["top1_agree"])), T=len(kl), kl_median=float(np.median(kl)), kl_max=float(kl.max()))
(R / "heads-local.json").write_text(json.dumps(out, indent=1) + "\n")
for leg in out:
    for arm in out[leg]:
        for pid, d in out[leg][arm].items():
            print(leg, arm, pid, d["layers"], d["pairs"], round(d["rel_y_median"], 5), round(d["rel_y_max"], 3), d["over_0p05"],
                  f"{d['share_over']:.3f}", d["top1_agree"], d["T"], f"{d['kl_median']:.3g}", f"{d['kl_max']:.3g}")
