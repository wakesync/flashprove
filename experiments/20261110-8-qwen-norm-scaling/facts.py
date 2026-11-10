#!/usr/bin/env python3
"""Print the exact numbers RESULTS.md quotes, from runs/*.summary.json and runs/mech.json. Usage: facts.py"""
import json
from pathlib import Path
R = Path(__file__).resolve().parent / "runs"
c = json.load(open(R / "cand-stock.summary.json")); m = json.load(open(R / "mech.json"))["summary"]
for a in ("C0", "C1", "D-R15", "C3P", "C4P", "X3"):
    d = c[a]
    print(a, "o max", int(d["max"]["o"]), "S", int(d["max"]["S"]), "M", int(d["max"]["M"]), "w", int(d["max"]["w"]), "shift", d["max"]["shift"],
          "layer rel_y", {k: round(v, 5) for k, v in d["layer_rel_y"].items()}, "Fo_min", d["Fo_min"], "over", d["pairs_over_by_class"])
for k in ("one_minus_a_int_median", "share_tokens_one_minus_a_below_8", "q_hat_abs_median_int", "k_hat_abs_median_int", "o_rms_int_median",
          "y_abs_median_int", "v_abs_median_int", "share_tokens_a_rounds_to_one"):
    print(k, {kk: round(v, 4) for kk, v in m[k].items()})
for k in ("pairs_o_rms_median_below_4", "pairs_o_rms_median_below_16", "pairs_with_any_token_a_rounding_to_one"): print(k, m[k])
