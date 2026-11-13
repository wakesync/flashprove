#!/usr/bin/env python3
# Copyright 2026 Anthropic PBC
# SPDX-License-Identifier: Apache-2.0

"""Tests the digest lines that scales/words_to_policy.py writes, for a base file with and without experts.

usage: test_words_to_policy_dense.py

new_lines() replaces the digest lines of a base parameter file with those that policy_tables.py computes
from the new values. Before PR #158 policy_tables.digests() raised for a file with NE 0, so the converter
ended with input-policy-tables on a dense base file with digest lines. Since then it writes the 32 lines.
These tests pin that path, and the path of a file with experts as a control.

The base file is the small model's parameter file of integrations/vllm/integer_model (read, not copied or
edited). The dense variant changes only the line NE, as test_policy_tables.py does: such a file is not one
that the verifier accepts, but the converter and the table tool read no other line for the tables.
Exit status 0 and a last line "OK": every test passed.
"""

import importlib.util
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
TREE = os.path.join(HERE, "..", "..")
SMALL = os.path.join(TREE, "integrations", "vllm", "integer_model", "tests", "configurations", "tiny_without_clamps", "policy.txt")
sys.dont_write_bytecode = True


def load(name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(HERE, "..", name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


w2p = load("words_to_policy")
policy_tables = load("policy_tables")
DW = policy_tables.DW


def read_lines(path):
    with open(path, encoding="ascii", newline="") as f:
        return f.read()[:-1].split("\n")


def value(lines, name):
    return int(next(line for line in lines if line.startswith(name + " ")).split(" ")[1])


def model(lines, **changed):
    """The values that new_lines() writes, read back from the base file, so that only `changed` moves."""
    m = {"MF": value(lines, "MF"), "KF": value(lines, "KF"), "S": value(lines, "S"), "rx": value(lines, "rx"),
         "cs": value(lines, "cs"), "E_logit": value(lines, "s")}  # fmt: skip
    for line, name in (("eps1", "eps1"), ("eps2", "eps2"), ("epsF", "epsF"), ("theta0", "theta")):
        m[name] = value(lines, line + "_lo") + (value(lines, line + "_hi") << 32)
    m.update(changed)
    return m


def digest_part(lines):
    return [line for line in lines if policy_tables.is_table_line(line)]


def plain_part(lines):
    return [line for line in lines if not policy_tables.is_table_line(line)]


class Converter(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.experts = read_lines(SMALL)
        assert value(cls.experts, "NE") > 0
        cls.dense = ["NE 0" if line.startswith("NE ") else line for line in cls.experts]

    def check_written(self, base, m):
        """new_lines() writes the full set of digest lines, equal to policy_tables.py's for the new file, in the
        place of the base file's first digest line."""
        new, _ = w2p.new_lines(base, m)
        lines = digest_part(new)
        self.assertEqual(len(lines), policy_tables.TBLW)
        self.assertEqual(lines, policy_tables.table_lines(policy_tables.digests(plain_part(new))))
        first = next(i for i, line in enumerate(base) if policy_tables.is_table_line(line))
        self.assertEqual(new[first : first + policy_tables.TBLW], lines)
        return new, lines

    def test_a_dense_base_with_digest_lines_gets_the_dense_lines(self):
        new, lines = self.check_written(self.dense, model(self.dense))
        self.assertEqual([line for line in lines if line.startswith("tsig")], ["tsig%d 0" % i for i in range(DW)])
        # SiLU, rotary and softmax lines are those of the file with experts (the tables do not depend on NE).
        same = [line for line in digest_part(self.experts) if not line.startswith("tsig")]
        self.assertEqual([line for line in lines if not line.startswith("tsig")], same)
        self.assertEqual(plain_part(new), plain_part(self.dense))

    def test_a_dense_base_with_the_expert_lines_is_corrected(self):
        """The base file's (wrong, nonzero) sigmoid lines are replaced, not kept."""
        self.assertNotEqual([line for line in digest_part(self.dense) if line.startswith("tsig")], ["tsig%d 0" % i for i in range(DW)])
        _, lines = self.check_written(self.dense, model(self.dense))
        self.assertTrue(all(line.split(" ")[1] == "0" for line in lines if line.startswith("tsig")))

    def test_a_dense_base_with_partial_lines_is_completed(self):
        partial = [line for line in self.dense if not line.startswith("tsig")]
        self.check_written(partial, model(partial))

    def test_a_new_value_moves_only_its_table_on_a_dense_base(self):
        _, before = self.check_written(self.dense, model(self.dense))
        _, after = self.check_written(self.dense, model(self.dense, rx=value(self.dense, "rx") + 2))
        moved = {line.rstrip("0123456789 ") for line in after if line not in before}
        self.assertEqual(moved, {"texp"})

    def test_a_dense_base_without_digest_lines_gets_none(self):
        plain = plain_part(self.dense)
        new, _ = w2p.new_lines(plain, model(plain))
        self.assertEqual(new, plain)

    def test_control_a_base_with_experts_is_unchanged(self):
        """Control: with experts and the base file's own values, the new file is the base file."""
        new, moved = w2p.new_lines(self.experts, model(self.experts))
        self.assertEqual((new, moved), (self.experts, 0))
        self.assertNotEqual([line for line in digest_part(new) if line.startswith("tsig")], ["tsig%d 0" % i for i in range(DW)])


if __name__ == "__main__":
    unittest.main()
