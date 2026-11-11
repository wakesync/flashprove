#!/usr/bin/env python3
"""Issue #35 per-head q/k RMSNorm proof constraint. CPU only, Python standard library.

  run.py build [--ubsan] [--out D]   compile work/qk_norm[-ubsan].bin, write build receipt into D
  run.py debug                       seeds 901..903 (disjoint from the registered suite), work/ only
  run.py suite [--ubsan] [--out D]   registered seeds 1..10, arms alternating (odd: D16,D256; even: D256,D16)
  run.py fidelity [--out D]          float64 reference vs the fixed-point outputs of the release fixtures
  run.py summary [--out D]           per-case counts and size/time stats from the receipts

Default out dir: experiments/20261111-35-qk-rmsnorm/runs. Every receipt refuses to overwrite.
"""
import hashlib
import json
import math
import os
import pathlib
import platform
import statistics
import subprocess
import sys
import time

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[2]
REL = HERE.relative_to(ROOT)
EXP = ROOT / 'experiments/20261111-35-qk-rmsnorm'
WORK = HERE / 'work'
SEEDS = list(range(1, 11))
DEBUG_SEEDS = [901, 902, 903]
ARMS = (16, 256)


def sh(args, check=True):
    p = subprocess.run(args, cwd=ROOT, text=True, capture_output=True)
    if check and p.returncode:
        raise SystemExit(f'{args}: rc={p.returncode}\n{p.stdout[-2000:]}\n{p.stderr[-2000:]}')
    return p


def exe(ubsan):
    return WORK / ('qk_norm-ubsan.bin' if ubsan else 'qk_norm.bin')


def refuse(path):
    if path.exists():
        raise SystemExit(f'refusing to overwrite {path}')


def build(ubsan, out):
    WORK.mkdir(exist_ok=True)
    binary = exe(ubsan)
    cmd = ['g++', '-std=c++17', '-O2', '-Wall', '-Wextra', '-fno-ipa-modref', '-DBLK_FIELD=2', '-DBLK_HASH=1',
           '-I', 'blocks', f'{REL}/qk_norm.cpp', '-o', str(binary.relative_to(ROOT))]
    if ubsan:
        cmd += ['-fsanitize=undefined', '-fno-sanitize-recover=undefined']
    path = None
    if out is not None:
        path = out / f'build{"-ubsan" if ubsan else ""}.json'
        refuse(path)
    sh(cmd)
    receipt = dict(
        source_commit=sh(['git', 'rev-parse', 'HEAD']).stdout.strip(),
        dirty_tracked=bool(sh(['git', 'diff', '--name-only', 'HEAD']).stdout.strip()),
        compiler=sh(['g++', '--version']).stdout.splitlines()[0],
        python=platform.python_version(),
        command=cmd,
        qk_norm_cpp_sha256=hashlib.sha256((HERE / 'qk_norm.cpp').read_bytes()).hexdigest(),
        binary_sha256=hashlib.sha256(binary.read_bytes()).hexdigest(),
    )
    if path is not None:
        path.write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps(receipt))


def order(seed):
    return ARMS if seed % 2 else ARMS[::-1]


def run_seeds(seeds, ubsan, fixdir):
    rows, failures = [], 0
    fixdir.mkdir(parents=True, exist_ok=True)
    for s in seeds:
        for D in order(s):
            fx = fixdir / f'fixtures-D{D}-seed{s}{"-ubsan" if ubsan else ""}.jsonl'
            refuse(fx)
            t0 = time.time()
            p = sh([str(exe(ubsan)), 'suite', str(D), str(s), str(fx)], check=False)
            wall = time.time() - t0
            if p.stderr.strip():
                print(p.stderr, file=sys.stderr)
            if p.returncode not in (0, 1):
                raise SystemExit(f'D{D} seed {s}: harness error rc={p.returncode}: {p.stderr[-2000:]}')
            failures += p.returncode
            for line in p.stdout.splitlines():
                r = json.loads(line)
                r['ubsan'] = ubsan
                r['stderr_bytes'] = len(p.stderr)
                r['process_wall_s'] = wall
                rows.append(r)
            print(f'D{D} seed {s} rc={p.returncode} wall={wall:.1f}s', flush=True)
    return rows, failures


def stats(v):
    return dict(n=len(v), median=statistics.median(v), sd=statistics.stdev(v) if len(v) > 1 else 0.0,
                min=min(v), max=max(v))


def summarize(rows):
    cases = {}
    for r in rows:
        if 'accepted' not in r:
            continue
        key = f"{r['arm']}/{r['case']}/{r['kind']}"
        a = cases.setdefault(key, dict(runs=0, accepted=0, as_registered=0, expected_accept=r['expected_accept'], seeds=[]))
        a['runs'] += 1
        a['accepted'] += r['accepted']
        a['as_registered'] += r['as_registered']
        a['seeds'].append(r['seed'])
    sizes = {}
    for arm in ('D16', 'D256'):
        sel = [r for r in rows if r.get('arm') == arm and r.get('case') == 'honest' and r.get('kind') == 'uniform']
        if sel:
            sizes[arm] = {k: stats([r[k] for r in sel]) for k in ('columns', 'relations', 'proof_bytes', 'prove_s', 'verify_s')}
    hostile = [a for k, a in cases.items() if not a['expected_accept']]
    complete = [r for r in rows if r.get('kind') == 'complete']
    return dict(cases=cases, sizes=sizes,
                hostile_subcases=sum(a['runs'] for a in hostile),
                hostile_rejected=sum(a['runs'] - a['accepted'] for a in hostile),
                complete_malicious=len(complete),
                complete_rejected=sum(1 for r in complete if not r['accepted']),
                honest=sum(a['runs'] for k, a in cases.items() if a['expected_accept']),
                honest_accepted=sum(a['accepted'] for k, a in cases.items() if a['expected_accept']),
                stderr_bytes=sum(r.get('stderr_bytes', 0) for r in rows if r.get('case') == 'summary'),
                all_as_registered=all(a['as_registered'] == a['runs'] for a in cases.values()))


