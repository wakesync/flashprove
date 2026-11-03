#!/usr/bin/env python3
"""Independent CPU mutation audit; run after run.py from repository root.
SPDX-License-Identifier: Apache-2.0
Uses the unmodified upstream alteration helpers, copyright Anthropic PBC.
"""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shlex
import struct
import subprocess
import sys
import tempfile
import time

ROOT = Path.cwd().resolve()
if os.geteuid() == 0:
    sys.exit('Refusing root')
OUT = ROOT / sys.argv[1]
OUT.mkdir(parents=True, exist_ok=False)
WORK = Path(tempfile.mkdtemp(prefix='flashprove-audit-'))
spec = importlib.util.spec_from_file_location('alter', ROOT / 'examples/rejected-proofs/try_altered_copies.py')
a = importlib.util.module_from_spec(spec)
spec.loader.exec_module(a)
verifier = ROOT / 'bin/cp_verify'
records = []

def scrub(s):
    return s.replace(str(ROOT), '<REPO>').replace(str(WORK), '<WORK>').replace(str(Path.home()), '<HOME>')

def run(command):
    start = time.monotonic()
    p = subprocess.run(list(map(str, command)), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=120)
    # Preserve merged stdout/stderr in emission order.
    text = p.stdout
    lines = text.strip().split('\n')
    record = dict(command=scrub(shlex.join(map(str, command))), exit=p.returncode,
                  elapsed_seconds=round(time.monotonic()-start, 3), last_line=lines[-1])
    records.append(record)
    (OUT / ('%03d.log' % len(records))).write_text(scrub(text))
    return p.returncode, lines

a.run = run
failures = []
for example in a.TABLES:
    a.EXAMPLE = ROOT / 'examples' / example
    a.stated_policy.cache_clear()
    a.exact_places.cache_clear()
    true_id = a.read('ID.txt').decode().strip()
    rows = [('honest control', {}, true_id, (0, a.stated_policy()[1]))]
    rows += [(desc, changed, cid, (1, expected)) for desc, changed, cid, expected in
             a.cases(verifier, ROOT / 'examples/rejected-proofs' / a.TABLES[example])]
    req = a.read('example.req')
    T = len(req)//4-2
    r, e = struct.unpack('<II', req[-8:])
    def word(i, value):
        return req[:i*4] + struct.pack('<I', value) + req[(i+1)*4:]
    rows += [
        ('request range start changed', {'example.req': word(T, r-1)}, true_id, (1, 'NO: proof-refused')),
        ('request range end changed', {'example.req': word(T+1, e-1)}, true_id, (1, 'NO: statement-range' if e == T else 'NO: proof-refused')),
        ('empty proof', {'example.proof': b''}, true_id, (1, 'NO: cp-proof-length')),
        ('proof header bit', {'example.proof': a.altered(a.read('example.proof'), 0, 'flip')}, true_id, (1, 'NO: cp-proof-head')),
        ('empty key', {'ivk/key.bin': b''}, true_id, (1, 'NO: cp-key-length')),
        ('empty leaf', {'ivk/leaf/0.bin': b''}, true_id, (1, 'NO: entry-refused')),
        ('token outside vocabulary', {'example.req': word(0, 512)}, true_id, (1, 'NO: token-range')),
        ('request range inverted', {'example.req': word(T, e)}, true_id, (1, 'NO: statement-range')),
    ]
    if e == T:
        rows.append(('range end changed with valid zero sentinel', {'example.req': word(T+1, e-1), 'example.y': struct.pack('<I', 0)}, true_id, (1, 'NO: proof-refused')))
    # Negative policy selection tests operate on CLI values, not on attacker-controlled config.
    for i, (desc, changed, cid, expected) in enumerate(rows):
        directory = WORK / (example + '-%02d' % i)
        directory.mkdir()
        code, lines = a.check(verifier, directory, changed, cid)
        records[-1].update(example=example, case=desc, expected_exit=expected[0], expected_last=expected[1],
            changed_sha256={k: hashlib.sha256(v).hexdigest() for k,v in changed.items()}, commitment_id=cid)
        if (code, lines[-1]) != expected:
            failures.append((example, desc, code, lines[-1], expected))
    base = a.EXAMPLE
    command = [verifier, base/'config', base/'ivk', base/'example.req', base/'example.y', base/'example.proof', '-id', true_id, '-q']
    policy = 'clipped-gap,9244130,323342,1,16,8' if example.endswith('clipped-gap') else 'clipped-gap,9244130,323343,1,16,8'
    code, lines = run(command + ['-policy', policy])
    records[-1].update(example=example, case='wrong trusted policy', expected_exit=1, expected_last='NO: policy')
    if (code, lines[-1]) != (1, 'NO: policy'):
        failures.append((example, 'wrong trusted policy', code, lines[-1]))

(OUT/'results.json').write_text(json.dumps(records, indent=2)+'\n')
(OUT/'failures.json').write_text(json.dumps(failures, indent=2)+'\n')
print(json.dumps({'calls':len(records), 'failures':failures}, indent=2))
sys.exit(bool(failures))
