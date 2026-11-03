#!/usr/bin/env python3
"""Reproduce the five additional seed checks; no performance conclusion is drawn."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

p = argparse.ArgumentParser()
p.add_argument('--a', required=True)
p.add_argument('--b', required=True)
p.add_argument('--out', required=True)
a = p.parse_args()
out = Path(a.out)
out.mkdir(parents=True, exist_ok=False)
records = []
for seed in range(1, 6):
    arms = []
    for arm, binary in [('A', a.a), ('B', a.b)]:
        dest = out / f'{seed}-{arm}'
        dest.mkdir()
        run = subprocess.run([binary, str(dest), str(seed)], capture_output=True, text=True, timeout=120)
        (dest / 'stdout.txt').write_text(run.stdout)
        (dest / 'stderr.txt').write_text(run.stderr)
        assert run.returncode == 0 and run.stdout.endswith('ok\n'), (seed, arm, run.stderr)
        arms.append({f.name: f.read_bytes() for f in dest.iterdir() if f.suffix in ('.bin', '.root')})
    assert len(arms[0]) == 7 and arms[0] == arms[1]
    records.append({'seed': seed, 'byte_identical': True, 'honest_accepted': 5, 'mutations_rejected': 5,
                    'artifacts': {name: {'bytes': len(b), 'sha256': hashlib.sha256(b).hexdigest()} for name, b in arms[0].items()}})
(out / 'hashes.json').write_text(json.dumps(records, indent=2) + '\n')
print('5 additional seeds: seven artifacts byte-identical, honest verification and five mutations pass per arm')
