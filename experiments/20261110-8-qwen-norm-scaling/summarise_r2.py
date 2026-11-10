#!/usr/bin/env python3
"""PREREG amendment A-4: summary of runs/r2/r2-stock.jsonl with the full bounds predicate.
Every row of an r2 arm carries the maxima of every class and of every exact intermediate and remainder, and their
minima (`min_ext`). For each arm this reports, per class, the number of pairs over:
  (a) the stated honest class of the arm (summarise.bounds, unchanged), and
  (b) the limb budget runs/cost.json counted for each exact quantity (count_cost.py: b bits = ceil(b / 12) keys,
      so a value fits if it is below 2^(12 ceil(b / 12))), plus the tight width b itself, and
  (c) non-negativity and the interval of every remainder (floor by 2^m: [0, 2^m); rr, gap: [0, sigma)).
A pair is "in the full counted bounds" only if (a), (b) and (c) all hold. Field-product maxima are listed; the
soundness-bound question is answered by reviewer_constructions.py, not here.
Also compares the -r2b arms with the committed rows of runs/cand-stock.jsonl (rel_y, rel_S, every committed max field).
Usage: summarise_r2.py runs/r2/r2-stock.jsonl"""
import json, math, sys
from pathlib import Path
import numpy as np
import summarise as S0
HERE = Path(__file__).resolve().parent
K12 = lambda b: 12 * math.ceil(b / 12)

def counted_widths(arm):
    """Tight widths b (bits) that count_cost.py assumed for each exact quantity of this arm, by its own formulas."""
    base = arm.split("-r2")[0].split("+")[0]
    if base.startswith("round") or base.startswith("exact"):   # localisation rows: M2 norm at Fo = 12 (count_model.py widths)
        return dict(sigma=24, e1=24, e2=24, Rc=36, rr=24, gap=24)
    c4 = base.startswith("C4"); x = base.startswith("X")
    Uo = 28 if c4 else 18
    sig_b = math.ceil((2 * Uo + 7) / 2) + 1
    RC = 56 if c4 else (36 if base == "C0" else 46)
    return dict(sigma=sig_b, e1=sig_b + 1, e2=sig_b + 1, Rc=RC, rr=sig_b, gap=sig_b)

def stat(v):
    v = np.asarray(v, dtype=float); return dict(n=int(v.size), median=float(np.median(v)), min=float(v.min()), max=float(v.max()))

