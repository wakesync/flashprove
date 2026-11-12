#!/usr/bin/env python3
"""Insert (or replace) the qwen-deltanet-decay-tables row in research/results.yaml from runs/eval/summary.json.
Usage: add_results_row.py <commit sha holding runs/eval/summary.json> <pr number> <YYYY-MM-DD>"""
import json, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent; ROOT = HERE.parents[1]; Y = ROOT / "research" / "results.yaml"
C, PR, D = sys.argv[1], int(sys.argv[2]), sys.argv[3]
X = "experiments/20261112-136-deltanet-decay"; SRC = f"{X}/runs/eval/summary.json"; HW = "cpu-epyc-rome-kvm-16"
S = json.load(open(HERE / "runs" / "eval" / "summary.json")); dm = S["domain"]
NOTE = ("abliterated Qwen3.8-27B, 48 DeltaNet layers x 48 V heads x 10 frozen prompts (1,461 tokens) from PR #88's float64 forward; "
        "integer table emulation vs float64 decay, no proof; one deterministic run, no spread across runs")
def g(v): return float(f"{v:.4g}")
def m(name, stat, value, unit, n, spread=None, arm=None, series=None, total=None, note=None):
    d = dict(name=name)
    if series: d["series"] = series
    if arm: d["arm"] = arm
    d.update(stat=stat, value=value)
    if total is not None: d["total"] = total
    d.update(unit=unit, n=n, spread=spread, hardware=HW, date=D, commit=C, source=SRC)
    if note: d["note"] = note
    return "      - " + json.dumps(d)
rows = []
for arm in ("T0", "T1", "T2", "T3"):
    a = S["arms"][arm]
    rows.append(m(f"decay_{arm.lower()}_failing_heads", "count", a["n_fail_layer_heads"], "count", a["of_layer_heads"], total=a["of_layer_heads"],
                  arm=arm, series="decay-table-fail-heads",
                  note=f"(layer, head) pairs failing the bar on at least one prompt (reject, per-token |a_table - a| > 2^-9, or max_t |prod a_table - prod a| > 0.01); "
                       f"{a['verdict']} vs prereg; failing cells {a['n_fail_cells']} of {a['n_cells']}; {NOTE}"))
    ec = a["e_cum_max_over_cells"]
    rows.append(m(f"decay_{arm.lower()}_ecum_median", "median", g(ec["median"]), "abs_diff", ec["n"], arm=arm, series="decay-table-ecum",
                  spread=dict(sd=g(ec["sd"]), min=g(ec["min"]), max=g(ec["max"])),
                  note=f"per (layer, head, prompt) cell, max over tokens of |prod a_table - prod a| (accumulated state decay); spread over the 23,040 cells; bar 0.01 on every cell; {NOTE}"))
rows.append(m("decay_softplus_input_out_of_domain", "single", g(dm["share_x_out"]), "fraction", dm["n_token_head_values"],
              note=f"share of (token, head, layer) values with x = ar + dt_bias outside [-8, 8): {dm['x_out_of_domain']} of {dm['n_token_head_values']} "
                   f"({dm['x_lt_m8']} below -8, {dm['x_ge_8']} at or above 8); {dm['heads_any_x_out']} of 2,304 (layer, head) pairs have at least one; {NOTE}"))
rows.append(m("decay_g_below_v1_step", "single", g(dm["share_g_below_step"]), "fraction", dm["n_token_head_values"],
              note=f"share of values with g = A softplus(x) below 1/256 (one v1 exp-table row): {dm['g_below_step']} of {dm['n_token_head_values']}; "
                   f"{dm['heads_majority_g_below_step']} of 2,304 (layer, head) pairs have it on most tokens; {NOTE}"))
summary = ("FAIL vs prereg: all four table designs miss the bar; H (T2 passes, T0 and T1 fail) is false. Failing (layer, head) of 2,304: "
           + ", ".join(f"{a} {S['arms'][a]['n_fail_layer_heads']}" for a in ("T0", "T1", "T2", "T3"))
           + f". The softplus input leaves v1's [-8, 8) on {dm['share_x_out']:.1%} of 3.37M (token, head, layer) values, mostly below -8, on {dm['heads_any_x_out']} heads; "
           f"g is below one v1 exp row (1/256) on {dm['share_g_below_step']:.1%}. Descriptive split: the accumulated-decay misses of T3 come mostly from the g floor at 2^-12, "
           "the per-token misses from rounding cA with one exponent per layer and from the softplus row step. Proxy fidelity of the decay only: no proof, no end-to-end token check")
entry = f'''  - id: qwen-deltanet-decay-tables
    title: "Qwen3.8-27B abliterated, all 48 DeltaNet layers: softplus table domain, exp table step, and four decay table designs vs float64 decay"
    status: negative
    replication: unreplicated
    pr: {PR}
    summary: {json.dumps(summary)}
    conditions: "teacher-forced float64 forward (PR #88 code unchanged) on PR #124's 10 frozen prompts (1,461 tokens); abl = stock layers 0 to 16 (byte-identical) then abl 17 to 63; decay inputs recorded per layer, V head, token; table designs emulated in integers with the pinned v1 softplus table and v1-layout exp tables from the pinned generator; CPU, one deterministic run, shared loaded host; no proof, no constraint build, no table digest change"
    evidence: [{X}/RESULTS.md]
    metrics:
''' + "\n".join(rows) + "\n\n"
t = Y.read_text()
start = t.find("  - id: qwen-deltanet-decay-tables\n")
if start >= 0:
    end = t.find("\n  - id: ", start + 5); t = t[:start] + t[end + 1:]
anchor = "  - id: qwen-e2e-agreement\n"
assert t.count(anchor) == 1
Y.write_text(t.replace(anchor, entry + anchor)); print("inserted", len(rows), "metrics")
