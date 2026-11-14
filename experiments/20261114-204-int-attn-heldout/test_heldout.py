#!/usr/bin/env python3
"""Unit tests for the frozen-scale evaluator and the summariser (PREREG "Debug", checks a to d). Synthetic data only
(numpy default_rng(0)); no weights, no registered prompt. Run: python3 test_heldout.py  (writes runs/debug/unit-tests.json)"""
import copy, hashlib, json, math, sys, tempfile, unittest
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import heldout as H
import summarise_heldout as S   # own name: PR #178's dir (on sys.path via heldout) also has a summarise.py
IA = H.IA
NH, NKV, HD = H.NH, H.NKV, H.HD

def synth(rng, T, sq=0.6, sk=12.0, sv=7.0):
    q = rng.standard_normal((T, NH, HD)) * sq * math.sqrt(HD) / 3   # |q/16| about sq
    k = rng.standard_normal((T, NKV, HD)) * sk / 3
    v = rng.standard_normal((T, NKV, HD)) * sv / 3
    return q, k, v

class Evaluator(unittest.TestCase):
    def test_a_bit_equal_to_int_attn_with_in_run_fit(self):
        rng = np.random.default_rng(0)
        for T, cl in [(7, 2047), (11, 1665), (16, 2047)]:
            q, k, v = synth(rng, T)
            ex_ = IA.fit(float(np.abs(q).max()) / math.sqrt(HD), float(np.abs(k).max()), float(np.abs(v).max()), cl)
            oa_ref, oi_ref, st_ref = IA.arm_prompt(q, k, v, ex_, cl)
            frozen = {f: ex_[f] for f in ("Eq", "Ek", "Ev", "sh")}
            oa, oi, st = H.eval_frozen(q, k, v, frozen, cl)
            self.assertTrue(np.array_equal(oi, oi_ref))
            self.assertTrue(np.array_equal(oa, oa_ref))
            for kk, vv in st_ref.items(): self.assertEqual(st[kk], vv, kk)
            self.assertEqual(st["guard_fail"], [])
            self.assertEqual(st["scales_used"], frozen)

    def test_b_evaluation_maximum_cannot_mutate_frozen_scale(self):
        table = H.load_table()
        before = {k: dict(v) for k, v in table.items()}
        rng = np.random.default_rng(0)
        for arm, cl in H.ARMS.items():
            sc = table[(arm, 3)]
            q, k, v = synth(rng, 9)
            _, _, st0 = H.eval_frozen(q, k, v, sc, cl)
            for which, pos in (("q", (4, 13, 7)), ("k", (5, 2, 100)), ("v", (6, 3, 200))):
                q2, k2, v2 = q.copy(), k.copy(), v.copy()
                arr = {"q": q2, "k": k2, "v": v2}[which]
                arr[pos] = 100.0 * float(np.abs(arr).max())               # outlier 100x the evaluation maximum
                _, _, st = H.eval_frozen(q2, k2, v2, sc, cl)
                self.assertEqual(st["scales_used"], dict(sc))           # the scale used is the frozen one
                self.assertEqual(dict(table[(arm, 3)]), before[(arm, 3)])
                self.assertGreaterEqual(st[f"{which}_over"], st0[f"{which}_over"] + 1)   # the outlier clamps and is counted
                loc = st["q_over_by_head"] if which == "q" else st[f"{which}_over_by_kvhead"]
                self.assertGreaterEqual(loc[pos[1]], 1)                  # with its head location
                self.assertGreater(st[f"obs_mx_{which}"], st0[f"obs_mx_{which}"])   # the maximum changed, the scale did not
        with self.assertRaises(TypeError): table[("C2047", 3)]["Eq"] = 0  # read-only
        self.assertEqual({k: dict(v) for k, v in table.items()}, before)

    def test_b2_wide_guard_is_recorded(self):
        rng = np.random.default_rng(0); sc = H.load_table()[("C2047", 3)]
        q, k, v = synth(rng, 5); v[2, 1, 3] = 1e6                        # RNE far above 32,767 at the frozen E_v
        _, _, st = H.eval_frozen(q, k, v, sc, 2047)
        self.assertIn("wide value over 32767", st["guard_fail"]); self.assertGreaterEqual(st["v_over"], 1)

