#!/usr/bin/env python3
"""Write arms-local.json (localisation) and arms-cand.json (registered candidates), exactly as PREREG.md fixes them."""
import json
from pathlib import Path
import scaled_head as SH
HERE = Path(__file__).resolve().parent

loc = {"C0": dict(cfg={}), "all_exact": dict(cfg=dict(exact=list(SH.STAGES)))}
for s in SH.STAGES:
    loc[f"exact1-{s}"] = dict(cfg=dict(exact=[s]))
    loc[f"round1-{s}"] = dict(cfg=dict(exact=[x for x in SH.STAGES if x != s]))
groups = dict(public=["in_qkv", "in_ab", "in_z", "conv", "silu", "l2n", "gates"], state=["mem", "delta", "state"],
              output=["o", "sigma", "rc", "w", "cg", "y"])
for g, st in groups.items():
    loc[f"exactG-{g}"] = dict(cfg=dict(exact=st))
    loc[f"roundG-{g}"] = dict(cfg=dict(exact=[x for x in SH.STAGES if x not in st]))

NORM = dict(Fw=16, Fy=20)
P = dict(Fx=16, TAP=16, Fc=16, Fab=14, Fz=14, Fg=18, rnd="rhu", ornd="rhu")
cand = {
    "C0": dict(cfg={}),
    "C1": dict(cfg=dict(NORM, Fo=15, RC=18 + 16 + 12)),
    "C2": dict(cfg=dict(NORM, RC=18 + 16 + 12), Fo_loo=dict(cap=24)),
    "C3": dict(cfg=dict(NORM, omode="shift", RC=18 + 16 + 12)),
    "C4": dict(cfg=dict(NORM, Fo=24, RC=28 + 16 + 12)),
    "C5": dict(cfg=dict(q_unscaled=True)),
}
for k in ("C1", "C2", "C3", "C4"):
    c = json.loads(json.dumps(cand[k])); c["cfg"].update(P)
    if k == "C1": c["cfg"]["ornd"] = "rhu"
    cand[k + "P"] = c
c = json.loads(json.dumps(cand["C3P"])); c["cfg"]["FS"] = 14; c["cfg"]["Fk"] = 14; c["cfg"]["Fq"] = 14
cand["C3P-S14"] = c
(HERE / "arms-local.json").write_text(json.dumps(loc, indent=1) + "\n")
(HERE / "arms-cand.json").write_text(json.dumps(cand, indent=1) + "\n")
print(len(loc), len(cand))
