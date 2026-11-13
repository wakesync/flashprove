#!/usr/bin/env python3
"""Insert (or replace) the qwen-deltanet-decay-tables-r2 row in research/results.yaml from runs/eval/summary.json.
Usage: add_results_row.py <commit sha holding runs/eval/summary.json and eval-meta.json> <pr number> <YYYY-MM-DD>"""
import json, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent; ROOT = HERE.parents[1]; Y = ROOT / "research" / "results.yaml"
C, PR, D = sys.argv[1], int(sys.argv[2]), sys.argv[3]
X = "experiments/20261113-155-deltanet-decay-r2"; SRC = f"{X}/runs/eval/summary.json"; META = f"{X}/runs/eval/eval-meta.json"; HW = "cpu-epyc-rome-kvm-16"
RID = "qwen-deltanet-decay-tables-r2"
S = json.load(open(HERE / "runs" / "eval" / "summary.json")); M = json.load(open(HERE / "runs" / "eval" / "eval-meta.json"))
assert S["coverage"]["label"] == "COMPLETE"
NOTE = ("abliterated Qwen3.8-27B, 48 DeltaNet layers x 48 V heads x 10 frozen prompts (1,461 tokens): the decay inputs PR #146 recorded, reused; "
        "integer table emulation vs float64 decay, no proof; one deterministic evaluation (rerun byte-equal), no spread across runs")
DESC = dict(U1="T3 of PR #146 with one cA exponent per head", U2="U1 with the softplus output, g, the fine exp key and a at 2^-20 (fine exp table 2^20 rows)",
            U3="U2 with the softplus table extended down to -16", U4="one per-head table keyed on x, 12,288 rows per head, one lookup")
def g(v): return float(f"{v:.4g}")
def m(name, stat, value, unit, n, spread=None, arm=None, series=None, total=None, note=None, source=SRC):
    d = dict(name=name)
    if series: d["series"] = series
    if arm: d["arm"] = arm
    d.update(stat=stat, value=value)
    if total is not None: d["total"] = total
    d.update(unit=unit, n=n, spread=spread, hardware=HW, date=D, commit=C, source=source)
    if note: d["note"] = note
    return "      - " + json.dumps(d)
rows = []
for arm in ("U1", "U2", "U3", "U4"):
    a = S["arms"][arm]; b = a["fail_by_reason"]
    rows.append(m(f"decay_{arm.lower()}_failing_heads", "count", a["n_fail_layer_heads"], "count", a["of_layer_heads"], total=a["of_layer_heads"], arm=arm, series="decay-table-r2-fail-heads",
                  note=f"{DESC[arm]}; (layer, head) pairs failing the bar on at least one prompt (reject, per-token |a_table - a| > 2^-9, or max_t |prod a_table - prod a| > 0.01); "
                       f"{a['verdict']} vs prereg; {NOTE}"))
    rows.append(m(f"decay_{arm.lower()}_failing_cells", "count", a["n_fail_cells"], "count", a["n_cells"], total=a["n_cells"], arm=arm, series="decay-table-r2-fail-cells",
                  note=f"(layer, head, prompt) cells failing the bar; by reason (a cell can have several): reject {b['reject']}, per-token {b['e_tok']}, accumulated {b['e_cum']}; {a['verdict']} vs prereg; {NOTE}"))
    et = a["e_tok_max_over_cells"]; ec = a["e_cum_max_over_cells"]
    rows.append(m(f"decay_{arm.lower()}_etok_median", "median", g(et["median"]), "abs_diff", et["n"], arm=arm, series="decay-table-r2-etok",
                  spread=dict(sd=g(et["sd"]), min=g(et["min"]), max=g(et["max"])),
                  note=f"per (layer, head, prompt) cell, max over tokens of |a_table - a|; spread over the 23,040 cells; bar 2^-9 = 0.001953 on every cell; {NOTE}"))
    rows.append(m(f"decay_{arm.lower()}_ecum_median", "median", g(ec["median"]), "abs_diff", ec["n"], arm=arm, series="decay-table-r2-ecum",
                  spread=dict(sd=g(ec["sd"]), min=g(ec["min"]), max=g(ec["max"])),
                  note=f"per (layer, head, prompt) cell, max over tokens of |prod a_table - prod a| (accumulated state decay); spread over the 23,040 cells; bar 0.01 on every cell; {NOTE}"))
