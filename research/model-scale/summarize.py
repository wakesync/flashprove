#!/usr/bin/env python3
"""Summarize results/sweep_t10.jsonl into markdown tables and a log-log fit (stdout + results/summary.json).

  python3 research/model-scale/summarize.py

Measured: every number read from the jsonl. Calculated: the fitted exponents and the
extrapolation block, which use only the closed-form column count (kda_scale.columns_formula)."""
import json, math, statistics, sys
from collections import defaultdict
from pathlib import Path
here = Path(__file__).resolve().parent
sys.path.insert(0, str(here))
import kda_scale as K

rows = [json.loads(l) for l in (here / 'results' / 'sweep_t10.jsonl').read_text().splitlines() if l.strip()]
proved = [r for r in rows if r['status'] == 'proved']
other = [r for r in rows if r['status'] != 'proved']

by_L = defaultdict(list)
for r in proved:
    by_L[r['log_len']].append(r)

def med(xs):
    return statistics.median(xs)

print(f'points: {len(rows)} total, {len(proved)} proved, {len(other)} not proved ({", ".join(sorted(set(r["status"] for r in other))) or "none"})')
print()
print('| log_len | n | columns (min..max) | prove s across configs median (min..max) | verify s across configs median (min..max) | proof bytes across configs median (min..max) | max RSS MiB across configs median (min..max) |')
print('|---|---|---|---|---|---|---|')
table = []
for L in sorted(by_L):
    rs = by_L[L]
    f = lambda k: [r[k] for r in rs]
    rss = [x / 1024 for x in f('max_rss_kb')]
    t = dict(log_len=L, n=len(rs), columns_min=min(f('columns')), columns_max=max(f('columns')),
             prove_med=med(f('prove_s')), prove_min=min(f('prove_s')), prove_max=max(f('prove_s')),
             verify_med=med(f('verify_s')), verify_min=min(f('verify_s')), verify_max=max(f('verify_s')),
             bytes_med=med(f('proof_bytes')), bytes_min=min(f('proof_bytes')), bytes_max=max(f('proof_bytes')),
             rss_med=med(rss), rss_min=min(rss), rss_max=max(rss))
    table.append(t)
    print(f"| {L} | {t['n']} | {t['columns_min']}..{t['columns_max']} | {t['prove_med']:.2f} ({t['prove_min']:.2f}..{t['prove_max']:.2f}) | "
          f"{t['verify_med']:.3f} ({t['verify_min']:.3f}..{t['verify_max']:.3f}) | {t['bytes_med']:.0f} ({t['bytes_min']}..{t['bytes_max']}) | "
          f"{t['rss_med']:.0f} ({t['rss_min']:.0f}..{t['rss_max']:.0f}) |")

# least-squares fit of log2(metric) vs log2(columns) over points with log_len >= 14 (fixed overheads dominate below)
def fit(key, minL=14, padded=False):
    # x = log2(real columns), or (padded=True) x = log_len, i.e. log2 of the 2^L table the prover actually allocates
    pts = [(r['log_len'] if padded else math.log2(r['columns']), math.log2(r[key])) for r in proved if r['log_len'] >= minL and r[key] > 0]
    n = len(pts); mx = sum(p[0] for p in pts) / n; my = sum(p[1] for p in pts) / n
    b = sum((x - mx) * (y - my) for x, y in pts) / sum((x - mx) ** 2 for x, _ in pts)
    return dict(slope=b, intercept=my - b * mx, n=n)
fits = {k: fit(k) for k in ('prove_s', 'verify_s', 'max_rss_kb', 'proof_bytes')}
fits_padded = {k: fit(k, padded=True) for k in ('prove_s', 'verify_s', 'max_rss_kb', 'proof_bytes')}
print()
for k, v in fits.items():
    print(f'fit log2({k}) = {v["slope"]:.3f} * log2(columns) + {v["intercept"]:.3f}  (n={v["n"]}, log_len>=14)')
for k, v in fits_padded.items():
    print(f'fit log2({k}) = {v["slope"]:.3f} * log_len (padded 2^L) + {v["intercept"]:.3f}  (n={v["n"]}, log_len>=14)')
print('NOTE: prove_s / verify_s in the sweep are single runs on a contended VM; see results/repeat-t10-summary.json for n=10 repeats.')

print()
print('| d | tokens | bits | log_len | columns | prove s | verify s | proof bytes | RSS MiB | max abs err | static rejected | hostile provers rejected |')
print('|---|---|---|---|---|---|---|---|---|---|---|---|')
for r in sorted(proved, key=lambda r: (r['bits'], r['d_k'], r['tokens'])):
    if r['d_k'] >= 32:
        print(f"| {r['d_k']} | {r['tokens']} | {r['bits']} | {r['log_len']} | {r['columns']} | {r['prove_s']:.2f} | {r['verify_s']:.3f} | "
              f"{r['proof_bytes']} | {r['max_rss_kb'] / 1024:.0f} | {r['max_abs_err']:.4g} | {r['rejected_static']} | {r['hostile_provers']}/3 |")
