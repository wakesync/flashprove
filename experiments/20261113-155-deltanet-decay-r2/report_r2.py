#!/usr/bin/env python3
"""Descriptive tables for RESULTS.md (no threshold decided here; the verdicts are summarise_r2.py's).
usage: report_r2.py   -> runs/descriptive/report.json, runs/descriptive/report.md

Inputs, all committed: runs/eval/{summary.json, cells.csv.gz, heads.json.gz}; runs/descriptive/split-U4.csv.gz
(registered: split of the best arm); runs/descriptive/split-U3.csv.gz and gband.csv.gz (POST HOC, PREREG Amendment
A3); PR #146's runs/eval/{summary.json, domain.json.gz} for the T3 comparison and the per-head g and x ranges.
The table-size counts are arithmetic on the registered table shapes (counted, not built)."""
import csv, gzip, json
from collections import Counter, defaultdict
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent; E = HERE / "runs" / "eval"; D = HERE / "runs" / "descriptive"
P146 = HERE.parent / "20261112-136-deltanet-decay" / "runs" / "eval"
E_TOK, E_CUM = 2.0 ** -9, 0.01
ARMS = ("U1", "U2", "U3", "U4")


def rd(p):
    with gzip.open(p, "rt") as fh: return list(csv.DictReader(fh))


def st(v):
    v = np.asarray(v, float)
    return dict(n=int(len(v)), min=float(v.min()), median=float(np.median(v)), max=float(v.max()), sd=float(v.std())) if len(v) else None


S = json.load(open(E / "summary.json")); cells = rd(E / "cells.csv.gz")
heads = json.load(gzip.open(E / "heads.json.gz", "rt")); dom = json.load(gzip.open(P146 / "domain.json.gz", "rt"))
S146 = json.load(open(P146 / "summary.json"))
dk = {(x["layer"], x["head"]): x for x in dom}; hk = {(x["layer"], x["head"]): x for x in heads}
R = {}; L = []

# ---- 0. comparison with PR #146's best arm
t3 = S146["arms"]["T3"]
R["pr146_T3"] = dict(n_fail_cells=t3["n_fail_cells"], n_fail_layer_heads=t3["n_fail_layer_heads"], fail_by_reason=t3["fail_by_reason"])
L.append("### Registered arms next to PR #146's T3 (T3 from PR #146's committed summary.json)\n")
L.append("| arm | failing cells / 23,040 | reject, e_tok, e_cum | failing heads / 2,304 |"); L.append("|---|---|---|---|")
L.append(f"| T3 (PR #146) | {t3['n_fail_cells']} | {t3['fail_by_reason'].get('reject', 0)}, {t3['fail_by_reason'].get('e_tok', 0)}, {t3['fail_by_reason'].get('e_cum', 0)} | {t3['n_fail_layer_heads']} |")
for a in ARMS:
    v = S["arms"][a]; b = v["fail_by_reason"]
    L.append(f"| {a} | {v['n_fail_cells']} | {b['reject']}, {b['e_tok']}, {b['e_cum']} | {v['n_fail_layer_heads']} |")

# ---- 1. per-head exponent
e = np.array([x["e_h"] for x in heads]); cA = np.array([x["cA_h"] for x in heads])
R["per_head_exponent"] = dict(e_min=int(e.min()), e_max=int(e.max()), cA_min=int(cA.min()), cA_max=int(cA.max()),
                              e_histogram={str(k): int(v) for k, v in sorted(Counter(e.tolist()).items())},
                              distinct_e_per_layer=st([len({x["e_h"] for x in heads if x["layer"] == l}) for l in sorted({x["layer"] for x in heads})]),
                              pr146_heads_cA_lt_16=sum(x["cA"] < 16 for x in dom),
                              heads_with_shift_gt_12=int((e > 12).sum()), pr146_heads_with_layer_shift_gt_12=sum(x["e_A"] > 12 for x in dom))