class Table(unittest.TestCase):
    def setUp(self):
        self.rows = [json.loads(l) for l in H.TABLE.read_text().splitlines() if l.strip()]
        self.td = tempfile.TemporaryDirectory(); self.p = Path(self.td.name) / "t.jsonl"
    def tearDown(self): self.td.cleanup()
    def put(self, rows): self.p.write_text("".join(json.dumps(r) + "\n" for r in rows))
    def test_real_table_loads(self):
        t = H.load_table(); self.assertEqual(len(t), 32)
        self.assertEqual(dict(t[("C2047", 3)]), dict(Eq=11, Ek=7, Ev=8, sh=10))
    def test_c_wrong_hash(self):
        self.put(self.rows)
        with self.assertRaises(H.TableError): H.load_table(self.p, expect_sha="0" * 64)
    def test_c_missing(self):
        self.put(self.rows[:-1])
        with self.assertRaises(H.TableError): H.load_table(self.p, expect_sha=None)
    def test_c_duplicate(self):
        self.put(self.rows + [self.rows[0]])
        with self.assertRaises(H.TableError): H.load_table(self.p, expect_sha=None)
    def test_c_extra(self):
        r = dict(self.rows[0]); r["layer"] = 4; self.put(self.rows + [r])
        with self.assertRaises(H.TableError): H.load_table(self.p, expect_sha=None)
    def test_c_wrong_clamp(self):
        rows = copy.deepcopy(self.rows); rows[1]["clamp"] = 2047; self.put(rows)
        with self.assertRaises(H.TableError): H.load_table(self.p, expect_sha=None)
    def test_c_bad_exponent(self):
        rows = copy.deepcopy(self.rows); rows[2]["Ev"] = 7.0; self.put(rows)
        with self.assertRaises(H.TableError): H.load_table(self.p, expect_sha=None)

# ------------------------------------------------------------------ summariser on made-up records
PROMPTS = [f"x{i}" for i in range(8)]; DET = ("x0", "x4")

def records(table, n_layers=16, rel=0.004, clamp_at=None):
    lay, cells, prows, tim = [], [], [], []
    for l in S.LAYERS[:n_layers]:
        tim.append(dict(layer=l, total_s=1.0, mix_bit_equal_q1={p: True for p in PROMPTS}))
        for a, cl in S.ARMS.items():
            vals = []; pr = []
            for pi, p in enumerate(PROMPTS):
                over = 1 if clamp_at == (a, l, p) else 0
                pr.append(dict(arm=a, layer=l, prompt=p, T=5, mix_rel=0.001, q_over=over, q_n=5 * 24 * 256, k_over=0, k_n=5 * 4 * 256,
                               v_over=0, v_n=5 * 4 * 256, guard_fail=[], scales_used=table[(a, l)]))
                for h in range(24):
                    r = rel * (1 + 0.01 * h + 0.001 * pi); vals.append(r); cells.append(dict(arm=a, layer=l, prompt=p, head=h, rel_y=r))
            prows += pr; arr = np.array(vals); clamps = sum(x["q_over"] for x in pr)
            lay.append(dict(arm=a, layer=l, clamp=cl, Smax=256 * cl * cl, **table[(a, l)], n_clamped=clamps, guard_failures=[],
                            q_over=clamps, q_n=8 * 5 * 24 * 256, k_over=0, k_n=8 * 5 * 4 * 256, v_over=0, v_n=8 * 5 * 4 * 256,
                            rel_median=float(np.median(arr)), rel_max=float(arr.max()), range_pass=clamps == 0,
                            fid_pass=bool(np.median(arr) <= 0.01 and arr.max() <= 0.05), det_bit_equal={d: True for d in DET},
                            scales_frozen_ok=True))
    return dict(layers=lay, cells=cells, prompt_rows=prows, timing=tim)

