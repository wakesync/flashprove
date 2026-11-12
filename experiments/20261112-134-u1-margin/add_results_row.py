#!/usr/bin/env python3
"""Insert (or replace) the qwen-u1-margin row in research/results.yaml from runs/analysis.json.
Usage: add_results_row.py <commit holding runs/analysis.json> <pr number> <YYYY-MM-DD>"""
import json, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent; ROOT = HERE.parents[1]; Y = ROOT / "research" / "results.yaml"
C, PR, D = sys.argv[1], int(sys.argv[2]), sys.argv[3]
X = "experiments/20261112-134-u1-margin"; SRC = f"{X}/runs/analysis.json"; HW = "cpu-epyc-rome-kvm-16"
A = json.load(open(HERE / "runs" / "analysis.json"))
P = A["pooled"]; V = A["verdict"]; n = P["XS18"]["n"]; npr = V["prompts_run"]
SUB = f"{npr} of the 10 registered prompts ({n} positions; p03-repeat-word not run, PREREG A-1 tier 2)" if V["subset"] else f"all 10 prompts ({n} positions)"
NOTE = (f"D = KL(REF_stock || REF_abl) per teacher-forced position, float64; E = max over checkpoints of PR #124's committed XS18 KL "
        f"(head-only integer lowering); {SUB}; one deterministic run, spread over positions; no proof")
def g(v): return float(f"{v:.4g}")
def m(name, stat, value, unit, spread=None, note=None, total=None):
    d = dict(name=name, stat=stat, value=value)
    if total is not None: d["total"] = total
    d.update(unit=unit, n=n, spread=spread, hardware=HW, date=D, commit=C, source=SRC)
    if note: d["note"] = note
    return "      - " + json.dumps(d)
x = P["XS18"]; lr = x["log10r"]
rows = [m("u1_share_D_gt_10E_xs18", "single", g(x["share_gt10"]), "fraction", note=f"bar >= 0.95; {NOTE}"),
        m("u1_share_D_gt_100E_xs18", "single", g(x["share_gt100"]), "fraction", note=f"bar >= 0.50; {NOTE}"),
        m("u1_log10_ratio_median_xs18", "median", g(lr["median"]), "ratio", spread=dict(sd=g(lr["sd"]), min=g(lr["min"]), max=g(lr["max"])),
          note=f"log10(D / E) over positions; {NOTE}"),
        m("u1_D_median", "median", g(P["D"]["median"]), "ratio", spread=dict(sd=None, min=g(P["D"]["min"]), max=g(P["D"]["max"])),
          note=f"D in nats (the ledger has no nats unit); {NOTE}"),
        m("u1_top1_differ_stock_vs_abl", "count", P["top1_differ"], "count", total=n,
          note=f"positions where float64 stock and abl argmax differ; PR #124's committed ref_top1 gives {P['top1_differ_pr124_same_prompts']} on the same prompts; {NOTE}")]
summ = (f"{V['verdict']} vs prereg (subset result: {SUB}). Share of positions with D > 10 E: {x['share_gt10']:.3f} (bar 0.95), "
        f"D > 100 E: {x['share_gt100']:.3f} (bar 0.50), prompts with share(D > 10 E) >= 0.90: {x['prompts_share10_ge_090']} of {npr} "
        f"(bar {V['prompts_needed']}). D median {P['D']['median']:.3g} nats, E (XS18) median {P['E_XS18']['median']:.3g} nats; "
        f"median log10(D/E) {lr['median']:.2f}. Float64 stock and abl differ at top-1 on {P['top1_differ']} of {n} positions. "
        f"Measured, unreplicated; head-only E, a fully integer model may have a larger E")
block = "\n".join([
    "  - id: qwen-u1-margin",
    '    title: "Qwen3.8-27B stock vs abliterated float64 output distance D against the head-only integer lowering error E (U1 margin)"',
    "    status: measured", "    replication: unreplicated", f"    pr: {PR}",
    "    summary: " + json.dumps(summ),
    '    conditions: "teacher-forced, float64 numpy forward (PR #88 / #124 code unchanged), both checkpoints from the shared layer-16 state, one lm_head pass; E read from PR #124 committed files only; CPU, shared loaded host; no integer arm re-run, no proof, no served replies"',
    f"    evidence: [{X}/RESULTS.md]", "    metrics:"] + rows) + "\n"
t = Y.read_text()
if "  - id: qwen-u1-margin\n" in t:
    a = t.index("  - id: qwen-u1-margin\n"); b = t.find("\n  - id: ", a + 5); b = len(t) if b < 0 else b + 1
    t = t[:a] + block + ("\n" if b < len(t) else "") + t[b:]
else:
    t = t.rstrip("\n") + "\n\n" + block
Y.write_text(t); print(block)