pe = R["per_head_exponent"]
L.append(f"\n### Per-head exponent (rule of the PREREG): e_h {pe['e_min']} to {pe['e_max']}, cA_h {pe['cA_min']} to {pe['cA_max']} over 2,304 heads; "
         f"distinct exponents within a layer: median {pe['distinct_e_per_layer']['median']:.0f}, max {pe['distinct_e_per_layer']['max']:.0f}. "
         f"Under PR #146's per-layer rule {pe['pr146_heads_cA_lt_16']} heads had cA below 16. "
         f"Heads whose product floor has a shift above 12 (two remainder limbs under DESIGN 5.0's layout): {pe['heads_with_shift_gt_12']} with the per-head rule, "
         f"{pe['pr146_heads_with_layer_shift_gt_12']} with PR #146's per-layer rule (counted from the exponents, not built).")

# ---- 2. failing heads per layer and failing cells per prompt
R["fail_heads_per_layer"] = {a: {l: len(h) for l, h in S["arms"][a]["fail_heads_per_layer"].items()} for a in ARMS}
R["fail_cells_per_prompt"] = {a: S["arms"][a]["fail_cells_per_prompt"] for a in ARMS}
prompts = sorted({c["prompt"] for c in cells}); Tp = {c["prompt"]: int(c["T"]) for c in cells}
L.append("\n### Failing cells per prompt (of 2,304 per prompt; token count in brackets)\n")
L.append("| arm | " + " | ".join(f"{p} ({Tp[p]})" for p in prompts) + " |"); L.append("|---" * (len(prompts) + 1) + "|")
for a in ARMS: L.append(f"| {a} | " + " | ".join(str(R["fail_cells_per_prompt"][a].get(p, 0)) for p in prompts) + " |")
layers = sorted({int(c["layer"]) for c in cells})
L.append("\n### Failing heads per layer (of 48)\n")
for a in ("U1", "U2", "U3"):
    L.append(f"- {a}: " + ", ".join(f"L{l}: {R['fail_heads_per_layer'][a].get(str(l), 0)}" for l in layers))

# ---- 3. split by source
def split_table(arm, posthoc):
    rows = rd(D / f"split-{arm}.csv.gz"); g = defaultdict(list)
    for r in rows: g[r["source"]].append(r)
    out = {k: dict(n_cells=len(v), n_cells_e_tok_gt_bar=sum(float(r["e_tok_max"]) > E_TOK for r in v), n_cells_e_cum_gt_bar=sum(float(r["e_cum_max"]) > E_CUM for r in v),
                   e_tok_max=st([float(r["e_tok_max"]) for r in v]), e_cum_max=st([float(r["e_cum_max"]) for r in v])) for k, v in g.items()}
    L.append(f"\n### {arm} error split by source (each source alone, the rest float64), over 23,040 cells" + (" [POST HOC, Amendment A3]" if posthoc else " [registered: best arm]") + "\n")
    L.append("| source | cells e_tok > 2^-9 | cells e_cum > 0.01 | e_tok max per cell: median (max) | e_cum max per cell: median (max) |"); L.append("|---|---|---|---|---|")
    for k, v in out.items():
        L.append(f"| {k} | {v['n_cells_e_tok_gt_bar']} | {v['n_cells_e_cum_gt_bar']} | {v['e_tok_max']['median']:.3g} ({v['e_tok_max']['max']:.3g}) | {v['e_cum_max']['median']:.3g} ({v['e_cum_max']['max']:.3g}) |")
    return rows, out

rows4, R["split_U4"] = split_table("U4", False)
rows3, R["split_U3_posthoc"] = split_table("U3", True)

# attribution of U3's failing heads by single source
sp = defaultdict(dict)
for r in rows3:
    k = (int(r["layer"]), int(r["head"])); cur = sp[k].get(r["source"], (0.0, 0.0))
    sp[k][r["source"]] = (max(cur[0], float(r["e_tok_max"])), max(cur[1], float(r["e_cum_max"])))
