#!/usr/bin/env python3
"""PREREG amendment A-4: recount of the exact (key-proved) quantities of each candidate, after the reviews of PR #74.
COUNTED, NOT BUILT. Units: entries = gate columns + RNG range cells + LKP keys, against count_model.py arm B
(T = 16, o_witness, norm) = 1,605,872 entries, the base runs/cost.json uses. Not term counts (see RESULTS).

What changes against runs/cost.json (count_cost.py, unchanged and still committed):
 1. An exact quantity of b bits proved with ceil(b / 12) 12-bit keys is only proved below 2^(12 ceil(b / 12)). If
    b is not a multiple of 12, its top limb t must also be proved below 2^(b mod 12), or a floor is not unique
    (opus review). Two ways to price that top limb, both reported:
      way A, shifted key: one more 12-bit key on t * 2^(12 - b mod 12) (+1 key per quantity, same table);
      way B, second table: the top limb is looked up in a table of size 2^(b mod 12) (+0 keys; one extra table per
             distinct residual width, listed, its rows not counted here).
 2. Widths that the honest runs exceed: X1 to X3 read eps at Fo up to 30, so sigma needs 24 bits and e1, e2 need
    25 bits (count_cost.py assumed 23 and 24; astra review: e1 / e2 over 2^24 in 37 / 32 of 480 X3 pairs). Those get
    the extra limb (+1 key each) and then the tight top limb.
 3. Complementary pairs (r and 2^s - 1 - r, the shift remainder) are tight by construction and need nothing.
 RNG cells (|x| < 2^18 honest, |x| < 2^23 proved) are not changed here; the gap between the honest class and the
 proved bound is a soundness question (reviewer_constructions.py), not a count.
Usage: count_cost_r2.py   (writes runs/r2/cost-r2.json, prints a table)"""
import json, math, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "research/operators/qwen_deltanet_m2"))
import count_model as CM
D = 128; T = 16
K = lambda b: math.ceil(b / 12) if b > 0 else 0

def inventory(arm):
    """(name, tight width in bits, instances per head per token, width count_cost.py assumed)."""
    inv = []
    def norm(sig_b, e_b, RC, w_rem, y_rem, o_rem, sig_b0=None, e_b0=None):
        inv.extend([("sigma", sig_b, 1, sig_b0 or sig_b), ("e1", e_b, 1, e_b0 or e_b), ("e2", e_b, 1, e_b0 or e_b), ("Rc", RC, 1, RC),
                    ("rr", sig_b, 1, sig_b0 or sig_b), ("gap", sig_b, 1, sig_b0 or sig_b),
                    ("w remainder", w_rem, D, w_rem), ("y remainder", y_rem, D, y_rem)])
        if o_rem: inv.append(("o remainder", o_rem, D, o_rem))
    def state(Fg):
        inv.extend([("S' remainder", Fg, D * D, Fg), ("M remainder", Fg + 12, D, Fg + 12), ("delta remainder", Fg, D, Fg)])
    def shift_gadget():
        inv.extend([("o + 2^17 (tight o class)", 18, D, 18), ("|o*| - 2^16 (outside check)", 17, 1, 17)])
    def sigma_limbs():
        inv.extend([("Sigma lo limb", 18, D, 18), ("Sigma hi limb (signed 10 bits)", 10, D, 10)])
    b = arm.rstrip("P") if arm[0] == "C" else arm
    P = arm[0] == "C" and arm.endswith("P") or arm[0] == "X"
    if arm == "C0": norm(24, 24, 36, 24, 12, 12); state(12)
    elif b == "C1": norm(23, 24, 46, 30, 8, 9); state(18 if P else 12)
    elif b == "C3": norm(23, 24, 46, 30, 8, 0); shift_gadget(); state(18 if P else 12)
    elif b == "C4": norm(33, 34, 56, 40, 8, 0); sigma_limbs(); state(18 if P else 12)
    elif arm == "X3":   # X2 + state at 2^18; eps at Fo <= 30: sigma 24 bits, e1 / e2 25 bits (count_cost.py: 23 and 24)
        norm(24, 25, 46, 30, 12, 0, sig_b0=23, e_b0=24); shift_gadget(); state(18)
    return inv

def price(inv):
    old = sum(n * K(b0) for _, b, n, b0 in inv)
    ext = sum(n * (K(b) - K(b0)) for _, b, n, b0 in inv)                    # extra limbs for widths the runs exceed
    tightA = sum(n for _, b, n, _ in inv if b % 12)                          # way A: +1 shifted key per non-multiple width
    tables = sorted({b % 12 for _, b, n, _ in inv if b % 12})
    return dict(keys_counted_before=old, extra_limb_keys=ext, wayA_tight_keys=tightA, wayB_extra_tables_residual_bits=tables,
                non_multiple_quantities=[(nm, b, n) for nm, b, n, _ in inv if b % 12],
                exceeded_quantities=[(nm, b0, b, n) for nm, b, n, b0 in inv if K(b) > K(b0)])

def main():
    cost = json.load(open(HERE / "runs" / "cost.json"))
    m2 = CM.summary("B", T=16, o_witness=True, norm=True)
    base = m2["gate_columns"] + m2["range_cells"] + m2["lkp_keys"]
    assert base == 1_605_872, base
    out = dict(_base=dict(entries_T16=base, terms_T16=m2["terms"], unit="entries = gate columns + range cells + LKP keys"))
    assert price(inventory("C0"))["wayA_tight_keys"] == 0 and price(inventory("C0"))["extra_limb_keys"] == 0
    print("| arm | entries T16 (cost.json) | + extra limbs | way A (shifted key) entries T16 | delta vs M2 | way B (second table) entries T16 | delta vs M2 | extra tables (bits) |")
    print("|---|---|---|---|---|---|---|---|")
    for arm in ("C1", "C3", "C4", "C1P", "C3P", "C4P", "X3"):
        p = price(inventory(arm)); e0 = cost[arm]["T16_entries"]
        eB = e0 + T * p["extra_limb_keys"]; eA = eB + T * p["wayA_tight_keys"]
        out[arm] = dict(p, entries_T16_cost_json=e0, entries_T16_wayA=eA, entries_T16_wayB=eB,
                        delta_pct_cost_json=round(100 * (e0 - base) / base, 3), delta_pct_wayA=round(100 * (eA - base) / base, 3),
                        delta_pct_wayB=round(100 * (eB - base) / base, 3))
        print(f"| {arm} | {e0:,} (+{out[arm]['delta_pct_cost_json']}%) | {T * p['extra_limb_keys']:,} | {eA:,} | +{out[arm]['delta_pct_wayA']}% | {eB:,} | +{out[arm]['delta_pct_wayB']}% | {p['wayB_extra_tables_residual_bits']} |")
    out["_note"] = ("COUNTED, NOT BUILT. Recount of key-proved exact quantities only (A-4). Way A prices each non-multiple-of-12 width with one "
                    "shifted key; way B with a second table (rows not counted). Neither makes the candidates sound: RNG-cell soundness "
                    "bounds and the norm aliases are separate (reviewer_constructions.py).")
    (HERE / "runs" / "r2").mkdir(parents=True, exist_ok=True)
    (HERE / "runs" / "r2" / "cost-r2.json").write_text(json.dumps(out, indent=1) + "\n")

if __name__ == "__main__": main()
