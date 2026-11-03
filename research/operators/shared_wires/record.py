#!/usr/bin/env python3
"""Bounded CPU receipt. No network/GPU dependencies."""
import hashlib
import json
import pathlib
import platform
import subprocess
import time
root = pathlib.Path(__file__).resolve().parents[3]
here = pathlib.Path(__file__).resolve().parent
commands = [
    ['g++', '-std=c++17', '-O2', '-Wall', '-Wextra', '-fno-ipa-modref',
     '-DBLK_FIELD=2', '-DBLK_HASH=1', '-I', 'blocks',
     'research/operators/shared_wires/test.cpp', '-o', 'research/operators/shared_wires/test.bin'],
    ['research/operators/shared_wires/test.bin'],
]
report = {'platform': platform.platform(), 'commands': [], 'sha256': {}}
for path in [here / 'product.h', here / 'test.cpp', here / 'record.py',
             here.parent / 'public_binding/product.h', root / 'blocks/toy/product.h',
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
print('record: PASS')
