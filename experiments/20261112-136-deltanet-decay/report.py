#!/usr/bin/env python3
"""Descriptive tables for RESULTS.md from runs/eval (written after the verdicts; no threshold here).
usage: report.py   -> runs/eval/report.md, runs/eval/report.json"""
import csv, gzip, json
from collections import defaultdict
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent; D = HERE / "runs" / "eval"
E_TOK, E_CUM = 2.0 ** -9, 0.01
S = json.load(open(D / "summary.json")); dom = json.load(gzip.open(D / "domain.json.gz", "rt"))
def rd(p):
    with gzip.open(p, "rt") as fh: return list(csv.DictReader(fh))
cells = rd(D / "cells.csv.gz"); split = rd(D / "split-T3.csv.gz"); sweep = rd(D / "sweep-T3-F.csv.gz")
dk = {(x["layer"], x["head"]): x for x in dom}
R = {}; L = []

# per-layer e_A, A range, cA of the smallest head
lay = defaultdict(list)
for x in dom: lay[x["layer"]].append(x)
rows = []
for l, xs in sorted(lay.items()):
    A = [x["A"] for x in xs]; e = xs[0]["e_A"]; cz = sum(x["cA"] == 0 for x in xs); c_small = sum(0 < x["cA"] < 16 for x in xs)
    rows.append(dict(layer=l, e_A=e, A_min=min(A), A_max=max(A), heads_cA_zero=cz, heads_cA_1_15=c_small))
R["per_layer_cA"] = rows
L.append("### Per-layer cA exponent (DESIGN 5.0 honest conversion: one e_A per layer from max A)\n")
L.append("| layer | e_A | A min | A max | heads with cA = 0 | heads with cA in 1..15 |"); L.append("|---|---|---|---|---|---|")
for r in rows: L.append(f"| {r['layer']} | {r['e_A']} | {r['A_min']:.4g} | {r['A_max']:.4g} | {r['heads_cA_zero']} | {r['heads_cA_1_15']} |")
R["heads_cA_zero_total"] = sum(r["heads_cA_zero"] for r in rows); R["heads_cA_lt16_total"] = sum(r["heads_cA_zero"] + r["heads_cA_1_15"] for r in rows)

# failing (layer, head) of T3: attribute by the split sources (which single source alone fails the bar on that head)
sp = defaultdict(dict)
for r in split:
    k = (int(r["layer"]), int(r["head"])); s = r["source"]
    cur = sp[k].get(s, (0.0, 0.0)); sp[k][s] = (max(cur[0], float(r["e_tok_max"])), max(cur[1], float(r["e_cum_max"])))
fail3 = defaultdict(lambda: [0.0, 0.0, 0])
for c in cells:
    if c["arm"] != "T3": continue
    et, ec = float(c["e_tok_max"]), float(c["e_cum_max"])
    if et > E_TOK or ec > E_CUM:
        f = fail3[(int(c["layer"]), int(c["head"]))]; f[0] = max(f[0], et); f[1] = max(f[1], ec); f[2] += 1
attr = defaultdict(int)
for k in fail3:
    srcs = [s for s, (et, ec) in sp[k].items() if et > E_TOK or ec > E_CUM]
    attr["+".join(sorted(srcs)) if srcs else "none alone (combination)"] += 1
R["T3_failing_heads_attribution"] = dict(attr)
# cA zero/small vs failing
R["T3_fail_heads_with_cA_lt16"] = sum(1 for k in fail3 if dk[k]["cA"] < 16)
R["T3_fail_heads"] = len(fail3)
# per source over all cells
L.append("\n### T3 error split by source (each source alone, rest float64), over all 23,040 (layer, head, prompt) cells\n")
L.append("| source | cells e_tok > 2^-9 | cells e_cum > 0.01 | e_tok max: median (max) | e_cum max: median (max) |"); L.append("|---|---|---|---|---|")
for s, v in S["split-T3"].items():
    L.append(f"| {s} | {v['n_cells_e_tok_gt_bar']} | {v['n_cells_e_cum_gt_bar']} | {v['e_tok_max']['median']:.3g} ({v['e_tok_max']['max']:.3g}) | {v['e_cum_max']['median']:.3g} ({v['e_cum_max']['max']:.3g}) |")
