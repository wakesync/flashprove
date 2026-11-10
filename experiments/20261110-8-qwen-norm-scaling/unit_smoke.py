#!/usr/bin/env python3
"""Code test, no weights: every arm configuration of arms-cand.json and arms-local.json on synthetic random inputs
(2 heads, 4 tokens). Catches runtime errors in the engine before a heavy slot is spent. Produces no result number.
Usage: unit_smoke.py"""
import json, sys
from pathlib import Path
import numpy as np
import scaled_head as SH
HERE = Path(__file__).resolve().parent
rng = np.random.default_rng(0); T, H, D = 4, 2, 128
xq, xk, xv, zz = (rng.standard_normal((T, H, D)) * 3 for _ in range(4))
ar, br = rng.standard_normal((T, H)), rng.standard_normal((T, H))
Wc = rng.uniform(-0.5, 0.5, (3, H, D, 4)); A = np.array([0.01, 0.3]); dtb = np.array([-3.0, 5.0]); gain = np.full(D, 0.9)
bad = 0; n = 0
for f in ("arms-cand.json", "arms-local.json"):
    for name, arm in json.load(open(HERE / f)).items():
        cfg = dict(arm["cfg"])
        if "Fo_loo" in arm: cfg["Fo"] = [15, 24]
        n += 1
        try:
            st = {}
            for S, o, y, Fo in SH.Head(cfg, H=H).run(xq, xk, xv, ar, br, zz, Wc, A, dtb, gain, st): pass
            assert np.isfinite(y).all() and np.isfinite(S).all()
        except Exception as e:
            bad += 1; print("FAIL", f, name, type(e).__name__, e)
print("arms", n, "failed", bad)
sys.exit(1 if bad else 0)