fail3 = defaultdict(lambda: [0.0, 0.0, 0])
for c in cells:
    if c["arm"] != "U3": continue
    et, ec = float(c["e_tok_max"]), float(c["e_cum_max"])
    if et > E_TOK or ec > E_CUM:
        f = fail3[(int(c["layer"]), int(c["head"]))]; f[0] = max(f[0], et); f[1] = max(f[1], ec); f[2] += 1
attr = Counter()
for k in fail3:
    srcs = [s for s, (et, ec) in sp[k].items() if et > E_TOK or ec > E_CUM]
    attr["+".join(sorted(srcs)) if srcs else "none alone (only the combination)"] += 1
R["U3_failing_heads_attribution_posthoc"] = dict(attr)
L.append(f"\nU3 failing heads ({len(fail3)} of 2,304) by which single source alone already fails the bar on that head [POST HOC]: " + "; ".join(f"{k}: {v}" for k, v in attr.most_common()))

# ---- 4. g band (post hoc)
gb = rd(D / "gband.csv.gz"); R["gband_posthoc"] = {}
L.append("\n### Per-token error by band of the float64 exponent g, table-chain arms [POST HOC, Amendment A3]\n")
L.append("| arm | cells over the e_tok bar | of these, largest error on a token with g >= 1 | cells whose g < 1 tokens alone exceed the bar | largest error on g < 1 tokens | largest error on g >= 1 tokens | smallest g at the worst token of a failing cell |"); L.append("|---|---|---|---|---|---|---|")
tok_hi = None
for a in ("U1", "U2", "U3"):
    v = [r for r in gb if r["arm"] == a]
    over = [r for r in v if float(r["e_tok_max"]) > E_TOK]
    at_hi = sum(float(r["g_at_max"]) >= 1.0 for r in over)
    lo_alone = sum(r["e_tok_max_g_lt_1"] != "" and float(r["e_tok_max_g_lt_1"]) > E_TOK for r in v)
    hi_alone = sum(r["e_tok_max_g_ge_1"] != "" and float(r["e_tok_max_g_ge_1"]) > E_TOK for r in v)
    mlo = max(float(r["e_tok_max_g_lt_1"]) for r in v if r["e_tok_max_g_lt_1"] != ""); mhi = max(float(r["e_tok_max_g_ge_1"]) for r in v if r["e_tok_max_g_ge_1"] != "")
    gmin = min((float(r["g_at_max"]) for r in over), default=None); xs = [float(r["x_at_max"]) for r in over]
    tok_hi = sum(int(r["n_g_ge_1"]) for r in v); tok_all = sum(int(r["T"]) for r in v)
    R["gband_posthoc"][a] = dict(cells_e_tok_gt_bar=len(over), of_these_worst_token_has_g_ge_1=at_hi, cells_g_lt_1_tokens_alone_gt_bar=lo_alone, cells_g_ge_1_tokens_alone_gt_bar=hi_alone,
                                 max_e_tok_g_lt_1=mlo, max_e_tok_g_ge_1=mhi, min_g_at_worst_token_of_failing_cells=gmin,
                                 x_at_worst_token_of_failing_cells=st(xs), g_at_worst_token_of_failing_cells=st([float(r["g_at_max"]) for r in over]),
                                 tokens_g_ge_1=tok_hi, tokens=tok_all)
    L.append(f"| {a} | {len(over)} | {at_hi} | {lo_alone} | {mlo:.3g} | {mhi:.3g} | " + (f"{gmin:.3g}" if gmin is not None else "n/a") + " |")
L.append(f"\n(token, head) values with g >= 1: {tok_hi} of {tok_all} ({tok_hi / tok_all:.2%}).")

