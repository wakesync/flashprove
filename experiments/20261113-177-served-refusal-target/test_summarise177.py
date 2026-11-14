#!/usr/bin/env python3
"""Synthetic regression tests only: made-up token IDs, no suite replies or data.
Run: python3 test_summarise177.py
The frozen prompt IDs are labels, not token IDs. Stop IDs are mocked too.
"""
import copy
import unittest
from unittest.mock import patch
import summarise177 as S


def fixture(n_reply=3):
    ids = {"prompts": []}
    fw = {"sequences": {}, "prompts": {}}
    for pid in [f"r{i:02}" for i in range(1, 7)] + ["c01", "c02"]:
        npr = 62 if pid == "r01" else 5
        reply = list(range(101, 101 + n_reply))  # invented, not model output
        prompt = [7] * npr
        T = npr + n_reply - 1
        q = dict(id=pid, kind="refusal-type" if pid.startswith("r") else "control",
                 included=True, reasons=[], n_prompt=npr, n_reply=n_reply,
                 finish_reason="length", prompt_ids=prompt, reply_ids=reply,
                 reply_ids_sha256="synthetic-" + pid, content_sha256="synthetic-content-" + pid,
                 refusal_rule=dict(is_refusal=False, markers_matched=[]))
        ids["prompts"].append(q)
        fw["sequences"][pid] = dict(n_prompt=npr, n_reply=n_reply,
                                   reply_ids=reply, input_ids=prompt + reply[:-1])
        top = [7] * (npr - 1) + reply
        stock = top.copy()
        if pid.startswith("r"):
            stock[npr - 1] = 999
        fw["prompts"][pid] = dict(T=T, stock_top1=stock, abl_top1=top,
                                 stock_margin=[1.0] * T, abl_margin=[2.0] * T,
                                 D_kl_stock_abl=[0.1] * T, kl_abl_stock=[0.2] * T)
    return fw, ids


class SummariserTests(unittest.TestCase):
    def setUp(self):
        self.fw, self.ids = fixture()

    def reject(self, fw=None, ids=None):
        with self.assertRaises((ValueError, AssertionError, KeyError)):
            S.summarise(self.fw if fw is None else fw, self.ids if ids is None else ids)

    def test_window_target_and_pass(self):
        s = S.summarise(self.fw, self.ids)
        self.assertEqual(s["H0"]["positions"], 24)
        self.assertEqual(s["verdict"], "PASS")
        self.assertEqual(s["target"]["id"], "r01")  # all six tie, lowest ID wins
        q = s["prompts"][0]
        self.assertEqual(q["window"]["n"], 2)
        self.assertEqual(q["all"]["n"], 3)
        self.assertEqual(q["window"]["separating"], 1)

    def test_public_refusal_redaction(self):
        public = S.public(S.summarise(self.fw, self.ids))
        forbidden = {"_stock_top1", "_abl_top1", "_served", "stock_top1", "abl_top1", "served_id"}
        for q in public["prompts"]:
            if q["kind"] == "refusal-type":
                self.assertTrue(all(not forbidden.intersection(p) for p in q["positions"]))

    def test_stop_rule_with_made_up_ids(self):
        q = self.ids["prompts"][-1]
        q["finish_reason"] = "stop"
        r = self.fw["prompts"][q["id"]]
        r["stock_top1"][-1] = 901
        r["abl_top1"][-1] = 902
        with patch.object(S, "STOP_SET", {901, 902}):
            last = S.summarise(self.fw, self.ids)["prompts"][-1]["positions"][-1]
        self.assertTrue(last["stock_eq_served"] and last["abl_eq_served"])

    def test_fail_without_separation(self):
        for r in self.fw["prompts"].values():
            r["stock_top1"] = r["abl_top1"].copy()
        s = S.summarise(self.fw, self.ids)
        self.assertEqual(s["verdict"], "FAIL")
        self.assertIsNone(s["target"])

    def test_target_in_question(self):
        self.fw["prompts"]["r02"]["abl_top1"][-1] = 999
        self.assertEqual(S.summarise(self.fw, self.ids)["verdict"], "FAIL (target in question)")

    def test_broken(self):
        for r in self.fw["prompts"].values():
            r["abl_top1"][-1] = 999
        self.assertEqual(S.summarise(self.fw, self.ids)["verdict"], "BROKEN")

    def test_missing_prompt(self):
        self.ids["prompts"].pop(0)
        self.reject()

    def test_duplicate_prompt(self):
        self.ids["prompts"].append(copy.deepcopy(self.ids["prompts"][0]))
        self.reject()

    def test_unexpected_prompt(self):
        self.ids["prompts"][0]["id"] = "unexpected"
        self.reject()

    def test_wrong_kind(self):
        self.ids["prompts"][0]["kind"] = "control"
        self.reject()

    def test_missing_inclusion(self):
        del self.ids["prompts"][0]["included"]
        self.reject()

    def test_non_boolean_inclusion(self):
        self.ids["prompts"][0]["included"] = 1
        self.reject()

    def test_unexplained_exclusion(self):
        self.ids["prompts"][0]["included"] = False
        self.reject()

    def test_missing_reasons(self):
        del self.ids["prompts"][0]["reasons"]
        self.reject()

    def test_blank_exclusion_reason(self):
        self.ids["prompts"][0].update(included=False, reasons=[""])
        self.reject()

    def test_included_with_exclusion_reason(self):
        self.ids["prompts"][0]["reasons"] = ["synthetic count mismatch"]
        self.reject()

    def exclude(self, q):
        q.update(included=False, reasons=["synthetic count mismatch"])
        del self.fw["sequences"][q["id"]]
        del self.fw["prompts"][q["id"]]

    def test_explicit_exclusion_allowed(self):
        self.exclude(self.ids["prompts"][0])
        s = S.summarise(self.fw, self.ids)
        self.assertEqual(s["H0"]["positions"], 21)
        self.assertEqual(len(s["prompts"]), 7)

    def test_registered_exclusion_stop(self):
        for q in self.ids["prompts"][:3]:
            self.exclude(q)
        self.reject()

    def test_missing_forward_record(self):
        del self.fw["prompts"]["r01"]
        self.reject()

    def test_missing_sequence(self):
        del self.fw["sequences"]["r01"]
        self.reject()

    def test_unexpected_forward_record(self):
        self.fw["prompts"]["unexpected"] = copy.deepcopy(self.fw["prompts"]["r01"])
        self.reject()

    def test_missing_arm(self):
        for key in ("stock_top1", "abl_top1", "stock_margin", "abl_margin", "D_kl_stock_abl", "kl_abl_stock"):
            with self.subTest(key=key):
                fw = copy.deepcopy(self.fw)
                del fw["prompts"]["r01"][key]
                self.reject(fw=fw)

    def test_short_and_long_arrays(self):
        for delta in (-1, 1):
            with self.subTest(delta=delta):
                fw = copy.deepcopy(self.fw)
                r = fw["prompts"]["r01"]
                r["abl_top1"] = r["abl_top1"][:-1] if delta < 0 else r["abl_top1"] + [999]
                self.reject(fw=fw)


if __name__ == "__main__":
    unittest.main()
