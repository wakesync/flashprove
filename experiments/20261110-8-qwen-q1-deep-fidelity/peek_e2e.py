#!/usr/bin/env python3
"""Print the end-to-end and U1 parts of runs/summary.json, and the last abl divergence row (descriptive, stage E partial)."""
import json
from pathlib import Path
R = Path(__file__).resolve().parent / "runs"
s = json.load(open(R / "summary.json"))
for k in ("e2e_stock", "e2e_abl", "u1_layer20", "slow_state_rule", "smallest_FS_slow", "H1_XS18_all_targets"):
    v = s.get(k)
    if k == "u1_layer20" and isinstance(v, dict):
        v = {a: b for a, b in v.items() if a != "rows"}
    print(k, json.dumps(v, indent=1))
for tg, T in s["targets"].items():
    print(tg, "n_slow", T["n_slow"], "bf16_context_rel_y", T["bf16_context_rel_y"])
    for a in ("XS18", "XS20"):
        d = T["arms"][a]
        print(" ", a, "slow_pass", d["slow_pass"], "over_class", d["over_class"], "resid_frob", d["resid_frob"], "layer_rel_y", d["layer_rel_y"])
rows = [json.loads(l) for l in open(R / "e2e-abl-divergence.jsonl")]
print("abl divergence rows", len(rows), "first layer", rows[0]["layer"], "last layer", rows[-1]["layer"])
print("last", json.dumps(rows[-1]))
rows = [json.loads(l) for l in open(R / "e2e-stock-divergence.jsonl")]
print("stock divergence rows", len(rows), "last", json.dumps(rows[-1]))
