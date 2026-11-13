#!/usr/bin/env python3
"""The tabulation that fixed the design constants of PREREG.md (per-head exponent range, G = 20, the -16 softplus
bound, U4's [-16, 32) domain). It reads ONLY PR #146's committed per-head table (runs/eval/domain.json.gz); no
activation array is opened. It was run before the PREREG was written, from the lane's planning directory; this is a
copy of that script with only this docstring changed, committed after the run for the record.
usage: design_inputs.py ../20261112-136-deltanet-decay/runs/eval/domain.json.gz"""
import gzip, json, sys, hashlib
import numpy as np
p = sys.argv[1]
raw = open(p, "rb").read()
print("domain.json.gz sha256", hashlib.sha256(raw).hexdigest())
d = json.loads(gzip.decompress(raw))
print("heads", len(d))
A = np.array([r["A"] for r in d]); dt = np.array([r["dt_bias"] for r in d])
xmin = np.array([r["x_min_med_max"][0] for r in d]); xmax = np.array([r["x_min_med_max"][2] for r in d])
gmed = np.array([r["g_min_med_max"][1] for r in d]); gmax = np.array([r["g_min_med_max"][2] for r in d]); gmin = np.array([r["g_min_med_max"][0] for r in d])
print("A min/max", A.min(), A.max(), "dt min/max", dt.min(), dt.max())
print("x min/max", xmin.min(), xmax.max())
print("g max", gmax.max(), "heads with g max >= 8", int((gmax >= 8).sum()), ">=16", int((gmax >= 16).sum()), "g max quantiles", np.quantile(gmax, [0.5, 0.9, 0.99, 1]).tolist())
print("g med quantiles 0,1,5,25,50,75,95,99,100 %", np.quantile(gmed, [0, .01, .05, .25, .5, .75, .95, .99, 1]).tolist())
for G in (12, 14, 16, 18, 20):
    lv = gmed * 2 ** G
    print("G", G, "heads with median g < 1 level", int((lv < 1).sum()), "< 16 levels", int((lv < 16).sum()), "< 256 levels", int((lv < 256).sum()), "512*2^-G", 512 * 2.0 ** -G)
def rne(v): return int(round(v))
eh = []
for a in A:
    e = 0
    while e < 24 and rne(2 ** (e + 1) * a) <= 4095: e += 1
    eh.append(e)
eh = np.array(eh); cA = np.array([rne(2 ** e * a) for e, a in zip(eh, A)])
print("per-head e range", int(eh.min()), int(eh.max()), "cA range", int(cA.min()), int(cA.max()), "heads with e==0", int((eh == 0).sum()), "e==24", int((eh == 24).sum()))
print("heads with x_min < -8", int((xmin < -8).sum()), "x_min < -12", int((xmin < -12).sum()), "x_min < -16", int((xmin < -16).sum()), "x_max >= 8", int((xmax >= 8).sum()), "x_max >= 32", int((xmax >= 32).sum()))
rows = np.ceil(xmax * 256) - np.floor(xmin * 256) + 1
print("per-head trimmed rows at 1/256: sum", int(rows.sum()), "max", int(rows.max()), "median", float(np.median(rows)))
big = np.argsort(-A)[:8]
for i in big: print("largeA", d[i]["layer"], d[i]["head"], "A", d[i]["A"], "dt", d[i]["dt_bias"], "x", d[i]["x_min_med_max"], "g", d[i]["g_min_med_max"])
