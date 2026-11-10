#!/usr/bin/env python3
"""Summarise runs/<file>.jsonl (scaled_head.py output) into runs/<file>.summary.json and print a markdown table.
Pass rule as PREREG: median rel_y, rel_S <= 0.01, max <= 0.05, and every class inside its stated bound on 480/480 pairs.
Usage: summarise.py <runs/file.jsonl> [arm_order_json]"""
import json, math, sys
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent
B18 = 2 ** 18

def bounds(arm):
    """Stated class bounds per candidate (PREREG): RNG cells < 2^18 (o, S, M, delta two-limb, w), public classes of DESIGN 2.
    xin < 2^31, ar/br/z < 2^20, cg < 2^24, y < 2^31. C3: o in [-2^17, 2^17) exact. C4: Sigma < 2^28 (proved, two limbs)."""
    b = dict(S=B18, M=B18, o=B18, w=B18 + 1, xin=2 ** 31, ar=2 ** 20, br=2 ** 20, z=2 ** 20, cg=2 ** 24, y=2 ** 31,
             delta=2 ** 36)  # delta two-limb: lo in [0, 2^18), |hi| < 2^18
    if arm.startswith("C3"): b["o"] = 2 ** 17 + 1
    if arm.startswith("C4"): b.pop("o"); b["Sigma"] = 2 ** 28
    if arm.startswith("C5"): b["o"] = B18
    return b

def stat(v):
    v = np.asarray(v, dtype=float)
    return dict(n=int(v.size), median=float(np.median(v)), min=float(v.min()), max=float(v.max()))

def main():
    f = Path(sys.argv[1]); rows = [json.loads(l) for l in open(f)]
    arms = []
    for r in rows:
        if r["arm"] not in arms: arms.append(r["arm"])
    out = {}
    for a in arms:
        rs = [r for r in rows if r["arm"] == a and "error" not in r]
        errs = [r for r in rows if r["arm"] == a and "error" in r]
        d = dict(n=len(rs), error_prompts=[(e["prompt"], e["error"]) for e in errs])
        if not rs: out[a] = d; continue
        d["rel_y"] = stat([r["rel_y"] for r in rs]); d["rel_S"] = stat([r["rel_S"] for r in rs])
        lay = [r["layer"] for r in rs if "layer" in r]
        d["layer_rel_y"] = stat([l["rel_y"] for l in lay]); d["layer_bf16_rel_y"] = stat([l["bf16_rel_y"] for l in lay])
        d["resid_frob"] = stat([l["resid"]["frob"] for l in lay]); d["resid_tok_max"] = max(l["resid"]["tok_max"] for l in lay)
        d["resid_tok_median"] = float(np.median([l["resid"]["tok_median"] for l in lay]))
        d["resid_bf16_frob"] = stat([l["resid_bf16"]["frob"] for l in lay]); d["resid_bf16_tok_max"] = max(l["resid_bf16"]["tok_max"] for l in lay)
        d["mixer_over_resid_frob"] = stat([l["mixer_over_resid"]["frob"] for l in lay])
        mx = {k: max(r["max"][k] for r in rs) for k in rs[0]["max"]}
        d["max"] = mx; d["bits_signed"] = {k: (int(math.ceil(math.log2(v + 1))) + 1 if v > 0 else 1) for k, v in mx.items()}
        bd = bounds(a)
        ok = [all(r["max"][k] < lim for k, lim in bd.items()) for r in rs]
        d["bounds"] = {k: v for k, v in bd.items()}
        d["pairs_in_bounds"] = int(sum(ok))
        over = {}
        for r in rs:
            for k, lim in bd.items():
                if r["max"][k] >= lim: over[k] = over.get(k, 0) + 1
        d["pairs_over_by_class"] = over
        # field checks at stated bounds are analytic (RESULTS); measured maxima of the products recorded here
        d["field_products_max"] = {k: mx[k] for k in ("aP", "aS", "kd", "oRc", "cgw", "Vx") if k in mx}
        fid = d["rel_y"]["median"] <= 0.01 and d["rel_y"]["max"] <= 0.05 and d["rel_S"]["median"] <= 0.01 and d["rel_S"]["max"] <= 0.05
        d["fidelity_pass"] = bool(fid); d["pass"] = bool(fid and d["pairs_in_bounds"] == 480 and len(errs) == 0 and d["n"] == 480)
        if any(r.get("shift_min") is not None for r in rs):
            d["shift_max"] = mx.get("shift"); d["shift_min"] = min(r["shift_min"] for r in rs if r.get("shift_min") is not None)
        d["Fo_min"] = min(r["Fo_min"] for r in rs); d["FS"] = sorted({r["FS"] for r in rs})
        out[a] = d
    (f.parent / (f.stem + ".summary.json")).write_text(json.dumps(out, indent=1) + "\n")
    print("| arm | n | rel_y median (min / max) | rel_S median (min / max) | layer rel_y median | pairs in bounds | pass |")
    print("|---|---|---|---|---|---|---|")
    for a, d in out.items():
        if not d.get("n"): print(f"| {a} | 0 | error {d['error_prompts'][:1]} | | | | |"); continue
        y, s = d["rel_y"], d["rel_S"]
        print(f"| {a} | {d['n']} | {y['median']:.4g} ({y['min']:.3g} / {y['max']:.3g}) | {s['median']:.4g} ({s['min']:.3g} / {s['max']:.3g}) | "
              f"{d['layer_rel_y']['median']:.4g} | {d['pairs_in_bounds']} / {d['n']} | {'PASS' if d['pass'] else 'fail'} |")

if __name__ == "__main__": main()