for r in other:
    print(f"| {r['d_k']} | {r['tokens']} | {r['bits']} | {r['est_log_len']} | {r['columns']} | {r['status']} | | planned {r.get('planned_bytes', 0)} | | | | |")

hostile_total = sum(r['hostile_provers'] for r in proved); static_total = sum(r['rejected_static'] for r in proved)
print(f'\nhostile complete proofs rejected: {hostile_total} / {3 * len(proved)}; static mutations rejected: {static_total} / {24 * len(proved)}')

# extrapolation (CALCULATED): one GLM-5.3-Flash KDA layer = 64 heads x 128 x 128 per token
ext = {}
for bits in (8, 12, 16):
    for T in (1, 8, 128):
        cols = K.columns_formula(128, 128, T, 64, bits)
        L = math.ceil(math.log2(cols))
        e = {k: 2 ** (v['slope'] * math.log2(cols) + v['intercept']) for k, v in fits.items()}
        ep = {k: 2 ** (v['slope'] * L + v['intercept']) for k, v in fits_padded.items()}
        ext[f'b{bits}_T{T}'] = dict(bits=bits, tokens=T, heads=64, columns=cols, log_len=L, padded_columns=2 ** L,
                                   prove_s_fit=e['prove_s'], verify_s_fit=e['verify_s'], rss_gib_fit=e['max_rss_kb'] / 2**20, proof_bytes_fit=e['proof_bytes'],
                                   prove_s_fit_padded=ep['prove_s'], verify_s_fit_padded=ep['verify_s'], rss_gib_fit_padded=ep['max_rss_kb'] / 2**20)
L21 = [r for r in proved if r['log_len'] == max(by_L)]
if L21:
    ref = max(L21, key=lambda r: r['columns'])
    for v in ext.values():
        f = v['columns'] / ref['columns']
        v['prove_s_linear_from_largest'] = ref['prove_s'] * f
        v['rss_gib_linear_from_largest'] = ref['max_rss_kb'] * f / 2**20
        fp = 2 ** (v['log_len'] - ref['log_len'])  # the prover allocates the padded 2^L table
        v['prove_s_linear_padded_from_largest'] = ref['prove_s'] * fp
        v['rss_gib_linear_padded_from_largest'] = ref['max_rss_kb'] * fp / 2**20
        v['largest_measured'] = dict(d=ref['d_k'], tokens=ref['tokens'], bits=ref['bits'], columns=ref['columns'], prove_s=ref['prove_s'], max_rss_kb=ref['max_rss_kb'])
print('\nCALCULATED extrapolation, one KDA layer recurrence (64 heads, d_k=d_v=128), target 10, single thread:\n')
print('| bits | tokens | columns | log2 | padded L | RSS GiB (linear, padded 2^L) | RSS GiB (fit, padded) | RSS GiB (linear, real cols; superseded) | RSS GiB (fit, real cols; superseded) | proof KB (fit) |')
print('|---|---|---|---|---|---|---|---|---|---|')
for k, v in ext.items():
    print(f"| {v['bits']} | {v['tokens']} | {v['columns']:,} | {math.log2(v['columns']):.2f} | {v['log_len']} | {v.get('rss_gib_linear_padded_from_largest', 0):,.0f} | {v['rss_gib_fit_padded']:,.0f} | "
          f"{v.get('rss_gib_linear_from_largest', 0):,.0f} | {v['rss_gib_fit']:,.0f} | {v['proof_bytes_fit'] / 1000:.1f} |")
print('\nTime estimators (from contended single-run sweep timings; order of magnitude only):\n')
print('| bits | tokens | padded L | prove h (linear, padded) | prove h (fit, padded) | prove h (linear, real cols; superseded) | prove h (fit, real cols; superseded) | verify min (fit, padded) |')
print('|---|---|---|---|---|---|---|---|')
for k, v in ext.items():
    print(f"| {v['bits']} | {v['tokens']} | {v['log_len']} | {v.get('prove_s_linear_padded_from_largest', 0) / 3600:.2f} | {v['prove_s_fit_padded'] / 3600:.2f} | "
          f"{v.get('prove_s_linear_from_largest', 0) / 3600:.2f} | {v['prove_s_fit'] / 3600:.2f} | {v['verify_s_fit_padded'] / 60:.1f} |")
(here / 'results' / 'summary.json').write_text(json.dumps(dict(points=len(rows), proved=len(proved), by_log_len=table, by_log_len_note='spread is across different configurations at that log_len, NOT repeat variance', fits=fits, fits_padded=fits_padded,
    hostile_rejected=hostile_total, static_rejected=static_total, extrapolation_calculated=ext), indent=2) + '\n')
