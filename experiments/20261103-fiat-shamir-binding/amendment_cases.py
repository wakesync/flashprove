#!/usr/bin/env python3
"""Amendment 2026-11-04 rows: extra expected-reject cases OUTSIDE the registered 11x5 set.

Added after independent review of PR #41 (see PREREG.md, Amendments, 2026-11-04). The
registered arms in run.py, measurements.json and summary.json are untouched; these rows
are written to a separate directory (default: amendment-20261104/ next to this file).

Cases, each five paired repetitions with the same alternating order as run.py:
  range-end-legal-y0  request word 65 (e) - 1 together with y = 0, so the range form at
                      cp_verify.cpp:324 stays legal (the case RESULTS.md listed as untried)
  layout-missing      config/layout.txt removed
  layout-empty        config/layout.txt present with zero bytes

Requires bin/cp_verify (verifier/build.sh) and the diagnostic build (build_trace.py).
CPU only. Never changes tracked fixture files. Deterministic inputs: the repetitions show
determinism, not independent trials.
"""
import argparse
import json
from pathlib import Path
import shutil
import statistics
import struct
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import run  # noqa: E402  (reuse invoke/arguments/trace_value; run.main is not called)

ROOT, FIX, WORK = run.ROOT, run.FIX, Path('bin/fs-binding-inputs-amendment')
EXPECTED = {'range-end-legal-y0': 'NO: proof-refused',
            'layout-missing': 'NO: plan-layout',
            'layout-empty': 'NO: plan-layout'}


def make_cases():
    cases = {}
    for name in EXPECTED:
        dest = ROOT / WORK / name
        if dest.exists():
            shutil.rmtree(dest)
        dest.mkdir(parents=True)
        shutil.copytree(ROOT / FIX / 'config', dest / 'config')
        for f in ('example.req', 'example.y'):
            shutil.copyfile(ROOT / FIX / f, dest / f)
        c = {'config': WORK / name / 'config', 'request': WORK / name / 'example.req',
             'reply': WORK / name / 'example.y',
             'id': (ROOT / FIX / 'ID.txt').read_text().strip(), 'semantic': True}
        if name == 'range-end-legal-y0':
            p = dest / 'example.req'
            b = bytearray(p.read_bytes())
            e = struct.unpack_from('<I', b, 4 * 65)[0]
            struct.pack_into('<I', b, 4 * 65, e - 1)
            p.write_bytes(b)
            (dest / 'example.y').write_bytes(struct.pack('<I', 0))
        elif name == 'layout-missing':
            (dest / 'config/layout.txt').unlink()
        else:
            (dest / 'config/layout.txt').write_bytes(b'')
        cases[name] = c
    return cases


def stats(values):
    return {'n': len(values), 'sum': sum(values), 'median': statistics.median(values),
            'sd_population': statistics.pstdev(values), 'min': min(values), 'max': max(values)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--runs', type=int, default=5)
    parser.add_argument('--output-dir', type=Path, default=HERE / 'amendment-20261104')
    args = parser.parse_args()
    cases = make_cases()
    base = {'config': FIX / 'config', 'request': FIX / 'example.req',
            'reply': FIX / 'example.y', 'id': (ROOT / FIX / 'ID.txt').read_text().strip()}
    args.output_dir.mkdir(parents=True, exist_ok=True)
    records = []
    for name, case in cases.items():
        for repetition in range(1, args.runs + 1):
            row = {'case': name, 'repeat': repetition, 'semantic': case['semantic'],
                   'baseline': {}, 'mutated': {}}
            for arm in (('baseline', 'mutated') if repetition % 2 else ('mutated', 'baseline')):
                for kind, binary in run.BINS.items():
                    row[arm][kind] = run.invoke(binary, run.arguments(base if arm == 'baseline' else case))
            b, m = row['baseline'], row['mutated']
            row['baseline_accept'] = b['production']['exit'] == 0 and b['production']['last'] == 'YES'
            row['mutation_accept'] = m['production']['exit'] == 0
            row['build_verdict_agreement'] = all(
                row[a]['production']['exit'] == row[a]['trace']['exit']
                and row[a]['production']['last'] == row[a]['trace']['last'] for a in ('baseline', 'mutated'))
            bt, mt = run.trace_value(b['trace'], 'challenge'), run.trace_value(m['trace'], 'challenge')
            row['first_challenge_changed'] = None if mt is None else bt != mt
            row['expected_last'] = EXPECTED[name]
            row['as_expected'] = (m['production']['exit'] == 1
                                  and m['production']['last'] == EXPECTED[name])
            records.append(row)
            print(name, repetition, m['production']['exit'], m['production']['last'],
                  'first_changed=', row['first_challenge_changed'], flush=True)
    (args.output_dir / 'measurements.json').write_text(
        json.dumps({'runs': args.runs, 'records': records}, indent=2) + '\n')
    summary = {}
    for name in cases:
        rows = [r for r in records if r['case'] == name]
        entry = {}
        for key in ('baseline_accept', 'mutation_accept', 'build_verdict_agreement',
                    'first_challenge_changed', 'as_expected'):
            values = [int(r[key]) for r in rows if r.get(key) is not None]
            entry[key] = stats(values) if values else None
        entry['production_verdicts'] = sorted(
            {(r['mutated']['production']['exit'], r['mutated']['production']['last']) for r in rows})
        summary[name] = entry
    (args.output_dir / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
    ok = all(r['baseline_accept'] and r['build_verdict_agreement'] and not r['mutation_accept']
             and r['as_expected'] for r in records)
    print('amendment rows:', len(records), 'records;', 'all as expected' if ok else 'UNEXPECTED outcome')
    sys.exit(0 if ok else 1)


if __name__ == '__main__':
    main()
