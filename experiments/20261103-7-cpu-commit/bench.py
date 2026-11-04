#!/usr/bin/env python3
"""Alternating AB/BA CPU experiment. Run from repository root, no GPU access."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import statistics
import subprocess

p = argparse.ArgumentParser()
p.add_argument('--a', required=True)
p.add_argument('--b', required=True)
p.add_argument('--out', required=True)
p.add_argument('--cpu', type=int, default=13)
p.add_argument('--runs', type=int, default=10)
a = p.parse_args()
assert a.runs >= 10
out = Path(a.out)
out.mkdir(parents=True, exist_ok=False)
rows = []
reference = None
for pair in range(-2, a.runs):
    for arm in ('AB' if pair % 2 == 0 else 'BA'):
        label = f'{pair:02d}-{arm}' if pair >= 0 else f'warm{-pair}-{arm}'
        folder = out / label
        folder.mkdir()
        load = list(os.getloadavg())
        cmd = ['taskset', '-c', str(a.cpu), a.a if arm == 'A' else a.b, str(folder), '0']
        run = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        (folder / 'stdout.txt').write_text(run.stdout)
        (folder / 'stderr.txt').write_text(run.stderr)
        assert run.returncode == 0 and run.stdout.endswith('ok\n'), (label, run.returncode, run.stderr)
        stats = {line.split()[0]: float(line.split()[1]) for line in run.stdout.splitlines() if len(line.split()) == 2}
        stats['commit'] = sum(stats[k] for k in ('configure', 'tables', 'make_key', 'make_entry'))
        blobs = {f.name: f.read_bytes() for f in folder.iterdir() if f.suffix in ('.bin', '.root')}
        assert len(blobs) == 7
        if reference is None:
            reference = blobs
        assert blobs == reference, ('nonidentical output', label)
        hashes = {name: {'bytes': len(b), 'sha256': hashlib.sha256(b).hexdigest()} for name, b in blobs.items()}
        rows.append({'pair': pair, 'arm': arm, 'warmup': pair < 0, 'load': load, 'seconds': stats, 'artifacts': hashes})
        (out / 'raw.json').write_text(json.dumps(rows, indent=2) + '\n')
summary = {}
for metric in ('total_generate', 'commit', 'prove_batch', 'configure', 'tables', 'make_key', 'make_entry', 'cpu_generate'):
    summary[metric] = {}
    for arm in 'AB':
        values = [r['seconds'][metric] for r in rows if not r['warmup'] and r['arm'] == arm]
        summary[metric][arm] = {'n': len(values), 'median': statistics.median(values), 'sd': statistics.stdev(values), 'min': min(values), 'max': max(values)}
    x, y = summary[metric]['A'], summary[metric]['B']
    summary[metric]['median_reduction_percent'] = 100 * (1-y['median']/x['median'])
    summary[metric]['nonoverlap'] = y['max'] < x['min']
primary = summary['total_generate']
summary['verdict'] = 'PASS' if primary['nonoverlap'] and primary['median_reduction_percent'] >= 5 else 'FAIL'
(out / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
print(json.dumps(summary, indent=2))
