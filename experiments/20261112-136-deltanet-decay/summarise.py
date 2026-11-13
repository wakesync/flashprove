#!/usr/bin/env python3
"""Verdicts and summary tables from decay_tables.py output (PREREG "Acceptance threshold").
usage: summarise.py <eval_dir> [--set S10|S7] [--partial-layers N] [--fixture]   -> <eval_dir>/summary.json, summary.md

Before any verdict the input is checked against the registered suite (suite.py; added after the run, review of
PR #146, RESULTS section 6): eval-meta.json must name exactly the registered DeltaNet layers and prompts, and
cells.csv.gz must hold exactly one row per (arm, layer, head, prompt) of that grid, with the registered token count,
an integer reject count, and finite e_tok / e_cum unless the cell has a rejected lookup. domain.json.gz, split and
sweep files must cover the same grid. Anything else exits non-zero with no output written. A PARTIAL run
(PREREG "Kill criterion") must be declared with --partial-layers N (the first N registered DeltaNet layers); the
debug fixture with --fixture. Neither is ever inferred from a short input."""
import csv, gzip, json, sys
from collections import Counter, defaultdict
from pathlib import Path
import numpy as np
import suite as SU

E_TOK, E_CUM = 2.0 ** -9, 0.01
ARMS = ("T0", "T1", "T2", "T3")
need = SU.need

def rd(p):
    with gzip.open(p, "rt") as fh: return list(csv.DictReader(fh))

def st(v):
    v = np.asarray(v, float); v = v[np.isfinite(v)] if np.isfinite(v).any() else v
    return dict(n=int(len(v)), min=float(v.min()), median=float(np.median(v)), max=float(v.max()), sd=float(v.std()))

def parse_mode(argv):
    mode = dict(fixture=False, set="S10", partial_layers=None); a = list(argv)
    while a:
        k = a.pop(0)
        if k == "--fixture": mode["fixture"] = True
        elif k == "--set": need(a, "--set needs a value"); mode["set"] = a.pop(0)
        elif k == "--partial-layers":
            need(a, "--partial-layers needs a value"); v = a.pop(0)
            need(v.isdigit(), "--partial-layers needs an integer"); mode["partial_layers"] = int(v)
        else: raise SU.Incomplete(f"unknown argument {k!r}")
    return mode

def load(d):
    d = Path(d)
    with open(d / "eval-meta.json") as fh: meta = json.load(fh)
    with gzip.open(d / "domain.json.gz", "rt") as fh: dom = json.load(fh)
    cells = rd(d / "cells.csv.gz")
    split = rd(d / "split-T3.csv.gz"); sweep = rd(d / "sweep-T3-F.csv.gz")
    return meta, cells, dom, split, sweep

def _grid(rows, keyname, keys, layers, prompts, what):
    """rows must hold exactly one row per (key, layer, head, prompt) of the grid."""
    need(len(rows) > 0, f"{what}: no rows")
    ids = Counter((r[keyname], SU.as_int(r["layer"], what + " layer"), SU.as_int(r["head"], what + " head"), r["prompt"]) for r in rows)
    dup = [k for k, v in ids.items() if v > 1]
    need(not dup, f"{what}: {len(dup)} duplicated cells, e.g. {dup[:3]}")
    want = {(k, l, h, p) for k in keys for l in layers for h in range(SU.N_HEADS) for p in prompts}
    have = set(ids)
    need(have == want, f"{what}: cell set differs from the expected grid: {len(want - have)} missing (e.g. {sorted(want - have)[:3]}), "
                       f"{len(have - want)} unexpected (e.g. {sorted(have - want)[:3]})")

