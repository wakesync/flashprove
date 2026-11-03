#!/usr/bin/env python3
"""CPU-only reproduction. Run from repository root; writes a new evidence folder.
SPDX-License-Identifier: Apache-2.0
"""
import hashlib
import json
import os
from pathlib import Path
import platform
import shlex
import subprocess
import sys
import tempfile
import time

PIN = '9e2bdd8ff5bf9c62f18263d7dac189b0400b260c'
ROOT = Path.cwd().resolve()
if os.geteuid() == 0:
    sys.exit('Refusing root')
if not (ROOT / 'verifier/build.sh').is_file():
    sys.exit('Run from repository root')
OUT = ROOT / (sys.argv[1] if len(sys.argv) > 1 else 'research/reproduction/evidence')
OUT.mkdir(parents=True, exist_ok=False)
WORK = Path(tempfile.mkdtemp(prefix='flashprove-cpu-'))
env = dict(os.environ, MAKEFLAGS='-j4', OMP_NUM_THREADS='4', LC_ALL='C')
# Keep upstream default compiler/flags and avoid inherited make overrides.
for name in ('CXX', 'CXXFLAGS', 'MFLAGS'):
    env.pop(name, None)

def scrub(text):
    text = text.replace(str(ROOT), '<REPO>').replace(str(WORK), '<WORK>')
    for ancestor in ROOT.parents:
        if ancestor == Path.home() or ancestor == Path('/'):
            break
        text = text.replace(str(ancestor), '<CHECKOUT_ANCESTOR>')
    return text.replace(str(Path.home()), '<HOME>')

results = []
def run(name, args, expected=0, cwd=ROOT):
    start = time.monotonic()
    p = subprocess.run(args, cwd=cwd, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, errors='backslashreplace')
    elapsed = time.monotonic() - start
    text = scrub(p.stdout)
    (OUT / (name + '.log')).write_text(text)
    item = dict(name=name, command=scrub(shlex.join(map(str, args))), cwd=scrub(str(cwd)), exit=p.returncode, expected_exit=expected, elapsed_seconds=round(elapsed, 3), last_line=text.rstrip().split('\n')[-1])
    results.append(item)
    (OUT / 'results.json').write_text(json.dumps(results, indent=2) + '\n')
    print(json.dumps(item), flush=True)
    if p.returncode != expected:
        sys.exit('Unexpected exit; evidence retained, stopping')

metadata = {'upstream': 'https://github.com/anthropics/FlashProve', 'upstream_sha': PIN, 'kernel': platform.release(), 'architecture': platform.machine(), 'non_root': True, 'build_jobs_max': 4, 'runtime_cpu_affinity': sorted(os.sched_getaffinity(0)), 'environment_overrides': {k: env[k] for k in ('MAKEFLAGS', 'OMP_NUM_THREADS', 'LC_ALL')}, 'scope': 'Synthetic stored proofs and toy library only; no real inference, no GPU'}
metadata['cpu_model'] = next((line.split(':', 1)[1].strip() for line in Path('/proc/cpuinfo').read_text().splitlines() if line.startswith('model name')), 'unknown')
metadata['os_release'] = Path('/etc/os-release').read_text()
(OUT / 'environment.json').write_text(json.dumps(metadata, indent=2) + '\n')
run('compiler', ['g++', '--version'])
run('python', ['python3', '--version'])
run('make', ['make', '--version'])
run('upstream-pin', ['git', 'rev-parse', PIN])
# Resolving an object alone does not show that its sources are being built.
run('upstream-source-match', ['git', 'diff', '--exit-code', PIN, '--', '.', ':(exclude)research'])
run('checkout-head', ['git', 'rev-parse', 'HEAD'])
run('checkout-status', ['git', 'status', '--short'])
for example in ('accepted-proof', 'accepted-proof-clipped-gap'):
    run('hashes-' + example, ['sha256sum', '-c', 'SHA256SUMS'], cwd=ROOT / 'examples' / example)
run('build', ['bash', 'verifier/build.sh'])
run('verifier-binary-hash', ['sha256sum', 'bin/cp_verify'])
for example, policy in [('accepted-proof', []), ('accepted-proof-clipped-gap', ['-policy', 'clipped-gap,9244130,323343,1,16,8'])]:
    base = 'examples/' + example
    commitment = (ROOT / base / 'ID.txt').read_text().strip()
    run('verify-' + example, ['bin/cp_verify', base + '/config', base + '/ivk', base + '/example.req', base + '/example.y', base + '/example.proof', '-id', commitment] + policy)
    run('negative-' + example, ['python3', 'examples/rejected-proofs/try_altered_copies.py', 'bin/cp_verify', str(WORK / ('altered-' + example)), '--example', example])
run('toy', ['bash', 'blocks/first_look.sh', str(WORK / 'look')])
for name in ('make.log', 'honest.log', 'honest.status', 'honest.txt', 'bent.log', 'bent.status', 'bent.txt'):
    (OUT / ('toy-' + name)).write_text(scrub((WORK / 'look' / name).read_text()))
# Preserve every toy rejection description, not just its aggregate count.
for table in ('on-the-first-table', 'on-the-copy'):
    (OUT / ('toy-' + table + '-altered.tsv')).write_text((WORK / 'look/proofs' / table / 'altered.tsv').read_text())
artifacts = {}
for path in sorted((WORK / 'look').rglob('*')):
    if path.is_file():
        artifacts[str(path.relative_to(WORK))] = hashlib.sha256(path.read_bytes()).hexdigest()
artifacts['research/reproduction/run.py'] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
(OUT / 'artifact-sha256.json').write_text(json.dumps(artifacts, indent=2) + '\n')
print('All selected CPU checks completed; work files retained outside checkout.')
