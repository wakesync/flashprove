#!/usr/bin/env python3
"""Descriptive partial control (not the registered control, which needs logits): XS18's per-layer residual relative
difference vs REF here against PR #124's committed runs/divergence-abl.jsonl, for every finished layer and prompt.
Writes runs/partial-control.json. Usage: partial_control.py"""
import json
from pathlib import Path
H = Path(__file__).resolve().parent
mine = [json.loads(l) for l in open(H / "runs" / "divergence-abl.jsonl")]
p124 = {r["layer"]: r for r in (json.loads(l) for l in open(H.parent / "20261111-8-qwen-e2e-agreement" / "runs" / "divergence-abl.jsonl"))}
d = 0.0; n = 0; eq = 0
for r in mine:
    o = p124[r["layer"]]["XS18"]
    for pid, v in r["XS18"].items():
        n += 1; d = max(d, abs(v - o[pid])); eq += v == o[pid]
out = dict(layers=len(mine), pairs=n, bit_equal_pairs=eq, max_abs_diff=d,
           note="XS18 residual rel diff vs REF per (layer, prompt), this run vs PR #124's committed abl divergence file; descriptive")
(H / "runs" / "partial-control.json").write_text(json.dumps(out, indent=1) + "\n"); print(json.dumps(out))