class Summariser(unittest.TestCase):
    def setUp(self):
        self.table = {k: dict(v) for k, v in H.load_table().items()}
        self.td = tempfile.TemporaryDirectory(); self.d = Path(self.td.name)
    def tearDown(self): self.td.cleanup()
    def write(self, R):
        for name, key in (("layers.jsonl", "layers"), ("cells.jsonl", "cells"), ("prompt-rows.jsonl", "prompt_rows"), ("attn-timing.jsonl", "timing")):
            (self.d / name).write_text("".join(json.dumps(r) + "\n" for r in R[key]))
    def run_s(self, R):
        self.write(R); return S.summarise(self.d, PROMPTS, DET, self.table)
    def refuse(self, R):
        with self.assertRaises(S.Refuse): self.run_s(R)
    def test_complete_pass(self):
        s = self.run_s(records(self.table))
        for a in S.ARMS: self.assertEqual((s["arms"][a]["H_R"], s["arms"][a]["H_F"]), ("PASS", "PASS"))
    def test_fidelity_fail_range_pass_kept_apart(self):
        s = self.run_s(records(self.table, rel=0.02))
        for a in S.ARMS: self.assertEqual((s["arms"][a]["H_R"], s["arms"][a]["H_F"]), ("PASS", "FAIL"))
    def test_clamp_is_range_fail_only(self):
        s = self.run_s(records(self.table, clamp_at=("C1665", 23, "x3")))
        self.assertEqual((s["arms"]["C1665"]["H_R"], s["arms"]["C1665"]["H_F"]), ("FAIL", "PASS"))
        self.assertEqual(s["arms"]["C1665"]["layers_range_fail"], [23]); self.assertEqual(s["arms"]["C2047"]["H_R"], "PASS")
    def test_partial(self):
        s = self.run_s(records(self.table, n_layers=5))
        self.assertEqual(s["arms"]["C2047"]["H_R"], "NOT TESTED (partial)"); self.assertEqual(len(s["arms"]["C2047"]["not_tested_layers"]), 11)
    def test_determinism_false_invalid(self):
        R = records(self.table); R["layers"][6]["det_bit_equal"]["x4"] = False
        self.assertEqual(self.run_s(R)["arms"][R["layers"][6]["arm"]]["H_F"], "comparison invalid")
    def test_split_false_invalid(self):
        R = records(self.table); R["timing"][2]["mix_bit_equal_q1"]["x1"] = False
        self.assertEqual(self.run_s(R)["arms"]["C2047"]["H_R"], "comparison invalid")
    def test_d_duplicate_cell(self):
        R = records(self.table); R["cells"].append(R["cells"][10]); self.refuse(R)
    def test_d_duplicate_head_id(self):
        R = records(self.table); R["cells"][1]["head"] = 0; self.refuse(R)
    def test_d_missing_cell(self):
        R = records(self.table); del R["cells"][100]; self.refuse(R)
    def test_d_unexpected_prompt(self):
        R = records(self.table); R["cells"][5]["prompt"] = "p01-ordinary-short"; self.refuse(R)
    def test_d_missing_arm(self):
        R = records(self.table); R["layers"] = [r for r in R["layers"] if r["arm"] != "C2047"]; self.refuse(R)
    def test_d_hole(self):
        R = records(self.table); del R["layers"][4:6]; self.refuse(R)
    def test_d_duplicate_layer(self):
        R = records(self.table); R["layers"].append(R["layers"][0]); self.refuse(R)
    def test_d_wrong_scale(self):
        R = records(self.table); R["layers"][3]["Ev"] += 1; self.refuse(R)
    def test_d_scales_used_differ(self):
        R = records(self.table); R["prompt_rows"][9]["scales_used"] = dict(R["prompt_rows"][9]["scales_used"], sh=4); self.refuse(R)
    def test_d_hidden_clamp(self):
        R = records(self.table); R["prompt_rows"][0]["q_over"] = 3; self.refuse(R)
    def test_d_wrong_median(self):
        R = records(self.table); R["layers"][0]["rel_median"] *= 0.5; self.refuse(R)
    def test_d_wrong_flag(self):
        R = records(self.table, rel=0.02); R["layers"][0]["fid_pass"] = True; self.refuse(R)
    def test_d_det_evidence_missing(self):
        R = records(self.table); R["layers"][1]["det_bit_equal"] = {"x0": True}; self.refuse(R)
    def test_d_malformed(self):
        self.write(records(self.table)); (self.d / "cells.jsonl").write_text("{not json\n")
        with self.assertRaises(S.Refuse): S.summarise(self.d, PROMPTS, DET, self.table)
    def test_d_missing_file(self):
        self.write(records(self.table)); (self.d / "attn-timing.jsonl").unlink()
        with self.assertRaises(S.Refuse): S.summarise(self.d, PROMPTS, DET, self.table)
    def test_d_interrupted_layer_cells(self):
        R = records(self.table, n_layers=4); R["cells"].append(dict(arm="C2047", layer=19, prompt="x0", head=0, rel_y=0.1)); self.refuse(R)

if __name__ == "__main__":
    res = unittest.main(exit=False, verbosity=2).result
    out = dict(ran=res.testsRun, failures=len(res.failures), errors=len(res.errors), ok=res.wasSuccessful(),
               int_attn_sha256=hashlib.sha256((H.SRC176 / "int_attn.py").read_bytes()).hexdigest(), table_sha256=H.TABLE_SHA,
               note="synthetic data only; no weights, no registered prompt")
    (HERE / "runs" / "debug").mkdir(parents=True, exist_ok=True)
    (HERE / "runs" / "debug" / "unit-tests.json").write_text(json.dumps(out, indent=1) + "\n")
    raise SystemExit(0 if res.wasSuccessful() else 1)
