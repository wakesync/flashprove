#!/usr/bin/env python3
"""Write arms-r2.json, the arms PREREG amendment A-4 registers (fix lane after the two reviews of PR #74).
Every arm here sets ext_stats, so its rows also carry the exact intermediates (sigma, e1, e2, Rc, rr, gap) and every
floor remainder (M, delta, S', o, w, y), maxima and minima. Groups, in run order:
  r2b  : C3P, C4P, X3 exactly as committed (v by round half even, shift-path o floored). Must reproduce the committed
         rel_y / rel_S of runs/cand-stock.jsonl bit for bit; adds the missing classes for the full bounds check.
  r2   : every P arm with the registered rounding R = rhu applied to the v rescale and to the shift-path o as well
         (PREREG text: "R = rhu in M, delta, S' and o"; v = R(SiLU(c) 2^(FS - Fc))).
  abl  : bundle P taken apart on C4P (registered rounding). P = G (gates at 2^18) + R (round half up) + U (public
         stage finer). Each part alone on C4, and C4P with each part removed.
  loc  : two descriptive localisation rows: only the o floor and the S' floor round; o and S' exact (rest M2).
Usage: make_arms_r2.py"""
import json
from pathlib import Path
import scaled_head as SH
HERE = Path(__file__).resolve().parent
cand = json.load(open(HERE / "arms-cand.json"))

def arm(base, **upd):
    c = json.loads(json.dumps(cand[base])); c["cfg"].update(upd); c["cfg"]["ext_stats"] = True; return c

G = dict(Fg=18)
Rr = dict(rnd="rhu", ornd="rhu", vrnd="rhu", shift_ornd="rhu")
U = dict(Fx=16, TAP=16, Fc=16, Fab=14, Fz=14)
FLOOR = dict(rnd="floor", ornd="floor", vrnd="floor", shift_ornd="floor")
PUB12 = dict(Fx=12, TAP=12, Fc=12, Fab=12, Fz=12)

out = {}
for a in ("C3P", "C4P", "X3"):
    out[f"{a}-r2b"] = arm(a)                                       # committed rounding (defaults vrnd=rint, shift_ornd=floor)
for a in ("C1P", "C2P", "C3P", "C4P", "C3P-S14", "X1", "X2", "X3"):
    out[f"{a}-r2"] = arm(a, vrnd="rhu", shift_ornd="rhu")            # registered rounding everywhere
# ablation of P on C4P, registered rounding where R is on
out["C4+G-r2"] = arm("C4", **G)
out["C4+R-r2"] = arm("C4", **Rr)
out["C4+U-r2"] = arm("C4", **U, vrnd="floor")                      # R off: the v rescale floors, as M2's floors
out["C4P-noG-r2"] = arm("C4P", Fg=12, vrnd="rhu", shift_ornd="rhu")
out["C4P-noR-r2"] = arm("C4P", **FLOOR)
out["C4P-noU-r2"] = arm("C4P", **PUB12, vrnd="rhu", shift_ornd="rhu")
# descriptive localisation rows (M2 configuration otherwise)
ex_all = list(SH.STAGES)
out["round-o+state-r2"] = dict(cfg=dict(exact=[s for s in ex_all if s not in ("o", "state")], ext_stats=True))
out["exact-o+state-r2"] = dict(cfg=dict(exact=["o", "state"], ext_stats=True))
(HERE / "arms-r2.json").write_text(json.dumps(out, indent=1) + "\n")
print(len(out), list(out))
