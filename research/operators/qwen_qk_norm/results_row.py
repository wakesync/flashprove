#!/usr/bin/env python3
"""Append the qwen-qk-rmsnorm entry to research/results.yaml (refuses if present). Numbers are read
from the committed receipts, not typed: runs/summary.json and runs/fidelity.json at COMMIT."""
import json
import pathlib
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[2]
EXP = 'experiments/20261111-35-qk-rmsnorm'
COMMIT = sys.argv[1]
PR = int(sys.argv[2])


def show(path):
    return json.loads(subprocess.run(['git', 'show', f'{COMMIT}:{path}'], cwd=ROOT, text=True, capture_output=True, check=True).stdout)


summ = show(f'{EXP}/runs/summary.json')
fid = show(f'{EXP}/runs/fidelity.json')['summary']
base = dict(hardware='cpu-epyc-rome-kvm-16', date='2026-11-11', commit=COMMIT)
m = []


def add(**kw):
    d = dict(kw)
    d.update(base)
    m.append(d)


for b, key in (('release', 'suite'), ('ubsan', 'suite-ubsan')):
    s = summ[key]
    src = f'{EXP}/runs/summary.json'
    add(name=f'honest_accept_{b}', stat='count', value=s['honest_accepted'], total=s['honest'], unit='count', n=10, spread=None, source=src,
        note='5 distributions x 10 seeds x 2 arms (D16, D256); F = 12, Hq = 2, Hk = 1')
    add(name=f'hostile_reject_{b}', stat='count', value=s['hostile_rejected'], total=s['hostile_subcases'], unit='count', n=10, spread=None, source=src,
        note='21 sampled sub-cases x 10 seeds x 2 arms; sampled classes, not exhaustive')
    add(name=f'complete_malicious_reject_{b}', stat='count', value=s['complete_rejected'], total=s['complete_malicious'], unit='count', n=10, spread=None, source=src,
        note='12 complete malicious sub-cases x 10 seeds x 2 arms; rejected by an equation check, not a low-probability round')
for arm in ('D16', 'D256'):
    sz = summ['suite']['sizes'][arm]
    for k, unit in (('prove_s', 's'), ('verify_s', 's'), ('proof_bytes', 'B'), ('columns', 'count'), ('relations', 'count')):
        st = sz[k]
        add(name=f'{arm.lower()}_{k}', series='qk-rmsnorm-size', arm=arm, stat='median', value=st['median'], unit=unit, n=st['n'],
            spread=dict(sd=st['sd'], min=st['min'], max=st['max']), source=f'{EXP}/runs/summary.json',
            note='honest uniform proof, 3 heads, release build, 4 pinned cores on a shared loaded host; descriptive, not a performance claim'
                 + ('; prove time excludes relation building and sizing' if k == 'prove_s' else ''))
for arm in ('D16', 'D256'):
    for dist in ('uniform', 'outlier', 'low', 'unit-spike'):
        f = fid[f'{arm}/{dist}']
        add(name=f'{arm.lower()}_{dist.replace("-", "_")}_rel_l2_median', series='qk-rmsnorm-fidelity', arm=f'{arm}/{dist}', stat='median',
            value=f['median_of_seed_medians'], unit='ratio', n=f['seeds'],
            spread=dict(sd=f['sd_of_seed_medians'], min=f['min_seed_median'], max=f['max_seed_median']), source=f'{EXP}/runs/fidelity.json',
            note='median over 10 seeds of the per-seed median (3 heads) vector-relative L2 error vs float64 RMSNorm on the same integers; synthetic, not model fidelity')
        add(name=f'{arm.lower()}_{dist.replace("-", "_")}_rel_l2_max', series='qk-rmsnorm-fidelity-max', arm=f'{arm}/{dist}', stat='max',
            value=f['max_rel_l2'], unit='ratio', n=f['heads'], spread=None, source=f'{EXP}/runs/fidelity.json',
            note='max over 30 heads (10 seeds x 3 heads); registered threshold 1e-2')

entry = dict(
    id='qwen-qk-rmsnorm',
    title='Per-head q/k RMSNorm (epsilon, learned gain) as proof constraints, bounded CPU prototype',
    status='measured',
    status_note='research only; inputs and gains are public statement fields with no provenance (not tied to a projection or to model norm weights)',
    replication='unreplicated',
    pr=PR,
    summary=('PASS vs prereg: exact isqrt and division with range-checked residuals, per-channel gain and epsilon in the relation, '
             '2 q heads + 1 k head per proof at D16 and D256; honest 100/100, hostile 420/420 (240 complete malicious proofs) in release and UBSan builds; '
             'fixed-point error vs float64 at most 2e-3 relative L2 per head, zero heads exact'),
    conditions=('F = 12, synthetic inputs (uniform, outlier, low, unit-spike, zero), seeds 1..10, CPU shared loaded host, research target 10 bits per round incl. 6 bits proof-of-work, toy coins, '
                'no whole-proof soundness figure; sampled hostile classes; not composed with projection, rotary or attention; not in cp_verify'),
    evidence=[f'{EXP}/RESULTS.md', 'research/operators/qwen_qk_norm/README.md'],
    metrics=m,
)

P = ROOT / 'research/results.yaml'
t = P.read_text()
if 'id: qwen-qk-rmsnorm\n' in t:
    sys.exit('already present')


def q(v):
    return json.dumps(v)


lines = ['', f'  - id: {entry["id"]}']
for k in ('title', 'status', 'status_note', 'replication'):
    lines.append(f'    {k}: {q(entry[k])}')
lines.append(f'    pr: {PR}')
for k in ('summary', 'conditions'):
    lines.append(f'    {k}: {q(entry[k])}')
lines.append(f'    evidence: {q(entry["evidence"])}')
lines.append('    metrics:')
for x in m:
    lines.append(f'      - {json.dumps(x)}')
if not t.endswith('\n'):
    t += '\n'
P.write_text(t + '\n'.join(lines) + '\n')
print(len(m), 'metrics')
