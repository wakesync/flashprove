#!/usr/bin/env python3
"""Differential correctness of verifier builds on the honest example and eight negative cases.

usage: differential.py <output dir> --cpu N reference=/path/cp_verify label=/path/cp_verify ...

The cases are those of the earlier account-reuse receipt (research/performance/followup,
cpu_adversarial.py): honest; middle byte of the proof flipped; proof truncated by one byte; middle
byte of the key flipped; middle byte of the leaf entry flipped; middle byte of the request flipped;
middle byte of the reply flipped; wrong commitment ID; parameter file with an unknown line.
Every arm must give the same exit status and the same verdict and public lines as the first
(reference) arm: every line that starts accounting:, commitment:, proof of work:, covered:,
result-v1, YES or NO:, with the source digest (build=, which differs by construction when the
sources differ) cut off. The honest case must end YES with status 0 and every other case NO: with
status 1. Also compared, and reported separately: the complete stdout with the build= field and
timing figures (seconds, wall timers) removed. Output directory must not exist.
"""
import argparse
import json
from pathlib import Path
import re
import shutil
import subprocess

CASES = [('honest', None, None), ('proof-middle', 'example.proof', 'flip'), ('proof-truncated', 'example.proof', 'truncate'),
         ('key-middle', 'ivk/key.bin', 'flip'), ('leaf-middle', 'ivk/leaf/0.bin', 'flip'), ('request-token', 'example.req', 'flip'),
         ('reply-token', 'example.y', 'flip'), ('wrong-id', None, None), ('policy-invalid', 'config/policy.txt', 'policy')]
PUBLIC = ('accounting:', 'commitment:', 'proof of work:', 'covered:', 'result-v1', 'YES', 'NO:')


def timing_free(text):
    out = []
    for line in text.splitlines():
        line = re.sub(r' build=[0-9a-f]{64}', ' build=<digest>', line)
        line = re.sub(r'build=[0-9a-f]{64}', 'build=<digest>', line)
        line = re.sub(r'\b\d+\.\d{3} s\b', '<t> s', line)
        line = re.sub(r'\b\d+\.\d{3}\b', '<t>', line) if ('seconds' in line or line.startswith('---- stage') or line.startswith('read:') or line.startswith('ok public inputs')) else line
        out.append(line)
    return out


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('output', type=Path)
    p.add_argument('arms', nargs='+')
    p.add_argument('--cpu', required=True)
    a = p.parse_args()
    arms = [(s.partition('=')[0], Path(s.partition('=')[2]).resolve()) for s in a.arms]
    top = Path(__file__).resolve().parents[3]
    source = top / 'examples/accepted-proof'
    a.output.mkdir(parents=True, exist_ok=False)
    rows, ok = [], True
    for name, rel, action in CASES:
        f = a.output / name
        shutil.copytree(source, f)
        if rel:
            path = f / rel
            data = bytearray(path.read_bytes())
            if action == 'flip':
                data[len(data) // 2] ^= 1
            elif action == 'truncate':
                data = data[:-1]
            elif action == 'policy':
                data += b'\nunknown_research_test 1\n'
            path.write_bytes(bytes(data))
        ident = (f / 'ID.txt').read_text().strip()
        if name == 'wrong-id':
            ident = ('0' if ident[0] != '0' else '1') + ident[1:]
        results = []
        for label, binary in arms:
            cmd = ['taskset', '-c', a.cpu, str(binary), str(f / 'config'), str(f / 'ivk'), str(f / 'example.req'),
                   str(f / 'example.y'), str(f / 'example.proof'), '-id', ident, '-j', '1']
            c = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            (a.output / f'{name}-{label}.stdout').write_text(c.stdout)
            (a.output / f'{name}-{label}.stderr').write_text(c.stderr)
            public = [x.split(' build=')[0] for x in c.stdout.splitlines() if x.startswith(PUBLIC)]
            results.append({'arm': label, 'exit': c.returncode, 'last': c.stdout.splitlines()[-1] if c.stdout else '',
                            'public': public, 'full': timing_free(c.stdout)})
        ref = results[0]
        expect = (ref['exit'] == 0 and ref['last'] == 'YES') if name == 'honest' else (ref['exit'] == 1 and ref['last'].startswith('NO:'))
        same_public = all(r['exit'] == ref['exit'] and r['public'] == ref['public'] for r in results)
        same_full = all(r['full'] == ref['full'] for r in results)
        ok &= expect and same_public
        rows.append({'case': name, 'expected_verdict': expect, 'equal_public': same_public, 'equal_full_stdout_without_timings': same_full,
                     'results': [{k: v for k, v in r.items() if k != 'full'} for r in results]})
        print(f"{name:16s} ref={ref['last'][:40]!r:44s} exit={ref['exit']} expected={expect} equal_public={same_public} equal_full={same_full}", flush=True)
        shutil.rmtree(f)
    (a.output / 'results.json').write_text(json.dumps({'arms': [[l, str(b)] for l, b in arms], 'all_ok': ok, 'rows': rows}, indent=2) + '\n')
    print('ALL OK' if ok else 'MISMATCH')
    raise SystemExit(0 if ok else 1)


if __name__ == '__main__':
    main()
