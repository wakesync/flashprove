#!/usr/bin/env python3
"""Matched stored-proof CPU verification measurement, not proving/serving throughput.
Build each checkout with verifier/build.sh first. No dependencies beyond Linux,
Python 3, taskset and GNU time. Output directory must not exist.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import statistics
import subprocess


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def capture(args):
    return subprocess.check_output(args, text=True).strip()


def pressure():
    return {name: Path('/proc/pressure/' + name).read_text()
            for name in ('cpu', 'memory', 'io')}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('upstream', type=Path)
    p.add_argument('fork', type=Path)
    p.add_argument('output', type=Path)
    p.add_argument('--cpu', type=int, required=True)
    p.add_argument('--repetitions', type=int, default=5)
    a = p.parse_args()
    if a.repetitions < 3:
        p.error('at least three repetitions required')
    if a.cpu not in os.sched_getaffinity(0):
        p.error('CPU is not in current allowed affinity')
    a.output.mkdir(parents=True, exist_ok=False)
    roots = {'upstream': a.upstream.resolve(), 'fork': a.fork.resolve()}
    fixture = roots['upstream'] / 'examples/accepted-proof'
    manifest = {
        'scope': 'stored synthetic proof, full key+leaf+request CPU verification only',
        'cpu': a.cpu, 'threads_per_stage': 1,
        'cache': 'one warmup per binary, OS cache not flushed; no amortization',
        'repetitions': a.repetitions,
        'hardware': capture(['lscpu']),
        'compiler': capture(['g++', '--version']),
        'kernel': capture(['uname', '-srmo']),
        'pressure_before': pressure(),
        'proof_bytes': (fixture / 'example.proof').stat().st_size,
        'fixtures': {str(f.relative_to(fixture)): sha(f)
                     for f in sorted(fixture.rglob('*')) if f.is_file()},
        'sources': {label: {'sha': capture(['git', '-C', str(root), 'rev-parse', 'HEAD']),
                            'dirty': capture(['git', '-C', str(root), 'status', '--porcelain']),
                            'binary_sha256': sha(root / 'bin/cp_verify')}
                    for label, root in roots.items()},
        'rows': [],
        'limits': ['Shared KVM host, no exclusive-core reservation.',
                   'GNU time maximum RSS is maximum per process, NOT simultaneous process-tree peak.',
                   'No GPU, inference, proving, queue, or network timings.',
                   'Phase timings overlap across forked children; do not add their wall times.'],
    }
    result = a.output / 'results.json'
    def persist():
        result.write_text(json.dumps(manifest, indent=2) + '\n')
    persist()
    ident = (fixture / 'ID.txt').read_text().strip()
    altered = bytearray((fixture / 'example.proof').read_bytes())
    altered[len(altered) // 2] ^= 1
    (a.output / 'altered.proof').write_bytes(altered)
    def run(label, repetition, negative=False):
        stem = f'{label}-{repetition}'
        proof = a.output.resolve() / 'altered.proof' if negative else fixture / 'example.proof'
        command = ['taskset', '-c', str(a.cpu), str(roots[label] / 'bin/cp_verify'),
                   str(fixture / 'config'), str(fixture / 'ivk'),
                   str(fixture / 'example.req'), str(fixture / 'example.y'),
                   str(proof), '-id', ident, '-j', '1']
        with (a.output / (stem + '.stdout')).open('w') as out, (a.output / (stem + '.stderr')).open('w') as err:
            completed = subprocess.run(['/usr/bin/time', '-f', '%e %U %S %M %F %R %c %w',
                                        '-o', str(a.output / (stem + '.time'))] + command,
                                       stdout=out, stderr=err, timeout=120)
        text = (a.output / (stem + '.stdout')).read_text()
        values = (a.output / (stem + '.time')).read_text().splitlines()[-1].split()
        row = dict(zip(('wall_s', 'user_s', 'system_s', 'max_process_rss_kib',
                        'major_faults', 'minor_faults', 'involuntary_switches', 'voluntary_switches'),
                       map(float, values)))
        row.update(label=label, repetition=repetition, exit=completed.returncode,
                   last_line=text.splitlines()[-1] if text else '',
                   phase_lines=[line for line in text.splitlines() if 'seconds:' in line or line.startswith('---- stage')],
                   pressure_after=pressure())
        manifest['rows'].append(row)
        persist()
        valid = (row['exit'] == 1 and row['last_line'].startswith('NO:')) if negative else (row['exit'] == 0 and row['last_line'] == 'YES')
        if not valid:
            raise RuntimeError(f'unexpected verifier result: {row}')
        return row
    for label in roots:
        run(label, 'warmup')
    for rep in range(a.repetitions):
        for label in (('upstream', 'fork') if rep % 2 == 0 else ('fork', 'upstream')):
            run(label, rep)
        if rep >= 2:
            for label in roots:
                times = [r['wall_s'] for r in manifest['rows'] if r['label'] == label and isinstance(r['repetition'], int)]
                if (max(times) - min(times)) / statistics.median(times) > .10:
                    manifest['timing_stability_screen'] = 'FAIL: range exceeds 10%; stopped, no performance claim'
                    persist()
                    print(manifest['timing_stability_screen'])
                    return 77
    for label in roots:
        run(label, 'negative', True)
    manifest['summary'] = {}
    stable = True
    for label in roots:
        rows = [r for r in manifest['rows'] if r['label'] == label and isinstance(r['repetition'], int)]
        times = [r['wall_s'] for r in rows]
        median = statistics.median(times)
        spread = (max(times) - min(times)) / median
        stable &= spread <= .10
        manifest['summary'][label] = {'wall_median_s': median, 'wall_min_s': min(times),
                                      'wall_max_s': max(times), 'wall_sample_stdev_s': statistics.stdev(times),
                                      'range_over_median': spread,
                                      'max_process_rss_kib': [r['max_process_rss_kib'] for r in rows]}
    manifest['timing_stability_screen'] = 'PASS' if stable else 'FAIL: range exceeds 10%; no performance claim'
    manifest['pressure_after'] = pressure()
    persist()
    print(json.dumps(manifest['summary'], indent=2))
    print(manifest['timing_stability_screen'])
    return 0 if stable else 77


if __name__ == '__main__':
    raise SystemExit(main())
