#!/usr/bin/env python3
"""Append this experiment's entry to research/results.yaml from runs/summary.json (committed).
Usage: add_results_row.py <full sha of the runs commit> <pr number>"""
import json, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent; REPO = HERE.parents[1]
EXP = "experiments/20261114-204-int-attn-heldout"
sha, pr = sys.argv[1], int(sys.argv[2]); assert len(sha) == 40
S = json.load(open(HERE / "runs/summary.json")); A = S["arms"]
src = f"{EXP}/runs/summary.json"
common = f"hardware: cpu-epyc-rome-kvm-16, date: 2026-11-14, commit: {sha}, source: {src}"
g = lambda x: f"{x:.3g}"
complete = S["complete"]
verds = [v for a in A.values() for v in (a["H_R"], a["H_F"])]
if not complete: status = "in progress"
elif all(v == "PASS" for v in verds): status = "measured"
elif all(v in ("PASS", "FAIL") for v in verds): status = "negative" if "FAIL" in verds else "measured"
else: status = "in progress"

def arm_txt(a):
    x = A[a]; per = x["layers"]
    meds = [p["rel_median"] for p in per]; mxs = [p["rel_max"] for p in per]
    q = sum(p["q_over"] for p in per); k = sum(p["k_over"] for p in per); v = sum(p["v_over"] for p in per)
    return (f"{a}: H_R {x['H_R']} (clamped q/k/v {q:,}/{k:,}/{v:,} of {sum(p['q_n'] for p in per):,}/{sum(p['k_n'] for p in per):,}/{sum(p['v_n'] for p in per):,}, "
            f"guard failures {x['total_guard_failures']}, range-fail layers {x['layers_range_fail'] or 'none'}), "
            f"H_F {x['H_F']} ({len(per) - len(x['layers_fid_fail'])} of {len(per)} layers meet the bar, failing {x['layers_fid_fail'] or 'none'}; per-layer median rel_y {g(min(meds))} to {g(max(meds))}, "
            f"per-layer max {g(min(mxs))} to {g(max(mxs))}; pooled {x['pooled']['n']:,} cells median {g(x['pooled']['median'])}, over 0.05: {x['pooled']['n_over_005']:,})")

summary = (("" if complete else f"PARTIAL ({len(S['layers_done'])} of 16 attention layers done). ")
           + "Held-out check of PR 178's integer attention: per-layer exponents frozen from PR 178's in-sample fit, evaluated open loop on 8 new prompts (541 tokens) "
           + "on the 16 full-attention layers of Qwen3.8-27B abliterated, nothing fitted on the new prompts. Two axes per arm: H_R = zero q/k/v clamps and zero guard failures; "
           + "H_F = PR 88's A2 per-head bar (median rel_y <= 0.01, max <= 0.05 over 192 (prompt, head) cells per layer, every layer). "
           + "Measured, unreplicated, one deterministic CPU run: " + "; ".join(arm_txt(a) for a in ("C2047", "C1665"))
           + ". Open loop per head: not token agreement, no logits. Eight prompts are not a deployment distribution. No proof")
cond = ("abliterated checkpoint (stock layers 0 to 16 byte-identical), 8 held-out prompts written for this experiment (prompts-heldout.json, split sha256 e5245bd6), "
        "no exact match with PR 124's 10 calibration prompts; open loop per attention layer on the float64 stream; lowered from rotated q, k, v to o only; "
        "E_q, E_k, E_v, sh copied from PR 178 runs/layers.jsonl (sha256 73404d47), int_attn.py imported unchanged; CPU, one deterministic run, determinism checked; shared loaded host; no proof")
M = []
def met(name, stat, value, unit, n, spread, note, total=None):
    t = f", total: {total}" if total is not None else ""
    M.append(f"      - {{name: {name}, stat: {stat}, value: {value}{t}, unit: {unit}, n: {n}, spread: {spread}, {common}, note: \"{note}\"}}")
for a in ("C2047", "C1665"):
    x = A[a]; per = x["layers"]
    mxs = [p["rel_max"] for p in per]; meds = [p["rel_median"] for p in per]
    met(f"heldout_int_attn_{a}_clamped_entries", "count", x["total_clamped"], "count", len(per), "null",
        f"arm {a}: q+k+v entries with |RNE| over the clamp at the frozen PR 178 exponents, all layers done and 8 held-out prompts; H_R {x['H_R']}; guard failures {x['total_guard_failures']}")
    met(f"heldout_int_attn_{a}_layers_meeting_bar", "count", len(per) - len(x["layers_fid_fail"]), "count", len(per), "null",
        f"arm {a}: attention layers with median rel_y <= 0.01 and max <= 0.05 over 192 (prompt, head) cells; H_F {x['H_F']}", total=len(per))
    met(f"heldout_int_attn_{a}_rel_y_pooled", "median", f"{x['pooled']['median']:.4g}", "ratio", x["pooled"]["n"],
        f"{{sd: null, min: null, max: {x['pooled']['max']:.4g}}}",
        f"arm {a}: per (prompt, layer, head) relative L2 of the integer head output vs float64, pooled; cells over 0.01: {x['pooled']['n_over_001']:,}, over 0.05: {x['pooled']['n_over_005']:,}; per-layer medians {min(meds):.4g} to {max(meds):.4g}")
entry = f'''
  - id: qwen-int-attn-heldout-204
    title: "Qwen3.8-27B abliterated: integer attention with frozen PR 178 scales on 8 held-out prompts, range transfer and per-head fidelity{'' if complete else ' (partial)'}"
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
assert "id: qwen-int-attn-heldout-204" not in Y
p.write_text(Y.rstrip("\n") + "\n" + entry)
print(entry)
