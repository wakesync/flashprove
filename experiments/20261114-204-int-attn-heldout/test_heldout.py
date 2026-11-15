#!/usr/bin/env python3
"""Unit tests for the frozen-scale evaluator and the summariser (PREREG "Debug", checks a to d, plus the fail-closed checks
of Amendments A1, A2 and A3). Synthetic data (numpy default_rng(0)), plus temporary copies of the committed run records
that the tests create and remove (the committed files are only read); no weights, no model forward, no registered prompt
run. Run: python3 test_heldout.py  (writes runs/debug/unit-tests-a3.json; runs/debug/unit-tests.json is the 27b057dd
receipt, runs/debug/unit-tests-a1.json the 2e7dc350 receipt and runs/debug/unit-tests-a2.json the d516e11e receipt; none
is overwritten)"""
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

NTOK = {p: 5 for p in PROMPTS}   # synthetic manifest lengths (Amendment A1 tests pass it as ntok)

def records(table, n_layers=16, rel=0.004, clamp_at=None):
    # Amendment A1: rows now also carry the per-head clamp arrays and max |RNE| the real run records carry
    # (q_over_by_head, k_over_by_kvhead, v_over_by_kvhead, q_maxw, k_maxw, v_maxw), consistent with the counts.
    lay, cells, prows, tim = [], [], [], []
    for l in S.LAYERS[:n_layers]:
        tim.append(dict(layer=l, total_s=1.0, float_s=0.2, ref_attention_s=0.3, mix_bit_equal_q1={p: True for p in PROMPTS}))
        for a, cl in S.ARMS.items():
            vals = []; pr = []
            for pi, p in enumerate(PROMPTS):
                over = 1 if clamp_at == (a, l, p) else 0
                qh = [0] * 24; qh[5] = over
                pr.append(dict(arm=a, layer=l, prompt=p, T=5, mix_rel=0.001, q_over=over, q_n=5 * 24 * 256, k_over=0, k_n=5 * 4 * 256,
                               v_over=0, v_n=5 * 4 * 256, q_maxw=cl + 10 if over else 1000, k_maxw=1000, v_maxw=1000,
                               q_over_by_head=qh, k_over_by_kvhead=[0] * 4, v_over_by_kvhead=[0] * 4,
                               guard_fail=[], scales_used=table[(a, l)],
                               # A2: the descriptive fields the real rows carry
                               max_abs_s=1000.0, e_zero=0, causal=24 * 5 * 6 // 2, wide_over_32767=0,
                               obs_mx_q=0.5, obs_mx_k=10.0, obs_mx_v=5.0))
                for h in range(24):
                    r = rel * (1 + 0.01 * h + 0.001 * pi); vals.append(r); cells.append(dict(arm=a, layer=l, prompt=p, head=h, rel_y=r))
            prows += pr; arr = np.array(vals); clamps = sum(x["q_over"] for x in pr)
            lay.append(dict(arm=a, layer=l, clamp=cl, Smax=256 * cl * cl, **table[(a, l)], n_clamped=clamps, guard_failures=[],
                            q_over=clamps, q_n=8 * 5 * 24 * 256, k_over=0, k_n=8 * 5 * 4 * 256, v_over=0, v_n=8 * 5 * 4 * 256,
                            q_maxw=max(x["q_maxw"] for x in pr), k_maxw=1000, v_maxw=1000,
                            obs_mx_q=0.5, obs_mx_k=10.0, obs_mx_v=5.0, max_abs_s=1000.0, e_zero=0, causal=8 * 360,
                            wide_over_32767=0, n_pairs=192, n_cells_valid=192, rel_min=float(arr.min()),
                            n_over_001=int((arr > 0.01).sum()), n_over_005=int((arr > 0.05).sum()), arm_seconds=1.0,
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

# ------------------------------------------------------------------ Amendment A1: fail closed on malformed evidence
# One test per malformed case named in the review of PR #206 (comment 6874859970), each on synthetic records, plus
# the same cases on a COPY of the committed run records (CommittedCopy below): the copy lives in a temporary
# directory the test creates and removes; the committed files under runs/ are only read.

def find(rows, **kv): return next(i for i, r in enumerate(rows) if all(r.get(k) == v for k, v in kv.items()))

class FailClosed(unittest.TestCase):
    setUp, tearDown, write = Summariser.setUp, Summariser.tearDown, Summariser.write   # helpers only, not the tests
    def refuse(self, R):
        self.write(R)
        with self.assertRaises(S.Refuse): S.summarise(self.d, PROMPTS, DET, self.table)
    def refuse_nt(self, R):
        self.write(R)
        with self.assertRaises(S.Refuse): S.summarise(self.d, PROMPTS, DET, self.table, NTOK)
    def test_a1_wellformed_with_manifest_lengths(self):
        self.write(records(self.table, clamp_at=("C2047", 23, "x2")))
        s = S.summarise(self.d, PROMPTS, DET, self.table, NTOK)
        self.assertEqual((s["arms"]["C2047"]["H_R"], s["arms"]["C1665"]["H_R"]), ("FAIL", "PASS"))
    def test_a1_negative_count_cancelling_a_clamp(self):
        # the review's case: a real clamp on one prompt and -1 on another make the layer total 0 -> was a false H_R PASS
        R = records(self.table, clamp_at=("C2047", 23, "x2"))
        R["prompt_rows"][find(R["prompt_rows"], arm="C2047", layer=23, prompt="x0")]["q_over"] = -1
        R["prompt_rows"][find(R["prompt_rows"], arm="C2047", layer=23, prompt="x0")]["q_over_by_head"][0] = -1
        i = find(R["layers"], arm="C2047", layer=23); R["layers"][i].update(q_over=0, n_clamped=0, range_pass=True)
        self.refuse_nt(R)
    def test_a1_negative_count_alone(self):
        R = records(self.table); R["prompt_rows"][3]["v_over"] = -1; self.refuse_nt(R)
    def test_a1_count_over_denominator(self):
        R = records(self.table); p = R["prompt_rows"][3]; p["k_over"] = p["k_n"] + 1; self.refuse_nt(R)
    def test_a1_float_or_bool_count(self):
        R = records(self.table); R["prompt_rows"][3]["q_over"] = 0.0; self.refuse_nt(R)
        R = records(self.table); R["prompt_rows"][3]["q_over"] = False; self.refuse_nt(R)
    def test_a1_per_head_counts_disagree_with_total(self):
        R = records(self.table, clamp_at=("C1665", 11, "x3"))
        R["prompt_rows"][find(R["prompt_rows"], arm="C1665", layer=11, prompt="x3")]["q_over_by_head"] = [0] * 24
        self.refuse_nt(R)
    def test_a1_per_head_array_wrong_length(self):
        R = records(self.table); R["prompt_rows"][0]["v_over_by_kvhead"] = [0] * 3; self.refuse_nt(R)
    def test_a1_count_without_rne_over_clamp(self):
        R = records(self.table, clamp_at=("C2047", 23, "x2"))
        R["prompt_rows"][find(R["prompt_rows"], arm="C2047", layer=23, prompt="x2")]["q_maxw"] = 1000; self.refuse_nt(R)
    def test_a1_rne_over_clamp_without_count(self):
        R = records(self.table); R["prompt_rows"][0]["k_maxw"] = 5000; self.refuse_nt(R)
    def test_a1_nan_rel_y(self):
        R = records(self.table); R["cells"][7]["rel_y"] = float("nan"); self.refuse_nt(R)
    def test_a1_infinite_rel_y(self):
        R = records(self.table); R["cells"][7]["rel_y"] = float("inf"); self.refuse_nt(R)
    def test_a1_negative_rel_y(self):
        R = records(self.table); R["cells"][7]["rel_y"] = -1.0; self.refuse_nt(R)
    def test_a1_nan_layer_statistic(self):
        R = records(self.table); R["layers"][2]["rel_median"] = float("nan"); self.refuse_nt(R)
    def test_a1_T_zero(self):
        R = records(self.table); R["prompt_rows"][0]["T"] = 0; self.refuse_nt(R)
        R = records(self.table); R["prompt_rows"][0]["T"] = 0; self.refuse(R)          # also without the manifest
    def test_a1_T_not_manifest_length(self):
        R = records(self.table); R["prompt_rows"][0]["T"] = 6
        for t, nh in (("q", 24), ("k", 4), ("v", 4)): R["prompt_rows"][0][f"{t}_n"] = 6 * nh * 256
        self.refuse_nt(R)
    def test_a1_denominator_not_T_times_heads(self):
        R = records(self.table); R["prompt_rows"][0]["q_n"] += 1; self.refuse_nt(R)
    def test_a1_layer_denominator_not_manifest_total(self):
        R = records(self.table); R["layers"][0]["v_n"] += 256; self.refuse_nt(R)
    def test_a1_string_false_determinism(self):
        # the review's case: both values "false" (strings) were truthy and counted as determinism held
        R = records(self.table); R["layers"][4]["det_bit_equal"] = {d: "false" for d in DET}; self.refuse_nt(R)
    def test_a1_string_split_flag(self):
        R = records(self.table); R["timing"][1]["mix_bit_equal_q1"]["x2"] = "true"; self.refuse_nt(R)
    def test_a1_non_boolean_pass_flag(self):
        R = records(self.table); R["layers"][0]["range_pass"] = 1; self.refuse_nt(R)
    def test_a1_string_scales_frozen_ok(self):
        R = records(self.table); R["layers"][0]["scales_frozen_ok"] = "yes"; self.refuse_nt(R)

RUNS = HERE / "runs"
class CommittedCopy(unittest.TestCase):
    """The review's probes, reproduced on a temporary copy of the committed run records."""
    def setUp(self):
        self.table = {k: dict(v) for k, v in H.load_table().items()}
        man = json.loads((HERE / "prompts-heldout.json").read_text())
        self.prompts = [p["id"] for p in man["prompts"]]; self.det = tuple(man["determinism_subset"])
        self.ntok = {p["id"]: p["n_tokens"] for p in man["prompts"]}
        self.td = tempfile.TemporaryDirectory(); self.d = Path(self.td.name)
        self.R = {n: [json.loads(x) for x in (RUNS / n).read_text().splitlines() if x.strip()]
                  for n in ("layers.jsonl", "cells.jsonl", "prompt-rows.jsonl", "attn-timing.jsonl")}
    def tearDown(self): self.td.cleanup()
    def run_copy(self):
        for n, rows in self.R.items(): (self.d / n).write_text("".join(json.dumps(r) + "\n" for r in rows))
        return S.summarise(self.d, self.prompts, self.det, self.table, self.ntok)
    def refuse(self):
        with self.assertRaises(S.Refuse): self.run_copy()
    def test_copy_unmodified_is_accepted_and_unchanged(self):
        s = self.run_copy()
        for a in S.ARMS: self.assertEqual((s["arms"][a]["H_R"], s["arms"][a]["H_F"], s["arms"][a]["valid"]), ("FAIL", "FAIL", True))
        self.assertEqual(json.dumps(s, indent=1) + "\n", (RUNS / "summary.json").read_text())
    def test_copy_negative_v_over_cancels_real_clamp(self):
        P, L = self.R["prompt-rows.jsonl"], self.R["layers.jsonl"]
        P[find(P, arm="C2047", layer=23, prompt="h01-prose-short")]["v_over"] = -1
        L[find(L, arm="C2047", layer=23)].update(v_over=0, n_clamped=0, range_pass=True)
        self.refuse()
    def test_copy_nan_rel_y(self):
        C = self.R["cells.jsonl"]; C[find(C, arm="C2047", layer=31)]["rel_y"] = float("nan"); self.refuse()
    def test_copy_negative_minimum_rel_y(self):
        C = self.R["cells.jsonl"]; idx = [i for i, c in enumerate(C) if c["arm"] == "C2047" and c["layer"] == 3]
        C[min(idx, key=lambda i: C[i]["rel_y"])]["rel_y"] = -1.0; self.refuse()
    def test_copy_T_zero(self):
        self.R["prompt-rows.jsonl"][0]["T"] = 0; self.refuse()
    def test_copy_string_false_determinism(self):
        L = self.R["layers.jsonl"]; L[5]["det_bit_equal"] = {k: "false" for k in L[5]["det_bit_equal"]}; self.refuse()

# ------------------------------------------------------------------ Amendment A2 (second review of PR #206, comment 6875930332)
GUARD = "score not an exact integer"      # the text of int_attn's first assertion, as heldout.eval_frozen records it

def guard_prompt(R, a, l, p, cells_key, prows_key, layers_key, guard=GUARD):
    """Rewrite one prompt of one layer into the representation heldout.py writes when the arithmetic assertion fires
    (eval_frozen except-branch + attention_layer): null mix_rel / max_abs_s / e_zero / causal, guard_fail [text], 24 null
    rel_y; the layer row's guard list, flags and statistics recomputed the way attention_layer computes them. A3: if the
    prompt is a determinism prompt its det_bit_equal is set false, as attention_layer does when the integer output is None
    (until A3 this helper left it true, which the evaluator never writes)."""
    P, C, L = R[prows_key], R[cells_key], R[layers_key]
    dbe = L[find(L, arm=a, layer=l)]["det_bit_equal"]
    if p in dbe: dbe[p] = False
    P[find(P, arm=a, layer=l, prompt=p)].update(mix_rel=None, max_abs_s=None, e_zero=None, causal=None, guard_fail=[guard])
    for c in C:
        if (c["arm"], c["layer"], c["prompt"]) == (a, l, p): c["rel_y"] = None
    pr = [x for x in P if (x["arm"], x["layer"]) == (a, l)]
    allrel = [c["rel_y"] for c in C if (c["arm"], c["layer"]) == (a, l)]
    good = [x for x in allrel if x is not None]; arr = np.array(good) if good else np.array([np.nan])
    L[find(L, arm=a, layer=l)].update(
        guard_failures=[dict(prompt=x["prompt"], guard=g) for x in pr for g in x["guard_fail"]], range_pass=False, fid_pass=False,
        n_pairs=len(allrel), n_cells_valid=len(good), rel_median=float(np.median(arr)), rel_max=float(arr.max()),
        rel_min=float(arr.min()), n_over_001=int((arr > 0.01).sum()), n_over_005=int((arr > 0.05).sum()),
        max_abs_s=max([0.0] + [x["max_abs_s"] or 0 for x in pr]), e_zero=sum(x["e_zero"] or 0 for x in pr),
        causal=sum(x["causal"] or 0 for x in pr))

class GuardedNull(unittest.TestCase):
    """A2 (1): the evaluator's guarded-null path is a registered FAIL, admitted; nulls anywhere else are refused."""
    setUp, tearDown, write = Summariser.setUp, Summariser.tearDown, Summariser.write
    def run_nt(self, R):
        self.write(R); return S.summarise(self.d, PROMPTS, DET, self.table, NTOK)
    def refuse_nt(self, R):
        with self.assertRaises(S.Refuse): self.run_nt(R)
    def test_a2_one_guarded_prompt_is_fail_fail(self):
        R = records(self.table); guard_prompt(R, "C2047", 3, "x2", "cells", "prompt_rows", "layers")
        s = self.run_nt(R)["arms"]["C2047"]
        self.assertEqual((s["H_R"], s["H_F"], s["valid"], s["total_guard_failures"]), ("FAIL", "FAIL", True, 1))
        self.assertEqual((s["layers_range_fail"], s["layers_fid_fail"]), ([3], [3]))
        x = s["layers"][0]; self.assertEqual((x["n_cells"], x["n_valid"]), (192, 168))
    def test_a2_whole_layer_guarded_gives_nan_statistics_and_fail(self):
        # A3: the guarded determinism prompts x0 and x4 now carry det false, as the evaluator writes, so V2 fails and the
        # registered validity rule makes the arm "comparison invalid" (A2's version kept det true and expected FAIL / FAIL)
        R = records(self.table)
        for p in PROMPTS: guard_prompt(R, "C1665", 7, p, "cells", "prompt_rows", "layers")
        self.assertTrue(math.isnan(R["layers"][find(R["layers"], arm="C1665", layer=7)]["rel_median"]))
        s = self.run_nt(R)["arms"]["C1665"]
        self.assertEqual((s["H_R"], s["H_F"], s["valid"], s["total_guard_failures"]), ("comparison invalid", "comparison invalid", False, 8))
        self.assertEqual((s["layers_range_fail"], s["layers_fid_fail"]), ([7], [7]))
        x = s["layers"][1]; self.assertEqual((x["n_cells"], x["n_valid"], x["rel_median"], x["rel_max"]), (192, 0, None, None))
        self.assertEqual(s["pooled"]["n"], 15 * 192)
    def test_a2_assertion_plus_wide_guard(self):
        R = records(self.table); guard_prompt(R, "C2047", 3, "x2", "cells", "prompt_rows", "layers")
        P = R["prompt_rows"]; i = find(P, arm="C2047", layer=3, prompt="x2")
        P[i].update(q_over=1, q_maxw=40000, wide_over_32767=1, guard_fail=[GUARD, S.WIDE_GUARD]); P[i]["q_over_by_head"][0] = 1
        Li = find(R["layers"], arm="C2047", layer=3)
        R["layers"][Li].update(q_over=1, n_clamped=1, q_maxw=40000, wide_over_32767=1,
                               guard_failures=[dict(prompt="x2", guard=GUARD), dict(prompt="x2", guard=S.WIDE_GUARD)])
        self.assertEqual(self.run_nt(R)["arms"]["C2047"]["total_guard_failures"], 2)
    def test_a2_null_mix_rel_without_guard(self):
        R = records(self.table); R["prompt_rows"][3]["mix_rel"] = None; self.refuse_nt(R)
    def test_a2_all_four_null_without_guard(self):
        R = records(self.table); R["prompt_rows"][3].update(mix_rel=None, max_abs_s=None, e_zero=None, causal=None); self.refuse_nt(R)
    def test_a2_partial_null_set_with_guard(self):
        R = records(self.table); guard_prompt(R, "C2047", 3, "x2", "cells", "prompt_rows", "layers")
        R["prompt_rows"][find(R["prompt_rows"], arm="C2047", layer=3, prompt="x2")]["causal"] = 360; self.refuse_nt(R)
    def test_a2_null_with_only_the_wide_guard(self):
        R = records(self.table); guard_prompt(R, "C2047", 3, "x2", "cells", "prompt_rows", "layers", guard=S.WIDE_GUARD)
        self.refuse_nt(R)
    def test_a2_null_rel_y_on_an_unguarded_prompt_of_a_guarded_layer(self):
        R = records(self.table); guard_prompt(R, "C2047", 3, "x2", "cells", "prompt_rows", "layers")
        C = R["cells"]; C[find(C, arm="C2047", layer=3, prompt="x5", head=0)]["rel_y"] = None
        L = R["layers"][find(R["layers"], arm="C2047", layer=3)]; L["n_cells_valid"] -= 1
        self.refuse_nt(R)
    def test_a2_guarded_prompt_with_a_non_null_cell(self):
        R = records(self.table); guard_prompt(R, "C2047", 3, "x2", "cells", "prompt_rows", "layers")
        C = R["cells"]; C[find(C, arm="C2047", layer=3, prompt="x2", head=4)]["rel_y"] = 0.004; self.refuse_nt(R)
    def test_a2_empty_guard_text(self):
        R = records(self.table); guard_prompt(R, "C2047", 3, "x2", "cells", "prompt_rows", "layers", guard=""); self.refuse_nt(R)
    def test_a2_nan_layer_statistic_with_valid_cells(self):
        R = records(self.table); R["layers"][2]["rel_min"] = float("nan"); self.refuse_nt(R)

# ------------------------------------------------------------------ Amendment A3 (third review of PR #206, comment 6876740819)
class EmptyAggregate(unittest.TestCase):
    """A3: an arm with no finite cell (or a run with no layer) is reported with n 0 and null statistics, not a crash and
    not an invented observation; the verdict comes from the unchanged rules; the guarded representation is exact."""
    setUp, tearDown, write = Summariser.setUp, Summariser.tearDown, Summariser.write
    def run_nt(self, R):
        self.write(R); return S.summarise(self.d, PROMPTS, DET, self.table, NTOK)
    def refuse_nt(self, R):
        with self.assertRaises(S.Refuse): self.run_nt(R)
    def all_guarded(self, R, a, layers):
        for l in layers:
            for p in PROMPTS: guard_prompt(R, a, l, p, "cells", "prompt_rows", "layers")
    def check_empty_arm(self, s, n_layers):
        c = s["arms"]["C2047"]
        self.assertEqual((c["H_R"], c["H_F"], c["valid"]), ("comparison invalid", "comparison invalid", False))
        self.assertEqual(c["pooled"], dict(n=0, median=None, max=None, n_over_001=0, n_over_005=0))
        self.assertEqual((c["total_guard_failures"], c["layers_range_fail"], c["layers_fid_fail"]),
                         (8 * n_layers, S.LAYERS[:n_layers], S.LAYERS[:n_layers]))
        self.assertEqual(sum(x["n_cells"] for x in c["layers"]), 192 * n_layers)
        self.assertTrue(all(x["n_valid"] == 0 and x["rel_median"] is None and x["rel_min"] is None for x in c["layers"]))
        self.assertEqual(s["arms"]["C1665"]["pooled"]["n"], 192 * n_layers)
        self.assertTrue("n/a" in S.md(s))
    def test_a3_partial_one_layer_arm_all_guarded(self):
        R = records(self.table, n_layers=1); self.all_guarded(R, "C2047", [3])
        s = self.run_nt(R); self.check_empty_arm(s, 1)
        self.assertEqual(s["arms"]["C1665"]["H_R"], "NOT TESTED (partial)")
    def test_a3_complete_arm_all_guarded(self):
        R = records(self.table); self.all_guarded(R, "C2047", S.LAYERS)
        s = self.run_nt(R); self.check_empty_arm(s, 16)
        self.assertEqual((s["arms"]["C1665"]["H_R"], s["arms"]["C1665"]["H_F"]), ("PASS", "PASS"))
    def test_a3_empty_run(self):
        s = self.run_nt(dict(layers=[], cells=[], prompt_rows=[], timing=[]))
        for a in S.ARMS:
            v = s["arms"][a]
            self.assertEqual((v["H_R"], v["H_F"], v["layers_done"], len(v["not_tested_layers"])), ("NOT TESTED (partial)", "NOT TESTED (partial)", 0, 16))
            self.assertEqual(v["pooled"], dict(n=0, median=None, max=None, n_over_001=0, n_over_005=0))
        S.md(s)
    def test_a3_missing_rel_y_key_on_a_guarded_cell(self):
        R = records(self.table); guard_prompt(R, "C2047", 3, "x2", "cells", "prompt_rows", "layers")
        R["cells"][find(R["cells"], arm="C2047", layer=3, prompt="x2", head=0)].pop("rel_y"); self.refuse_nt(R)
    def test_a3_finite_statistic_on_an_all_guarded_layer(self):
        for f in ("rel_max", "rel_median", "rel_min"):
            R = records(self.table); self.all_guarded(R, "C1665", [7])
            R["layers"][find(R["layers"], arm="C1665", layer=7)][f] = 0.0; self.refuse_nt(R)
    def test_a3_guarded_determinism_prompt_with_true_flag(self):
        R = records(self.table); guard_prompt(R, "C2047", 3, "x0", "cells", "prompt_rows", "layers")
        self.assertEqual(self.run_nt(R)["arms"]["C2047"]["H_F"], "comparison invalid")
        R["layers"][find(R["layers"], arm="C2047", layer=3)]["det_bit_equal"]["x0"] = True; self.refuse_nt(R)

class Descriptive(unittest.TestCase):
    """A2 (2), (3): retained descriptive fields finite, in domain and reconciled; per-head counts bounded by T x 256."""
    setUp, tearDown, write = Summariser.setUp, Summariser.tearDown, Summariser.write
    def refuse_nt(self, R):
        self.write(R)
        with self.assertRaises(S.Refuse): S.summarise(self.d, PROMPTS, DET, self.table, NTOK)
    def test_a2_wide_count_without_guard(self):
        R = records(self.table); R["prompt_rows"][0]["wide_over_32767"] = 1; self.refuse_nt(R)
    def test_a2_causal_not_triangle(self):
        R = records(self.table); R["prompt_rows"][0]["causal"] += 24
        R["layers"][0]["causal"] += 24; self.refuse_nt(R)
    def test_a2_e_zero_over_causal(self):
        R = records(self.table); R["prompt_rows"][0]["e_zero"] = 361
        R["layers"][0]["e_zero"] = 361; self.refuse_nt(R)
    def test_a2_max_abs_s_over_smax(self):
        R = records(self.table); R["prompt_rows"][0]["max_abs_s"] = 256.0 * 2047 * 2047 + 1
        R["layers"][0]["max_abs_s"] = 256.0 * 2047 * 2047 + 1; self.refuse_nt(R)
    def test_a2_layer_count_fields_disagree_with_cells(self):
        R = records(self.table); R["layers"][0]["n_over_001"] = 3; self.refuse_nt(R)
        R = records(self.table); R["layers"][0]["n_pairs"] = 191; self.refuse_nt(R)
    def test_a2_negative_timing(self):
        R = records(self.table); R["timing"][0]["float_s"] = -0.1; self.refuse_nt(R)

class CommittedCopyA2(CommittedCopy):
    """The second review's probes, on a temporary copy of the committed run records."""
    test_copy_unmodified_is_accepted_and_unchanged = test_copy_negative_v_over_cancels_real_clamp = None
    test_copy_nan_rel_y = test_copy_negative_minimum_rel_y = test_copy_T_zero = test_copy_string_false_determinism = None
    def test_a2_copy_guarded_null_c2047_l3_h02_is_fail_fail(self):
        # the review's constructed guard case: accepted, registered verdict FAIL / FAIL, every cell identity retained
        guard_prompt(self.R, "C2047", 3, "h02-prose-paragraph", "cells.jsonl", "prompt-rows.jsonl", "layers.jsonl")
        s = self.run_copy()
        for a in S.ARMS: self.assertEqual((s["arms"][a]["H_R"], s["arms"][a]["H_F"], s["arms"][a]["valid"]), ("FAIL", "FAIL", True))
        c = s["arms"]["C2047"]; self.assertEqual(c["total_guard_failures"], 1); self.assertIn(3, c["layers_range_fail"])
        self.assertIn(3, c["layers_fid_fail"]); self.assertEqual(c["pooled"]["n"], 3072 - 24)
        self.assertEqual(sum(x["n_cells"] for x in c["layers"]), 3072)
        self.assertEqual(c["layers"][0]["mix_rel"][self.prompts.index("h02-prose-paragraph")], None)
    def test_a2_copy_nan_max_abs_s(self):
        self.R["layers.jsonl"][0]["max_abs_s"] = float("nan"); self.refuse()
    def test_a2_copy_infinite_obs_mx_q(self):
        self.R["layers.jsonl"][0]["obs_mx_q"] = float("inf"); self.refuse()
    def test_a2_copy_missing_obs_mx_q(self):
        self.R["layers.jsonl"][0].pop("obs_mx_q"); self.refuse()
    def test_a2_copy_negative_arm_seconds(self):
        self.R["layers.jsonl"][0]["arm_seconds"] = -1; self.refuse()
    def test_a2_copy_layer_maximum_not_from_prompt_rows(self):
        self.R["layers.jsonl"][0]["obs_mx_k"] *= 2; self.refuse()
    def test_a2_copy_head_count_over_head_capacity(self):
        # the review's case: 5121 clamps in one head of a T=20 prompt (capacity 20 x 256 = 5120), totals made consistent
        P, L = self.R["prompt-rows.jsonl"], self.R["layers.jsonl"]
        p = P[find(P, arm="C2047", layer=3, prompt="h01-prose-short")]; self.assertEqual(p["T"], 20)
        p.update(q_over=5121, q_over_by_head=[5121] + [0] * 23, q_maxw=2048)
        L[find(L, arm="C2047", layer=3)].update(q_over=5121, n_clamped=5121, q_maxw=2048, range_pass=False)
        self.refuse()
        p.update(q_over=5120, q_over_by_head=[5120] + [0] * 23)          # at capacity: the head bound itself admits it
        L[find(L, arm="C2047", layer=3)].update(q_over=5120, n_clamped=5120)
        self.assertEqual(self.run_copy()["arms"]["C2047"]["H_R"], "FAIL")

class CommittedCopyA3(CommittedCopy):
    """The third review's two reproductions, on a temporary copy of the committed run records: every C2047 prompt guarded
    (evaluator representation, determinism false), (1) on a layer-3-only prefix, (2) on all 16 layers. Both through the
    summariser and through the command line, which must write both summaries."""
    test_copy_unmodified_is_accepted_and_unchanged = test_copy_negative_v_over_cancels_real_clamp = None
    test_copy_nan_rel_y = test_copy_negative_minimum_rel_y = test_copy_T_zero = test_copy_string_false_determinism = None
    def guard_arm(self, layers):
        for l in layers:
            for p in self.prompts: guard_prompt(self.R, "C2047", l, p, "cells.jsonl", "prompt-rows.jsonl", "layers.jsonl")
    def cli(self):
        import subprocess
        for n, rows in self.R.items(): (self.d / n).write_text("".join(json.dumps(r) + "\n" for r in rows))
        out = self.d / "out"; out.mkdir()
        r = subprocess.run([sys.executable, str(HERE / "summarise_heldout.py"), str(self.d), str(out)], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(sorted(x.name for x in out.iterdir()), ["summary.json", "summary.md"])
        return json.loads((out / "summary.json").read_text())
    def check(self, s, layers):
        c = s["arms"]["C2047"]
        self.assertEqual((c["H_R"], c["H_F"], c["valid"]), ("comparison invalid", "comparison invalid", False))
        self.assertEqual(c["pooled"], dict(n=0, median=None, max=None, n_over_001=0, n_over_005=0))
        self.assertEqual(c["total_guard_failures"], 8 * len(layers))
        self.assertEqual((c["layers_range_fail"], c["layers_fid_fail"]), (layers, layers))
        self.assertEqual(sum(x["n_cells"] for x in c["layers"]), 192 * len(layers))
        self.assertEqual(s["arms"]["C1665"]["pooled"]["n"], 192 * len(layers))
    def test_a3_copy_partial_layer3_all_c2047_guarded(self):
        self.R = {n: [r for r in rows if r["layer"] == 3] for n, rows in self.R.items()}
        self.guard_arm([3]); self.check(self.run_copy(), [3])
        self.check(self.cli(), [3])
    def test_a3_copy_complete_all_c2047_guarded(self):
        self.guard_arm(S.LAYERS); s = self.run_copy(); self.check(s, S.LAYERS)
        o = s["arms"]["C1665"]; self.assertEqual((o["H_R"], o["H_F"], o["valid"]), ("FAIL", "FAIL", True))
        self.assertEqual(o, json.loads((RUNS / "summary.json").read_text())["arms"]["C1665"])   # other arm unchanged
        self.check(self.cli(), S.LAYERS)

if __name__ == "__main__":
    res = unittest.main(exit=False, verbosity=2).result
    out = dict(ran=res.testsRun, failures=len(res.failures), errors=len(res.errors), ok=res.wasSuccessful(),
               int_attn_sha256=hashlib.sha256((H.SRC176 / "int_attn.py").read_bytes()).hexdigest(), table_sha256=H.TABLE_SHA,
               note="synthetic data only; no weights, no registered prompt")
    # runs/debug/unit-tests.json is the receipt of 27b057dd (code cc8f8504, 32 tests), runs/debug/unit-tests-a1.json the
    # receipt of 2e7dc350 (Amendment A1, 59 tests), runs/debug/unit-tests-a2.json the receipt of d516e11e (Amendment A2,
    # 83 tests); none is overwritten. This version (Amendment A3) writes its own.
    out["amendment"] = ("A3 (an aggregate with no finite cell is reported with n 0 and null statistics; rel_y key required; "
                        "all-guarded layer statistics all NaN; guarded determinism prompts carry det false)")
    out["note"] = ("synthetic data, plus (CommittedCopy) temporary copies of the committed run records, read only; "
                   "no weights, no model forward, no registered prompt run")
    (HERE / "runs" / "debug").mkdir(parents=True, exist_ok=True)
    (HERE / "runs" / "debug" / "unit-tests-a3.json").write_text(json.dumps(out, indent=1) + "\n")
    raise SystemExit(0 if res.wasSuccessful() else 1)
