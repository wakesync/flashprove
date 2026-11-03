#!/usr/bin/env python3
"""Alternating multi-arm timing of complete stored-proof CPU verification (key + leaf + request).

usage: bench.py <output dir> --cpu N [--reps 10] [--threads 1] label=/path/to/cp_verify ...

Every arm verifies the same fixture (examples/accepted-proof of this checkout) with the same
arguments, pinned with taskset to one CPU. One warmup per arm, then `reps` rounds; each round runs
every arm once, in an order that rotates each round, so no arm always goes first. Each call is
timed by GNU time (wall, user, sys, max RSS). Every honest call must exit 0 with last line YES, or
the run stops. Records the load average and CPU pressure around every call, so a reader can see if
the host was busy. Writes results.json after every call. Output directory must not exist.

The acceptance bar used in PERF-REAL-RESULT.md: at least 10 runs per arm and non-overlapping
min/max wall ranges between the arms compared. This script reports, it does not decide.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import statistics
import subprocess
import time


def sha(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def load():
    return {'loadavg': Path('/proc/loadavg').read_text().strip(),
            'cpu_pressure': Path('/proc/pressure/cpu').read_text().splitlines()[0]}


def stats(xs):
    return {'n': len(xs), 'median': statistics.median(xs), 'mean': statistics.mean(xs),
            'sd': statistics.stdev(xs) if len(xs) > 1 else 0.0, 'min': min(xs), 'max': max(xs)}


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('output', type=Path)
    p.add_argument('arms', nargs='+')
    p.add_argument('--cpu', type=str, required=True, help='taskset CPU list, e.g. 15 or 12-15')
    p.add_argument('--reps', type=int, default=10)
    p.add_argument('--threads', type=int, default=1)
    a = p.parse_args()
    arms = {}
    for spec in a.arms:
        label, _, path = spec.partition('=')
        if not path:
            p.error('arms are label=/path/to/cp_verify')
        arms[label] = Path(path).resolve()
    top = Path(__file__).resolve().parents[3]
    fixture = top / 'examples/accepted-proof'
    a.output.mkdir(parents=True, exist_ok=False)
    ident = (fixture / 'ID.txt').read_text().strip()
    manifest = {
        'scope': 'stored synthetic proof, complete key+leaf+request CPU verification',
        'cpu': a.cpu, 'threads': a.threads, 'reps': a.reps,
        'arms': {k: {'path': str(v), 'sha256': sha(v)} for k, v in arms.items()},
        'fixture_sha256': {str(f.relative_to(fixture)): sha(f) for f in sorted(fixture.rglob('*')) if f.is_file()},
        'hardware': subprocess.check_output(['lscpu'], text=True),
        'kernel': subprocess.check_output(['uname', '-srmo'], text=True).strip(),
        'load_before': load(), 'rows': []}
    out = a.output / 'results.json'

    def persist():
        out.write_text(json.dumps(manifest, indent=2) + '\n')

    def run(label, rep):
        stem = a.output / f'{label}-{rep}'
        cmd = ['taskset', '-c', a.cpu, str(arms[label]), str(fixture / 'config'), str(fixture / 'ivk'),
               str(fixture / 'example.req'), str(fixture / 'example.y'), str(fixture / 'example.proof'),
               '-id', ident, '-j', str(a.threads)]
        before = load()
        with open(f'{stem}.stdout', 'w') as o, open(f'{stem}.stderr', 'w') as e:
            c = subprocess.run(['/usr/bin/time', '-f', '%e %U %S %M', '-o', f'{stem}.time'] + cmd,
                               stdout=o, stderr=e, timeout=300)
        text = Path(f'{stem}.stdout').read_text()
        wall, user, system, rss = Path(f'{stem}.time').read_text().split()[-4:]
        row = {'label': label, 'rep': rep, 'exit': c.returncode, 'last': text.splitlines()[-1] if text else '',
               'wall_s': float(wall), 'user_s': float(user), 'sys_s': float(system), 'max_rss_kib': int(rss),
               'load_before': before, 'load_after': load(), 't': time.time()}
        manifest['rows'].append(row)
        persist()
        if row['exit'] != 0 or row['last'] != 'YES':
            raise SystemExit(f'unexpected verifier result: {row}')
        return row

    labels = list(arms)
    for label in labels:
        run(label, 'warmup')
    for rep in range(a.reps):
        k = rep % len(labels)
        for label in labels[k:] + labels[:k]:
            run(label, rep)
        print(f'rep {rep}: ' + ' '.join(f"{r['label']}={r['wall_s']:.2f}" for r in manifest['rows'] if r['rep'] == rep), flush=True)
    manifest['summary'] = {}
    for label in labels:
        rows = [r for r in manifest['rows'] if r['label'] == label and r['rep'] != 'warmup']
        manifest['summary'][label] = {'wall': stats([r['wall_s'] for r in rows]),
                                      'cpu_user_plus_sys': stats([r['user_s'] + r['sys_s'] for r in rows]),
                                      'max_rss_kib': [r['max_rss_kib'] for r in rows]}
    base = labels[0]
    for label in labels[1:]:
        A, B = manifest['summary'][base]['wall'], manifest['summary'][label]['wall']
        manifest['summary'][label]['vs_' + base] = {
            'median_change_pct': 100 * (B['median'] - A['median']) / A['median'],
            'ranges_overlap': not (B['max'] < A['min'] or A['max'] < B['min'])}
    manifest['load_after'] = load()
    persist()
    print(json.dumps(manifest['summary'], indent=2))


if __name__ == '__main__':
    main()
