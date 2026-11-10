#!/usr/bin/env python3
"""Print the per-prompt markdown tables for RESULTS.md from runs/summary.json. Usage: tables.py"""
import json
from pathlib import Path
S = json.load(open(Path(__file__).resolve().parent / "runs" / "summary.json"))
B = 1 << 18
for F in ("12", "14", "16"):
    a = S["arms"]["registered/stock"][F]
    print(f"\n### F = {F} (registered arm, conv taps at 2^12), per prompt: typical = median over 48 heads, worst = max over heads\n")
    print("| prompt | T | rel_S typ / worst | rel_o worst | rel_y typ / worst | norm-only rel_y typ | BF16-emul rel_y typ | max S | max M | max delta | max o | max w | pairs with an RNG class >= 2^18 |")
    print("|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    rows = [json.loads(l) for l in open(Path(__file__).resolve().parent / "runs" / "real-stock.jsonl")]
    for p, d in a["per_prompt"].items():
        over = sum(1 for r in rows if r["prompt"] == p and r["F"] == int(F) and any(r["max"][c] >= B for c in ("S", "M", "delta_lo", "delta_hi", "o", "w")))
        m = d["max"]
        print(f"| {p} | {d['T']} | {d['rel_S']['typical']:.3g} / {d['rel_S']['worst']:.3g} | {d['rel_o']['worst']:.3g} | {d['rel_y']['typical']:.3g} / {d['rel_y']['worst']:.3g} | "
              f"{d['norm_only_rel_y']['typical']:.3g} | {d['bf16_rel_y']['typical']:.3g} | {m['S']:,} | {m['M']:,} | {m['delta']:,} | {m['o']:,} | {m['w']:,} | {over} / 48 |")