# Counted-not-built numbers (table rows) are deliberately NOT ledger metrics: only measured values go in metrics[].
assert M["u4"]["rows_per_head"] == 12288
A = S["arms"]
summary = ("FAIL (mixed) vs prereg: H (U3 passes, U1 and U2 fail) is false because U3 fails; U1, U2, U3 FAIL, U4 PASS. Per arm, failing (layer, head) of 2,304 and failing cells of 23,040: "
           + ", ".join(f"{k} {A[k]['verdict']} {A[k]['n_fail_layer_heads']} / {A[k]['n_fail_cells']}" for k in ("U1", "U2", "U3", "U4"))
           + f" (PR #146's best, T3: 1513 / 6391). The three table-chain arms (softplus lookup, product with cA, exp lookup) still fail: U3, with a per-head exponent, 2^-20 scale and softplus rows down to -16, "
           f"has no accumulated-decay failure left but misses the per-token bar on {A['U3']['fail_by_reason']['e_tok']} cells (largest per-token error {g(A['U3']['e_tok_max_over_cells']['max'])}, bar 0.001953; that these misses sit on tokens with g >= 1 is a post hoc descriptive attribution). "
           f"U4, one per-head table keyed on x (12,288 rows per head, one lookup; rows computed in float64, not by an integer generator, and output a at 2^-20, not the 2^-12 stream scale), meets the bar on every cell (largest per-token error {g(A['U4']['e_tok_max_over_cells']['max'])}, "
           f"largest accumulated error {g(A['U4']['e_cum_max_over_cells']['max'])}, bar 0.01). Emulation of table semantics only: no proof, no end-to-end token check; the table domains were fixed from the ranges seen on the same 10 prompts; "
           "U4 needs a lookup into a committed per-head table (counted, not built: 28,311,552 rows for the 48 layers), which no design on main specifies")
entry = f'''  - id: {RID}
    title: "Qwen3.8-27B abliterated, all 48 DeltaNet layers, decay tables round 2: per-head cA exponent, 2^-20 scale, wider softplus, and one per-head table keyed on x, vs float64 decay"
    status: measured
    replication: unreplicated
    pr: {PR}
    summary: {json.dumps(summary)}
    conditions: "same recorded decay inputs, metric and bar as PR #146 (48 DeltaNet layers x 48 V heads x 10 frozen prompts, 1,461 tokens, at most 512 per prompt); the 48 recorded array files are PR #146's scratch output, pinned by sha256 in the PREREG before use and accepted only after PR #146's unchanged evaluation on them reproduced its committed per-cell output; four arms registered before any arm-evaluation code (one design-tabulation script over PR #146's committed per-head ranges ran before the registration); integer emulation with tables from the pinned integer generator (U4's per-head rows in float64 by registration); CPU, one deterministic evaluation run twice, shared loaded host; no forward pass, no proof, no constraint build, no table digest or format change"
    evidence: [{X}/RESULTS.md]
    metrics:
''' + "\n".join(rows) + "\n\n"
t = Y.read_text()
start = t.find(f"  - id: {RID}\n")
if start >= 0:
    end = t.find("\n  - id: ", start + 5); t = t[:start] + t[end + 1:]
anchor = "  - id: qwen-e2e-agreement\n"
assert t.count(anchor) == 1
Y.write_text(t.replace(anchor, entry + anchor)); print("inserted", len(rows), "metrics")
