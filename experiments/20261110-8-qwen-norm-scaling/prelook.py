#!/usr/bin/env python3
"""Pre-registration look at PR #68's COMMITTED run rows only (no fetch, no new run). Disclosed in PREREG."""
import json, sys, math
import numpy as np
p = sys.argv[1]
rows = [json.loads(l) for l in open(p)]
r12 = [r for r in rows if r["F"] == 12 and "error" not in r]
print("n F12", len(r12))
def col(k): return np.array([r[k] for r in r12], dtype=float)
def mx(k): return np.array([r["max"][k] for r in r12], dtype=float)
for k in ("rel_S", "rel_o", "rel_y", "norm_only_rel_y", "o_rms_int_median", "o_rms_int_min", "S_f_absmax", "y_f_absmax", "max_S"):
    v = col(k); print(k, "median %.4g min %.4g max %.4g  p10 %.4g p90 %.4g" % (np.median(v), v.min(), v.max(), np.percentile(v, 10), np.percentile(v, 90)))
for k in ("S", "M", "delta", "o", "v", "k_hat", "q_hat", "xin", "ar", "br", "z", "cg", "y", "sigma", "Vx"):
    v = mx(k); print("max", k, "median %.5g min %.5g max %.5g" % (np.median(v), v.min(), v.max()))
# per head across prompts: max S, max o, o rms
H = 48
byh = {h: [r for r in r12 if r["head"] == h] for h in range(H)}
print("head  maxS  maxM  maxv  maxo  o_rms_med(min..max over prompts)  rel_S(max) rel_y(med)")
for h in range(H):
    rs = byh[h]
    print(h, max(r["max"]["S"] for r in rs), max(r["max"]["M"] for r in rs), max(r["max"]["v"] for r in rs), max(r["max"]["o"] for r in rs),
          "%.3g..%.3g" % (min(r["o_rms_int_median"] for r in rs), max(r["o_rms_int_median"] for r in rs)),
          "%.3g" % max(r["rel_S"] for r in rs), "%.3g" % np.median([r["rel_y"] for r in rs]))
# correlation of rel_y with o rms and S max
print("corr log rel_y vs log o_rms", np.corrcoef(np.log(col("rel_y")), np.log(col("o_rms_int_median") + 1e-9))[0, 1])
print("corr log rel_S vs T", np.corrcoef(np.log(col("rel_S")), np.log(col("T")))[0, 1])
# worst rel_S pairs
for r in sorted(r12, key=lambda r: -r["rel_S"])[:8]:
    print("worst rel_S", r["prompt"], r["head"], "%.3g" % r["rel_S"], "S_f_absmax %.3g" % r["S_f_absmax"], "maxS", r["max"]["S"], "T", r["T"])
for r in sorted(r12, key=lambda r: -r["rel_y"])[:8]:
    print("worst rel_y", r["prompt"], r["head"], "%.3g" % r["rel_y"], "o_rms_med %.3g" % r["o_rms_int_median"], "y_f_absmax %.3g" % r["y_f_absmax"], "maxS", r["max"]["S"])
r16 = [r for r in rows if r["F"] == 16 and "error" not in r]
for r in sorted(r16, key=lambda r: -r["rel_y"])[:6]:
    print("F16 worst rel_y", r["prompt"], r["head"], "%.3g" % r["rel_y"], "o_rms_med %.3g" % r["o_rms_int_median"], "norm_only %.3g" % r["norm_only_rel_y"], "rel_o %.3g" % r["rel_o"], "rel_S %.3g" % r["rel_S"])
v = np.array([r["norm_only_rel_y"] for r in r16]); print("F16 norm-only max", v.max(), "median", np.median(v))
v = np.array([r["bf16_rel_y"] for r in r12]); print("bf16 rel_y per pair median", np.median(v), "max", v.max())
v = np.array([r["bf16_rel_S"] for r in r12]); print("bf16 rel_S per pair median", np.median(v), "max", v.max())
