#!/usr/bin/env python3
"""Offline tests of the round-2 arm code (decay_r2.py) and of the summary's completeness checks (summarise_r2.py).

No model, no weights, no network, and NO registered activation array: the heads are synthetic (A and dt_bias of
every head and x drawn uniformly between that head's committed minimum and maximum in PR #146's `domain.json.gz`,
numpy seed 155), as registered in PREREG.md "Runs" (debug).

usage: R2_FINE20=<fine20.npy> python3 test_r2.py        (fine20.npy from `decay_r2.py fine20`; about 1 minute)
"""
import gzip, json, math, os, sys, tempfile, unittest
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import decay_r2 as R
import summarise_r2 as S2
DT, SU = R.DT, R.SU

TOK = 64
_T = None


def tables():
    global _T
    if _T is None: _T = R.load_tables(os.environ["R2_FINE20"])
    return _T


def synthetic():
    """Per layer: (layer, A (48,), dt_bias (48,), ar (TOK, 48)) with x between each head's committed min and max."""
    with gzip.open(R.P146 / "runs" / "eval" / "domain.json.gz", "rt") as fh: dom = json.load(fh)
    rng = np.random.default_rng(155); out = []
    for l in SU.DELTANET_LAYERS:
        hs = sorted((d for d in dom if d["layer"] == l), key=lambda d: d["head"])
        A = np.array([d["A"] for d in hs]); dtb = np.array([d["dt_bias"] for d in hs])
        lo = np.array([d["x_min_med_max"][0] for d in hs]); hi = np.array([d["x_min_med_max"][2] for d in hs])
        x = lo[None, :] + (hi - lo)[None, :] * rng.random((TOK, len(hs)))
        out.append((l, A, dtb, x - dtb[None, :]))
    return out


class Tables(unittest.TestCase):
    def test_fine20_rows(self):
        T = tables(); F = T["FINE20"]
        self.assertEqual(F.shape, (1 << 20,)); self.assertEqual(int(F[0]), 1 << 20)
        for k in (0, 1, 2, 1000, 524288, (1 << 20) - 1): self.assertEqual(int(F[k]), R.fine_row(k))
        fl = np.rint(np.ldexp(np.exp(-np.arange(1 << 20) / (1 << 20)), 20)).astype(np.int64)
        self.assertLessEqual(int(np.abs(F - fl).max()), 1)
        self.assertTrue(bool((np.diff(F) <= 0).all()))

    def test_softplus_tables(self):
        T = tables()
        xs = (np.arange(R.SPW_ROWS) + R.SPW_LO) / 256.0
        self.assertLessEqual(int(np.abs(T["SP20W"] - np.rint(np.ldexp(np.logaddexp(0.0, xs), 20))).max()), 1)
        self.assertTrue(np.array_equal(T["SP20W"][2048:], T["SP20"]))
        self.assertEqual(int(T["SP20W"][0]), int(np.rint(np.ldexp(math.log1p(math.exp(-16.0)), 20))))
        # the scale-12 table of U1 is the pinned v1 table
        self.assertEqual(T["sha"]["softplus_f12_v1"], "d2c1a4504ec3a7eca897cd818e7e572e70e3f82835b52f4cf55f9fc61e633b24")
        self.assertEqual(T["sha"]["coarse_exp_f12"], "5c64304f1a54d50705addafc08d11f1de9a897e9ed65860f0445a0f5cc10fa44")

    def test_coarse20(self):
        T = tables(); xs = (np.arange(4096) - 2048) / 256.0
        self.assertLessEqual(int(np.abs(T["EXPC20"][2048:] - np.rint(np.ldexp(np.exp(-xs[2048:]), 20))).max()), 1)


