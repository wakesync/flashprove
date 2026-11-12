#!/usr/bin/env python3
"""Append this experiment's entry to research/results.yaml from runs/summary.json and runs/ledger-w.json.
Every number in the entry is read from those two committed files. Usage: add_results_row.py <full sha of the runs commit>"""
import json, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent; REPO = HERE.parents[1]
EXP = "experiments/20261112-148-norm-class"
sha = sys.argv[1]; assert len(sha) == 40
S = json.load(open(HERE / "runs/summary.json")); LW = json.load(open(HERE / "runs/ledger-w.json"))
B = S["baseline"]; A = S["arms"]; V = S["verdicts"]; ls = S["layer_set_done"]
a, m = B["input_layernorm"], B["post_attention_layernorm"]
kst = S["k_rule"]["k_star"]; sarm = V["S"].get("arm")
complete = ls in ("full", "r33") and S["baseline_complete"]
if not complete: status = "in progress"
elif any(v["verdict"] == "PASS" for v in V.values()): status = "measured"
else: status = "negative"
nl = len(S["layers_arms"]); nb = len(S["layers_baseline"])
src = f"{EXP}/runs/summary.json"
common = f"hardware: cpu-epyc-rome-kvm-16, date: 2026-11-12, commit: {sha}, source: {src}"
pct = lambda x: f"{100 * x:.2f}%"
g = lambda x: f"{x:.3g}"


def arm_txt(name):
    v = V[name]; arm = v.get("arm")
    if arm is None or arm not in A or not A[arm]["n_layers"]: return f"{name}: no verdict ({v.get('why', 'not measured')})"
    x = A[arm]; rm = x["r_median_over_layers"]; t = x["totals"]
    cls = "in class" if x["in_class_on_layers_done"] else f"OUT of class ({t['n_out_of_class']:,} entries)"
    extra = f", {t['n_clamped_a'] + t['n_clamped_m']:,} of {t['n_entries']:,} entries clamped" if arm == "C" else ""
    return (f"{name}{'' if arm == name else ' (k = ' + arm[1:] + ')'}: {v['verdict']}, {cls}{extra}, {x['layers_pass']} of {x['n_layers']} layers meet the bar, "
            f"per-layer median r from {g(rm['min'])} to {g(rm['max'])}, largest r {g(x['r_max_over_layers'])} (layer {x['worst_layer']})")


lead = ("PARTIAL / not finished vs prereg (no all-layer verdict). " if not complete else
        ("H holds: at least one arm passes. " if S["H_holds"] else "NEGATIVE vs prereg: no registered arm passes (class and per-layer fidelity bar together). "))
summary = (lead + f"Baseline at 2^12 over {nb} of 64 layers, 672 tokens: input_layernorm output over 2,047 on {a['total']['over']:,} of {a['total']['n']:,} entries "
           f"({pct(a['share_over_2047'])}), max {int(a['max_q12']):,} (layer {a['max_layer']}); post_attention_layernorm output over 2,047 on {m['total']['over']:,} of "
           f"{m['total']['n']:,} ({pct(m['share_over_2047'])}), max {int(m['max_q12']):,} (layer {m['max_layer']}); every layer has entries over the class on both norms: "
           f"{a['layers_with_any_over'] == a['n_layers'] and m['layers_with_any_over'] == m['n_layers']}. Arms, open loop, {nl} layers"
           f"{' (registered reduced set R33)' if ls == 'r33' else ''}, bar = per-layer output rel L2 vs float64 median <= 1e-3 and max <= 1e-2 over 6 prompts: "
           + "; ".join(arm_txt(n) for n in ("C", "S", "W")) + f". k rule gave k = {kst}. Open loop: no logits, no token agreement, no compounding. No proof")
cond = (f"abliterated checkpoint (stock layers 0 to 16 byte-identical), 6 of PR 124's frozen prompts (672 tokens, includes p03-repeat-word); open loop: each layer starts "
        f"from the float64 stream; arms change only the two pre-norm outputs (mixer input and MLP input); mixer float64 with float heads, MLP = PR 138's integer M3 "
        f"lowering; baseline on {nb} layers, arms on {nl} layers ({ls}; PREREG A-1); arm W's ledger cost is counted, not built; CPU, one deterministic run, "
        f"spread over prompts, shared loaded host; no logits, no proof")
