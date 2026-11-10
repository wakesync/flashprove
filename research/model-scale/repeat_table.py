#!/usr/bin/env python3
"""Print the markdown repeat-timing table from results/repeat-t10-summary.json, next to the original single-run sweep value.

  python3 research/model-scale/repeat_table.py"""
import json
from pathlib import Path
here = Path(__file__).resolve().parent
s = json.loads((here / 'results' / 'repeat-t10-summary.json').read_text())
orig = {(r['d_k'], r['tokens'], r['bits']): r for r in map(json.loads, (here / 'results' / 'sweep_t10.jsonl').read_text().splitlines()) if r.get('status') == 'proved'}
print('| d | T | bits | log_len | n ok | prove s median | SD | min | max | sweep single run | verify s median | SD | min | max | sweep single run | proof bytes | RSS MiB median (min..max) | load1 min..max |')
print('|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|')
for p in s['points']:
    o = orig[(p['d_k'], p['tokens'], p['bits'])]; ps = p['prove_s']; vs = p['verify_s']; m = p['max_rss_kb']; la = p['loadavg1']
    print(f"| {p['d_k']} | {p['tokens']} | {p['bits']} | {p['log_len']} | {p['ok_runs']}/{p['runs']} | {ps['median']:.2f} | {ps['sd']:.2f} | {ps['min']:.2f} | {ps['max']:.2f} | {o['prove_s']:.2f} | "
          f"{vs['median']:.3f} | {vs['sd']:.3f} | {vs['min']:.3f} | {vs['max']:.3f} | {o['verify_s']:.3f} | {','.join(map(str, p['proof_bytes']))} | "
          f"{m['median'] / 1024:.0f} ({m['min'] / 1024:.0f}..{m['max'] / 1024:.0f}) | {la['min']:.1f}..{la['max']:.1f} |")
