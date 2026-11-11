#!/usr/bin/env python3
"""Append the ref-divergence-ops row to research/results.yaml (values read from runs/summary.json)."""
import json

import refs

ROOT = refs.ROOT
SRC = 'experiments/20261111-8-ref-divergence/runs/summary.json'
COMMIT = 'fa0693676b802cc9e506027ab9064efa5e4dcc41'
s = json.loads((ROOT / SRC).read_text())['splits']['heldout']
HW, DATE = 'cpu-epyc-rome-kvm-16', '2026-11-11'


def g(v):
    return float(f'{v:.6g}')


metrics = []
for arm in ('bf16', 'fp8'):
    for f in refs.FS:
        v = s['verdict'][f'{arm}|F{f}']
        metrics.append(dict(name=f'{arm}_f{f}_checks_within_2x', series='ref-divergence-cells', arm=f'{arm} F{f}',
                            stat='count', value=v['passed_checks'], total=v['checks'], unit='count', n=5, spread=None,
                            hardware=HW, date=DATE, commit=COMMIT, source=SRC,
                            note=f"held-out seeds 1001..1005 x 10 ops; rule R_max <= 2 for all 50; worst {v['worst']['op']} seed {v['worst']['seed']} R_max {g(v['worst']['R_max'])}"))
for arm, op in (('bf16', 'l2'), ('bf16', 'rms'), ('bf16', 'silu'), ('fp8', 'rms'), ('fp8', 'silu')):
    c = s['cells'][f'{arm}|F12|{op}']['R_max']
    metrics.append(dict(name=f'r_max_{arm}_f12_{op}', series='ref-divergence-rmax', arm=f'{arm} {op}', stat='median',
                        value=g(c['median']), unit='ratio', n=5,
                        spread=dict(sd=g(c['sd']), min=g(c['min']), max=g(c['max'])),
                        hardware=HW, date=DATE, commit=COMMIT, source=SRC,
                        note='max|int - ref| / max|ref - fp64| per held-out run, F12; SD = sample SD over 5 runs (5 input seeds)'))
for arm, op in (('bf16', 'l2'), ('fp8', 'l2'), ('bf16', 'silu'), ('fp8', 'silu')):
    c = s['cells'][f'{arm}|F12|{op}']['max_ref_fp64']
    metrics.append(dict(name=f'ref_err_{arm}_{op}', series='ref-divergence-ref-error', arm=f'{arm} {op}', stat='median',
                        value=g(c['median']), unit='abs_diff', n=5,
                        spread=dict(sd=g(c['sd']), min=g(c['min']), max=g(c['max'])),
                        hardware=HW, date=DATE, commit=COMMIT, source=SRC,
                        note='max abs error of the reference format vs float64 per held-out run; denominator of R_max'))
for op in ('l2', 'silu'):
    c = s['cells'][f'bf16|F12|{op}']['max_int_fp64']
    metrics.append(dict(name=f'int_err_f12_{op}', series='ref-divergence-int-error', arm=f'int F12 {op}', stat='median',
                        value=g(c['median']), unit='abs_diff', n=5,
                        spread=dict(sd=g(c['sd']), min=g(c['min']), max=g(c['max'])),
                        hardware=HW, date=DATE, commit=COMMIT, source=SRC,
                        note='max abs error of the committed integer relation vs float64 per held-out run (input conversion included)'))

row = dict(
    id='ref-divergence-ops',
    title='BF16 and FP8 (E4M3) reference definitions; PR #67 integer operator relations vs each reference, per operator',
    status='measured', status_note='weak rule by construction; FP8 arm close to vacuous, see RESULTS section 3',
    replication='unreplicated', pr=110,
    summary=('PASS vs prereg in all 6 cells (BF16 and FP8, F = 12 / 14 / 16): 50 / 50 held-out checks each of '
             'R_max = max|int - ref| / max|ref - fp64| <= 2 over 10 ops x 5 runs. Worst BF16 R_max 1.55 (l2, F12), worst FP8 1.04. '
             'Since R_max <= 1 + int error / ref error, this says the committed integer relations are not a worse approximation than '
             'BF16 on these inputs; FP8 E4M3 error is 12 to 117x the integer error at F12, so the FP8 PASS carries little information. '
             'Stress inputs outside the integer domain: BF16 15 / 50, R_max up to 337 (clamps)'),
    conditions=('synthetic Gaussian inputs inside the integer domain, splits frozen by hash before evaluation (calibration seeds 1..5 '
                'set FP8 per-op delayed scales, held-out 1001..1005 decide, stress 2001..2005 descriptive); references emulated in numpy '
                '(BF16 RNE / FP8 E4M3 RNE satfinite, FP32 compute, sequential FP32 sums); PR #67 bounded relations only (no epsilon, '
                'no M2 norm, no DeltaNet, no matmul), no weights, no model, no proof, CPU'),
    evidence=['experiments/20261111-8-ref-divergence/RESULTS.md'],
    metrics=metrics,
)


def dump(v):
    return json.dumps(v, ensure_ascii=True)


lines = ['', f"  - id: {row['id']}"]
for k in ('title', 'status', 'status_note', 'replication', 'pr', 'summary', 'conditions', 'evidence'):
    lines.append(f'    {k}: {dump(row[k])}')
lines.append('    metrics:')
for m in metrics:
    lines.append(f'      - {dump(m)}')
p = ROOT / 'research/results.yaml'
text = p.read_text()
assert 'id: ref-divergence-ops' not in text
p.write_text(text.rstrip('\n') + '\n' + '\n'.join(lines) + '\n')
print('added', len(metrics), 'metrics')
