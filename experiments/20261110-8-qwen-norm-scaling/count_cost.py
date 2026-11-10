#!/usr/bin/env python3
"""Counted (not built) cost of each candidate lowering, per head per token, as a delta against M2 arm B of
research/operators/qwen_deltanet_m2/count_model.py (remainders as 12-bit LKP keys; RNG cells for S', M, delta, o, w).
Counting rules are count_model.py's: an exact quantity of b bits costs ceil(b / 12) keys; an RNG cell costs 1 range
cell; a product gate costs 1 column; a one-hot selector bit costs 1 column (booleanity is a gate); relations are
counted at 1 per new floor / tie / selector sum. Term counts are not given (count_model.py's norm term counts are
provisional, review of #66). Also writes the T = 16 head totals using count_model.summary('B', T=16, o_witness=True,
norm=True) as the base.

Usage: count_cost.py [runs/<cand>.summary.json]   (optional: reads the measured shift range for C3, Fo for C2)"""
import json, math, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "research/operators/qwen_deltanet_m2"))
import count_model as CM

D = 128
K = lambda b: max(1, math.ceil(b / 12)) if b > 0 else 0

def norm_cost(Uo, Fo_rem_bits, RC, Fw, Fy, eps_scale_extra=0):
    """Gated-norm cost per head per token for an o class |o| < 2^Uo, o floor remainder bits, reciprocal shift RC."""
    Vx_b = 2 * Uo + 7
    sig_b = math.ceil(Vx_b / 2) + 1
    e_b = sig_b + 1
    rc_b = RC
    keys = K(sig_b) + 2 * K(e_b) + K(rc_b) + 2 * K(sig_b)          # sigma, e1, e2, Rc, rr, gap
    keys += D * (K(RC - Fw) + K(Fw + 12 - Fy) + K(Fo_rem_bits))     # w remainder, y remainder, o remainder
    cols = 2 + 2 * D                                                 # sigma^2, Rc sigma; o*o, o*Rc
    rcells = D * 2                                                   # o and w
    rels = 6 + 2 * 2 + 2 * D + D * (2 + 2 + 1)                       # scalar relations, ties; per j o ties, w and y floors, o floor
    field = dict(Vx=Vx_b, oRc=RC + 1, cgw=24 + Fw + 1)
    return dict(keys=keys, cols=cols, rcells=rcells, rels=rels, field_bits=field)

def main():
    base = norm_cost(18, 12, 36, 12, 12)  # M2 (Uo = 18 honest class; remainder of o at 2^F = 12 bits)
    C = {}
    C["C0"] = dict(base)
    C["C1"] = norm_cost(18, 24 - 15, 46, 16, 20)
    C["C2"] = norm_cost(18, 12, 46, 16, 20)    # worst case: a head with Fo = 12 still has a 12-bit o remainder; Fo = 24 heads have none
    c3 = norm_cost(18, 12, 46, 16, 20)
    # shift witness: public table (s, 2^s, eps_s) one key per token; 2^s x o gate per j (o' = 2^s o + r); remainder r in [0, 2^s): two keys
    # per j (r and 2^s - 1 - r, both < 2^12, since s <= 12 is required); tight o class [-2^17, 2^17): o + 2^17 as 18-bit exact (2 keys) instead
    # of the RNG cell; one-hot selector over j (128 boolean columns, 1 sum relation), selected value gate (128 columns), outside [-2^16, 2^16):
    # |o*| - 2^16 as a 17-bit exact with a sign bit (2 keys + 1 column).
    c3["keys"] += 1 + D * (2 + 2) + 2 - D * 1            # minus the plain 12-bit o remainder key (replaced by the two r keys)
    c3["cols"] += D + D + D + 1
    c3["rcells"] -= D
    c3["rels"] += D * 2 + 1 + 2 + 2
    C["C3"] = c3
    c4 = norm_cost(28, 0, 56, 16, 20)
    c4["keys"] += D * 3                                   # Sigma as exact limbs: lo 18 bits (2 keys) + signed hi 10 bits (1 key)
    c4["rcells"] -= D                                     # no o RNG cell
    c4["rels"] += D                                       # Sigma = lo + 2^18 hi
    C["C4"] = c4
    C["C5"] = dict(base)                                  # same lowering, different public constant (eps x 128, q_hat scale)
    # P (state side): public-stage scales change only verifier work and coefficient sizes; rounding mode rhu adds a public
    # constant to each floor relation (no new cell). Gates a, beta at 2^18 instead of 2^12: the a P floor remainder is 2^(Fg + Fk) =
    # 2^30 instead of 2^24 (M), delta remainder 2^18 instead of 2^12, S' remainder 2^18 instead of 2^12: +1 key each per cell / column.
    Pd = dict(keys=D * D * 1 + D * 1 + D * 1, cols=0, rcells=0, rels=0)
    for k in ("C1", "C2", "C3", "C4"):
        C[k + "P"] = {kk: (C[k][kk] + Pd[kk]) if kk in Pd else C[k][kk] for kk in C[k]}
    out = {}
    for k, v in C.items():
        out[k] = dict(per_head_token=dict(keys=v["keys"], cols=v["cols"], rcells=v["rcells"], rels=v["rels"]),
                      delta_vs_M2=dict(keys=v["keys"] - base["keys"], cols=v["cols"] - base["cols"], rcells=v["rcells"] - base["rcells"],
                                       rels=v["rels"] - base["rels"]),
                      field_bits=v["field_bits"])
    m2 = CM.summary("B", T=16, o_witness=True, norm=True)
    T = 16
    for k, v in out.items():
        d = v["delta_vs_M2"]
        tot = dict(gate_columns=m2["gate_columns"] + T * d["cols"], range_cells=m2["range_cells"] + T * d["rcells"],
                   lkp_keys=m2["lkp_keys"] + T * d["keys"], relations=m2["relations"] + T * d["rels"])
        v["T16_head_totals"] = tot
        v["T16_entries"] = tot["gate_columns"] + tot["range_cells"] + tot["lkp_keys"]
    out["_M2_base_T16"] = {k: m2[k] for k in ("gate_columns", "range_cells", "lkp_keys", "relations", "log_length")}
    out["_note"] = "COUNTED, NOT BUILT. Deltas are per head per token against M2 arm B by count_model.py's rules; T16 totals add 16 x delta to count_model.summary('B', T=16, o_witness=True, norm=True). Term counts omitted (provisional in #66)."
    (HERE / "runs" / "cost.json").write_text(json.dumps(out, indent=1) + "\n")
    print("| arm | keys | cols | range cells | relations | delta keys | delta cols | delta cells | T16 entries |")
    print("|---|---|---|---|---|---|---|---|---|")
    for k, v in out.items():
        if k.startswith("_"): continue
        p, d = v["per_head_token"], v["delta_vs_M2"]
        print(f"| {k} | {p['keys']} | {p['cols']} | {p['rcells']} | {p['rels']} | {d['keys']:+d} | {d['cols']:+d} | {d['rcells']:+d} | {v['T16_entries']:,} |")
    print(out["_M2_base_T16"])

if __name__ == "__main__": main()
