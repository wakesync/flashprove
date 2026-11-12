#!/usr/bin/env python3
"""Arm W cost, COUNTED from the existing bound ledger, not built and not measured (PREREG "Arm W cost").

Imports research/operators/qwen_m3/bounds.py unchanged and re-sums, with bounds.py's own `row` function and
constants, the two no-wrap rows that contain the public norm class A (in_proj and M3a-MLP gate / up) at
A = 2,047 (registered in the design), 2^15 - 1, 2^17 - 1, 2^18 - 1. Also counts the 12-bit lookup keys a
committed cell of each class would need, by the pattern bounds.py already uses for a class wider than 12 bits
(its dt_bias rows: value + 2^b = lo + 2^12 hi, lo one 12-bit key, hi one key plus one complement key).
Records no activation. usage: ledger_w.py <out.json>
"""
import json, math, sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "research/operators/qwen_m3"))
import bounds as B       # unchanged


def keys_for(bits):
    """12-bit keys for an exact signed class of `bits` bits: one key if it fits 12 bits; else ceil(bits / 12) limb
    keys plus one complement key when the top limb is narrower than 12 bits (bounds.py dt_bias pattern)."""
    if bits <= 12: return dict(limb_keys=1, complement_keys=0, total=1, relations=1)
    limbs = math.ceil(bits / 12); comp = 0 if bits % 12 == 0 else 1
    return dict(limb_keys=limbs, complement_keys=comp, total=limbs + comp, relations=1 + comp)


out = dict(note="counted on class edges from bounds.py (unchanged), not built, not measured; no activation is read",
           bounds_py_constants=dict(DIN=B.DIN, W=B.W, RNG=B.RNG, S_MAX=B.S_MAX, A_PUB=B.A_PUB, F_MLP=B.F_MLP), classes=[])
for label, A in (("2,047 (design, A_PUB)", B.A_PUB), ("2^15 - 1", 2 ** 15 - 1), ("2^17 - 1", 2 ** 17 - 1), ("2^18 - 1", 2 ** 18 - 1)):
    r_in = B.row("in_proj: sum_k a_k W_kj - 2^s x_j - r_j", [B.DIN * A * B.W, 2 ** B.S_MAX * B.RNG, B.R_S], "a: class A", "")
    r_mlp = B.row("M3a-MLP gate/up: sum_k m_k W - 2^s x - r", [B.DIN * A * B.W, 2 ** B.S_MAX * B.RNG, B.R_S], "m: class A", "")
    bits = (A + 1).bit_length()                 # signed class [-(A+1), A+1): bit_length(A+1) = log2(A+1) + 1 bits
    worst_acc = B.DIN * A * B.W                  # largest |sum_k a_k W_kj| on class edges
    out["classes"].append(dict(
        A_label=label, A=A, signed_bits=bits,
        in_proj_row=dict(bound=r_in["bound"], log2=r_in["log2"], below_2_63=r_in["below_2_63"], headroom_bits=round(63 - r_in["log2"], 6)),
        mlp_gate_up_row=dict(bound=r_mlp["bound"], log2=r_mlp["log2"], below_2_63=r_mlp["below_2_63"], headroom_bits=round(63 - r_mlp["log2"], 6)),
        accumulator_edge=worst_acc, accumulator_edge_log2=round(math.log2(worst_acc), 6),
        # the output cell x = floor(acc / 2^s) is an rng cell, |x| < 2^23: the smallest public shift s that keeps the EDGE accumulator
        # inside it. An honest tensor's shift is its exponent e (1..24); a class edge is not an honest activation.
        min_shift_for_edge_acc_in_rng=max(0, math.ceil(math.log2(worst_acc / (2 ** 23 - 1)))),
        keys_if_committed_cell=keys_for(bits),
        m3a_public_input_cells=0))
ref = out["classes"][0]
for c in out["classes"]:
    c["delta_vs_2047"] = dict(in_proj_log2=round(c["in_proj_row"]["log2"] - ref["in_proj_row"]["log2"], 6),
                              keys_per_committed_cell=c["keys_if_committed_cell"]["total"] - ref["keys_if_committed_cell"]["total"],
                              relations_per_committed_cell=c["keys_if_committed_cell"]["relations"] - ref["keys_if_committed_cell"]["relations"])
out["reading"] = ("In M3a the norm outputs a and m are public statement words checked at admission (DESIGN 3.2, 5.5; bounds.py 'admit'), "
                  "so a wider class adds no cell there: only the two no-wrap rows change, and both stay below 2^63. In the full-model form "
                  "(DESIGN 3.1) a norm output is a committed cell; keys_if_committed_cell counts what its class check would need per value. "
                  "What the wider class does to the honest sizes of gw, u, h and the in_proj outputs is measured by the run, not counted here.")
Path(sys.argv[1]).write_text(json.dumps(out, indent=1) + "\n")
print(json.dumps([dict(A=c["A_label"], in_proj_log2=c["in_proj_row"]["log2"], below_2_63=c["in_proj_row"]["below_2_63"],
                       keys=c["keys_if_committed_cell"]["total"], min_shift=c["min_shift_for_edge_acc_in_rng"]) for c in out["classes"]]))
