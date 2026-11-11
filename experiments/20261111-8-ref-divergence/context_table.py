#!/usr/bin/env python3
"""Held-out, per op and F: median over 5 runs of max|int - fp64|, max|bf16 - fp64|, max|fp8 - fp64| (context table)."""
import json

import refs

s = json.loads((refs.HERE / 'runs/summary.json').read_text())['splits']['heldout']['cells']
print('| op | F | max abs int-fp64 | max abs bf16-fp64 | max abs fp8-fp64 |')
print('|---|---|---|---|---|')
for op in refs.OPS:
    for f in refs.FS:
        b, e = s[f'bf16|F{f}|{op}'], s[f'fp8|F{f}|{op}']
        print(f"| {op} | {f} | {b['max_int_fp64']['median']:.3g} | {b['max_ref_fp64']['median']:.3g} | {e['max_ref_fp64']['median']:.3g} |")