def main():
    f = Path(sys.argv[1]); rows = [json.loads(l) for l in open(f)]
    arms = []
    for r in rows:
        if r["arm"] not in arms: arms.append(r["arm"])
    cfgs = json.load(open(HERE / "arms-r2.json"))
    out = {}
    for a in arms:
        rs = [r for r in rows if r["arm"] == a and "error" not in r]
        errs = [r for r in rows if r["arm"] == a and "error" in r]
        d = dict(n=len(rs), error_prompts=[(e["prompt"], e["error"]) for e in errs])
        if not rs: out[a] = d; continue
        d["rel_y"] = stat([r["rel_y"] for r in rs]); d["rel_S"] = stat([r["rel_S"] for r in rs])
        lay = [r["layer"] for r in rs if "layer" in r]
        d["layer_rel_y"] = stat([l["rel_y"] for l in lay]); d["resid_frob"] = stat([l["resid"]["frob"] for l in lay])
        d["resid_tok_max"] = max(l["resid"]["tok_max"] for l in lay)
        d["pairs_rel_y_le_0.05"] = int(sum(r["rel_y"] <= 0.05 for r in rs))
        mx = {k: max(r["max"][k] for r in rs) for k in rs[0]["max"]}; d["max"] = mx
        base = a.split("-r2")[0]
        stated = S0.bounds(base if not base.startswith("C4+") else "C4")
        over_a = {k: int(sum(r["max"][k] >= lim for r in rs)) for k, lim in stated.items()}
        cw = counted_widths(a) if any(k in rs[0]["max"] for k in ("e1",)) else {}
        over_b_alloc = {k: int(sum(r["max"].get(k, 0) >= 2 ** K12(b) for r in rs)) for k, b in cw.items() if k in rs[0]["max"]}
        over_b_tight = {k: int(sum(r["max"].get(k, 0) >= 2 ** b for r in rs)) for k, b in cw.items() if k in rs[0]["max"]}
        c = dict(cfgs[a]["cfg"]); full = {**dict(Fx=12, Fab=12, Fz=12, Fc=12, TAP=12, FS=12, Fk=12, Fq=12, Fg=12, Fw=12, Fy=12, Fcg=12, RC=36), **c}
        remlim = {"rem_M": 2 ** (full["Fg"] + full["Fk"]), "rem_delta": 2 ** full["Fg"], "rem_S": 2 ** full["Fg"],
                  "rem_w": 2 ** (full["RC"] - full["Fw"]), "rem_y": 2 ** (full["Fw"] + full["Fcg"] - full["Fy"])}
        over_c = {}
        for r in rs:
            m = r.get("min_ext", {})
            for k, L in remlim.items():
                if k in r["max"] and (r["max"][k] >= L or (m.get(k) is not None and m[k] < 0)): over_c[k] = over_c.get(k, 0) + 1
            for k in ("e1", "e2", "rr", "gap", "rem_o"):
                if m.get(k) is not None and m[k] < 0: over_c[k + "<0"] = over_c.get(k + "<0", 0) + 1
            if "rr" in r["max"] and r["max"]["rr"] >= r["max"]["sigma"]: over_c["rr>=sigma"] = over_c.get("rr>=sigma", 0) + 1
        ok_a = [all(r["max"][k] < lim for k, lim in stated.items()) for r in rs]
        ok_b = [all(r["max"].get(k, 0) < 2 ** K12(b) for k, b in cw.items()) for r in rs]
        ok_c = [all(r["max"].get(k, 0) < L for k, L in remlim.items() if k in r["max"]) and all((v is None or v >= 0) for v in r.get("min_ext", {}).values()) for r in rs]
        d["stated_class_bounds"] = stated; d["counted_widths_bits"] = cw
        d["pairs_over_stated_class"] = {k: v for k, v in over_a.items() if v}
        d["pairs_over_counted_limbs"] = {k: v for k, v in over_b_alloc.items() if v}
        d["pairs_over_counted_tight_width"] = {k: v for k, v in over_b_tight.items() if v}
        d["pairs_remainder_interval_fail"] = over_c
        d["pairs_in_stated_classes"] = int(sum(ok_a))
        d["pairs_in_full_counted_bounds"] = int(sum(x and y and z for x, y, z in zip(ok_a, ok_b, ok_c)))
        d["pairs_over_counted_limbs_any_of_e1_e2"] = int(sum((r["max"].get("e1", 0) >= 2 ** K12(cw["e1"])) or (r["max"].get("e2", 0) >= 2 ** K12(cw["e2"])) for r in rs)) if cw else None
        d["field_products_max_log2"] = {k: (round(math.log2(mx[k]), 2) if mx.get(k) else None) for k in ("aP", "aS", "kd", "oRc", "cgw", "Vx")}
        fid = d["rel_y"]["median"] <= 0.01 and d["rel_y"]["max"] <= 0.05 and d["rel_S"]["median"] <= 0.01 and d["rel_S"]["max"] <= 0.05
        d["fidelity_pass"] = bool(fid)
        if "shift" in mx: d["shift_max"] = mx["shift"]
        out[a] = d
    # -r2b reproduction check against committed rows
    com = {}
    for l in open(HERE / "runs" / "cand-stock.jsonl"):
        r = json.loads(l)
        if "error" not in r: com[(r["arm"], r["prompt"], r["head"])] = r
    repro = {}
    for a in arms:
        if not a.endswith("-r2b"): continue
        b = a[:-4]; same = 0; tot = 0; diff = []
        for r in rows:
            if r["arm"] != a or "error" in r: continue
            tot += 1; c = com.get((b, r["prompt"], r["head"]))
            ok = c is not None and c["rel_y"] == r["rel_y"] and c["rel_S"] == r["rel_S"] and all(c["max"][k] == r["max"][k] for k in c["max"])
            if ok: same += 1
            elif len(diff) < 3: diff.append((r["prompt"], r["head"]))
        repro[a] = dict(rows=tot, identical_to_committed=same, first_diffs=diff)
    out["_r2b_vs_committed"] = repro
    (f.parent / (f.stem + ".summary.json")).write_text(json.dumps(out, indent=1) + "\n")
    print("| arm | n | rel_y median (min / max) | rel_S median (max) | layer rel_y | in stated classes | in full counted bounds | over counted limbs |")
    print("|---|---|---|---|---|---|---|---|")
    for a, d in out.items():
        if a.startswith("_") or not d.get("n"): continue
        y, s = d["rel_y"], d["rel_S"]
        print(f"| {a} | {d['n']} | {y['median']:.4g} ({y['min']:.3g} / {y['max']:.3g}) | {s['median']:.4g} ({s['max']:.3g}) | {d['layer_rel_y']['median']:.4g} | "
              f"{d['pairs_in_stated_classes']} | {d['pairs_in_full_counted_bounds']} | {d['pairs_over_counted_limbs']} |")
    print(json.dumps(repro))

if __name__ == "__main__": main()
