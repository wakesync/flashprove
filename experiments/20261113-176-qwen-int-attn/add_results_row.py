#!/usr/bin/env python3
"""Append this experiment's entry to research/results.yaml from runs/summary.json (committed).
Usage: add_results_row.py <full sha of the runs commit> <pr number>
The summary wording was revised on 2026-11-13 after review of PR #178 (in-sample label, measured and unreplicated,
the N4 clamp qualified by C); no number in the entry changed. The entry in research/results.yaml is this script's output."""
import json, sys
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent; REPO = HERE.parents[1]
EXP = "experiments/20261113-176-qwen-int-attn"
sha, pr = sys.argv[1], int(sys.argv[2]); assert len(sha) == 40
S = json.load(open(HERE / "runs/summary.json")); A = S["arms"]
src = f"{EXP}/runs/summary.json"
common = f"hardware: cpu-epyc-rome-kvm-16, date: 2026-11-13, commit: {sha}, source: {src}"
g = lambda x: f"{x:.3g}"
verd = {a: A[a]["verdict"] for a in A}
complete = all(v in ("PASS", "FAIL") for v in verd.values())
status = "measured" if complete and "PASS" in verd.values() else ("negative" if complete else "in progress")

def arm_txt(a):
    x = A[a]; per = x["per_layer"]; meds = [p["rel_median"] for p in per]; mxs = [p["rel_max"] for p in per]
    worst = max(per, key=lambda p: p["rel_max"])
    return (f"{a}: {x['verdict']}, {x['layers_pass']} of {len(per)} layers meet the bar, per-layer median rel_y from {g(min(meds))} to {g(max(meds))}, "
            f"per-layer max from {g(min(mxs))} to {g(max(mxs))} (largest at layer {worst['layer']}); pooled over {x['pooled']['n']:,} cells: median {g(x['pooled']['median'])}, "
            f"over 0.05: {x['pooled']['n_over_005']:,}; over-clamp entries q/k/v {sum(p['q_over'] for p in per):,}/{sum(p['k_over'] for p in per):,}/{sum(p['v_over'] for p in per):,}")

summary = ((("PASS vs prereg. " if all(v == "PASS" for v in verd.values()) else ("NEGATIVE vs prereg: both arms FAIL. " if all(v == "FAIL" for v in verd.values()) else "Mixed vs prereg. ")) if complete else "PARTIAL vs prereg (not all 16 attention layers done). ")
           + "Upstream's integer attention (docs/model.md 6 steps 2 clamp only, 3, 4) on the 16 full-attention layers of Qwen3.8-27B abliterated, open loop, 10 frozen prompts (1,461 tokens), "
           + "bar = PR 88's A2 per-head bar (median rel_y <= 0.01, max <= 0.05 over 240 (prompt, head) pairs per layer, every layer). "
           + "Measured, unreplicated, one deterministic CPU run; the accuracy is in-sample (per-layer scales fitted on the same tokens it is measured on, not held out): "
           + "; ".join(arm_txt(a) for a in ("C2047", "C1665"))
           + ". 1,665 is the largest clamp that passes af-no-wrap-N4 at dh 256 for every admitted C, that is at the largest admitted C; at C = 0 the largest is 1,672 "
           + "(exact arithmetic in the PREREG); passing N4 is not admission. Open loop: no logits, no tokens. No proof")
cond = ("abliterated checkpoint (stock layers 0 to 16 byte-identical), PR 124's 10 frozen prompts (1,461 tokens); open loop per attention layer on the float64 stream; "
        "lowered from rotated q, k, v to o only, projections, q/k RMSNorm, partial rotary, gate and o_proj float64; per-layer power-of-two scales fitted in-sample by the "
        "scales/README cell rule, sh per layer in 4..12; CPU, one deterministic run, determinism checked, spread over (prompt, head) pairs; shared loaded host; no proof")
M = []
def met(name, stat, value, unit, n, spread, note, total=None):
    t = f", total: {total}" if total is not None else ""
    M.append(f"      - {{name: {name}, stat: {stat}, value: {value}{t}, unit: {unit}, n: {n}, spread: {spread}, {common}, note: \"{note}\"}}")
for a in ("C2047", "C1665"):
    x = A[a]; per = x["per_layer"]; meds = np.array([p["rel_median"] for p in per]); mxs = np.array([p["rel_max"] for p in per])
    met(f"int_attn_{a}_layers_meeting_bar", "count", x["layers_pass"], "count", len(per), "null",
        f"arm {a}: attention layers with median rel_y <= 0.01 and max <= 0.05 over 240 (prompt, head) pairs; verdict {x['verdict']}; determinism ok {x['determinism_ok']}", total=len(per))
    met(f"int_attn_{a}_rel_y_pooled", "median", f"{x['pooled']['median']:.4g}", "ratio", x["pooled"]["n"],
        f"{{sd: null, min: {x['pooled']['min']:.4g}, max: {x['pooled']['max']:.4g}}}",
        f"arm {a}: per (prompt, layer, head) relative L2 of the integer head output vs float64, pooled over all cells; one deterministic run; cells over 0.01: {x['pooled']['n_over_001']:,}, over 0.05: {x['pooled']['n_over_005']:,}")
    met(f"int_attn_{a}_layer_max_rel_y", "max", f"{float(mxs.max()):.4g}", "ratio", len(per), f"{{sd: null, min: {float(mxs.min()):.4g}, max: {float(mxs.max()):.4g}}}",
        f"arm {a}: largest per-layer max rel_y over the attention layers done (spread = min and max of the per-layer max); per-layer medians from {float(meds.min()):.4g} to {float(meds.max()):.4g}")
entry = f'''
  - id: qwen-int-attn-176
    title: "Qwen3.8-27B abliterated: upstream integer attention on the 16 full-attention layers at clamps 2,047 and 1,665, open loop per head{'' if complete else ' (partial)'}"
    status: {status}
    replication: unreplicated
    pr: {pr}
    summary: "{summary}"
    conditions: "{cond}"
    evidence: [{EXP}/RESULTS.md]
    metrics:
''' + "\n".join(M) + "\n"
assert '"' not in summary and '"' not in cond
p = REPO / "research/results.yaml"; Y = p.read_text()
assert "id: qwen-int-attn-176" not in Y
p.write_text(Y.rstrip("\n") + "\n" + entry)
print(entry)