def validate(meta, cells, dom, split, sweep, mode):
    """Raise SU.Incomplete unless the files are the complete expected cell set. Returns the coverage label."""
    layers, toks = SU.expected(mode)
    # metadata consistency
    need(isinstance(meta.get("layers"), list) and isinstance(meta.get("prompts"), list), "eval-meta.json: layers / prompts missing")
    need(len(set(meta["layers"])) == len(meta["layers"]) and len(set(meta["prompts"])) == len(meta["prompts"]), "eval-meta.json: duplicate layers or prompts")
    need(meta["prompts"] == sorted(meta["prompts"]), "eval-meta.json: prompts not in sorted order (decay_tables.py writes them sorted)")
    need(bool(meta.get("fixture")) == bool(mode["fixture"]), f"eval-meta.json fixture={meta.get('fixture')!r} but mode fixture={mode['fixture']}")
    need(meta.get("bar") == SU.BAR, f"eval-meta.json bar {meta.get('bar')!r} is not the registered bar {SU.BAR!r}")
    exp_meta = dict(set=None if mode["fixture"] else mode["set"], partial_layers=mode["partial_layers"])
    for k, v in exp_meta.items():   # written by decay_tables.py eval since the review; absent in the registered run's meta
        if k in meta: need(meta[k] == v, f"eval-meta.json {k}={meta[k]!r} but mode {k}={v!r}")
    if layers is None:   # fixture: internal consistency only
        layers = [SU.as_int(l, "eval-meta layer") for l in meta["layers"]]; prompts = list(meta["prompts"])
        need(layers and prompts, "fixture eval-meta.json names no layers or prompts")
        need(all(l in SU.DELTANET_LAYERS for l in layers), "fixture eval-meta.json names a non-DeltaNet layer")
    else:
        prompts = sorted(toks)
        need(meta["layers"] == layers, f"eval-meta.json layers {meta['layers']} are not the expected {layers}")
        need(meta["prompts"] == prompts, f"eval-meta.json prompts {meta['prompts']} are not the expected {prompts}")
    # cells
    need(len(cells) > 0 and set(cells[0]) >= {"arm", "layer", "head", "prompt", "T", "rejects", "e_tok_max", "e_tok_med", "e_cum_max"}, "cells.csv.gz: columns missing")
    need({c["arm"] for c in cells} == set(ARMS), f"cells.csv.gz: arms {sorted({c['arm'] for c in cells})} are not {list(ARMS)}")
    _grid(cells, "arm", ARMS, layers, prompts, "cells.csv.gz")
    seenT = defaultdict(set)
    for c in cells:
        T = SU.as_int(c["T"], "cells T"); r = SU.as_int(c["rejects"], "cells rejects"); seenT[c["prompt"]].add(T)
        need(T >= 1 and 0 <= r <= T, f"cells.csv.gz: T={T}, rejects={r} out of range at {c['arm']} L{c['layer']} h{c['head']} {c['prompt']}")
        need(c["arm"] == "T0" or r == 0, f"cells.csv.gz: rejects on clamping arm {c['arm']} (only T0 rejects)")
        if r == 0:
            for k in ("e_tok_max", "e_tok_med", "e_cum_max"):
                need(SU.finite(c[k]), f"cells.csv.gz: non-finite {k}={c[k]!r} in a cell without a rejected lookup ({c['arm']} L{c['layer']} h{c['head']} {c['prompt']})")
    for p, Ts in seenT.items():
        need(len(Ts) == 1, f"cells.csv.gz: prompt {p} has several token counts {sorted(Ts)}")
        if toks is not None: need(Ts == {toks[p]}, f"cells.csv.gz: prompt {p} has T={sorted(Ts)}, registered {toks[p]}")
    n_tok = sum(next(iter(seenT[p])) for p in prompts)
    # domain
    need(isinstance(dom, list) and len(dom) == len(layers) * SU.N_HEADS, f"domain.json.gz: {len(dom) if isinstance(dom, list) else '?'} rows, expected {len(layers) * SU.N_HEADS}")
    dk = Counter((x.get("layer"), x.get("head")) for x in dom)
    need(set(dk) == {(l, h) for l in layers for h in range(SU.N_HEADS)} and max(dk.values()) == 1, "domain.json.gz: (layer, head) set differs from the expected grid")
    for x in dom:
        need(x.get("n") == n_tok, f"domain.json.gz: L{x['layer']} h{x['head']} n={x.get('n')}, expected {n_tok} tokens")
        need(0 <= x["count_x_out"] <= x["n"] and 0 <= x["count_g_lt_step"] <= x["n"], f"domain.json.gz: counts out of range at L{x['layer']} h{x['head']}")
        need(all(SU.finite(v) for v in (x["A"], x["dt_bias"], x["share_x_lt_m8"], x["share_x_ge_8"], x["share_g_lt_step"], x["share_g_ge_8"], *x["x_min_med_max"], *x["g_min_med_max"])),
             f"domain.json.gz: non-finite value at L{x['layer']} h{x['head']}")
    # descriptive files
    _grid(split, "source", SU.SPLIT_SOURCES, layers, prompts, "split-T3.csv.gz")
    _grid(sweep, "F", SU.SWEEP_F, layers, prompts, "sweep-T3-F.csv.gz")
    for what, rows in (("split-T3.csv.gz", split), ("sweep-T3-F.csv.gz", sweep)):
        need(all(SU.finite(r["e_tok_max"]) and SU.finite(r["e_cum_max"]) for r in rows), f"{what}: non-finite e_tok_max / e_cum_max")
    return SU.coverage_label(mode)