# ---- 5. U2: accumulated failures and the softplus domain
def fail_heads(arm, reason):
    out = set()
    for c in cells:
        if c["arm"] != arm: continue
        if reason == "e_cum" and float(c["e_cum_max"]) > E_CUM: out.add((int(c["layer"]), int(c["head"])))
        if reason == "e_tok" and float(c["e_tok_max"]) > E_TOK: out.add((int(c["layer"]), int(c["head"])))
    return out
u2c = fail_heads("U2", "e_cum"); u1c = fail_heads("U1", "e_cum")
R["U2_e_cum_failing_heads"] = dict(n=len(u2c), with_x_min_lt_m8=sum(dk[k]["x_min_med_max"][0] < -8 for k in u2c), A=st([dk[k]["A"] for k in u2c]),
                                   share_x_lt_m8=st([dk[k]["share_x_lt_m8"] for k in u2c]))
R["U1_e_cum_failing_heads"] = dict(n=len(u1c), with_g_median_lt_2pow_m12=sum(dk[k]["g_min_med_max"][1] < 2.0 ** -12 for k in u1c),
                                   with_g_median_lt_1_256=sum(dk[k]["g_min_med_max"][1] < 1 / 256 for k in u1c))
x2 = R["U2_e_cum_failing_heads"]; x1 = R["U1_e_cum_failing_heads"]
L.append(f"\n### Accumulated-decay failures\n\n- U1: {x1['n']} heads fail e_cum on at least one prompt; {x1['with_g_median_lt_1_256']} of them have a median g below 1/256 and {x1['with_g_median_lt_2pow_m12']} below 2^-12 (median g from PR #146's committed table).")
L.append(f"- U2: {x2['n']} heads fail e_cum; {x2['with_x_min_lt_m8']} of them have x below -8 on at least one token (their A: {x2['A']['min']:.3g} to {x2['A']['max']:.3g}, median {x2['A']['median']:.3g}). U3 (softplus rows down to -16): 0 cells fail e_cum.")

# ---- 6. worst U3 heads
w = sorted(fail3.items(), key=lambda kv: -kv[1][0])[:15]
R["U3_worst_e_tok"] = [dict(layer=l, head=h, e_tok=et, e_cum=ec, prompts=n, A=hk[(l, h)]["A"], e_h=hk[(l, h)]["e_h"], cA_h=hk[(l, h)]["cA_h"], dt_bias=hk[(l, h)]["dt_bias"],
                            g_median=dk[(l, h)]["g_min_med_max"][1], g_max=dk[(l, h)]["g_min_med_max"][2]) for (l, h), (et, ec, n) in w]
L.append("\n### 15 worst U3 heads by per-token error\n"); L.append("| layer | head | A | cA_h (e_h) | dt_bias | g median | g max | e_tok max | prompts failing (of 10) |"); L.append("|---|---|---|---|---|---|---|---|---|")
for r in R["U3_worst_e_tok"]:
    L.append(f"| {r['layer']} | {r['head']} | {r['A']:.4g} | {r['cA_h']} ({r['e_h']}) | {r['dt_bias']:.4g} | {r['g_median']:.3g} | {r['g_max']:.3g} | {r['e_tok']:.3g} | {r['prompts']} |")
f3 = set(fail3)
R["U3_failing_heads"] = dict(n=len(f3), A=st([hk[k]["A"] for k in f3]), g_max=st([dk[k]["g_min_med_max"][2] for k in f3]), with_g_max_ge_1=sum(dk[k]["g_min_med_max"][2] >= 1 for k in f3),
                             heads_with_g_max_ge_1_in_model=sum(x["g_min_med_max"][2] >= 1 for x in dom))
r3 = R["U3_failing_heads"]
L.append(f"\nU3 failing heads: {r3['n']}; all {r3['with_g_max_ge_1']} have a g of at least 1 on some token; heads in the model with g >= 1 on some token: {r3['heads_with_g_max_ge_1_in_model']}; A of the failing heads {r3['A']['min']:.3g} to {r3['A']['max']:.3g} (median {r3['A']['median']:.3g}).")

