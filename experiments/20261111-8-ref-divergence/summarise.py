#!/usr/bin/env python3
"""Aggregate runs/{calibration,heldout,stress}.jsonl into runs/summary.json and runs/summary.md.

Decision rule (PREREG "Acceptance threshold"): cell (arm, F) PASSES iff R_max <= 2 for all 10 ops on all 5 held-out runs.
Across runs: median, sample SD (n - 1), min, max.
"""
import json
import math
import statistics

import refs

RUNS = refs.HERE / 'runs'
METRICS = ('R_max', 'R_rms', 'max_int_ref', 'rms_int_ref', 'max_ref_fp64', 'rms_ref_fp64', 'max_int_fp64',
           'rms_int_fp64', 'sign_flips', 'argmax_flips', 'int_clamps', 'int_ood', 'fp8_sat', 'fp8_under', 'bf16_over', 'n')
BAR = 2.0


def stats(xs):
    xs = [x for x in xs if x is not None]
    if not xs:
        return None
    return dict(median=statistics.median(xs), sd=statistics.stdev(xs) if len(xs) > 1 else 0.0,
                min=min(xs), max=max(xs), n=len(xs))


def load(split):
    return [json.loads(x) for x in (RUNS / f'{split}.jsonl').read_text().splitlines()]


def main():
    out = dict(bar=BAR, rule='cell (arm, F) passes iff R_max <= 2 for all 10 ops on all 5 held-out runs', splits={})
    for split in ('calibration', 'heldout', 'stress'):
        rows = load(split)
        cells = {}
        for r in rows:
            cells.setdefault((r['arm'], r['F'], r['op']), []).append(r)
        agg = {}
        for (arm, f, op), rs in sorted(cells.items()):
            assert len(rs) == 5, (split, arm, f, op)
            agg[f'{arm}|F{f}|{op}'] = {m: stats([r[m] for r in rs]) for m in METRICS}
            agg[f'{arm}|F{f}|{op}']['totals'] = {m: sum(r[m] or 0 for r in rs) for m in
                                                 ('sign_flips', 'argmax_flips', 'argmax_n', 'int_clamps', 'int_ood',
                                                  'fp8_sat', 'fp8_under', 'bf16_over', 'n')}
            agg[f'{arm}|F{f}|{op}']['seeds'] = sorted(r['seed'] for r in rs)
        verdict = {}
        for arm in ('bf16', 'fp8'):
            for f in refs.FS:
                checks = [r for r in rows if r['arm'] == arm and r['F'] == f]
                assert len(checks) == 50
                fails = [dict(op=r['op'], seed=r['seed'], R_max=r['R_max']) for r in checks if not r['R_max'] <= BAR]
                worst = max(checks, key=lambda r: r['R_max'])
                verdict[f'{arm}|F{f}'] = dict(checks=len(checks), passed_checks=len(checks) - len(fails),
                                             verdict='PASS' if not fails else 'FAIL', failures=fails,
                                             worst=dict(op=worst['op'], seed=worst['seed'], R_max=worst['R_max']))
        out['splits'][split] = dict(cells=agg, verdict=verdict)
    (RUNS / 'summary.json').write_text(json.dumps(out, indent=1, sort_keys=True) + '\n')

    g = lambda v: 'inf' if v == math.inf else f'{v:.3g}'
    lines = []
    for split in ('heldout', 'calibration', 'stress'):
        s = out['splits'][split]
        lines.append(f'## {split}\n')
        lines.append('| cell | checks R_max <= 2 | verdict (rule applied; binding only for held-out) | worst op (seed): R_max |')
        lines.append('|---|---|---|---|')
        for k, v in s['verdict'].items():
            lines.append(f"| {k} | {v['passed_checks']} / {v['checks']} | {v['verdict']} | {v['worst']['op']} ({v['worst']['seed']}): {g(v['worst']['R_max'])} |")
        lines.append('')
        lines.append('| arm, F, op | R_max median [min, max] SD | R_rms median [min, max] | max abs int-ref median [min, max] | max abs ref-fp64 median | RMS int-ref median | sign flips (sum) | argmax flips (sum / vectors) | int clamps | int OOD vectors | FP8 sat | FP8 underflow |')
        lines.append('|---|---|---|---|---|---|---|---|---|---|---|---|')
        for k, c in s['cells'].items():
            t = c['totals']
            am = '-' if c['argmax_flips'] is None else f"{t['argmax_flips']} / {t['argmax_n']}"
            lines.append(f"| {k} | {g(c['R_max']['median'])} [{g(c['R_max']['min'])}, {g(c['R_max']['max'])}] SD {g(c['R_max']['sd'])} | "
                         f"{g(c['R_rms']['median'])} [{g(c['R_rms']['min'])}, {g(c['R_rms']['max'])}] | "
                         f"{g(c['max_int_ref']['median'])} [{g(c['max_int_ref']['min'])}, {g(c['max_int_ref']['max'])}] | "
                         f"{g(c['max_ref_fp64']['median'])} | {g(c['rms_int_ref']['median'])} | {t['sign_flips']} | {am} | "
                         f"{t['int_clamps']} | {t['int_ood']} | {t['fp8_sat']} | {t['fp8_under']} |")
        lines.append('')
    (RUNS / 'summary.md').write_text('\n'.join(lines) + '\n')
    print(json.dumps({sp: {k: (v['verdict'], v['passed_checks'], v['worst']) for k, v in out['splits'][sp]['verdict'].items()}
                      for sp in out['splits']}, indent=1))


if __name__ == '__main__':
    main()
