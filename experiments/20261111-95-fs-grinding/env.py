#!/usr/bin/env python3
"""Writes ENV.json for this experiment (run from the repository root after the registered runs)."""
import json
import os
import pathlib
import platform
import subprocess

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def sh(args):
    return subprocess.run(args, cwd=ROOT, text=True, capture_output=True).stdout.strip()


def cpu_model():
    for line in pathlib.Path('/proc/cpuinfo').read_text().splitlines():
        if line.startswith('model name'):
            return line.split(':', 1)[1].strip()
    return platform.processor()


def mem_gb():
    for line in pathlib.Path('/proc/meminfo').read_text().splitlines():
        if line.startswith('MemTotal'):
            return round(int(line.split()[1]) / 1024 / 1024, 1)
    return None


build = json.loads((HERE / 'runs/build.json').read_text())
meta = json.loads((HERE / 'runs/runs-meta.json').read_text())
env = dict(
    experiment='20261111-95-fs-grinding',
    commits=dict(flashprove_base='7c40dd9fc728ab99d1659dc47af59c9d53e67107', prereg='5b89ea5', harness=sh(['git', 'rev-parse', 'HEAD']),
                 profile_source='research/operators/qwen_ops/proof.cpp (merged in PR #67), unmodified, included with main renamed'),
    toolchain=dict(compiler=build['compiler'], command=build['command'], python=platform.python_version(),
                   grind_cpp_sha256=build['grind_cpp_sha256'], proof_cpp_sha256=build['proof_cpp_sha256'], binary_sha256=build['binary_sha256']),
    hardware=dict(cpu=cpu_model(), logical_cores=os.cpu_count(), ram_gb=mem_gb(), os=platform.system() + ' ' + platform.release(),
                  provider='shared lane host (KVM), loaded by other lanes; the build ran through the heavy-job gate pinned to 6 cores (10-15); the registered runs (about 50 s of single-threaded CPU in total) ran pinned to the same cores without the gate',
                  gpu='none'),
    seeds=meta['seeds'],
    tries_per_run=meta['tries'],
    arms=meta['arms'],
    runs_binary_sha256=meta['binary_sha256'],
    note='Counts, not timings, are the measurement; wall times are for information only.',
)
(HERE / 'ENV.json').write_text(json.dumps(env, indent=2) + '\n')
print(json.dumps(env, indent=2))
