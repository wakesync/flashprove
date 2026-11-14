#!/usr/bin/env python3
"""Descriptive, post hoc (written after the registered numbers were read; no bar): per arm, how the cells over 0.01
spread over prompts, and per failing layer the median rel_y per prompt. -> runs/by-prompt.json"""
import json
from collections import defaultdict
from pathlib import Path
import numpy as np
HERE = Path(__file__).resolve().parent; R = HERE / "runs"
cells = [json.loads(l) for l in open(R / "cells.jsonl")]
lay = {(r["arm"], r["layer"]): r for r in map(json.loads, open(R / "layers.jsonl"))}
out = {}
for arm in ("C2047", "C1665"):
    c = [x for x in cells if x["arm"] == arm]
    over = defaultdict(int); tot = defaultdict(int)
    for x in c:
        tot[x["prompt"]] += 1; over[x["prompt"]] += x["rel_y"] > 0.01
    fails = sorted(l for (a, l), r in lay.items() if a == arm and not r["layer_pass"])
    per_fail = {}
    for l in fails:
        d = defaultdict(list)
        for x in c:
            if x["layer"] == l: d[x["prompt"]].append(x["rel_y"])
        per_fail[l] = {p: dict(median=float(np.median(v)), max=float(max(v))) for p, v in d.items()}
    out[arm] = dict(cells_over_001_by_prompt={p: dict(over=over[p], n=tot[p]) for p in tot}, failing_layers=fails, failing_layer_prompt_medians=per_fail)
(R / "by-prompt.json").write_text(json.dumps(out, indent=1) + "\n")
for arm in out:
    print(arm, {p: v["over"] for p, v in out[arm]["cells_over_001_by_prompt"].items()})
