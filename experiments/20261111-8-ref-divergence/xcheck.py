#!/usr/bin/env python3
"""Kill-criterion check: refs.py integer lowerings must reproduce the committed C++ fixtures word for word.

Builds research/operators/qwen_ops/reference_crosscheck.cpp (unchanged, same flags as crosscheck.py) into this
experiment's ignored work/ directory, then applies refs.int_* to every fixture input and compares outputs.
Writes runs/crosscheck.json.
"""
import hashlib
import json
import subprocess

import numpy as np

import refs

ROOT = refs.ROOT
WORK = refs.HERE / 'work'
RUNS = refs.HERE / 'runs'


def main():
    WORK.mkdir(exist_ok=True)
    RUNS.mkdir(exist_ok=True)
    exe = WORK / 'crosscheck.bin'
    src = 'research/operators/qwen_ops/reference_crosscheck.cpp'
    subprocess.run(['g++', '-std=c++17', '-O2', '-fno-ipa-modref', '-DBLK_FIELD=2', '-DBLK_HASH=1', '-I', 'blocks',
                    src, '-o', str(exe)], cwd=ROOT, check=True)
    out = subprocess.run([str(exe)], cwd=ROOT, check=True, text=True, capture_output=True).stdout
    cases, words, mismatches = 0, 0, []
    per_op = {}
    for line in out.splitlines():
        z = json.loads(line)
        op, f, x = z['op'], z['F'], np.array(z['x'], dtype=np.int64)
        if op == 'nonlinear':
            y = [int(refs.int_nonlinear(n, x[:1], f)[0]) for n in refs.NONLINEAR]
        elif op == 'conv':
            y = refs.int_conv(x[None, :7], x[None, 7:11], f)[0].tolist()
        elif op in ('l2', 'rms'):
            yy, key = refs.int_norm(op, x[None, :], f)
            assert 0 <= key[0] < 4096
            y = yy[0].tolist()
        else:
            y = refs.int_rotary(x[None, :], np.array([z['position']]), f)[0].tolist()
        cases += 1
        words += len(y)
        per_op[op] = per_op.get(op, 0) + 1
        if y != z['y']:
            mismatches.append(dict(op=op, F=f, seed=z['seed']))
    result = dict(cases=cases, output_words=words, matched=cases - len(mismatches), mismatches=mismatches,
                  per_op=per_op, cpp_stdout_sha256=hashlib.sha256(out.encode()).hexdigest(),
                  source=src, source_sha256=hashlib.sha256((ROOT / src).read_bytes()).hexdigest())
    (RUNS / 'crosscheck.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({k: v for k, v in result.items() if k != 'mismatches'}))
    assert not mismatches and cases == 150, 'KILL: integer lowering does not reproduce the C++ fixtures'


if __name__ == '__main__':
    main()