# ---- 7. table sizes (counted from the registered shapes, not built)
n_layers = len(layers); n_heads = 48; u4_rows = S["meta"]["u4"]["rows_per_head"]; spw = S["meta"]["softplus_wide"]["rows"]
obs_rows = [int(np.floor(x["x_min_med_max"][2] * 256)) - int(np.floor(max(x["x_min_med_max"][0], -16.0) * 256)) + 1 for x in dom]
R["counted_not_built"] = dict(
    T3=dict(public_table_rows=dict(softplus_f12=4096, coarse_exp_f12=4096, fine_exp_f12=4096), total_public_rows=3 * 4096, per_head_table_rows=0),
    U1=dict(public_table_rows=dict(softplus_f12=4096, coarse_exp_f12=4096, fine_exp_f12=4096), total_public_rows=3 * 4096, per_head_table_rows=0,
            public_exponents_per_layer=n_heads, public_exponents_model=n_layers * n_heads),
    U2=dict(public_table_rows=dict(softplus_f20=4096, coarse_exp_f20=4096, fine_exp_f20=1 << 20), total_public_rows=2 * 4096 + (1 << 20), per_head_table_rows=0,
            public_exponents_model=n_layers * n_heads),
    U3=dict(public_table_rows=dict(softplus_f20_wide=spw, coarse_exp_f20=4096, fine_exp_f20=1 << 20), total_public_rows=spw + 4096 + (1 << 20), per_head_table_rows=0,
            public_exponents_model=n_layers * n_heads),
    U4=dict(public_table_rows={}, total_public_rows=0, per_head_table_rows=u4_rows, per_layer_table_rows=u4_rows * n_heads, model_table_rows=u4_rows * n_heads * n_layers,
            rows_spanned_by_observed_x_per_head=st(obs_rows), rows_spanned_by_observed_x_model=int(sum(obs_rows))))
c = R["counted_not_built"]
L.append("\n### Table sizes (counted from the registered shapes, not built)\n")
L.append("| arm | public table rows | per-head table rows | per-head public exponents |"); L.append("|---|---|---|---|")
L.append(f"| T3 (PR #146) | {c['T3']['total_public_rows']:,} (softplus 4,096 + coarse exp 4,096 + fine exp 4,096) | 0 | 0 (one per layer) |")
L.append(f"| U1 | {c['U1']['total_public_rows']:,} (as T3) | 0 | {c['U1']['public_exponents_model']:,} (48 per layer) |")
L.append(f"| U2 | {c['U2']['total_public_rows']:,} (softplus 4,096 + coarse exp 4,096 + fine exp 1,048,576) | 0 | {c['U2']['public_exponents_model']:,} |")
L.append(f"| U3 | {c['U3']['total_public_rows']:,} (softplus {spw:,} + coarse exp 4,096 + fine exp 1,048,576) | 0 | {c['U3']['public_exponents_model']:,} |")
L.append(f"| U4 | 0 | {u4_rows:,} per head, {c['U4']['per_layer_table_rows']:,} per layer, {c['U4']['model_table_rows']:,} for {n_layers} layers | 0 |")
L.append(f"\nU4 rows spanned by the observed x range on these 10 prompts (descriptive, from PR #146's committed per-head x minimum and maximum, not a bound): "
         f"{c['U4']['rows_spanned_by_observed_x_model']:,} of {c['U4']['model_table_rows']:,}; per head median {c['U4']['rows_spanned_by_observed_x_per_head']['median']:.0f}, max {c['U4']['rows_spanned_by_observed_x_per_head']['max']:.0f}.")

(D / "report.json").write_text(json.dumps(R, indent=1) + "\n"); (D / "report.md").write_text("\n".join(L) + "\n"); print("\n".join(L))
