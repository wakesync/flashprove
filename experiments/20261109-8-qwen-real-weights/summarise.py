#!/usr/bin/env python3
"""Summarise runs/real-*.jsonl into runs/summary.json (and print markdown-ready tables).
Thresholds as registered in PREREG.md. Usage: summarise.py"""
import json, math
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent
R = HERE / "runs"
BOUND = 1 << 18
RNG = ("S", "M", "delta_lo", "delta_hi", "o", "w")
PUB = dict(xin=2 ** 31, ar=2 ** 20, br=2 ** 20, z=2 ** 20, y=2 ** 31, cg=2 ** 24, v=2 ** 31)
EXACT = dict(sigma=2 ** 24, e1=2 ** 24, e2=2 ** 24, rr=2 ** 24, gap=2 ** 24)   # DESIGN 4.4 / head_reference fit; Rc < 2^(3F)

def load(name):
    p = R / name
    return [json.loads(l) for l in open(p)] if p.exists() else []

def stat(x):
    x = np.asarray(x, dtype=float)
    return dict(n=int(x.size), median=float(np.median(x)), min=float(x.min()), max=float(x.max()))

def arm(rows, F):
    rs = [r for r in rows if r["F"] == F and "error" not in r]
    errs = [r for r in rows if r["F"] == F and "error" in r]
    if not rs: return dict(n=0, errors=len(errs))
    prompts = sorted({r["prompt"] for r in rs})
    out = dict(n=len(rs), errors=len(errs), error_list=[(e["prompt"], e["error"]) for e in errs])
    for k in ("rel_S", "max_S", "rel_o", "max_o", "rel_y", "max_y", "norm_only_rel_y", "bf16_rel_y", "bf16_rel_o", "bf16_rel_S", "o_rms_int_median"):
        out[k] = stat([r[k] for r in rs])
    lay = [r["layer"] for r in rs if "layer" in r]
    if lay:
        out["layer_level"] = {k: stat([l[k] for l in lay]) for k in lay[0]}
        out["layer_level_per_prompt"] = {r["prompt"]: r["layer"] for r in rs if "layer" in r}
    worst = max(rs, key=lambda r: r["rel_S"]); out["worst_rel_S"] = dict(prompt=worst["prompt"], head=worst["head"], rel_S=worst["rel_S"],
                                                                         S_f_absmax=worst["S_f_absmax"], max_S=worst["max_S"])
    worst = max(rs, key=lambda r: r["rel_y"]); out["worst_rel_y"] = dict(prompt=worst["prompt"], head=worst["head"], rel_y=worst["rel_y"],
                                                                         o_rms_int_median=worst["o_rms_int_median"], y_f_absmax=worst["y_f_absmax"])
    out["per_prompt"] = {}
    for p in prompts:
        pr = [r for r in rs if r["prompt"] == p]
        d = dict(T=pr[0]["T"], heads=len(pr))
        for k in ("rel_S", "max_S", "rel_o", "rel_y", "max_y", "norm_only_rel_y", "bf16_rel_y"):
            v = np.array([r[k] for r in pr]); d[k] = dict(typical=float(np.median(v)), worst=float(v.max()))
        d["max"] = {c: max(r["max"][c] for r in pr) for c in pr[0]["max"]}
        d["min_exact"] = {c: min(r["min_exact"][c] for r in pr) for c in pr[0]["min_exact"]}
        out["per_prompt"][p] = d
    # ranges
    mx = {c: max(r["max"][c] for r in rs) for c in rs[0]["max"]}
    mn = {c: min(r["min_exact"][c] for r in rs) for c in rs[0]["min_exact"]}
    out["max"] = mx; out["min_exact"] = mn
    out["bits_signed"] = {c: int(math.ceil(math.log2(v + 1))) + 1 for c, v in mx.items()}
    rc_lim = 2 ** (3 * F)
    def pair_ok(r):
        rng = all(r["max"][c] < BOUND for c in RNG)
        ex = all(r["min_exact"][c] >= 0 for c in r["min_exact"]) and all(r["max"][c] < lim for c, lim in EXACT.items()) and r["max"]["Rc"] < rc_lim
        pub = all(r["max"][c] < lim for c, lim in PUB.items())
        return rng, ex, pub
    oks = [pair_ok(r) for r in rs]
    out["pairs_rng_ok"] = sum(o[0] for o in oks); out["pairs_exact_ok"] = sum(o[1] for o in oks); out["pairs_public_ok"] = sum(o[2] for o in oks)
    out["pairs_all_ok"] = sum(all(o) for o in oks)
    out["rng_fail_classes"] = sorted({c for r in rs for c in RNG if r["max"][c] >= BOUND})
    out["public_fail_classes"] = sorted({c for r in rs for c, lim in PUB.items() if r["max"][c] >= lim})
    out["exact_fail_classes"] = sorted({c for r in rs for c, lim in EXACT.items() if r["max"][c] >= lim} |
                                       {c for r in rs for c in r["min_exact"] if r["min_exact"][c] < 0} |
                                       ({"Rc"} if any(r["max"]["Rc"] >= rc_lim for r in rs) else set()))
    out["delta_unsplit_pairs_over"] = sum(r["max"]["delta"] >= BOUND for r in rs)
    out["S_over_by_prompt"] = sorted({r["prompt"] for r in rs if r["max"]["S"] >= BOUND})
    # A2 sufficiency
    ry = np.array([r["rel_y"] for r in rs]); rS = np.array([r["rel_S"] for r in rs])
    out["A2_sufficient"] = bool(np.median(ry) <= 1e-2 and ry.max() <= 5e-2 and np.median(rS) <= 1e-2 and rS.max() <= 5e-2)
    out["A2_parts"] = dict(rel_y_median_ok=bool(np.median(ry) <= 1e-2), rel_y_max_ok=bool(ry.max() <= 5e-2),
                           rel_S_median_ok=bool(np.median(rS) <= 1e-2), rel_S_max_ok=bool(rS.max() <= 5e-2))
    return out

