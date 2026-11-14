"""Actual CLI regressions on disposable copies of the saved independent receipt.

Historical measurements and receipts are never written. Targets remain frozen.
"""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import recomp181_compare as C
import recomp181_compare_tests as T
import recomp181_reader as R

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]


class ReceiptCLITests(unittest.TestCase):
    def setUp(self):
        self.receipt = R.loads((HERE/'runs/independent-r3-1.json').read_text())
        self.cell = self.receipt['cells']['abl/XS18']
        self.flip = self.cell['flips'][0]
        self.pid = self.flip['prompt']

    def run_cli(self, expected, repo=REPO, existing=False):
        with tempfile.TemporaryDirectory() as tmp:
            inp, out = Path(tmp)/'input.json', Path(tmp)/'output.json'
            inp.write_text(json.dumps(self.receipt))
            if existing:
                out.write_text('do not overwrite\n')
            p = subprocess.run([sys.executable, str(HERE/'recomp181_compare.py'),
                                '--repo', str(repo), '--independent', str(inp), '--output', str(out)],
                               capture_output=True, text=True)
            self.assertEqual(p.returncode, expected, p.stdout+p.stderr)
            if expected == 2:
                self.assertIn('COMPARISON INVALID:', p.stderr)
                self.assertNotIn('MATCH:', p.stdout)
                if existing:
                    self.assertEqual(out.read_text(), 'do not overwrite\n')
                else:
                    self.assertFalse(out.exists(), p.stdout+p.stderr)
                return p.stderr
            result = json.loads(out.read_text())
            self.assertEqual(result['status'], 'MATCH' if expected == 0 else 'NEGATIVE')
            return result

    def test_wrong_checkpoint(self):
        self.flip['checkpoint'] = 'stock'
        self.assertIn('checkpoint/arm', self.run_cli(2))

    def test_missing_checkpoint(self):
        del self.flip['checkpoint']
        self.assertIn('flip', self.run_cli(2))

    def test_wrong_arm(self):
        self.flip['arm'] = 'BF16H'
        self.assertIn('checkpoint/arm', self.run_cli(2))

    def test_missing_input_sha256(self):
        del self.receipt['input_sha256']
        self.run_cli(2)

    def test_wrong_digest(self):
        self.receipt['input_sha256']['runs/e2e-abl.json'] = '0'*64
        self.assertIn('frozen digest mismatch', self.run_cli(2))

    def test_inconsistent_negative_status(self):
        self.receipt['status'] = 'NEGATIVE'
        self.assertIn('status', self.run_cli(2))

    def test_wrong_pooled_denominator(self):
        self.cell['kl']['n'] = 1
        self.assertIn('abl/XS18.kl.n', self.run_cli(2))

    def test_missing_cell(self):
        del self.receipt['cells']['stock/XS20']
        self.run_cli(2)

    def test_extra_cell(self):
        self.receipt['cells']['abl/BF16H'] = copy.deepcopy(self.cell)
        self.run_cli(2)

    def test_wrong_per_prompt_denominator(self):
        self.cell['per_prompt'][self.pid]['kl']['n'] = 1
        self.assertIn(self.pid+'.kl.n', self.run_cli(2))

    def test_non_string_digest(self):
        self.receipt['input_sha256']['runs/e2e-abl.json'] = 123
        self.assertIn('SHA-256 string', self.run_cli(2))

    def test_missing_and_extra_prompt(self):
        for extra in (False, True):
            with self.subTest(extra=extra):
                self.setUp()
                if extra:
                    self.cell['per_prompt']['extra'] = copy.deepcopy(self.cell['per_prompt'][self.pid])
                else:
                    del self.cell['per_prompt'][self.pid]
                self.run_cli(2)

    def test_missing_fields_and_wrong_types(self):
        for target, key in (('receipt','status'), ('cell','verdict'), ('cell','kl'),
                            ('flip','arm'), ('flip','prompt'), ('flip','position'),
                            ('flip','ref_token'), ('flip','path_token'), ('flip','ref_margin')):
            for mutation in ('missing', 'list'):
                with self.subTest(target=target, key=key, mutation=mutation):
                    self.setUp()
                    obj = getattr(self, target)
                    if mutation == 'missing': del obj[key]
                    else: obj[key] = []
                    self.run_cli(2)

    def test_boolean_and_string_numbers(self):
        for value in (True, '1461'):
            with self.subTest(value=value):
                self.setUp()
                self.cell['positions'] = value
                self.run_cli(2)
        self.setUp()
        self.cell['kl']['median'] = '0.0'
        message = self.run_cli(2)
        self.assertIn('expected number, got str', message)
        self.assertNotIn('not bool', message)

    def test_extra_digest_and_absence_corruption(self):
        self.receipt['input_sha256']['extra'] = '0'*64
        self.run_cli(2)
        self.setUp()
        self.receipt['input_sha256']['runs/errors-abl.jsonl'] = '0'*64
        self.run_cli(2)

    def test_duplicate_out_of_range_and_equal_token_flip(self):
        for kind in ('duplicate', 'position', 'tokens', 'unknown_prompt', 'token_bool'):
            with self.subTest(kind=kind):
                self.setUp()
                if kind == 'duplicate': self.cell['flips'].append(copy.deepcopy(self.flip))
                elif kind == 'position': self.flip['position'] = R.COUNTS[self.pid]
                elif kind == 'tokens': self.flip['path_token'] = self.flip['ref_token']
                elif kind == 'unknown_prompt': self.flip['prompt'] = 'unknown'
                else: self.flip['path_token'] = True
                self.run_cli(2)

    def test_bad_consistency_fields(self):
        for kind in ('fraction', 'agree', 'bar', 'verdict', 'determinism', 'coverage', 'negative', 'tolerance', 'status'):
            with self.subTest(kind=kind):
                self.setUp()
                if kind == 'fraction': self.cell['agreement_fraction'] = 1
                elif kind == 'agree': self.cell['per_prompt'][self.pid]['agree'] += 1
                elif kind == 'bar': self.cell['bars']['top1_ge_99pct'] = False
                elif kind == 'verdict': self.cell['verdict'] = 'FAIL'
                elif kind == 'determinism': self.receipt['global_recorded_determinism'] = False
                elif kind == 'coverage': self.receipt['layer_coverage']['abl']['physical_head_rows'] = 1
                elif kind == 'negative': self.receipt['cells']['stock/XS20']['negative_kl'] = []
                elif kind == 'tolerance': self.cell['negative_kl_tolerance'] = 1e-10
                else: self.receipt['status'] = 'MATCH'
                self.run_cli(2)

    def test_admission_precedes_target_access(self):
        del self.receipt['input_sha256']
        message = self.run_cli(2, repo='nonexistent-target-repository')
        self.assertIn('independent receipt', message)
        self.assertNotIn('fatal:', message)

    def test_existing_output_is_never_replaced(self):
        self.run_cli(2, existing=True)

    def test_honest_receipt_same_comparisons_and_explicit_counts(self):
        result = self.run_cli(0)
        original = json.loads((HERE/'runs/comparison.json').read_text())
        self.assertEqual(result['comparison_count'], 494)
        self.assertEqual(result['mismatch_count'], 0)
        self.assertEqual(result['comparison_counts_by_kind'],
                         {'independent_vs_target':479, 'fixed_expectation':14, 'threshold_contract':1})
        checks = [{k:v for k,v in check.items() if k != 'kind'} for check in result['checks']]
        self.assertEqual(checks, original['checks'])
        fixed = {c['field'] for c in result['checks'] if c['kind'] == 'fixed_expectation'}
        expected = {'source_main', 'cells'}
        expected.update(leg+'.'+key for leg in ('stock','abl') for key in ('finished','errors'))
        expected.update(leg+'/'+arm+'.'+key for leg in ('stock','abl') for arm in R.ARMS for key in ('guard','dead_prompts'))
        self.assertEqual(fixed, expected)

    def test_consistent_negative_receipt_remains_negative(self):
        self.receipt['checks']['abl']['sanity'] = False
        for cell in self.receipt['cells'].values():
            cell['verdict'] = 'FAIL'
        self.receipt['status'] = 'NEGATIVE'
        result = self.run_cli(1)
        self.assertGreater(result['mismatch_count'], 0)

    def test_valid_numeric_mismatch_remains_negative(self):
        self.flip['ref_margin'] += 0.001
        result = self.run_cli(1)
        self.assertEqual(result['mismatch_count'], 1)
        self.assertEqual(result['mismatches'][0]['field'], 'abl/XS18.flip0.margin')


