#!/usr/bin/env python3
"""Bounded CPU receipt. No network/GPU dependencies."""
import hashlib
import json
import pathlib
import platform
import resource
import subprocess
import time
root = pathlib.Path(__file__).resolve().parents[3]
here = pathlib.Path(__file__).resolve().parent
commands = [
    ['g++', '-std=c++17', '-O2', '-Wall', '-Wextra', '-fno-ipa-modref',
     '-DBLK_FIELD=2', '-DBLK_HASH=1', '-I', 'blocks',
     'research/operators/affine_rows/test.cpp', '-o', 'research/operators/affine_rows/test.bin'],
    ['research/operators/affine_rows/test.bin'],
]
resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
report = {'platform': platform.platform(), 'compiler': subprocess.check_output(['g++', '--version'], text=True), 'commands': [], 'sha256': {}}
for path in [here / 'product.h', here / 'test.cpp', here / 'record.py',
             here.parent / 'shared_wires/product.h', here.parent / 'public_binding/product.h', root / 'blocks/toy/product.h',
             root / 'blocks/iop/relation.h', root / 'blocks/iop/iopp.h', root / 'blocks/numbers/blocks.h']:
    report['sha256'][str(path.relative_to(root))] = hashlib.sha256(path.read_bytes()).hexdigest()
for command in commands:
    start = time.monotonic()
    run = subprocess.run(command, cwd=root, capture_output=True, text=True, timeout=300)
    report['commands'].append({'argv': command, 'exit': run.returncode,
                              'seconds': round(time.monotonic()-start, 3),
                              'stdout': run.stdout, 'stderr': run.stderr})
    (here / 'evidence.json').write_text(json.dumps(report, indent=2)+'\n')
    print(run.stdout, end='')
    print(run.stderr, end='')
    if run.returncode:
        raise SystemExit(run.returncode)
for case in range(8):
    command = ['research/operators/affine_rows/test.bin', str(case)]
    start = time.monotonic()
    run = subprocess.run(command, cwd=root, capture_output=True, text=True, timeout=30)
    report['commands'].append({'argv': command, 'exit': run.returncode, 'expected_exit': -6,
                              'seconds': round(time.monotonic()-start, 3),
                              'stdout': run.stdout, 'stderr': run.stderr})
    (here / 'evidence.json').write_text(json.dumps(report, indent=2)+'\n')
    if run.returncode != -6:
        raise SystemExit('invalid constructor did not SIGABRT: '+str(case))
report['sha256']['research/operators/affine_rows/test.bin'] = hashlib.sha256((here / 'test.bin').read_bytes()).hexdigest()
(here / 'evidence.json').write_text(json.dumps(report, indent=2)+'\n')
print('record: PASS; 8 invalid trusted constructors SIGABRT (not parser rejection)')