class Arms(unittest.TestCase):
    def test_exponent_rule(self):
        for l, A, dtb, ar in synthetic():
            e, cA = R.head_consts(A)
            self.assertTrue(bool(((e >= 1) & (e <= 24)).all()))
            self.assertTrue(bool((cA <= 4095).all()))
            for k, a in zip(e, A):
                if k < 24: self.assertGreater(DT.rne(2 ** (int(k) + 1) * float(a)), 4095)   # the largest admissible e
            self.assertTrue(bool((cA >= 2047).all()))                                       # so 12 bits are kept
        for a, want in ((1.0, 11), (0.5, 12), (139.42126035437516, 4), (0.0038391664740261636, 20), (4095.0 / 4096, 12), (2.0 ** -30, 24)):
            self.assertEqual(R.e_head(a), want)

    def test_u1_with_layer_exponent_is_T3(self):
        """U1 differs from PR #146's T3 only by the exponent rule: with T3's per-layer rule it must equal T3 bit for bit."""
        T = tables()
        for l, A, dtb, ar in synthetic():
            a3, _, _ = DT.arm_decay(ar, A, dtb, "T3", T["SP12"], T["EXPC12"])
            a1, rej = R.arm_decay(ar, A, dtb, "U1", T, per_head=False)
            self.assertTrue(np.array_equal(a1, a3)); self.assertFalse(bool(rej.any()))

    def test_u2_against_big_integer_recomputation(self):
        """U2's g path against a direct big-integer recomputation on a few (token, head) pairs."""
        T = tables(); l, A, dtb, ar = synthetic()[9]
        e, cA = R.head_consts(A); X, r = R.front(ar, dtb); a2, _ = R.arm_decay(ar, A, dtb, "U2", T)
        for t in range(0, TOK, 7):
            for h in range(0, 48, 5):
                Xi = int(X[t, h]); ri = Xi // 16
                sp = Xi << 8 if Xi >= 8 * 4096 else int(T["SP20"][min(max(ri + 2048, 0), 4095)])
                g = (int(cA[h]) * sp) >> int(e[h])
                want = R.fine_row(g) if g < (1 << 20) else int(T["EXPC20"][min(max((g >> 12) + 2048, 0), 4095)])
                self.assertEqual(a2[t, h], want / (1 << 20))

    def test_u3_equals_u2_inside_domain_and_differs_below(self):
        T = tables(); n_below = 0
        for l, A, dtb, ar in synthetic():
            X, r = R.front(ar, dtb)
            a2, _ = R.arm_decay(ar, A, dtb, "U2", T); a3, _ = R.arm_decay(ar, A, dtb, "U3", T)
            inside = r >= -2048
            self.assertTrue(np.array_equal(a2[inside], a3[inside]))
            self.assertTrue(bool((a3[~inside] >= a2[~inside]).all()))   # smaller softplus below -8 -> decay not smaller
            n_below += int((~inside).sum())
        self.assertGreater(n_below, 100)

    def test_u3_below_minus_16_clamps(self):
        T = tables(); A = np.array([139.4, 0.01]); dtb = np.array([0.0, 0.0]); ar = np.array([[-16.0, -16.0], [-20.0, -40.0]])
        a, rej = R.arm_decay(ar, A, dtb, "U3", T)
        self.assertTrue(np.array_equal(a[0], a[1])); self.assertFalse(bool(rej.any()))

    def test_u4_brute_force_and_bound(self):
        T = tables(); bound = (8.5 / 4096) / math.e + 2.0 ** -21 + 1e-12; worst = 0.0
        for l, A, dtb, ar in synthetic():
            a4, rej = R.arm_decay(ar, A, dtb, "U4", T); x, g, a = DT.float_decay(ar, A, dtb); X, r = R.front(ar, dtb)
            self.assertFalse(bool(rej.any()))
            for t in (0, TOK // 2, TOK - 1):
                for h in (0, 17, 47):
                    row = min(max(int(r[t, h]), -4096), 8191)
                    want = round(2 ** 20 * math.exp(-float(A[h]) * float(np.logaddexp(0.0, (row + 0.5) / 256.0))))
                    self.assertEqual(a4[t, h], want / (1 << 20))
            ok = x >= -16
            worst = max(worst, float(np.abs(a4 - a)[ok].max()))
        self.assertLessEqual(worst, bound)          # one centred key: (1/e) x (8.5 / 4096) + half an output unit
        self.assertLess(bound, R.E_TOK)

    def test_u4_rejects_above_32_and_clamps_below(self):
        T = tables(); A = np.array([1.0, 1.0, 1.0]); dtb = np.array([0.0, 0.0, 0.0])
        ar = np.array([[31.999, 32.0, -100.0]])
        a, rej = R.arm_decay(ar, A, dtb, "U4", T)
        self.assertEqual(rej.tolist(), [[False, True, False]]); self.assertTrue(math.isnan(a[0, 1])); self.assertGreater(a[0, 2], 0.999999)

    def test_no_reject_and_finite_on_u1_u2_u3(self):
        T = tables()
        for l, A, dtb, ar in synthetic()[::6]:
            for arm in ("U1", "U2", "U3"):
                a, rej = R.arm_decay(ar, A, dtb, arm, T)
                self.assertFalse(bool(rej.any())); self.assertTrue(bool(np.isfinite(a).all())); self.assertTrue(bool(((a >= 0) & (a <= 1)).all()))

    def test_split_sources_shapes(self):
        T = tables(); l, A, dtb, ar = synthetic()[0]
        for arm in R.ARMS:
            s = R.split_sources(ar, A, dtb, arm, T)
            self.assertEqual(tuple(s), R.SPLIT_SOURCES[arm])
            for v in s.values(): self.assertEqual(v.shape, ar.shape)


class Inputs(unittest.TestCase):
    def test_prereg_list(self):
        m = R.prereg_sha(); self.assertEqual(len(m), 48)
        self.assertEqual(m["ar-L00.npz"], "c2f30790d52eb90b3e88a44f3a4217c359a35563af7403d8202a601597a63139")

    def test_wrong_bytes_refused(self):
        with tempfile.TemporaryDirectory() as d:
            for n in R.prereg_sha(): (Path(d) / n).write_bytes(b"not the registered bytes " + n.encode())
            with self.assertRaises(SU.Incomplete): R.check_inputs(d)

    def test_missing_file_refused(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(SU.Incomplete): R.check_inputs(d)


def fake_cells(drop=None, dup=False, nan=False, arms=R.ARMS, T_bad=False, reject_arm=None):
    toks = SU.registered_tokens("S10"); rows = []
    for arm in arms:
        for l in SU.DELTANET_LAYERS:
            for h in range(SU.N_HEADS):
                for p in sorted(toks):
                    rows.append(dict(arm=arm, layer=str(l), head=str(h), prompt=p, T=str(toks[p]), rejects="0", e_tok_max="0.0001", e_tok_med="0.00001", e_cum_max="0.001", e_logcum_max="0.001"))
    if drop: rows = [r for r in rows if not drop(r)]
    if dup: rows.append(dict(rows[0]))
    if nan: rows[5]["e_cum_max"] = "nan"
    if T_bad: rows[7]["T"] = "3"
    if reject_arm:
        for r in rows:
            if r["arm"] == reject_arm and r["layer"] == "0" and r["head"] == "8": r["rejects"] = "1"; r["e_tok_max"] = "-inf"; r["e_tok_med"] = "nan"; break
    return rows


def fake_meta(**kw):
    m = dict(arms=list(R.ARMS), G=20, layers=list(SU.DELTANET_LAYERS), prompts=sorted(SU.registered_tokens("S10")), fixture=False, set="S10",
             input_list_sha256="x", bar=dict(e_tok=2.0 ** -9, e_cum=0.01, rejects=0))
    m.update(kw); return m


class Summary(unittest.TestCase):
    def refuse(self, meta, cells):
        with self.assertRaises(SU.Incomplete): S2.validate(meta, cells, fixture=False)

    def test_intact_control(self):
        self.assertEqual(S2.validate(fake_meta(), fake_cells(), fixture=False), "COMPLETE")
        s = S2.verdicts(fake_cells())
        self.assertEqual({a: s[a]["verdict"] for a in R.ARMS}, dict.fromkeys(R.ARMS, "PASS"))

    def test_dropped_cell(self): self.refuse(fake_meta(), fake_cells(drop=lambda r: r["arm"] == "U3" and r["layer"] == "42" and r["head"] == "12" and r["prompt"] == "p03-repeat-word"))
    def test_dropped_layer(self): self.refuse(fake_meta(), fake_cells(drop=lambda r: r["layer"] == "12"))
    def test_dropped_layer_with_meta(self): self.refuse(fake_meta(layers=[l for l in SU.DELTANET_LAYERS if l != 12]), fake_cells(drop=lambda r: r["layer"] == "12"))
    def test_dropped_prompt(self): self.refuse(fake_meta(), fake_cells(drop=lambda r: r["prompt"] == "p03-repeat-word"))
    def test_dropped_arm(self): self.refuse(fake_meta(), fake_cells(arms=("U1", "U2", "U3")))
    def test_duplicate(self): self.refuse(fake_meta(), fake_cells(dup=True))
    def test_nan(self): self.refuse(fake_meta(), fake_cells(nan=True))
    def test_wrong_T(self): self.refuse(fake_meta(), fake_cells(T_bad=True))
    def test_wrong_bar(self): self.refuse(fake_meta(bar=dict(e_tok=0.01, e_cum=0.01, rejects=0)), fake_cells())
    def test_fixture_flag(self): self.refuse(fake_meta(fixture=True), fake_cells())
    def test_reject_on_clamping_arm(self): self.refuse(fake_meta(), fake_cells(reject_arm="U3"))

    def test_reject_on_u4_is_a_failure_not_a_refusal(self):
        cells = fake_cells(reject_arm="U4")
        self.assertEqual(S2.validate(fake_meta(), cells, fixture=False), "COMPLETE")
        s = S2.verdicts(cells)
        self.assertEqual(s["U4"]["verdict"], "FAIL"); self.assertEqual(s["U4"]["fail_by_reason"]["reject"], 1); self.assertEqual(s["U3"]["verdict"], "PASS")

    def test_bar_edges(self):
        cells = fake_cells()
        cells[0]["e_tok_max"] = repr(2.0 ** -9); cells[1]["e_cum_max"] = "0.01"                 # at the bar: pass
        self.assertEqual(S2.verdicts(cells)["U1"]["verdict"], "PASS")
        cells[0]["e_tok_max"] = repr(float(np.nextafter(2.0 ** -9, 1)))
        v = S2.verdicts(cells)["U1"]; self.assertEqual(v["verdict"], "FAIL"); self.assertEqual(v["n_fail_cells"], 1)


if __name__ == "__main__":
    unittest.main(verbosity=1)
