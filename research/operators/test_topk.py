import itertools
import random
import subprocess
import tempfile
import unittest
from pathlib import Path
from topk import build, P

ROOT = Path(__file__).resolve().parents[2]


class Tests(unittest.TestCase):
    def test_random_and_exhaustive_orders(self):
        rng = random.Random(530042)
        for _ in range(100):
            n = rng.randrange(2, 9)
            s = [rng.randrange(256) for _ in range(n)]
            b = [rng.randrange(-128, 128) for _ in range(n)]
            k = rng.randrange(1, n+1)
            self.assertTrue(build(s, b, k).check())
        for s, b in [([3, 3, 3, 3], [0]*4), ([0, 255, 1, 9], [127, -128, 0, 0])]:
            expected = sorted(range(4), key=lambda i: (-(s[i]+b[i]), i))
            for order in itertools.permutations(range(4)):
                self.assertEqual(build(s, b, 2, order=order).check(), list(order) == expected)

    def test_dishonest_and_boundaries(self):
        self.assertFalse(build([0, 0], [0, 0], 1).check())
        self.assertTrue(build([255]*8, [127]*8, 8).check())
        self.assertTrue(build([1, 0], [-128, 127], 2).check())
        self.assertFalse(build([20, 10, 5], [0]*3, 2, order=[0, 0, 2]).check())
        self.assertFalse(build([1, 200], [127, -128], 1, order=[1, 0]).check())
        # unbiased normalization: bias flips selection but never enters denominator.
        c = build([10, 20, 30], [127, 0, -128], 2)
        self.assertTrue(c.check())
        self.assertEqual([c.values[c.names.index(f'weight{j}')] for j in range(2)], [85, 170])
        self.assertFalse(build([10, 20, 30], [127, 0, -128], 2, weights=[86, 170]).check())
        for s,b,k in [([256,1],[0,0],1), ([1,1],[128,0],1), ([True,1],[0,0],1), ([1,1],[0,0],True)]:
            with self.assertRaises(ValueError): build(s,b,k)

    def test_fixed_constraints_and_small_domain(self):
        honest = build([10, 20, 30], [0, 0, 0], 2)
        dishonest = build([10, 20, 30], [0, 0, 0], 2, order=[0, 1, 2])
        self.assertEqual(honest.rows, dishonest.rows)
        self.assertEqual(honest.names, dishonest.names)
        for scores in itertools.product(range(3), repeat=3):
            for biases in itertools.product([-1, 0, 1], repeat=3):
                for k in [1, 2, 3]:
                    order = sorted(range(3), key=lambda i: (-(scores[i]+biases[i]), i))
                    self.assertEqual(build(scores, biases, k).check(), sum(scores[i] for i in order[:k]) > 0)

    def test_every_wire_mutation(self):
        c = build([10, 20, 30, 40], [127, 0, -128, 0], 3)
        for i in range(len(c.values)):
            for delta in [1, -1, P//2]:
                w = c.values.copy()
                w[i] = (w[i]+delta) % P
                self.assertFalse(c.check(w), c.names[i])
        w = c.values.copy()
        w[1] += P
        self.assertFalse(c.check(w))

    def test_upstream_field_crosscheck(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            binary, fixture = d/'check', d/'fixture'
            subprocess.run(['g++', '-std=c++17', '-O2', '-DBLK_FIELD=2', '-I', str(ROOT/'blocks'), str(ROOT/'research/operators/check.cpp'), '-o', str(binary)], check=True)
            cases = [build([10,20,30], [127,0,-128], 2), build([10,20,30], [127,0,-128], 2, order=[1,0,2]), build([0,0],[0,0],1)]
            for c in cases:
                c.export(fixture)
                with fixture.open() as f:
                    p = subprocess.run([str(binary)], stdin=f, capture_output=True, text=True)
                self.assertEqual(p.returncode, 0 if c.check() else 1)
            c = cases[0]
            # Every wire also rejected by independent upstream-field evaluator.
            for i in range(len(c.values)):
                w = c.values.copy()
                w[i] = (w[i]+1) % P
                c.export(fixture, w)
                with fixture.open() as f:
                    p = subprocess.run([str(binary)], stdin=f, capture_output=True)
                self.assertEqual(p.returncode, 1, c.names[i])


if __name__ == '__main__':
    unittest.main(verbosity=2)