def main(d, argv=()):
    mode = parse_mode(argv)
    d = Path(d); meta, cells, dom, split, sweep = load(d)
    cov = validate(meta, cells, dom, split, sweep, mode)
    S = dict(meta=meta, coverage=dict(label=cov, set=None if mode["fixture"] else mode["set"], partial_layers=mode["partial_layers"],
                                      layers=len(meta["layers"]), heads=SU.N_HEADS, prompts=len(meta["prompts"]),
                                      cells_per_arm=len(meta["layers"]) * SU.N_HEADS * len(meta["prompts"]), checked_by="suite.py + summarise.validate"),
             arms={}, domain={})
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
                              heads_with_reject=len({(c["layer"], c["head"]) for c in cs if int(c["rejects"]) > 0}),
                              cells_with_reject=sum(int(c["rejects"]) > 0 for c in cs),
                              e_tok_max_over_cells=st(et_all) if et_all else None, e_cum_max_over_cells=st(ec_all),
                              e_tok_med_over_cells=st([float(c["e_tok_med"]) for c in cs if int(c["rejects"]) == 0]) if et_all else None,
                              worst=sorted(fail, key=lambda f: -f["e_cum_max"])[:20])
    n_tot = sum(x["n"] for x in dom)
    out_x = sum(x["count_x_out"] for x in dom); low_g = sum(x["count_g_lt_step"] for x in dom)
    S["domain"] = dict(n_token_head_values=n_tot, x_out_of_domain=out_x, share_x_out=out_x / n_tot,
                       x_ge_8=int(sum(round(x["share_x_ge_8"] * x["n"]) for x in dom)), x_lt_m8=int(sum(round(x["share_x_lt_m8"] * x["n"]) for x in dom)),
                       g_below_step=low_g, share_g_below_step=low_g / n_tot,
                       heads_any_x_out=sum(x["count_x_out"] > 0 for x in dom), heads_all_x_out=sum(x["count_x_out"] == x["n"] for x in dom),
                       heads_any_g_ge_8=sum(x["share_g_ge_8"] > 0 for x in dom),
                       heads_majority_g_below_step=sum(x["share_g_lt_step"] > 0.5 for x in dom), n_heads=len(dom),
                       share_x_out_per_head=st([x["count_x_out"] / x["n"] for x in dom]),
                       share_g_low_per_head=st([x["share_g_lt_step"] for x in dom]),
                       g_median_per_head=st([x["g_min_med_max"][1] for x in dom]), x_max_per_head=st([x["x_min_med_max"][2] for x in dom]),
                       x_min_per_head=st([x["x_min_med_max"][0] for x in dom]), dt_bias=st([x["dt_bias"] for x in dom]), A=st([x["A"] for x in dom]))
    per_layer = defaultdict(lambda: [0, 0, 0, 0])
    for x in dom:
        p = per_layer[x["layer"]]; p[0] += x["count_x_out"]; p[1] += x["count_g_lt_step"]; p[2] += x["n"]; p[3] += x["count_x_out"] > 0
    S["domain"]["per_layer"] = {str(l): dict(x_out=v[0], g_low=v[1], n=v[2], heads_any_x_out=v[3]) for l, v in sorted(per_layer.items())}
    for fn, rows in (("split-T3.csv.gz", split), ("sweep-T3-F.csv.gz", sweep)):
        key = "source" if "source" in rows[0] else "F"; g = defaultdict(list)
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
    if cov != "COMPLETE":
        L.append(f"\nCoverage: {cov}" + (f", first {mode['partial_layers']} of {len(SU.DELTANET_LAYERS)} DeltaNet layers" if mode["partial_layers"] else "") + "; not a verdict on the full registered suite.")
    (d / "summary.md").write_text("\n".join(L) + "\n"); print("\n".join(L)); print(json.dumps(S["domain"], indent=1)[:3000])
    return S

if __name__ == "__main__":
    try:
        main(sys.argv[1], sys.argv[2:])
    except SU.Incomplete as e:
        print("summarise.py: REFUSED, input is not the expected cell set: " + str(e), file=sys.stderr); sys.exit(2)
