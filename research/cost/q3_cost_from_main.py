#!/usr/bin/env python3
"""Q3 desk calculation: per-1,000-token figures from numbers already on main.

Reads only experiments/20261109-32-qwen-m3-design/runs/model-r2.json (merged with PR #70).
Every figure it prints is EXTRAPOLATED by that file, or arithmetic on it; nothing is measured,
and no rate is a bound. model-r3.json (the merged head's) differs from r2 only in
weights_resident_gb and vram_with_resident_weights_gb_central, by about 5e-6 GB (dt_bias); every
other field read here is identical.

Rate labels: the JSON keys are printed under the note's names. `high_all_in` is printed as
"high". `upper_bound_small_example` is a legacy r1 key name and is printed as "small-example":
PR #70's RESULTS.md (lines 168-175, 205-210) says neither it nor "high" is a proved upper bound.

USD per GPU-hour used:
- 2.16: the replication-1 invoice rate, H100 (research/gpu/replication-1/README.md line 70).
- 2.40: the listed rate in a reading that research/gpu/README.md line 22 itself corrects (read
  before billing caught up). It is NOT an invoice rate; that file's final invoice is 1.186 USD
  all-in for about 25.5 min of instance life (about 2.78 USD per hour, which the file does not
  break down). Kept only as a mid-range sensitivity point; 2.78 sits inside 2.16 to 3.00.
- 3.00: assumed by PR #70 (RESULTS.md line 195).
No H200 price is on main.

Usage, from the repository root:
    python3 research/cost/q3_cost_from_main.py
Deterministic; standard library only.
"""
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SRC = os.path.join(ROOT, "experiments/20261109-32-qwen-m3-design/runs/model-r2.json")
# 2.16 invoice; 2.40 a corrected pre-billing listed rate, not an invoice; 3.00 assumed by PR #70
RATES_USD_PER_GPU_HOUR = [2.16, 2.40, 3.00]
FRACTIONS = [1.0, 0.1, 0.01, 0.001]
# JSON key -> printed label. The legacy key upper_bound_small_example is NOT a bound.
LABEL = {"central": "central", "high_all_in": "high", "upper_bound_small_example": "small-example"}


def lab(rates):
    return {LABEL.get(k, k): v for k, v in rates.items()}


def main():
    d = json.load(open(SRC))
    case = d["packed"]["per_token_layer_segments"]
    own = d["H5_r2"]["own_small_example_rate"]["cases"]["per_token_layer_segments"]["gb"]
    print("EXTRAPOLATED, NOT MEASURED. Every number below is PR #70's extrapolation from another")
    print("model's rates, or arithmetic on it. No Qwen proof has run on a GPU. No rate is a bound:")
    print("'high' and 'small-example' are labels of a range (PR #70 RESULTS.md 168-175, 205-210).")
    print("source:", os.path.relpath(SRC, ROOT))
    print("case: packed, per-token state, one DeltaNet segment per layer (post hoc, exploratory)")
    print("USD rates: 2.16 invoice (H100); 2.40 a corrected pre-billing reading, not an invoice; 3.00 assumed")
    for key in ["T64", "T256", "T1024"]:
        t = int(key[1:])
        e = case[key]["extrapolated"]
        ps = lab(e["prove_s"])
        print(f"\n{key}: prove_s per window " + ", ".join(f"{k} {v:.2f}" for k, v in ps.items()))
        per_1k = {k: v / t * 1000 for k, v in ps.items()}
        print("  GPU-seconds per 1,000 window tokens: " + ", ".join(f"{k} {v:.1f}" for k, v in per_1k.items()))
        for r in RATES_USD_PER_GPU_HOUR:
            print(f"  USD per 1,000 window tokens at {r:.2f}/GPU-h: "
                  + ", ".join(f"{k} {v / 3600 * r:.4f}" for k, v in per_1k.items()))
        vram = e["vram_gb"]
        print(f"  largest-segment VRAM GB: low {vram['low_16B']:.1f}, central {vram['central']:.1f}, "
              f"high {vram['high']:.1f}, own small-example rate {own[key]:.1f}; "
              f"central with resident weights {e['vram_with_resident_weights_gb_central']:.1f}; "
              f"proof MB {e['proof_mb']:.1f}")
    e = lab(case["T1024"]["extrapolated"]["prove_s"])
    print("\nU2 proved fraction f of 1,024-token windows: variable proving work per 1,000 SERVED")
    print("prompt-plus-reply window tokens (fixed costs, receipts, retention and re-running excluded):")
    for f in FRACTIONS:
        print(f"  f = {f}: GPU-s " + ", ".join(f"{k} {v / 1024 * 1000 * f:.3f}" for k, v in e.items())
              + " | USD at 3.00/GPU-h " + ", ".join(f"{k} {v / 1024 * 1000 * f / 3600 * 3:.5f}" for k, v in e.items()))
    print("\nMultiple of plain inference = prove GPU-s per token x plain tokens per GPU-second.")
    print("No plain Qwen3.8-27B rate is on main, so the multiple is not computed here.")
    print(f"\nsegments per window {d['H5_r2']['segments_per_window']['per_token_layer_segments']}, "
          f"cp_verify cap {d['H5_r2']['cp_verify_segment_cap']}; "
          f"commit minutes (extrapolated) {d['extrapolated_commit']['commit_minutes']:.2f}")
    print("\nEXTRAPOLATED, NOT MEASURED (repeated): no figure above is a Qwen measurement or a bound.")


if __name__ == "__main__":
    main()