title = ("Qwen3.8-27B abliterated: pre-norm outputs against the public class 2,047 and three fixes (clamp, smaller scale, wider class), open loop per layer"
         + ("" if complete else " (partial)"))
M = []


def met(name, stat, value, unit, n, spread, note, total=None):
    t = f", total: {total}" if total is not None else ""
    M.append(f"      - {{name: {name}, stat: {stat}, value: {value}{t}, unit: {unit}, n: {n}, spread: {spread}, {common}, note: \"{note}\"}}")


for key, nm in (("input_layernorm", "a"), ("post_attention_layernorm", "m")):
    b = B[key]; sp = b["share_per_layer"]
    met(f"baseline_{nm}_over_2047", "count", b["total"]["over"], "count", b["total"]["n"], "null",
        f"entries of RNE(2^12 x {key} output) with magnitude over 2,047, float64 stream, {b['n_layers']} layers x 672 tokens x 5,120 channels; per-layer share "
        f"median {pct(sp['median'])}, min {pct(sp['min'])}, max {pct(sp['max'])}", total=b["total"]["n"])
    met(f"baseline_{nm}_max_abs_q12", "max", int(b["max_q12"]), "int", b["total"]["n"], "null",
        f"largest magnitude of RNE(2^12 x {key} output), at layer {b['max_layer']}, prompt {b['max_prompt']}; class bound 2,047; entries >= 2^15: {b['total']['ge15']:,}, "
        f">= 2^17: {b['total']['ge17']:,}, >= 2^18: {b['total']['ge18']:,}")
for name in ("C", "S", "W"):
    arm = V[name].get("arm")
    if arm is None or arm not in A or not A[arm]["n_layers"]: continue
    x = A[arm]; rm = x["r_median_over_layers"]; t = x["totals"]
    met(f"arm_{name}_layers_meeting_bar", "count", x["layers_pass"], "count", x["n_layers"], "null",
        f"arm {arm}: layers whose output rel L2 vs float64 has median over 6 prompts <= 1e-3 and max <= 1e-2; open loop; out-of-class entries {t['n_out_of_class']:,} "
        f"of {t['n_entries']:,}; SiLU v1 domain exits {t['silu_exits']:,} of {t['n_hidden']:,} hidden entries; verdict {V[name]['verdict']}", total=x["n_layers"])
    met(f"arm_{name}_r_per_layer_median", "median", f"{rm['median']:.4g}", "ratio", x["n_layers"], f"{{sd: null, min: {rm['min']:.4g}, max: {rm['max']:.4g}}}",
        f"arm {arm}: median over layers of the per-layer median (6 prompts) of the layer output rel L2 vs float64, open loop; largest single prompt-layer value "
        f"{g(x['r_max_over_layers'])} at layer {x['worst_layer']}; one deterministic run, spread over layers")
c18 = [c for c in LW["classes"] if c["A"] == 2 ** 18 - 1][0]; c0 = LW["classes"][0]
M.append(f"      - {{name: arm_W_ledger_in_proj_log2_class_2e18, stat: single, value: {c18['in_proj_row']['log2']}, unit: count, n: 1, spread: null, "
         f"hardware: cpu-epyc-rome-kvm-16, date: 2026-11-12, commit: {sha}, source: {EXP}/runs/ledger-w.json, note: \"COUNTED, not built, not measured: log2 of the no-wrap "
         f"bound of the in_proj and M3a-MLP gate/up rows of bounds.py with the public norm class widened to 2^18 - 1 (registered 2,047: {c0['in_proj_row']['log2']}); "
         f"stays below 2^63; a committed cell of that class needs {c18['keys_if_committed_cell']['total']} lookup keys instead of {c0['keys_if_committed_cell']['total']}\"}}")
entry = f'''
  - id: qwen-norm-class-148
    title: "{title}"
    status: {status}
    replication: {'n/a' if status == 'in progress' else 'unreplicated'}
    pr: 152
    summary: "{summary}"
    conditions: "{cond}"
    evidence: [{EXP}/RESULTS.md]
    metrics:
''' + "\n".join(M) + "\n"
assert '"' not in summary and '"' not in cond
p = REPO / "research/results.yaml"; Y = p.read_text()
assert "id: qwen-norm-class-148" not in Y
p.write_text(Y.rstrip("\n") + "\n" + entry)
print(entry)
