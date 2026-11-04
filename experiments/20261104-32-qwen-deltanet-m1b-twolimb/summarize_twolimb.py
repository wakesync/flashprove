#!/usr/bin/env python3
"""Per-distribution spread for runs/ranges-twolimb.json (added after review, PREREG amendment A2).

Reads only committed run data; does not rerun the recurrence. Writes runs/ranges-twolimb-summary.json with,
per arm and distribution (n = 5 seeds each): median, SD (sample, ddof = 1), min and max of every max_abs
field and of the float64 state divergence; the F10 / F12 divergence ratios; and a cell-by-cell comparison of
the F12 max values with the M1 range study (experiments/20261104-11-qwen-deltanet-m1/runs/ranges.json).
"""
import json, statistics
from pathlib import Path

here = Path(__file__).resolve().parent
root = here.parents[1]
DISTS = ('R1', 'R2', 'R3', 'R4')


def spread(xs):
    return dict(n=len(xs), median=statistics.median(xs), sd=statistics.stdev(xs) if len(xs) > 1 else None,
                min=min(xs), max=max(xs))


def main():
    d = json.loads((here / 'runs/ranges-twolimb.json').read_text())
    m1 = json.loads((root / 'experiments/20261104-11-qwen-deltanet-m1/runs/ranges.json').read_text())
    out = dict(source='runs/ranges-twolimb.json', sd='sample (ddof = 1)', arms={})
    for arm, a in d['arms'].items():
        out['arms'][arm] = {}
        for dist in DISTS:
            rs = [r for r in a['runs'] if r['dist'] == dist]
            st = {k: spread([r['max_abs'][k] for r in rs]) for k in rs[0]['max_abs']}
            st['divergence_vs_float64_max_abs'] = spread([r['divergence_vs_float64_max_abs'] for r in rs])
            out['arms'][arm][dist] = st
    # spread of the per-run high-limb maxima over all 20 F12 runs (the results.yaml f12_max_abs_* metrics)
    out['F12_all20'] = {k: spread([r['max_abs'][k] for r in d['arms']['F12_twolimb']['runs']]) for k in ('delta_hi', 'v_hi')}
    f12, f10 = out['arms']['F12_twolimb'], out['arms']['F10_single']
    ratios = {dist: f10[dist]['divergence_vs_float64_max_abs']['max'] / f12[dist]['divergence_vs_float64_max_abs']['max']
              for dist in DISTS}
    w10 = max(f10[x]['divergence_vs_float64_max_abs']['max'] for x in DISTS)
    w12 = max(f12[x]['divergence_vs_float64_max_abs']['max'] for x in DISTS)
    out['divergence_ratio_F10_over_F12'] = dict(per_dist_of_max=ratios, worst_case=dict(F10=w10, F12=w12, ratio=w10 / w12))
    # H3 re-derivation check: does the F12 arm reproduce M1's per-run max values exactly?
    # F12 arm vs M1 'realistic' (F = 12); F10 arm vs M1 'f_sweep' rows with F = 10
    m1rows = {(12, r['seed'], r['dist']): r for r in m1['realistic']}
    m1rows.update({(10, r['seed'], r['dist']): r for r in m1['f_sweep'] if r['F'] == 10})
    same, diff = 0, []
    for r in d['arms']['F12_twolimb']['runs'] + d['arms']['F10_single']['runs']:
        mr = m1rows[(r['F'], r['seed'], r['dist'])]
        for k in ('S', 'M', 'delta', 'v', 'o'):
            if mr['max_abs'][k] == r['max_abs'][k]:
                same += 1
            else:
                diff.append([r['F'], r['seed'], r['dist'], k, mr['max_abs'][k], r['max_abs'][k]])
        if mr['divergence_vs_float64']['max_abs'] == r['divergence_vs_float64_max_abs']:
            same += 1
        else:
            diff.append([r['F'], r['seed'], r['dist'], 'divergence', mr['divergence_vs_float64']['max_abs'], r['divergence_vs_float64_max_abs']])
    out['m1_comparison'] = dict(m1_source='experiments/20261104-11-qwen-deltanet-m1/runs/ranges.json',
                                fields='S, M, delta, v, o max_abs and divergence, per run; F12 arm vs M1 realistic, F10 arm vs M1 f_sweep F = 10 (40 runs x 6)',
                                identical=same, differing=diff)
    (here / 'runs/ranges-twolimb-summary.json').write_text(json.dumps(out, indent=1) + '\n')
    for arm in out['arms']:
        for dist in DISTS:
            s = out['arms'][arm][dist]
            print(arm, dist, {k: (v['median'], round(v['sd'], 4) if v['sd'] is not None else None, v['min'], v['max'])
                              for k, v in s.items()})
    print('ratios', {k: round(v, 3) for k, v in ratios.items()}, 'worst', round(w10 / w12, 3))
    print('F12_all20', out['F12_all20'])
    print('m1 identical', same, 'differing', len(diff))


if __name__ == '__main__':
    main()
