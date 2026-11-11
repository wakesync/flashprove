#!/usr/bin/env python3
"""Write arms-q1.json, the 14 arms of PREREG.md section "Arms", for scaled_head.py (PR #74, unchanged).
Usage: make_arms_q1.py"""
import json
from pathlib import Path
HERE = Path(__file__).resolve().parent

R = dict(rnd="rhu", ornd="rhu", vrnd="rhu", shift_ornd="rhu")
G = dict(Fg=18)
U = dict(Fx=16, TAP=16, Fc=16, Fab=14, Fz=14)
PUB12 = dict(Fx=12, TAP=12, Fc=12, Fab=12, Fz=12)
C4 = dict(Fw=16, Fy=20, Fo=24, RC=56)
XB = dict(Fw=16, Fy=20, omode="shift", RC=46, Fq=20, Fcg=16, Fk=12, **G, **U, **R)

def a(**c): c["ext_stats"] = True; return dict(cfg=c)

out = {
    "C0": a(),
    "C4P": a(**C4, **G, **R, **U),
    "C4+R": a(**C4, **R),
    "C4+U": a(**C4, **U, vrnd="floor"),       # R off: the v rescale floors, as PR #74's C4+U-r2
    "C4+G": a(**C4, **G),
    "C4+RU": a(**C4, **R, **U, Fg=12),        # = PR #74's C4P-noG-r2 (Fg 12 is the M2 default, stated as there)
}
for fs in (12, 14, 16, 18, 20):
    out[f"XS{fs}"] = a(**XB, FS=fs, smin=fs - 10)
out["XS18-K16"] = a(**{**XB, "Fk": 16}, FS=18, smin=8)
out["XS18-noG"] = a(**{**XB, "Fg": 12}, FS=18, smin=8)
out["XS18-noU"] = a(**{**XB, **PUB12}, FS=18, smin=8)
(HERE / "arms-q1.json").write_text(json.dumps(out, indent=1) + "\n")
print(len(out), list(out))
