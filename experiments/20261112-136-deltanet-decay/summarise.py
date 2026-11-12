#!/usr/bin/env python3
"""Verdicts and summary tables from decay_tables.py output (PREREG "Acceptance threshold").
usage: summarise.py <eval_dir>   -> <eval_dir>/summary.json, summary.md"""
import csv, gzip, json, sys
from collections import defaultdict
from pathlib import Path
import numpy as np

E_TOK, E_CUM = 2.0 ** -9, 0.01
ARMS = ("T0", "T1", "T2", "T3")

def rd(p):
    with gzip.open(p, "rt") as fh: return list(csv.DictReader(fh))

def st(v):
    v = np.asarray(v, float); v = v[np.isfinite(v)] if np.isfinite(v).any() else v
    return dict(n=int(len(v)), min=float(v.min()), median=float(np.median(v)), max=float(v.max()), sd=float(v.std()))

def main(d):
    d = Path(d); meta = json.load(open(d / "eval-meta.json"))
    cells = rd(d / "cells.csv.gz"); dom = json.load(gzip.open(d / "domain.json.gz", "rt"))
    S = dict(meta=meta, arms={}, domain={})
    for arm in ARMS:
        cs = [c for c in cells if c["arm"] == arm]
        fail = []
        for c in cs:
            r = int(c["rejects"]); et = float(c["e_tok_max"]); ec = float(c["e_cum_max"])
            why = []
            if r: why.append("reject")
            if not (et <= E_TOK) and not r: why.append("e_tok")
            if not (ec <= E_CUM): why.append("e_cum")
            if why: fail.append(dict(layer=int(c["layer"]), head=int(c["head"]), prompt=c["prompt"], why=why, rejects=r, e_tok_max=et, e_cum_max=ec))
        by = defaultdict(int)
        for k in ("reject", "e_tok", "e_cum"): by[k] = sum(k in f["why"] for f in fail)
        lh = sorted({(f["layer"], f["head"]) for f in fail})
        per_layer = defaultdict(set)
        for l, h in lh: per_layer[l].add(h)
        et_all = [float(c["e_tok_max"]) for c in cs if int(c["rejects"]) == 0]
        ec_all = [float(c["e_cum_max"]) for c in cs]
        S["arms"][arm] = dict(verdict="PASS" if not fail else "FAIL", n_cells=len(cs), n_fail_cells=len(fail), fail_by_reason=dict(by),
                              n_fail_layer_heads=len(lh), of_layer_heads=len({(c["layer"], c["head"]) for c in cs}),
                              fail_heads_per_layer={str(l): sorted(h) for l, h in sorted(per_layer.items())},
                              rejects_total=sum(int(c["rejects"]) for c in cs),
                              e_tok_max_over_cells=st(et_all) if et_all else None, e_cum_max_over_cells=st(ec_all),
                              e_tok_med_over_cells=st([float(c["e_tok_med"]) for c in cs if int(c["rejects"]) == 0]) if et_all else None,
                              worst=sorted(fail, key=lambda f: -f["e_cum_max"])[:20])
    n_tot = sum(x["n"] for x in dom)
    out_x = sum(x["count_x_out"] for x in dom); low_g = sum(x["count_g_lt_step"] for x in dom)
    S["domain"] = dict(n_token_head_values=n_tot, x_out_of_domain=out_x, share_x_out=out_x / n_tot,
                       x_ge_8=int(sum(round(x["share_x_ge_8"] * x["n"]) for x in dom)), x_lt_m8=int(sum(round(x["share_x_lt_m8"] * x["n"]) for x in dom)),
                       g_below_step=low_g, share_g_below_step=low_g / n_tot,
                       heads_any_x_out=sum(x["count_x_out"] > 0 for x in dom), heads_all_x_out=sum(x["count_x_out"] == x["n"] for x in dom),
                       heads_majority_g_below_step=sum(x["share_g_lt_step"] > 0.5 for x in dom), n_heads=len(dom),
                       share_x_out_per_head=st([x["count_x_out"] / x["n"] for x in dom]),
                       share_g_low_per_head=st([x["share_g_lt_step"] for x in dom]),
                       g_median_per_head=st([x["g_min_med_max"][1] for x in dom]), x_max_per_head=st([x["x_min_med_max"][2] for x in dom]),
                       x_min_per_head=st([x["x_min_med_max"][0] for x in dom]), dt_bias=st([x["dt_bias"] for x in dom]), A=st([x["A"] for x in dom]))
    per_layer = defaultdict(lambda: [0, 0, 0, 0])
    for x in dom:
        p = per_layer[x["layer"]]; p[0] += x["count_x_out"]; p[1] += x["count_g_lt_step"]; p[2] += x["n"]; p[3] += x["count_x_out"] > 0
    S["domain"]["per_layer"] = {str(l): dict(x_out=v[0], g_low=v[1], n=v[2], heads_any_x_out=v[3]) for l, v in sorted(per_layer.items())}
    for fn in ("split-T3.csv.gz", "sweep-T3-F.csv.gz"):
        rows = rd(d / fn); key = "source" if "source" in rows[0] else "F"; g = defaultdict(list)
        for r in rows: g[r[key]].append(r)
        S[fn.split(".")[0]] = {k: dict(e_tok_max=st([float(r["e_tok_max"]) for r in v]), e_cum_max=st([float(r["e_cum_max"]) for r in v]),
                                       n_cells_e_cum_gt_bar=sum(float(r["e_cum_max"]) > E_CUM for r in v),
                                       n_cells_e_tok_gt_bar=sum(float(r["e_tok_max"]) > E_TOK for r in v)) for k, v in g.items()}
    (d / "summary.json").write_text(json.dumps(S, indent=1) + "\n")
    L = ["| arm | verdict | cells failing / n | by reason (reject, e_tok, e_cum) | (layer, head) failing / n | e_tok max: median (max) | e_cum max: median (max) |", "|---|---|---|---|---|---|---|"]
    for arm, a in S["arms"].items():
        et = a["e_tok_max_over_cells"]; ec = a["e_cum_max_over_cells"]
        L.append(f"| {arm} | {a['verdict']} | {a['n_fail_cells']} / {a['n_cells']} | {a['fail_by_reason'].get('reject',0)}, {a['fail_by_reason'].get('e_tok',0)}, {a['fail_by_reason'].get('e_cum',0)} | {a['n_fail_layer_heads']} / {a['of_layer_heads']} | "
                 + (f"{et['median']:.3g} ({et['max']:.3g})" if et else "n/a") + f" | {ec['median']:.3g} ({ec['max']:.3g}) |")
    (d / "summary.md").write_text("\n".join(L) + "\n"); print("\n".join(L)); print(json.dumps(S["domain"], indent=1)[:3000])

if __name__ == "__main__": main(sys.argv[1])
