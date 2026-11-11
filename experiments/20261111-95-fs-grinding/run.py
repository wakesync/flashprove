#!/usr/bin/env python3
"""Registered runs for issue #95 (PREREG.md in this directory). CPU only, standard library only.

  python3 experiments/20261111-95-fs-grinding/run.py build   compile grind.cpp into work/ (ignored)
  python3 experiments/20261111-95-fs-grinding/run.py plan    write runs/plan.jsonl and runs/accounting.txt
  python3 experiments/20261111-95-fs-grinding/run.py runs    the registered runs: arms A, B, C x seeds 1..5 x 100000 tries
  python3 experiments/20261111-95-fs-grinding/run.py report  runs/summary.json from the raw run files

Run from the repository root. `--bin PATH` uses an already built binary instead of work/grind.bin.
"""
import hashlib
import json
import math
import pathlib
import platform
import statistics
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[1]
RUNS = HERE / 'runs'
WORK = HERE / 'work'
REL = HERE.relative_to(ROOT)
TRIES = 100000
SEEDS = [1, 2, 3, 4, 5]
ARMS = ['A', 'B', 'C']
CMD = ['g++', '-std=c++17', '-O2', '-Wall', '-Wextra', '-fno-ipa-modref', '-DBLK_FIELD=2', '-DBLK_HASH=1', '-I', 'blocks',
       f'{REL}/grind.cpp', '-o', f'{REL}/work/grind.bin']


def sh(args):
    p = subprocess.run(args, cwd=ROOT, text=True, capture_output=True)
    if p.returncode:
        raise RuntimeError((args, p.returncode, p.stdout[-2000:], p.stderr[-2000:]))
    return p.stdout


def binary():
    if '--bin' in sys.argv:
        return sys.argv[sys.argv.index('--bin') + 1]
    return str(ROOT / REL / 'work' / 'grind.bin')


# Exact binomial tail sums in log space; Clopper-Pearson by bisection on p.
def log_pmf(k, n, p):
    if p <= 0:
        return 0.0 if k == 0 else -math.inf
    if p >= 1:
        return 0.0 if k == n else -math.inf
    return math.lgamma(n + 1) - math.lgamma(k + 1) - math.lgamma(n - k + 1) + k * math.log(p) + (n - k) * math.log1p(-p)


def logsumexp(xs):
    m = max(xs)
    if m == -math.inf:
        return m
    return m + math.log(sum(math.exp(x - m) for x in xs))


def cdf_le(k, n, p):  # P[X <= k]
    return math.exp(logsumexp([log_pmf(i, n, p) for i in range(0, k + 1)]))


def cdf_ge(k, n, p):  # P[X >= k]
    if k <= 0:
        return 1.0
    return 1.0 - cdf_le(k - 1, n, p)


def clopper_pearson(k, n, conf=0.99):
    alpha = 1 - conf
    def solve(f, target, increasing):
        lo, hi = 0.0, 1.0
        for _ in range(80):
            mid = (lo + hi) / 2
            v = f(mid)
            if (v < target) == increasing:
                lo = mid
            else:
                hi = mid
        return (lo + hi) / 2
    # lower: P[X >= k | p] = alpha/2 (increasing in p); upper: P[X <= k | p] = alpha/2 (decreasing in p)
    lower = 0.0 if k == 0 else solve(lambda p: cdf_ge(k, n, p), alpha / 2, True)
    upper = 1.0 if k == n else solve(lambda p: cdf_le(k, n, p), alpha / 2, False)
    return lower, upper


def stats(v):
    return dict(n=len(v), median=statistics.median(v), sd=statistics.stdev(v) if len(v) > 1 else 0.0, min=min(v), max=max(v))


def build():
    WORK.mkdir(exist_ok=True)
    sh(CMD)
    meta = dict(command=CMD, compiler=sh(['g++', '--version']).splitlines()[0],
                grind_cpp_sha256=hashlib.sha256((HERE / 'grind.cpp').read_bytes()).hexdigest(),
                proof_cpp_sha256=hashlib.sha256((ROOT / 'research/operators/qwen_ops/proof.cpp').read_bytes()).hexdigest(),
                binary_sha256=hashlib.sha256((WORK / 'grind.bin').read_bytes()).hexdigest())
    RUNS.mkdir(exist_ok=True)
    (RUNS / 'build.json').write_text(json.dumps(meta, indent=2) + '\n')
    print(json.dumps(meta))


