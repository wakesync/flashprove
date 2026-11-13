#!/usr/bin/env python3
"""Descriptive partial report (no threshold, no verdict) from the per-layer files of a stopped run:
residual relative difference vs REF after the last finished layer, per path and prompt; decay error actually used per
layer and path; per-head closed-loop rel_y counts over 0.05; determinism. Writes runs/partial.json and partial.md.
Usage: partial_report.py"""
import json
from pathlib import Path
import numpy as np
R = Path(__file__).resolve().parent / "runs"
ARMS = ["XS18", "XS18+U4", "XS18+U3"]
jl = lambda p: [json.loads(l) for l in open(p)] if p.exists() else []
div = jl(R / "divergence-abl.jsonl"); dec = jl(R / "decay-err-abl.jsonl"); hd = jl(R / "heads-abl.jsonl")
last = div[-1] if div else None
out = dict(layers_done=len(div), last_layer=last["layer"] if last else None,
           layer_seconds=[r["seconds"] for r in div], det_bit_equal_all_layers=all(all(r["det_bit_equal"].values()) for r in div))
out["resid_rel_after_last_layer"] = {a: last[a] for a in ARMS} if last else None
out["resid_rel_max_over_prompts_per_layer"] = {a: [max(v for v in r[a].values() if v is not None) for r in div] for a in ARMS}
de = {a: [] for a in ARMS}
for r in dec:
    for a in ARMS: de[a].append(dict(layer=r["layer"], max=max(r["max_abs_a_minus_float"][a].values())))
out["decay_abs_err_per_layer"] = de
cnt = {a: {} for a in ARMS}
for r in hd:
    if r["path"] in cnt:
        c = cnt[r["path"]].setdefault(r["prompt"], [0, 0.0]); c[0] += sum(v > 0.05 for v in r["rel_y"]); c[1] = max(c[1], max(r["rel_y"]))
out["heads_over_0.05"] = {a: {p: dict(count=v[0], rel_y_max=v[1]) for p, v in d.items()} for a, d in cnt.items()}
out["errors"] = jl(R / "errors-abl.jsonl")
(R / "partial.json").write_text(json.dumps(out, indent=1) + "\n")
L = [f"# partial (descriptive, no verdict): {out['layers_done']} of 64 layers, last layer {out['last_layer']}", "",
     f"determinism (REF#2, XS18+U4#2 bit-equal every layer): {out['det_bit_equal_all_layers']}; guard errors: {len(out['errors'])}", "",
     "| prompt | " + " | ".join(f"{a} resid rel" for a in ARMS) + " | " + " | ".join(f"{a} heads>0.05 (rel_y max)" for a in ARMS) + " |",
     "|---|" + "---|" * (2 * len(ARMS))]
for p in sorted(last["XS18"]) if last else []:
    L.append(f"| {p} | " + " | ".join(f"{last[a][p]:.3g}" for a in ARMS) + " | " +
             " | ".join(f"{out['heads_over_0.05'][a].get(p, {}).get('count', 0)} ({out['heads_over_0.05'][a].get(p, {}).get('rel_y_max', 0):.3g})" for a in ARMS) + " |")
L += ["", "Decay error used, max over prompts, tokens and heads, per DeltaNet layer (|a_path / 2^18 - a_float64|):", "",
      "| layer | " + " | ".join(ARMS) + " |", "|---|" + "---|" * len(ARMS)]
for i in range(len(dec)):
    L.append(f"| {de['XS18'][i]['layer']} | " + " | ".join(f"{de[a][i]['max']:.3g}" for a in ARMS) + " |")
(R / "partial.md").write_text("\n".join(L) + "\n"); print("\n".join(L))