# ---- fidelity (float64 reference on the dequantized same integers) ----
def fidelity_rows(fixdir, seeds):
    out = []
    for s in seeds:
        for D in ARMS:
            fx = fixdir / f'fixtures-D{D}-seed{s}.jsonl'
            for line in fx.read_text().splitlines():
                st = json.loads(line)
                S = float(1 << st['F'])
                for h, (x, y) in enumerate(zip(st['x'], st['y'])):
                    g = st['gq'] if h < st['Hq'] else st['gk']
                    xf = [v / S for v in x]
                    ms = sum(v * v for v in xf) / len(xf)
                    inv = 1.0 / math.sqrt(ms + 1e-6)
                    ref = [gi / S * xi * inv for gi, xi in zip(g, xf)]
                    got = [v / S for v in y]
                    nref = math.sqrt(sum(v * v for v in ref))
                    nerr = math.sqrt(sum((a - b) ** 2 for a, b in zip(got, ref)))
                    out.append(dict(arm=f'D{D}', dist=st['dist'], seed=s, head=h,
                                    rel_l2=(nerr / nref) if nref > 0 else None,
                                    exact_zero=(nref == 0 and all(v == 0 for v in y)),
                                    max_abs=max(abs(a - b) for a, b in zip(got, ref))))
    return out


def fidelity_summary(rows):
    res = {}
    for arm in ('D16', 'D256'):
        for dist in ('uniform', 'outlier', 'low', 'unit-spike', 'zero'):
            sel = [r for r in rows if r['arm'] == arm and r['dist'] == dist]
            if not sel:
                continue
            key = f'{arm}/{dist}'
            if dist == 'zero':
                res[key] = dict(heads=len(sel), exact_zero=sum(r['exact_zero'] for r in sel))
                continue
            per_seed_med, per_seed_max = [], []
            for s in sorted({r['seed'] for r in sel}):
                v = [r['rel_l2'] for r in sel if r['seed'] == s]
                per_seed_med.append(statistics.median(v))
                per_seed_max.append(max(v))
            allv = [r['rel_l2'] for r in sel]
            res[key] = dict(heads=len(sel), seeds=len(per_seed_med),
                            median_of_seed_medians=statistics.median(per_seed_med),
                            sd_of_seed_medians=statistics.stdev(per_seed_med),
                            min_seed_median=min(per_seed_med), max_seed_median=max(per_seed_med),
                            median_of_seed_max=statistics.median(per_seed_max),
                            sd_of_seed_max=statistics.stdev(per_seed_max),
                            max_rel_l2=max(allv), median_rel_l2_all_heads=statistics.median(allv),
                            max_abs_err=max(r['max_abs'] for r in sel))
    return res


def main():
    args = sys.argv[1:]
    mode = args[0] if args else ''
    ubsan = '--ubsan' in args
    out = EXP / 'runs'
    if '--out' in args:
        out = (ROOT / args[args.index('--out') + 1]).resolve()
    if mode == 'build':
        out.mkdir(parents=True, exist_ok=True)
        build(ubsan, out)
    elif mode == 'debug':
        build(False, None)
        dbg = WORK / f'debug-{os.getpid()}'
        rows, fail = run_seeds(DEBUG_SEEDS, False, dbg)
        (dbg / 'debug.jsonl').write_text(''.join(json.dumps(r) + '\n' for r in rows))
        s = summarize(rows)
        s.pop('cases')
        print(json.dumps(s, indent=1))
        print(json.dumps(fidelity_summary(fidelity_rows(dbg, DEBUG_SEEDS)), indent=1))
        print('debug failures', fail)
    elif mode == 'suite':
        out.mkdir(parents=True, exist_ok=True)
        path = out / f'suite{"-ubsan" if ubsan else ""}.jsonl'
        refuse(path)
        start = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
        print('suite start', start, flush=True)
        rows, fail = run_seeds(SEEDS, ubsan, out / 'fixtures')
        path.write_text(''.join(json.dumps(r) + '\n' for r in rows))
        s = summarize(rows)
        s.pop('cases')
        print(json.dumps(s, indent=1))
        print('suite start', start, 'end', time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()))
        print('processes with a check not as registered:', fail)
    elif mode == 'fidelity':
        path = out / 'fidelity.json'
        refuse(path)
        rows = fidelity_rows(out / 'fixtures', SEEDS)
        res = dict(per_head=rows, summary=fidelity_summary(rows))
        path.write_text(json.dumps(res, indent=1) + '\n')
        print(json.dumps(res['summary'], indent=1))
    elif mode == 'summary':
        res = {}
        for name in ('suite', 'suite-ubsan'):
            p = out / f'{name}.jsonl'
            if p.exists():
                res[name] = summarize([json.loads(l) for l in p.read_text().splitlines()])
        path = out / 'summary.json'
        refuse(path)
        path.write_text(json.dumps(res, indent=2) + '\n')
        print(json.dumps({k: {kk: vv for kk, vv in v.items() if kk != 'cases'} for k, v in res.items()}, indent=1))
    else:
        print(__doc__)
        sys.exit(2)


if __name__ == '__main__':
    main()