def plan():
    RUNS.mkdir(exist_ok=True)
    out = sh([binary(), 'plan'])
    lines = out.splitlines()
    js = [l for l in lines if l.startswith('{')]
    acc = [l for l in lines if not l.startswith('{')]
    (RUNS / 'plan.jsonl').write_text('\n'.join(js) + '\n')
    (RUNS / 'accounting.txt').write_text('\n'.join(acc) + '\n')
    print(js[-1])


def runs():
    RUNS.mkdir(exist_ok=True)
    meta = dict(binary_sha256=hashlib.sha256(pathlib.Path(binary()).read_bytes()).hexdigest(), tries=TRIES, seeds=SEEDS, arms=ARMS)
    for arm in ARMS:
        lines = []
        for seed in SEEDS:
            out = sh([binary(), 'grind', arm, str(seed), str(TRIES)])
            lines.append(out.strip())
            print(out.strip(), flush=True)
        (RUNS / f'arm-{arm}.jsonl').write_text('\n'.join(lines) + '\n')
    (RUNS / 'runs-meta.json').write_text(json.dumps(meta, indent=2) + '\n')


def report():
    summary = {}
    for arm in ARMS:
        rows = [json.loads(l) for l in (RUNS / f'arm-{arm}.jsonl').read_text().splitlines() if l.strip()]
        r0 = rows[0]
        for r in rows:
            for key in ('round_index', 't', 'log_n', 'work_bits', 'A', 'n', 'p0', 'e'):
                assert r[key] == r0[key], (arm, key)
        tries = sum(r['tries'] for r in rows)
        forges = sum(r['forges'] for r in rows)
        nonces = sum(r['nonces'] for r in rows)
        lo, hi = clopper_pearson(forges, tries, 0.99)
        p0, e, w = r0['p0'], r0['e'], r0['work_bits']
        rate = forges / tries
        nonces_per_forge = nonces / forges if forges else None
        expected_npf = (2 ** w) / p0
        verdict = 'PASS' if (lo <= p0 <= hi and hi <= e * 1.05) else 'FAIL'
        summary[arm] = dict(
            round_index=r0['round_index'], round=r0['round'], where=r0['where'], t=r0['t'], log_n=r0['log_n'], work_bits=w,
            bits_without_work=r0['bits_without_work'], e=e, A=r0['A'], n=r0['n'], p0=p0,
            runs=len(rows), tries=tries, forges=forges, nonces=nonces,
            forge_rate=rate, forge_rate_log2=math.log2(rate) if rate else None,
            cp99_low=lo, cp99_high=hi, cp99_contains_p0=lo <= p0 <= hi, cp99_high_le_e_x1_05=hi <= e * 1.05,
            per_run_forge_rate=stats([r['forges'] / r['tries'] for r in rows]),
            per_run_nonces_per_try=stats([r['nonces'] / r['tries'] for r in rows]),
            per_run_wall_s=stats([r['wall_s'] for r in rows]),
            nonces_per_forge=nonces_per_forge, expected_nonces_per_forge=expected_npf,
            nonces_per_forge_within_10pct=(abs(nonces_per_forge / expected_npf - 1) <= 0.10) if nonces_per_forge else False,
            verdict=verdict)
    overall = 'PASS' if summary['A']['verdict'] == 'PASS' and summary['B']['verdict'] == 'PASS' else 'FAIL'
    out = dict(gate_arms=['A', 'B'], overall=overall, arms=summary,
               python=platform.python_version(), method='Clopper-Pearson 99%, exact binomial sums in log space (standard library)')
    (RUNS / 'summary.json').write_text(json.dumps(out, indent=2) + '\n')
    print(json.dumps(out, indent=2))


if __name__ == '__main__':
    mode = sys.argv[1] if len(sys.argv) > 1 else ''
    {'build': build, 'plan': plan, 'runs': runs, 'report': report}.get(mode, lambda: sys.exit(__doc__))()
