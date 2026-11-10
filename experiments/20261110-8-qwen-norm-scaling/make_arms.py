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
              output=["o", "sigma", "rc", "w", "cg", "y"],
              # amendment A-2: the o floor and the norm proper as separate groups, and everything upstream of o as one group
              norm=["sigma", "rc", "w", "cg", "y"],
              upstream=["in_qkv", "in_ab", "in_z", "conv", "silu", "l2n", "gates", "mem", "delta", "state"])
for g, st in groups.items():
    loc[f"exactG-{g}"] = dict(cfg=dict(exact=st))
    loc[f"roundG-{g}"] = dict(cfg=dict(exact=[x for x in SH.STAGES if x not in st]))

# amendment A-2: o rounded to nearest (not floored) with everything else exact, the PR #68 reviewer's "o rounding plus an exact norm"
loc["round1-o-rhu"] = dict(cfg=dict(exact=[x for x in SH.STAGES if x != "o"], ornd="rhu"))

# Run order (the run is arm-major and may be cut off at the time box): baseline and all-exact, then the grouped arms, then the
# o rows, then the remaining single-stage arms.
first = ["C0", "all_exact"] + [f"{a}-{g}" for g in ("upstream", "o", "norm", "output", "public", "state") for a in ("roundG", "exactG")
                              if f"{a}-{g}" in loc] + ["round1-o", "round1-o-rhu", "exact1-o"]
loc = {k: loc[k] for k in first + [k for k in loc if k not in first]}

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
# Post-registration arms, PREREG amendment A-2 (declared before any registered candidate run; after a 2-prompt smoke test).
# Nested, so each step isolates one change on top of C3P: X1 finer q_hat only; X2 = X1 + finer cg; X3 = X2 + finer state.
XB = dict(NORM, **P, omode="shift", RC=18 + 16 + 12)
cand["X1"] = dict(cfg=dict(XB, FS=12, Fk=12, Fq=20, smin=2))             # q_hat at 2^20; Sigma at 2^32, Fo <= 30; S, M classes as M2
cand["X2"] = dict(cfg=dict(XB, FS=12, Fk=12, Fq=20, smin=2, Fcg=16))     # + cg at 2^16 (class |cg| < 2^24 kept)
cand["X3"] = dict(cfg=dict(XB, FS=18, Fk=12, Fq=20, smin=8, Fcg=16))     # + state at 2^18 (S', M two-limb); Sigma at 2^38
# Descriptive replication of the PR #68 reviewer's split-scale arm: state at F = 12, o and the whole norm at 2^15.
cand["D-R15"] = dict(cfg=dict(Fo=15, Fz=15, Fcg=15, Fw=15, Fy=15, RC=45))
(HERE / "arms-local.json").write_text(json.dumps(loc, indent=1) + "\n")
(HERE / "arms-cand.json").write_text(json.dumps(cand, indent=1) + "\n")
print(len(loc), len(cand))
