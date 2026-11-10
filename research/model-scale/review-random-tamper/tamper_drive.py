#!/usr/bin/env python3
# Review-only driver: gen small fixtures, run honest run.bin and tamper.bin, then corrupted fixtures.
import json, subprocess, sys, os
from pathlib import Path
here = Path(__file__).resolve().parent
ms = here.parents[1] / 'flashprove-review-pr42b' / 'research' / 'model-scale'
plans = {int(x[0]): x[2:] for x in (l.split() for l in (ms / 'plan_t10.txt').read_text().split('\n')) if len(x) > 2 and x[1] != '0'}
fx = here / 'fx'; fx.mkdir(exist_ok=True)
N = int(sys.argv[1]) if len(sys.argv) > 1 else 20
out = []
for d, t, b in [(4, 4, 4), (8, 2, 8), (16, 1, 12), (8, 1, 12)]:
    f = fx / f'd{d}_t{t}_b{b}.bin'
    g = json.loads(subprocess.run([sys.executable, str(ms / 'gen.py'), str(d), str(d), str(t), '1', str(b), '7', str(f)], capture_output=True, text=True, check=True).stdout.strip().split('\n')[-1])
    L = g['log_len']
    base = [str(f), '10', '6', str(L)] + plans[L]
    r = subprocess.run(['taskset', '-c', '12', str(here / 'run.bin')] + base, capture_output=True, text=True)
    hon = json.loads(r.stdout.strip().split('\n')[-1])
    r2 = subprocess.run(['taskset', '-c', '12', str(here / 'tamper.bin')] + base + ['--', str(N), str(d * 1000 + t * 10 + b)], capture_output=True, text=True)
    tam = r2.stdout.strip().split('\n')
    # fixture-level corruptions: a/b/c cell flips that break a*b=c must be refused by the host reference check before proving
    raw = bytearray(f.read_bytes()); n = g['columns']; bad = []
    for name, off in [('a0', 128), ('c_mid', 128 + 8 * (2 * n + n // 2)), ('affine_target0', None)]:
        if off is None:
            continue
        x = bytearray(raw); x[off] ^= 1; p = fx / f'bad_{name}.bin'; p.write_bytes(x)
        rb = subprocess.run(['taskset', '-c', '12', str(here / 'run.bin'), str(p)] + base[1:], capture_output=True, text=True)
        bad.append(dict(mutation=name, exit=rb.returncode, out=rb.stdout.strip()[-120:]))
        p.unlink()
    row = dict(point=f'd{d}_t{t}_b{b}', log_len=L, columns=n, honest_exit=r.returncode, honest=hon, tamper_exit=r2.returncode, tamper=tam[-3:], fixture_corrupt=bad)
    print(json.dumps(row), flush=True); out.append(row)
    f.unlink()
(here / 'tamper-results.json').write_text(json.dumps(out, indent=2) + '\n')
