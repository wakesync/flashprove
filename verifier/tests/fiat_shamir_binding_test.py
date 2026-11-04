#!/usr/bin/env python3
"""Regression checks for the pre-registered CPU Fiat-Shamir binding probe.

Build bin/cp_verify with verifier/build.sh and the diagnostic executable with
experiments/20261103-fiat-shamir-binding/build_trace.py first. From the repo root:

  python3 verifier/tests/fiat_shamir_binding_test.py

This runs the registered 11 cases, five paired repeats, with records written to
bin/fs-binding-regression/. --check-recorded DIR only checks an existing run.
The known deferred binding of y is an EXPECTED observation, not an early-binding
pass or a security assertion. No GPU and no proof generation.
"""
import argparse
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
CONFIG = {'policy-equation', 'quant-scale', 'layout-placement', 'layout-comment'}
REQUEST = {'prompt-token', 'reply-token-in-request', 'last-request-token', 'range-start'}
EXPECTED = {name: ('NO: model-statement', None) for name in CONFIG | {'commitment-id'}}
EXPECTED.update({name: ('NO: proof-refused', True) for name in REQUEST})
EXPECTED.update({'range-end': ('NO: statement-range', None),
                 'next-token': ('NO: reply-differs', False)})


def phase(result, name):
    prefix = f'FS_TRACE {name} label={0x46524D01} '
    lines = [line for line in result['lines'] if line.startswith(prefix)]
    assert len(lines) <= 1, 'duplicate phase'
    return lines[0] if lines else None


def check(directory):
    data = json.loads((directory / 'measurements.json').read_text())
    assert data['runs'] == 5
    rows = data['records']
    assert len(rows) == 55
    assert {row['case'] for row in rows} == set(EXPECTED)
    baseline_challenges = set()
    for name, (last, changed) in EXPECTED.items():
        cases = [row for row in rows if row['case'] == name]
        assert sorted(row['repeat'] for row in cases) == [1, 2, 3, 4, 5]
        for row in cases:
            b, m = row['baseline'], row['mutated']
            assert b['production']['exit'] == 0 and b['production']['last'] == 'YES'
            assert m['production']['exit'] == 1 and m['production']['last'] == last
            assert row['baseline_accept'] and not row['mutation_accept']
            assert row['build_verdict_agreement']
            for arm in (b, m):
                assert (arm['production']['exit'], arm['production']['last']) == (
                    arm['trace']['exit'], arm['trace']['last'])
            bt, mt = phase(b['trace'], 'challenge'), phase(m['trace'], 'challenge')
            assert bt is not None, 'baseline first challenge absent'
            baseline_challenges.add(bt)
            actual = None if mt is None else mt != bt
            assert actual is changed and row['first_challenge_changed'] is changed
            if name in CONFIG:
                # Diagnostic only: altered config's NEW identity, not the original ID.
                assert row['plan']['exit'] == 4 and row['derived_id']
                original = (ROOT / 'examples/accepted-proof/ID.txt').read_text().strip()
                assert row['derived_id'] != original
                ct = phase(row['changed_id_trace'], 'challenge')
                assert ct is not None and ct != bt
                assert row['changed_config_first_challenge_changed'] is True
                assert row['changed_id_trace']['exit'] == 1
            if name == 'next-token':
                for p in ('start', 'reply'):
                    before, after = phase(b['trace'], p), phase(m['trace'], p)
                    assert before is not None and after == before
    assert len(baseline_challenges) == 1, 'fixed-proof baseline not deterministic'
    print('fiat_shamir_binding_test: expected outcomes, 55 pairs; 0/50 semantic '
          'mutations accepted; deferred y binding reproduced (5/5)')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check-recorded', type=Path)
    args = parser.parse_args()
    directory = args.check_recorded or ROOT / 'bin/fs-binding-regression'
    if args.check_recorded is None:
        subprocess.run([sys.executable,
                        'experiments/20261103-fiat-shamir-binding/run.py',
                        '--runs', '5', '--output-dir', str(directory)],
                       cwd=ROOT, check=True)
    check(directory)


if __name__ == '__main__':
    main()
