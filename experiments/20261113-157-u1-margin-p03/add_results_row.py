#!/usr/bin/env python3
"""Insert (or replace) the qwen-u1-margin-full row in research/results.yaml from runs/merged-analysis.json, and add a
superseding note to PR #139's qwen-u1-margin row (its numbers are not edited).
Usage: add_results_row.py <commit holding runs/merged-analysis.json> <pr number> <YYYY-MM-DD>"""
import json, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent; ROOT = HERE.parents[1]; Y = ROOT / "research" / "results.yaml"
C, PR, D = sys.argv[1], int(sys.argv[2]), sys.argv[3]
X = "experiments/20261113-157-u1-margin-p03"; SRC = f"{X}/runs/merged-analysis.json"; HW = "cpu-epyc-rome-kvm-16"
A = json.load(open(HERE / "runs" / "merged-analysis.json"))
T = A["ten"]; P = T["pooled"]; V = T["verdict"]; Q = A["p03_alone"]; det = A["determinism"] or {}
DET = "run 2 bit-identical to run 1" if det.get("all_bit_equal") else "determinism not shown"
NOTE = (f"D = KL(REF_stock || REF_abl) per teacher-forced position, float64; E = max over checkpoints of PR #124's committed XS18 KL "
        f"(head-only integer lowering); all 10 registered prompts: PR #139's committed D for 9, this PR's D for p03-repeat-word; "
        f"{DET}; spread over positions; no proof")
N3 = (f"p03-repeat-word only (512 positions), this PR's D; E = max over checkpoints of PR #124's committed XS18 KL; {DET}; "
      f"descriptive input to the 10-prompt rule")
def g(v): return float(f"{v:.4g}")
def m(name, stat, value, unit, n, spread=None, note=None, total=None):
    d = dict(name=name, stat=stat, value=value)
    if total is not None: d["total"] = total
    d.update(unit=unit, n=n, spread=spread, hardware=HW, date=D, commit=C, source=SRC)
    if note: d["note"] = note
    return "      - " + json.dumps(d)
x = P["XS18"]; lr = x["log10r"]; n = x["n"]; q = Q["XS18"]; ql = q["log10r"]
rows = [m("u1full_share_D_gt_10E_xs18", "single", g(x["share_gt10"]), "fraction", n, note=f"bar >= 0.95; {NOTE}"),
        m("u1full_share_D_gt_100E_xs18", "single", g(x["share_gt100"]), "fraction", n, note=f"bar >= 0.50; {NOTE}"),
        m("u1full_prompts_share10_ge_090", "count", x["prompts_share10_ge_090"], "count", n, total=10, note=f"bar >= 8 of 10; {NOTE}"),
        m("u1full_log10_ratio_median_xs18", "median", g(lr["median"]), "ratio", n, spread=dict(sd=g(lr["sd"]), min=g(lr["min"]), max=g(lr["max"])),
          note=f"log10(D / E) over positions; {NOTE}"),
        m("u1full_top1_differ_stock_vs_abl", "count", P["top1_differ"], "count", n, total=n,
          note=f"positions where float64 stock and abl argmax differ; PR #124's committed ref_top1 gives {P['top1_differ_pr124_same_prompts']}; {NOTE}"),
        m("u1p03_share_D_gt_10E_xs18", "single", g(q["share_gt10"]), "fraction", 512, note=N3),
        m("u1p03_share_D_gt_100E_xs18", "single", g(q["share_gt100"]), "fraction", 512, note=N3),
        m("u1p03_log10_ratio_median_xs18", "median", g(ql["median"]), "ratio", 512, spread=dict(sd=g(ql["sd"]), min=g(ql["min"]), max=g(ql["max"])),
          note=f"log10(D / E) over positions; {N3}"),
        m("u1p03_D_median", "median", g(Q["D"]["median"]), "ratio", 512, spread=dict(sd=None, min=g(Q["D"]["min"]), max=g(Q["D"]["max"])),
          note=f"D in nats (the ledger has no nats unit); {N3}")]
summ = (f"{V['verdict']} vs prereg, on the full registered set (10 prompts, {n} positions; PR #139's committed D for 9 prompts, this PR's for "
        f"p03-repeat-word). Share of positions with D > 10 E: {x['share_gt10']:.3f} (bar 0.95), D > 100 E: {x['share_gt100']:.3f} (bar 0.50), "
        f"prompts with share(D > 10 E) >= 0.90: {x['prompts_share10_ge_090']} of 10 (bar 8). p03 alone: D > 10 E at {q['share_gt10']:.3f}, "
        f"D > 100 E at {q['share_gt100']:.3f} of 512 positions. Float64 stock and abl differ at top-1 on {P['top1_differ']} of {n} positions. "
        f"Validity gates pass (p03 REF reproduces PR #124 bit for bit on both checkpoints). {DET}. Measured, unreplicated; head-only E, "
        f"a fully integer model may have a larger E")
block = "\n".join([
    "  - id: qwen-u1-margin-full",
    '    title: "Qwen3.8-27B stock vs abliterated U1 margin on the full registered prompt set (adds p03-repeat-word to PR #139)"',
    "    status: measured", "    replication: unreplicated", f"    pr: {PR}",
    "    summary: " + json.dumps(summ),
    '    conditions: "teacher-forced, float64 numpy forward (PR #88 / #124 / #139 code unchanged); p03: stock layers 0 to 16 recomputed, PR #139 fused pass for 17 to 63, one lm_head pass; other 9 prompts: PR #139 committed D; E read from PR #124 committed files only; CPU, shared loaded host; no proof, no served replies"',
    f"    evidence: [{X}/RESULTS.md]", "    metrics:"] + rows) + "\n"
t = Y.read_text()
OLD = '    summary: "FAIL (mixed) vs prereg (subset result: 9 of the 10'
SUP = f'    summary: "Superseded for the full registered set by qwen-u1-margin-full (PR #{PR}); the numbers below are unchanged. FAIL (mixed) vs prereg (subset result: 9 of the 10'
if OLD in t: t = t.replace(OLD, SUP, 1)
elif SUP not in t: raise SystemExit("PR #139 row summary not found")
if "  - id: qwen-u1-margin-full\n" in t:
    a = t.index("  - id: qwen-u1-margin-full\n"); b = t.find("\n  - id: ", a + 5); b = len(t) if b < 0 else b + 1
    t = t[:a] + block + ("\n" if b < len(t) else "") + t[b:]
else:
    t = t.rstrip("\n") + "\n\n" + block
Y.write_text(t); print(block)