def same_outputs(a, b):
    """Are stock and abl rows identical (all numbers)? Layer 0 tensors are byte-identical, so they must be."""
    key = lambda r: (r["prompt"], r["F"], r.get("head", -1))
    da = {key(r): r for r in a}; db = {key(r): r for r in b}
    if set(da) != set(db): return False, "row sets differ"
    strip = lambda r: {k: v for k, v in r.items() if k != "ckpt"}
    nd = sum(strip(da[k]) != strip(db[k]) for k in da)
    return nd == 0, f"{nd} of {len(da)} rows differ"

def main():
    S = dict(arms={})
    for tag, fn, Fs in (("registered", "real-{}.jsonl", (12, 14, 16)), ("tap_eq_F", "real-{}-tapF.jsonl", (12, 16)),
                        ("q_unscaled", "real-{}-qunscaled.jsonl", (12, 16))):
        for ck in ("stock", "abl"):
            rows = load(fn.format(ck))
            if not rows: continue
            S["arms"][f"{tag}/{ck}"] = {str(F): arm(rows, F) for F in Fs}
        a, b = load(fn.format("stock")), load(fn.format("abl"))
        if a and b: S["arms"][f"{tag}/identical_stock_abl"] = same_outputs(a, b)
    reg = S["arms"].get("registered/stock", {})
    S["needed_F"] = next((F for F in ("12", "14", "16") if reg.get(F, {}).get("A2_sufficient")), None)
    S["A1_F12"] = {ck: dict(pairs_all_ok=S["arms"][f"registered/{ck}"]["12"]["pairs_all_ok"], n=S["arms"][f"registered/{ck}"]["12"]["n"])
                   for ck in ("stock", "abl") if f"registered/{ck}" in S["arms"]}
    (R / "summary.json").write_text(json.dumps(S, indent=1) + "\n")
    for name, a in S["arms"].items():
        if not isinstance(a, dict): print(name, a); continue
        for F, x in a.items():
            if not x.get("n"): continue
            print(f"## {name} F={F}: n={x['n']} err={x['errors']} pairs ok rng {x['pairs_rng_ok']} exact {x['pairs_exact_ok']} public {x['pairs_public_ok']} all {x['pairs_all_ok']}; "
                  f"fails rng {x['rng_fail_classes']} pub {x['public_fail_classes']} exact {x['exact_fail_classes']}; A2 {x['A2_sufficient']} {x['A2_parts']}")
            for k in ("rel_S", "rel_o", "rel_y", "norm_only_rel_y", "bf16_rel_y", "max_S", "max_y", "o_rms_int_median"):
                s = x[k]; print(f"   {k}: median {s['median']:.3g} min {s['min']:.3g} max {s['max']:.3g}")
            for k, s in x.get("layer_level", {}).items(): print(f"   LAYER {k}: median {s['median']:.3g} min {s['min']:.3g} max {s['max']:.3g} (n={s['n']} prompts)")
            print("   worst S", x["worst_rel_S"], "worst y", x["worst_rel_y"])
            print("   max:", {c: x["max"][c] for c in ("S", "M", "delta", "delta_lo", "delta_hi", "o", "w", "v", "xin", "ar", "br", "z", "y", "cg", "sigma", "Rc")})
            print("   min_exact:", x["min_exact"], "delta unsplit over:", x["delta_unsplit_pairs_over"])
    print("needed_F", S["needed_F"], "A1", S["A1_F12"])

if __name__ == "__main__": main()
