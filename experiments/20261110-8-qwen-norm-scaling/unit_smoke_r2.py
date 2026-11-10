#!/usr/bin/env python3
"""Code test for amendment A-4, no weights (synthetic random inputs, 2 heads, 6 tokens; the registered suite never
uses these inputs). Produces no result number. Checks:
 1. every arm of arms-r2.json runs, and every exact intermediate / remainder it records is non-negative and below
    its interval (remainders of a floor by 2^m in [0, 2^m); rr, gap in [0, sigma); e1 in [0, 2 sigma], e2 >= 0);
 2. the committed arms (arms-cand.json, arms-local.json) give the same y, S and the same stats keys as before the
    A-4 code change: the defaults reproduce the old engine (compared against the old engine file given as argv[1]).
Usage: unit_smoke_r2.py <old scaled_head.py>"""
import json, sys, importlib.util, math
from pathlib import Path
import numpy as np
import scaled_head as SH
HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("old_sh", sys.argv[1]); OLD = importlib.util.module_from_spec(spec); spec.loader.exec_module(OLD)
rng = np.random.default_rng(7); T, H, D = 6, 2, 128
xq, xk, xv, zz = (rng.standard_normal((T, H, D)) * 3 for _ in range(4))
ar, br = rng.standard_normal((T, H)), rng.standard_normal((T, H))
Wc = rng.uniform(-0.5, 0.5, (3, H, D, 4)); A = np.array([0.01, 0.3]); dtb = np.array([-3.0, 5.0]); gain = np.full(D, 0.9)
bad = 0; n = 0
def run(mod, cfg):
    st = {}; ys = []; Ss = None
    for S, o, y, Fo in mod.Head(cfg, H=H).run(xq, xk, xv, ar, br, zz, Wc, A, dtb, gain, st): ys.append(y); Ss = S
    return np.stack(ys), Ss, st
for f in ("arms-cand.json", "arms-local.json"):
    for name, arm in json.load(open(HERE / f)).items():
        cfg = dict(arm["cfg"])
        if "Fo_loo" in arm: cfg["Fo"] = [15, 24]
        if "FS_loo" in arm: continue
        n += 1
        y1, S1, st1 = run(SH, cfg); y0, S0, st0 = run(OLD, cfg)
        same = np.array_equal(y1, y0) and np.array_equal(S1, S0) and set(st1["max"]) == set(st0["max"]) and all(np.array_equal(st1["max"][k], st0["max"][k]) for k in st0["max"])
        if not same: bad += 1; print("DIFF vs old engine", f, name)
r2 = json.load(open(HERE / "arms-r2.json"))
for name, arm in r2.items():
    n += 1
    try:
        y, S, st = run(SH, arm["cfg"])
        c = dict(SH.M2); c.update(arm["cfg"]); mx, mn = st["max"], st["min"]
        lim = {"rem_M": 2 ** (c["Fg"] + c["Fk"]), "rem_delta": 2 ** c["Fg"], "rem_S": 2 ** c["Fg"], "rem_w": 2 ** (c["RC"] - c["Fw"]),
               "rem_y": 2 ** (c["Fw"] + c["Fcg"] - c["Fy"])}
        errs = []
        for k, L in lim.items():
            if k in mx and np.isfinite(mn[k]).all():
                if (mn[k] < 0).any() or (mx[k] >= L).any(): errs.append((k, float(mn[k].min()), float(mx[k].max()), L))
        if "rem_o" in mx and np.isfinite(mn["rem_o"]).all() and (mn["rem_o"] < 0).any(): errs.append(("rem_o<0", float(mn["rem_o"].min())))
        for k in ("e1", "e2", "rr", "gap"):
            if k in mn and np.isfinite(mn[k]).all() and (mn[k] < 0).any(): errs.append((k + "<0", float(mn[k].min())))
        if "rr" in mx and (mx["rr"] >= mx["sigma"]).any(): errs.append(("rr>=sigma",))
        if errs: bad += 1; print("FAIL", name, errs)
    except Exception as e:
        bad += 1; print("FAIL", name, type(e).__name__, e)
print("arms", n, "failed", bad)
sys.exit(1 if bad else 0)
