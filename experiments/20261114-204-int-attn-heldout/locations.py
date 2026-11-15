#!/usr/bin/env python3
"""Clamp locations, validity evidence and descriptive per-layer figures from the committed run records (PREREG "Metric":
counts with location; post-gate / o_proj descriptive error; timing). Reads runs/*.jsonl, writes runs/locations.json."""
import json
from pathlib import Path
import numpy as np
HERE = Path(__file__).resolve().parent; R = HERE / "runs"
jl = lambda n: [json.loads(l) for l in (R / n).read_text().splitlines() if l.strip()]
pr, lay, cells, tim = jl("prompt-rows.jsonl"), jl("layers.jsonl"), jl("cells.jsonl"), jl("attn-timing.jsonl")
clamps = []
for p in pr:
    for which, key in (("q", "q_over_by_head"), ("k", "k_over_by_kvhead"), ("v", "v_over_by_kvhead")):
        for h, n in enumerate(p[key]):
            if n: clamps.append(dict(arm=p["arm"], layer=p["layer"], prompt=p["prompt"], tensor=which,
                                     head=h, head_kind="query head" if which == "q" else "kv head", count=n,
                                     max_abs_rne=p[f"{which}_maxw"], clamp=2047 if p["arm"] == "C2047" else 1665,
                                     denominator_prompt=p[f"{which}_n"]))
worst = {}
for c in cells:
    k = (c["arm"], c["layer"])
    if c["rel_y"] is not None and (k not in worst or c["rel_y"] > worst[k]["rel_y"]): worst[k] = c
by_prompt = {}
for arm in ("C2047", "C1665"):
    for pid in sorted({c["prompt"] for c in cells}):
        v = np.array([c["rel_y"] for c in cells if c["arm"] == arm and c["prompt"] == pid])
        by_prompt.setdefault(arm, {})[pid] = dict(n=int(v.size), median=float(np.median(v)), max=float(v.max()), n_over_001=int((v > 0.01).sum()))
mix = {}
for arm in ("C2047", "C1665"):
    for l in sorted({p["layer"] for p in pr}):
        v = [p["mix_rel"] for p in pr if p["arm"] == arm and p["layer"] == l]
        mix.setdefault(arm, {})[l] = dict(median=float(np.median(v)), max=float(max(v)))
headroom = {}
for r in lay:
    cl = r["clamp"]
    headroom.setdefault(r["arm"], {})[r["layer"]] = dict(q=round(r["q_maxw"] / cl, 4), k=round(r["k_maxw"] / cl, 4), v=round(r["v_maxw"] / cl, 4),
                                                          max_abs_s=r["max_abs_s"], Smax=r["Smax"])
out = dict(clamped_entries=clamps,
           validity=dict(split_bit_equal_all=all(all(t["mix_bit_equal_q1"].values()) for t in tim),
                         split_checks=sum(len(t["mix_bit_equal_q1"]) for t in tim),
                         determinism_all=all(all(r["det_bit_equal"].values()) for r in lay),
                         determinism_checks=sum(len(r["det_bit_equal"]) for r in lay),
                         scales_frozen_all=all(r["scales_frozen_ok"] for r in lay), layer_records=len(lay)),
           worst_cell_per_layer={f"{a} {l}": v for (a, l), v in sorted(worst.items(), key=lambda x: (x[0][0], x[0][1]))},
           by_prompt=by_prompt, mix_rel_post_gate_oproj=mix, headroom_max_rne_over_clamp=headroom,
           layer_seconds={t["layer"]: t["total_s"] for t in tim},
           arm_seconds={f"{r['arm']} {r['layer']}": r["arm_seconds"] for r in lay})
(R / "locations.json").write_text(json.dumps(out, indent=1) + "\n")
print(json.dumps(dict(clamped=clamps, validity=out["validity"]), indent=1))
print(json.dumps({a: {p: (round(v["median"], 5), round(v["max"], 5)) for p, v in d.items()} for a, d in by_prompt.items()}))
print(json.dumps({k: (v["prompt"], v["head"], round(v["rel_y"], 4)) for k, v in out["worst_cell_per_layer"].items() if v["rel_y"] > 0.02}))