class TargetDiagnosticsTests(unittest.TestCase):
    def test_missing_summary_per_prompt_key_has_path(self):
        for missing in ('prompt', 'T', 'median'):
            with self.subTest(missing=missing):
                ind, summary, ledger, text = T.targets()
                prompts = summary['legs']['abl']['cells']['XS20']['per_prompt']
                if missing == 'prompt': del prompts['synthetic-other']
                elif missing == 'T': del prompts['synthetic-other']['T']
                else: del prompts['synthetic-other']['kl']['median']
                with self.assertRaisesRegex(R.InvalidEvidence, r'summary.abl/XS20.per_prompt.*missing field'):
                    C.compare(ind, summary, ledger, text)

    def test_missing_ledger_metric_has_name(self):
        ind, summary, ledger, text = T.targets()
        ledger = '\n'.join(line for line in ledger.splitlines() if 'top1_agree_xs18_stock' not in line)
        with self.assertRaisesRegex(R.InvalidEvidence, 'ledger metrics: missing field top1_agree_xs18_stock'):
            C.compare(ind, summary, ledger, text)

    def test_string_target_number_reports_actual_type(self):
        ind, summary, ledger, text = T.targets()
        summary['legs']['abl']['cells']['XS20']['kl_median'] = '0.0'
        with self.assertRaisesRegex(R.InvalidEvidence, 'expected number, got str'):
            C.compare(ind, summary, ledger, text)

    def test_string_ledger_number_reports_actual_type(self):
        ind, summary, ledger, text = T.targets()
        ledger = ledger.replace('"value": 0.0', '"value": "0.0"')
        with self.assertRaisesRegex(R.InvalidEvidence, 'expected printed number, got str'):
            C.compare(ind, summary, ledger, text)


if __name__ == '__main__':
    unittest.main(verbosity=2)
