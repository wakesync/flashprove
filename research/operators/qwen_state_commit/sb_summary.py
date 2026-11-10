#!/usr/bin/env python3
"""Per-arm H4 tally from runs/sb-ranges.json (written by sb_ref.py). Prints JSON."""
import json, pathlib, statistics, sys
root = pathlib.Path(__file__).resolve().parents[3]
name = sys.argv[1] if len(sys.argv) > 1 else 'sb-ranges'
d = json.loads((root / f'experiments/20261109-34-qwen-state-commit/runs/{name}.json').read_text())
out = {}
for C in (1, 16, 64):
    rs = [r for r in d['rows'] if r['C'] == C]
    div = [r['divergence_vs_float64_max_abs'] for r in rs]
    out[C] = dict(n=len(rs), fits=sum(r['fits_contract'] for r in rs),
                  div_le_0064=sum(x <= 0.064 for x in div),
                  div=dict(median=statistics.median(div), min=min(div), max=max(div), sd=statistics.stdev(div)),
                  over=[(r['dist'], r['seed'], round(r['divergence_vs_float64_max_abs'], 4)) for r in rs if r['divergence_vs_float64_max_abs'] > 0.064],
                  num_bits_max=max(max(r['max_numerator_bits'].values()) for r in rs),
                  by_dist={dd: max(r['divergence_vs_float64_max_abs'] for r in rs if r['dist'] == dd) for dd in ('R1', 'R2', 'R3', 'R4')})
print(json.dumps(out, indent=1))
(root / f'experiments/20261109-34-qwen-state-commit/runs/{name}-summary.json').write_text(json.dumps(out, indent=1) + '\n')
