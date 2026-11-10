#!/usr/bin/env python3
"""Q3 desk calculation: per-1,000-token figures from numbers already on main.

Reads only experiments/20261109-32-qwen-m3-design/runs/model-r2.json (merged with PR #70).
Every figure it prints is EXTRAPOLATED by that file, or arithmetic on it; nothing is measured.
The USD rates are the two marketplace H100 invoices on main (research/gpu/README.md line 22,
research/gpu/replication-1/README.md line 70) and the 3 USD per GPU-hour that PR #70 assumes
(RESULTS.md line 195). No H200 price is on main.

Usage, from the repository root:
    python3 research/cost/q3_cost_from_main.py
Deterministic; standard library only.
"""
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SRC = os.path.join(ROOT, "experiments/20261109-32-qwen-m3-design/runs/model-r2.json")
RATES_USD_PER_GPU_HOUR = [2.16, 2.40, 3.00]
FRACTIONS = [1.0, 0.1, 0.01, 0.001]
PLAIN_TOKENS_PER_GPU_SECOND = [100, 1000, 10000]  # placeholders, NOT measured anywhere on main


def main():
    d = json.load(open(SRC))
    case = d["packed"]["per_token_layer_segments"]
    own = d["H5_r2"]["own_small_example_rate"]["cases"]["per_token_layer_segments"]["gb"]
    print("source:", os.path.relpath(SRC, ROOT))
    print("case: packed, per-token state, one DeltaNet segment per layer (post hoc, exploratory)")
    for key in ["T64", "T256", "T1024"]:
        t = int(key[1:])
        e = case[key]["extrapolated"]
        print(f"\n{key}: prove_s per window " + ", ".join(f"{k} {v:.2f}" for k, v in e["prove_s"].items()))
        per_1k = {k: v / t * 1000 for k, v in e["prove_s"].items()}
        print("  GPU-seconds per 1,000 window tokens: " + ", ".join(f"{k} {v:.1f}" for k, v in per_1k.items()))
        for r in RATES_USD_PER_GPU_HOUR:
            print(f"  USD per 1,000 window tokens at {r:.2f}/GPU-h: "
                  + ", ".join(f"{k} {v / 3600 * r:.4f}" for k, v in per_1k.items()))
        vram = e["vram_gb"]
        print(f"  largest-segment VRAM GB: low {vram['low_16B']:.1f}, central {vram['central']:.1f}, "
              f"high {vram['high']:.1f}, own small-example rate {own[key]:.1f}; "
              f"central with resident weights {e['vram_with_resident_weights_gb_central']:.1f}; "
              f"proof MB {e['proof_mb']:.1f}")
    e = case["T1024"]["extrapolated"]["prove_s"]
    print("\nU2 proved fraction f of 1,024-token windows, per 1,000 SERVED window tokens (fixed costs excluded):")
    for f in FRACTIONS:
        print(f"  f = {f}: GPU-s " + ", ".join(f"{k} {v / 1024 * 1000 * f:.3f}" for k, v in e.items())
              + " | USD at 3.00/GPU-h " + ", ".join(f"{k} {v / 1024 * 1000 * f / 3600 * 3:.5f}" for k, v in e.items()))
    print("\nMultiple of plain inference = prove GPU-s per token x plain tokens per GPU-second.")
    print("No plain Qwen3.8-27B rate is on main; the rows below are placeholders, not results:")
    for p in PLAIN_TOKENS_PER_GPU_SECOND:
        print(f"  if plain = {p} tok/s per GPU: " + ", ".join(f"{k} {v / 1024 * p:.1f}x" for k, v in e.items()))
    print(f"\nsegments per window {d['H5_r2']['segments_per_window']['per_token_layer_segments']}, "
          f"cp_verify cap {d['H5_r2']['cp_verify_segment_cap']}; "
          f"commit minutes (extrapolated) {d['extrapolated_commit']['commit_minutes']:.2f}")


if __name__ == "__main__":
    main()
