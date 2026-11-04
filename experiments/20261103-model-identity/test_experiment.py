#!/usr/bin/env python3
"""Checks fixture equivalence, interventions, and the saved score arithmetic."""
import json
import struct
from pathlib import Path
import unittest
import run


class ExperimentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        run.torch.set_num_threads(2)
        cls.p = run.Parameters.read(run.CONFIG / 'policy.txt')
        cls.weights, _ = run.make_weights(cls.p)
        cls.stock = run.IntegerModel(cls.p, cls.weights['stock'], 'cpu')

    def test_same_model_as_stored_exact_fixture(self):
        folder = run.ROOT / 'examples/accepted-proof'
        data = (folder / 'example.req').read_bytes()
        words = list(struct.unpack('<' + 'I' * (len(data) // 4), data))
        tokens, r, e = words[:-2], words[-2], words[-1]
        y, = struct.unpack('<I', (folder / 'example.y').read_bytes())
        seq = self.stock.new_sequence()
        choices, gaps = self.stock.extend(seq, tokens, gap_for=tokens[1:] + [y])
        self.stock.free(seq)
        self.assertEqual(gaps[r:e].tolist(), [0] * (e - r))
        self.assertEqual(choices[r:e].tolist(), (tokens[1:] + [y])[r:e])

    def test_projection_is_exact_and_not_stock_mutation(self):
        stock, projected = self.weights['stock'], self.weights['direction_projected']
        self.assertTrue(run.torch.equal(stock._embedding[:, 1:], projected._embedding[:, 1:]))
        self.assertEqual(int(projected._embedding[:, 0].abs().sum()), 0)
        self.assertGreater(int(stock._embedding[:, 0].abs().sum()), 0)
        for key, matrix in stock._matrices.items():
            changed = projected._matrices[key]
            if key[0] in ('Wo', 'Wd', 'Wdr'):
                self.assertEqual(int(changed[0].abs().sum()), 0)
                self.assertTrue(run.torch.equal(matrix[1:], changed[1:]))
            else:
                self.assertTrue(run.torch.equal(matrix, changed))

    def test_weight_surrogate_changes_only_one_column(self):
        stock, surrogate = self.weights['stock'], self.weights['column_doubled_surrogate']
        for key, matrix in stock._matrices.items():
            changed = surrogate._matrices[key]
            if key == ('Wd', 0, None):
                self.assertTrue(run.torch.equal(matrix[:, 1:], changed[:, 1:]))
                expected = (2 * matrix[:, 0].to(run.torch.int32)).clamp(-4096, 4095)
                self.assertTrue(run.torch.equal(changed[:, 0], expected))
            else:
                self.assertTrue(run.torch.equal(matrix, changed))

    def test_runtime_injection_at_layer_boundary(self):
        model = run.RuntimeSteered(self.p, self.weights['stock'], 'cpu')
        prompt = [17, 400, 3]
        observed = {}
        def record(name, layer, tensor):
            if name == 'x' and layer == 1:
                observed['x'] = tensor.clone()
        for vector in [None, run.torch.arange(self.p.d, dtype=run.torch.int64) - 256]:
            model.vector, model.capture = vector, True
            seq = model.new_sequence()
            model.extend(seq, prompt, record=record)
            model.free(seq)
            expected = model.residuals if vector is None else model.residuals + vector
            self.assertTrue(run.torch.equal(observed['x'], expected))

    def test_saved_scores_independent_integer_recount(self):
        data = json.loads((run.HERE / 'numbers.json').read_text())
        self.assertEqual(len(data['dose_rows']), 65)
        self.assertEqual(len(data['variant_rows']), 15)
        self.assertEqual(data['fresh_commitments'], 0)
        self.assertEqual(data['fresh_proofs'], 0)
        for row in data['dose_rows']:
            if 'error' in row:
                continue
            self.assertLess(abs(row['realized_dose'] - abs(row['dose'])), .001)
            costs = [gap + 256 for gap in row['score']['gaps']]
            for policy, params in data['policies'].items():
                accepts = (sum(min(c, params['C']) for c in costs) <= 4 * params['theta']
                           and len([c for c in costs if c > params['C']]) <= params['cap'])
                self.assertEqual(accepts, row['score'][policy]['accept'])
            self.assertEqual(row['changed_tokens'] == 0, row['score']['strict']['accept'])
        for row in data['variant_rows']:
            if 'error' not in row:
                self.assertTrue(row['own_model_score']['strict']['accept'])
        self.assertEqual(len(data['stored_proof_controls']), 22)


if __name__ == '__main__':
    unittest.main(verbosity=2)