L.append("\n### T3 at a finer internal scale F' (descriptive)\n")
L.append("| F' | cells e_tok > 2^-9 | cells e_cum > 0.01 | e_tok max: median (max) | e_cum max: median (max) |"); L.append("|---|---|---|---|---|")
for s, v in sorted(S["sweep-T3-F"].items()):
    L.append(f"| {s} | {v['n_cells_e_tok_gt_bar']} | {v['n_cells_e_cum_gt_bar']} | {v['e_tok_max']['median']:.3g} ({v['e_tok_max']['max']:.3g}) | {v['e_cum_max']['median']:.3g} ({v['e_cum_max']['max']:.3g}) |")
L.append(f"\n### T3 failing (layer, head): {len(fail3)} of 2,304; with cA < 16: {R['T3_fail_heads_with_cA_lt16']}; attribution by which single source alone already fails the bar on that head\n")
for k, v in sorted(attr.items(), key=lambda kv: -kv[1]): L.append(f"- {k}: {v}")
# T3 failing heads per layer
pl = defaultdict(int)
for (l, h) in fail3: pl[l] += 1
R["T3_fail_heads_per_layer"] = {str(l): pl.get(l, 0) for l in sorted(lay)}
L.append("\nT3 failing heads per layer (of 48): " + ", ".join(f"L{l}: {pl.get(l, 0)}" for l in sorted(lay)))
# worst 15 T3 heads
w = sorted(fail3.items(), key=lambda kv: -kv[1][1])[:15]
L.append("\n### 15 worst T3 heads by e_cum\n"); L.append("| layer | head | A | cA (e_A) | dt_bias | g median | e_tok max | e_cum max | prompts failing (of 10) |"); L.append("|---|---|---|---|---|---|---|---|---|")
for (l, h), (et, ec, n) in w:
    x = dk[(l, h)]; L.append(f"| {l} | {h} | {x['A']:.4g} | {x['cA']} ({x['e_A']}) | {x['dt_bias']:.4g} | {x['g_min_med_max'][1]:.3g} | {et:.3g} | {ec:.3g} | {n} |")
R["T3_worst"] = [dict(layer=l, head=h, e_tok=et, e_cum=ec, prompts=n, A=dk[(l, h)]["A"], cA=dk[(l, h)]["cA"], e_A=dk[(l, h)]["e_A"]) for (l, h), (et, ec, n) in w]
# fraction of T2/T3 failures among slow heads (g median < 1/256)
slow = {k for k, x in dk.items() if x["g_min_med_max"][1] < 1 / 256}
R["heads_slow_g_median_lt_step"] = len(slow); R["T3_fail_heads_slow"] = len(set(fail3) & slow)
# per prompt fail counts per arm
pp = defaultdict(lambda: defaultdict(int))
for c in cells:
    if int(c["rejects"]) or float(c["e_tok_max"]) > E_TOK or float(c["e_cum_max"]) > E_CUM: pp[c["arm"]][c["prompt"]] += 1
R["fail_cells_per_prompt"] = {a: dict(v) for a, v in pp.items()}
L.append("\n### Failing cells per prompt (of 2,304 per prompt)\n"); prompts = sorted({c["prompt"] for c in cells})
L.append("| arm | " + " | ".join(prompts) + " |"); L.append("|---" * (len(prompts) + 1) + "|")
for a in ("T0", "T1", "T2", "T3"): L.append(f"| {a} | " + " | ".join(str(pp[a].get(p, 0)) for p in prompts) + " |")
(D / "report.md").write_text("\n".join(L) + "\n"); (D / "report.json").write_text(json.dumps(R, indent=1) + "\n")
print("\n".join(L)); print(json.dumps({k: v for k, v in R.items() if k not in ("per_layer_cA", "T3_worst")}, indent=1))
