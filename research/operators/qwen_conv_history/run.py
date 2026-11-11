#!/usr/bin/env python3
"""Issue #35 conv1d history binding. CPU only.

  run.py build [--ubsan]          compile work/conv_history[-ubsan].bin, write build receipt
  run.py debug                    seeds 101..103 (disjoint from the registered suite), work/ only
  run.py suite [--ubsan] [--out D] registered seeds 1..10, refuses an existing receipt
  run.py summary [--out D]        per-arm counts and size/time stats from the receipts
"""
import hashlib
import json
import pathlib
import platform
import statistics
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[2]
REL = HERE.relative_to(ROOT)
EXP = ROOT / 'experiments/20261111-35-conv-history-binding'
WORK = HERE / 'work'
SEEDS = list(range(1, 11))
DEBUG_SEEDS = [101, 102, 103]


def sh(args, check=True):
    p = subprocess.run(args, cwd=ROOT, text=True, capture_output=True)
    if check and p.returncode:
        raise SystemExit(f'{args}: rc={p.returncode}\n{p.stdout[-2000:]}\n{p.stderr[-2000:]}')
    return p


def exe(ubsan):
    return WORK / ('conv_history-ubsan.bin' if ubsan else 'conv_history.bin')


def build(ubsan, out):
    WORK.mkdir(exist_ok=True)
    binary = exe(ubsan)
    cmd = ['g++', '-std=c++17', '-O2', '-Wall', '-Wextra', '-fno-ipa-modref', '-DBLK_FIELD=2', '-DBLK_HASH=1',
           '-I', 'blocks', f'{REL}/conv_history.cpp', '-o', str(binary.relative_to(ROOT))]
    if ubsan:
        cmd += ['-fsanitize=undefined', '-fno-sanitize-recover=undefined']
    sh(cmd)
    receipt = dict(
        source_commit=sh(['git', 'rev-parse', 'HEAD']).stdout.strip(),
        dirty_tracked=bool(sh(['git', 'diff', '--name-only', 'HEAD']).stdout.strip()),
        compiler=sh(['g++', '--version']).stdout.splitlines()[0],
        python=platform.python_version(),
        command=cmd,
        conv_history_cpp_sha256=hashlib.sha256((HERE / 'conv_history.cpp').read_bytes()).hexdigest(),
        binary_sha256=hashlib.sha256(binary.read_bytes()).hexdigest(),
    )
    if out is not None:
        path = out / f'build{"-ubsan" if ubsan else ""}.json'
        if path.exists():
            raise SystemExit(f'refusing to overwrite {path}')
        path.write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps(receipt))


def run_seeds(seeds, ubsan):
    rows, failures = [], 0
    for s in seeds:
        p = sh([str(exe(ubsan)), 'suite', str(s)], check=False)
        if p.stderr.strip():
            print(p.stderr, file=sys.stderr)
        if p.returncode not in (0, 1):
            raise SystemExit(f'seed {s}: harness error rc={p.returncode}: {p.stderr[-2000:]}')
        failures += p.returncode
        for line in p.stdout.splitlines():
            r = json.loads(line)
            r['ubsan'] = ubsan
            r['stderr_bytes'] = len(p.stderr)
            rows.append(r)
    return rows, failures


def stats(v):
    return dict(n=len(v), median=statistics.median(v), sd=statistics.stdev(v) if len(v) > 1 else 0.0,
                min=min(v), max=max(v))


def summarize(rows):
    arms = {}
    for r in rows:
        if r['arm'] == 'summary' or 'accepted' not in r:
            continue
        key = f"{r['arm']}/{r['sub']}"
        a = arms.setdefault(key, dict(runs=0, accepted=0, as_registered=0, expected_accept=r['expected_accept'], seeds=[]))
        a['runs'] += 1
        a['accepted'] += r['accepted']
        a['as_registered'] += r['as_registered']
        a['seeds'].append(r['seed'])
    sizes = {}
    for arm in ('honest-chain', 'honest-unbound'):
        sel = [r for r in rows if r['arm'] == arm]
        if sel:
            sizes[arm] = {k: stats([r[k] for r in sel]) for k in ('columns', 'relations', 'proof_bytes', 'prove_s', 'verify_s')}
    na = sum(1 for r in rows if r.get('sub') == 'not-applicable-palindrome')
    return dict(arms=arms, sizes=sizes, not_applicable=na,
                all_as_registered=all(a['as_registered'] == a['runs'] for a in arms.values()))


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
        rows, fail = run_seeds(DEBUG_SEEDS, False)
        WORK.mkdir(exist_ok=True)
        (WORK / 'debug.jsonl').write_text(''.join(json.dumps(r) + '\n' for r in rows))
        print(json.dumps(summarize(rows), indent=1))
        print('debug failures', fail)
    elif mode == 'suite':
        out.mkdir(parents=True, exist_ok=True)
        path = out / f'suite{"-ubsan" if ubsan else ""}.jsonl'
        if path.exists():
            raise SystemExit(f'refusing to overwrite {path}')
        rows, fail = run_seeds(SEEDS, ubsan)
        path.write_text(''.join(json.dumps(r) + '\n' for r in rows))
        print(json.dumps(summarize(rows)['arms'], indent=1))
        print('seeds with a check not as registered:', fail)
    elif mode == 'summary':
        res = {}
        for name in ('suite', 'suite-ubsan'):
            p = out / f'{name}.jsonl'
            if p.exists():
                res[name] = summarize([json.loads(l) for l in p.read_text().splitlines()])
        path = out / 'summary.json'
        if path.exists():
            raise SystemExit(f'refusing to overwrite {path}')
        path.write_text(json.dumps(res, indent=2) + '\n')
        print(json.dumps(res, indent=1))
    else:
        print(__doc__)
        sys.exit(2)


if __name__ == '__main__':
    main()
