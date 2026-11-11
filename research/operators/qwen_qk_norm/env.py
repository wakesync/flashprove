#!/usr/bin/env python3
"""Write experiments/20261111-35-qk-rmsnorm/ENV.json (refuses to overwrite). Records no host name or path."""
import hashlib
import json
import os
import pathlib
import platform
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[2]
EXP = ROOT / 'experiments/20261111-35-qk-rmsnorm'


def sh(*a):
    return subprocess.run(list(a), cwd=ROOT, text=True, capture_output=True).stdout.strip()


def cpu_model():
    for line in open('/proc/cpuinfo'):
        if line.startswith('model name'):
            return line.split(':', 1)[1].strip()
    return platform.processor()


def mem_gb():
    for line in open('/proc/meminfo'):
        if line.startswith('MemTotal'):
            return round(int(line.split()[1]) / 1024 / 1024, 1)
    return None


def main():
    path = EXP / 'ENV.json'
    if path.exists():
        sys.exit(f'refusing to overwrite {path}')
    runs = EXP / 'runs'
    builds = {n: json.loads((runs / f'{n}.json').read_text()) for n in ('build', 'build-ubsan')}
    env = dict(
        experiment='20261111-35-qk-rmsnorm',
        commits=dict(
            repo='wakesync/flashprove',
            base_main='ec902e7d2c4c4b29cac66c5d2fabe19b2d175279',
            prereg='669cf39',
            binary_source_commit=builds['build']['source_commit'],
            env_written_at=sh('git', 'rev-parse', 'HEAD'),
            upstream='none (no external code or weights)'),
        toolchain=dict(
            compiler=builds['build']['compiler'],
            release_command=builds['build']['command'],
            ubsan_command=builds['build-ubsan']['command'],
            python=platform.python_version(),
            qk_norm_cpp_sha256=builds['build']['qk_norm_cpp_sha256'],
            release_binary_sha256=builds['build']['binary_sha256'],
            ubsan_binary_sha256=builds['build-ubsan']['binary_sha256'],
            field='Goldilocks (BLK_FIELD=2)', hash='BLK_HASH=1'),
        hardware=dict(
            cpu=cpu_model(), logical_cpus=os.cpu_count(), ram_gb=mem_gb(), provider='KVM cloud VM (cpu-epyc-rome-kvm-16)',
            pinned_cores='4 cores via taskset through the shared heavy-job gate',
            shared_loaded_host=True, gpu=None,
            note='host shared with other build lanes during the runs; timings are descriptive only'),
        seeds=dict(registered=list(range(1, 11)), debug_disjoint=[901, 902, 903],
                   arm_order='odd seed: D16 then D256; even seed: D256 then D16',
                   prover_coins='ToyCoins(seed*100 + k), fixed, deterministic'),
        os=dict(kernel=platform.release(), system=platform.system()),
    )
    path.write_text(json.dumps(env, indent=2) + '\n')
    print(json.dumps(env, indent=1))


if __name__ == '__main__':
    main()
