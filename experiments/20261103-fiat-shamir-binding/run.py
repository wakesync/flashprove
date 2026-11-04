#!/usr/bin/env python3
"""CPU-only synthetic-fixture mutation study. Never changes tracked fixture files.

Requires bin/cp_verify and build_trace.py's diagnostic binary. JSON records the
full terminal verdict, relevant output and trace, not private paths. Five repeats
are deterministic regression trials, not independent forgery attempts.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import statistics
import struct
import subprocess
import time

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
FIX = Path('examples/accepted-proof')
WORK = Path('bin/fs-binding-inputs')
LABEL = str(0x46524D01)
BINS = {'production': 'bin/cp_verify', 'trace': 'bin/fs-trace/cp_verify_trace'}


def digest(data):
    return hashlib.sha256(data).hexdigest()


def invoke(binary, args):
    # cp_verify runs its stages in child processes and prints their output only on a pass or
    # under -show-stages. The diagnostic binary's FS_TRACE lines live in that output, so the
    # trace build is always asked to show its stages; the production verdict is taken without it.
    if binary == BINS['trace']:
        args = [*args, '-show-stages']
    p = subprocess.run([binary, *map(str, args)], cwd=ROOT,
                       capture_output=True, text=True, timeout=120)
    lines = p.stdout.splitlines()
    keep = ('FS_TRACE ', 'commitment ID:', 'commitment:', 'proof of work:',
            'covered:', 'result-v1 ', 'proof:', 'key:', 'entry:', 'h_par=')
    return {'exit': p.returncode, 'last': lines[-1] if lines else '',
            'lines': [line for line in lines if line.startswith(keep)],
            'stdout_sha256': digest(p.stdout.encode()), 'stderr': p.stderr}


def trace_value(result, phase):
    lines = [s for s in result['lines']
             if s.startswith('FS_TRACE ' + phase + ' label=' + LABEL + ' ')]
    if len(lines) > 1:
        raise AssertionError('duplicate request-chain trace')
    return lines[0] if lines else None


def make_cases():
    cases = {}
    for name in ('policy-equation', 'quant-scale', 'layout-placement', 'layout-comment',
                 'prompt-token', 'reply-token-in-request', 'last-request-token',
                 'range-start', 'range-end', 'next-token', 'commitment-id'):
        dest = ROOT / WORK / name
        dest.mkdir(parents=True, exist_ok=True)
        shutil.copytree(ROOT / FIX / 'config', dest / 'config', dirs_exist_ok=True)
        for f in ('example.req', 'example.y'):
            shutil.copyfile(ROOT / FIX / f, dest / f)
        c = {'config': WORK / name / 'config', 'request': WORK / name / 'example.req',
             'reply': WORK / name / 'example.y',
             'id': (ROOT / FIX / 'ID.txt').read_text().strip(), 'semantic': True}
        if name == 'policy-equation':
            p = dest / 'config/policy.txt'
            text = p.read_text()
            assert text.count('epsF_lo 1\n') == 1
            p.write_text(text.replace('epsF_lo 1\n', 'epsF_lo 2\n'))
        elif name == 'quant-scale':
            p = dest / 'config/KL.bin'
            b = bytearray(p.read_bytes())
            assert struct.unpack_from('<I', b)[0] == 29
            struct.pack_into('<I', b, 0, 28)
            p.write_bytes(b)
        elif name == 'layout-placement':
            p = dest / 'config/layout.txt'
            text = p.read_text()
            a = '1 1 1 2 2048 9 0 7 r 48 0 0 16 0\n'
            b = '1 1 1 5 2688 5 0 11 r 49 0 0 16 0\n'
            assert text.count(a) == text.count(b) == 1
            text = text.replace(a, a.replace('r 48 ', 'r 49 '))
            text = text.replace(b, b.replace('r 49 ', 'r 48 '))
            p.write_text(text)
        elif name == 'layout-comment':
            p = dest / 'config/layout.txt'
            p.write_bytes(p.read_bytes() + b'# byte binding control\n')
            c['semantic'] = False
        elif name in ('prompt-token', 'reply-token-in-request', 'last-request-token',
                      'range-start', 'range-end'):
            p = dest / 'example.req'
            b = bytearray(p.read_bytes())
            i = {'prompt-token': 0, 'reply-token-in-request': 61,
                 'last-request-token': 63, 'range-start': 64, 'range-end': 65}[name]
            v = struct.unpack_from('<I', b, 4 * i)[0]
            v = v - 1 if name.startswith('range-') else (v + 1) % 512
            struct.pack_into('<I', b, 4 * i, v)
            p.write_bytes(b)
        elif name == 'next-token':
            p = dest / 'example.y'
            assert struct.unpack('<I', p.read_bytes())[0] == 199
            p.write_bytes(struct.pack('<I', 200))
        else:
            c['id'] = ('0' if c['id'][0] != '0' else '1') + c['id'][1:]
        cases[name] = c
    return cases


def arguments(c, identity=None):
    return [c['config'], FIX / 'ivk', c['request'], c['reply'], FIX / 'example.proof',
            '-id', identity or c['id'], '-j', '2']


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--runs', type=int, default=5)
    args = parser.parse_args()
    if args.runs < 1:
        parser.error('--runs must be positive')
    cases = make_cases()
    base = {'config': FIX / 'config', 'request': FIX / 'example.req',
            'reply': FIX / 'example.y', 'id': (ROOT / FIX / 'ID.txt').read_text().strip()}
    records = []
    out = HERE / 'measurements.json'
    t_start = time.time()
    for name, case in cases.items():
        plan = None
        if name in ('policy-equation', 'quant-scale', 'layout-placement', 'layout-comment'):
            plan = invoke(BINS['production'], ['-plan', 'id', case['config'], FIX / 'ivk/key.bin'])
        ids = [s.split(': ', 1)[1] for s in (plan or {}).get('lines', []) if s.startswith('commitment ID: ')]
        derived_id = ids[0] if len(ids) == 1 and plan['exit'] == 4 else None
        for repetition in range(1, args.runs + 1):
            row = {'case': name, 'repeat': repetition, 'semantic': case['semantic'],
                   'plan': plan, 'derived_id': derived_id, 'baseline': {}, 'mutated': {}}
            for arm in (('baseline', 'mutated') if repetition % 2 else ('mutated', 'baseline')):
                for kind, binary in BINS.items():
                    row[arm][kind] = invoke(binary, arguments(base if arm == 'baseline' else case))
            # A changed ID is ONLY a diagnostic to reach changed-config chains. Never count
            # it as acceptance at the original ID, nor a proof generated for that config.
            if derived_id is not None:
                row['changed_id_trace'] = invoke(BINS['trace'], arguments(case, derived_id))
            b, m = row['baseline'], row['mutated']
            row['baseline_accept'] = b['production']['exit'] == 0 and b['production']['last'] == 'YES'
            row['mutation_accept'] = m['production']['exit'] == 0
            row['build_verdict_agreement'] = all(row[a]['production']['exit'] == row[a]['trace']['exit']
                and row[a]['production']['last'] == row[a]['trace']['last'] for a in ('baseline', 'mutated'))
            bt, mt = trace_value(b['trace'], 'challenge'), trace_value(m['trace'], 'challenge')
            row['first_challenge_changed'] = None if mt is None else bt != mt
            if derived_id is not None:
                ct = trace_value(row['changed_id_trace'], 'challenge')
                row['changed_config_first_challenge_changed'] = None if ct is None else bt != ct
            records.append(row)
            out.write_text(json.dumps({'runs': args.runs, 'records': records}, indent=2) + '\n')
            print(name, repetition, m['production']['exit'], m['production']['last'],
                  'first_changed=', row['first_challenge_changed'], flush=True)
    def stats(values):
        return {'n': len(values), 'sum': sum(values), 'median': statistics.median(values),
                'sd_population': statistics.pstdev(values), 'min': min(values), 'max': max(values)}
    summary = {}
    for name in cases:
        rows = [r for r in records if r['case'] == name]
        entry = {}
        for key in ('baseline_accept', 'mutation_accept', 'build_verdict_agreement',
                    'first_challenge_changed', 'changed_config_first_challenge_changed'):
            values = [int(r[key]) for r in rows if r.get(key) is not None]
            entry[key] = stats(values) if values else None
        entry['production_verdicts'] = sorted({(r['mutated']['production']['exit'], r['mutated']['production']['last']) for r in rows})
        summary[name] = entry
    summary['_wall_seconds'] = round(time.time() - t_start, 1)
    (HERE / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
    assert all(r['baseline_accept'] and r['build_verdict_agreement'] and not r['mutation_accept'] for r in records)
    print('Mutation rejections and build outcome agreement hold. Read summary for early-binding exceptions.')


if __name__ == '__main__':
    main()
