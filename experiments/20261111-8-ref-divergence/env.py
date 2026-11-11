#!/usr/bin/env python3
"""Write ENV.json for this experiment (host facts are read, not typed)."""
import hashlib
import json
import os
import platform
import subprocess

import numpy as np

import refs

H = refs.HERE


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def sh(*a):
    return subprocess.run(a, capture_output=True, text=True, cwd=refs.ROOT).stdout.strip()


cpu = next((l.split(':', 1)[1].strip() for l in open('/proc/cpuinfo') if l.startswith('model name')), None)
mem = next((int(l.split()[1]) for l in open('/proc/meminfo') if l.startswith('MemTotal')), None)
files = ['PREREG.md', 'splits.py', 'refs.py', 'xcheck.py', 'test_formats.py', 'harness.py', 'summarise.py',
         'splits/MANIFEST.json', 'runs/fp8-scales.json', 'runs/crosscheck.json', 'runs/format-selftest.json',
         'runs/calibration.jsonl', 'runs/heldout.jsonl', 'runs/stress.jsonl', 'runs/summary.json']
env = {
    'commits': {
        'base': 'ec902e7d2c4c4b29cac66c5d2fabe19b2d175279',
        'prereg': 'b25e590c747b55051113b7be0589d56b0d93d28f',
        'splits_frozen': 'a0c5f54dd6ca74b5e13806ac21869da4319ee560',
        'harness': 'b056d2d32c89a8d67437ca42a4e6695f689510be',
        'format_selftest': '0b0ae04c612885a49f0b878451b7dcb326dea6c6',
        'calibration_and_fp8_scales': '33cf923b718bc86d8d3aa65386127b593f6d8959',
        'heldout_and_stress_runs': 'fa0693676b802cc9e506027ab9064efa5e4dcc41',
        'operators_under_test': 'research/operators/qwen_ops at base (PR #67), unchanged; tables read from research/operators/qwen_ops/tables',
    },
    'toolchain': {
        'python': platform.python_version(),
        'numpy': np.__version__,
        'compiler': sh('g++', '--version').splitlines()[0],
        'crosscheck_build_flags': ['-std=c++17', '-O2', '-fno-ipa-modref', '-DBLK_FIELD=2', '-DBLK_HASH=1', '-I', 'blocks'],
        'threads_env': {'OPENBLAS_NUM_THREADS': '1', 'OMP_NUM_THREADS': '1'},
        'float_notes': 'BF16/E4M3 rounding by refs.round_to_format (float64 arithmetic, np.rint ties-to-even); FP32 compute via numpy float32 ufuncs (exp/log1p/sqrt/cos/sin as numpy implements them, not correctly rounded)',
        'platform': platform.system(),
        'kernel': platform.release(),
    },
    'hardware': {
        'key': 'cpu-epyc-rome-kvm-16', 'cpu': cpu, 'logical_cpus': os.cpu_count(), 'memory_kib': mem,
        'affinity': 'taskset -c 14,15 (2 cores)', 'shared_loaded_host': True, 'exclusive_core': False,
        'heavy_gate': False, 'heavy_gate_note': 'each split is under 1 s of CPU (cpu_s_seed in the run rows), far under the 2-min gate threshold registered in PREREG Runs',
        'gpu': False,
    },
    'seeds': {'calibration': list(range(1, 6)), 'heldout': list(range(1001, 1006)), 'stress': list(range(2001, 2006)),
              'rng': 'numpy.random.Generator(PCG64(seed))'},
    'debug_seeds_not_evidence': [9001],
    'file_sha256': {f: sha(H / f) for f in files},
}
(H / 'ENV.json').write_text(json.dumps(env, indent=2) + '\n')
print('ok', len(files))
