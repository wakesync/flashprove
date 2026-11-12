#!/usr/bin/env python3
"""Offline negative tests for the completeness checks (suite.py, summarise.validate, decay_tables.load_layers),
added after the run (review of PR #146, RESULTS section 6). No model, no weights, no network.

Every mutated input must be REFUSED (suite.Incomplete); the intact committed evaluation files and a complete
synthetic ar directory must be accepted. Also checks that summarise.py on the committed files still reproduces
the committed summary.md byte for byte and the registered verdicts.

usage: python3 test_completeness.py      (about 1 to 2 minutes on one core)
"""
import copy, csv, gzip, json, math, subprocess, sys, tempfile, unittest
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import suite as SU
import summarise as SM
import decay_tables as DT

EVAL = HERE / "runs" / "eval"
FULL = dict(fixture=False, set="S10", partial_layers=None)
_DATA = None


def data():
    global _DATA
    if _DATA is None: _DATA = SM.load(EVAL)
    return _DATA


def fresh():
    meta, cells, dom, split, sweep = data()
    return copy.deepcopy(meta), [dict(c) for c in cells], copy.deepcopy(dom), list(split), list(sweep)


class Summarise(unittest.TestCase):
    def refuse(self, args, mode=FULL):
        with self.assertRaises(SU.Incomplete): SM.validate(*args, dict(mode))

    def test_intact_control_passes(self):
        self.assertEqual(SM.validate(*fresh(), dict(FULL)), "COMPLETE")

    def test_dropped_layer(self):
        meta, cells, dom, split, sweep = fresh()
        cells = [c for c in cells if c["layer"] != "12"]
        self.refuse((meta, cells, dom, split, sweep))

    def test_dropped_layer_everywhere_with_meta(self):
        # layer 12 removed from every file AND from eval-meta.json: still not the registered suite
        meta, cells, dom, split, sweep = fresh()
        meta["layers"] = [l for l in meta["layers"] if l != 12]
        cells = [c for c in cells if c["layer"] != "12"]; dom = [x for x in dom if x["layer"] != 12]
        split = [r for r in split if r["layer"] != "12"]; sweep = [r for r in sweep if r["layer"] != "12"]
        self.refuse((meta, cells, dom, split, sweep))

    def test_dropped_head(self):
        meta, cells, dom, split, sweep = fresh()
        cells = [c for c in cells if not (c["layer"] == "42" and c["head"] == "12")]
        self.refuse((meta, cells, dom, split, sweep))

    def test_dropped_prompt(self):
        meta, cells, dom, split, sweep = fresh()
        cells = [c for c in cells if c["prompt"] != "p03-repeat-word"]
        self.refuse((meta, cells, dom, split, sweep))

    def test_dropped_prompt_everywhere_with_meta(self):
        meta, cells, dom, split, sweep = fresh()
        meta["prompts"] = [p for p in meta["prompts"] if p != "p03-repeat-word"]
        cells = [c for c in cells if c["prompt"] != "p03-repeat-word"]
        split = [r for r in split if r["prompt"] != "p03-repeat-word"]; sweep = [r for r in sweep if r["prompt"] != "p03-repeat-word"]
        self.refuse((meta, cells, dom, split, sweep))

    def test_dropped_failing_T3_cells(self):
        # opus mutation: every failing T3 row deleted -> used to print T3 PASS
        meta, cells, dom, split, sweep = fresh()
        cells = [c for c in cells if not (c["arm"] == "T3" and (float(c["e_tok_max"]) > SM.E_TOK or float(c["e_cum_max"]) > SM.E_CUM))]
        self.refuse((meta, cells, dom, split, sweep))

    def test_single_dropped_cell(self):
        meta, cells, dom, split, sweep = fresh()
        del cells[12345]
        self.refuse((meta, cells, dom, split, sweep))

    def test_one_row_per_arm_with_full_meta(self):
        # astra repro 2: one passing row per arm, full-suite meta/domain/descriptive files -> used to print PASS x4
        meta, cells, dom, split, sweep = fresh()
        keep = {}
        for c in cells:
            if c["arm"] not in keep and int(c["rejects"]) == 0 and float(c["e_tok_max"]) <= SM.E_TOK and float(c["e_cum_max"]) <= SM.E_CUM: keep[c["arm"]] = c
        self.assertEqual(len(keep), 4)
        self.refuse((meta, list(keep.values()), dom, split, sweep))

    def test_duplicate_cell(self):
        meta, cells, dom, split, sweep = fresh()
        cells[0] = dict(cells[1])   # same total count, one cell missing and one duplicated
        self.refuse((meta, cells, dom, split, sweep))

    def test_wrong_token_count(self):
        meta, cells, dom, split, sweep = fresh()
        for c in cells:
            if c["prompt"] == "p01-ordinary-short": c["T"] = "12"
        self.refuse((meta, cells, dom, split, sweep))

    def test_nan_e_cum(self):
        meta, cells, dom, split, sweep = fresh()
        i = next(i for i, c in enumerate(cells) if c["arm"] == "T3" and int(c["rejects"]) == 0)
        cells[i]["e_cum_max"] = "nan"
        self.refuse((meta, cells, dom, split, sweep))

    def test_nan_e_tok(self):
        meta, cells, dom, split, sweep = fresh()
        i = next(i for i, c in enumerate(cells) if c["arm"] == "T2" and int(c["rejects"]) == 0)
        cells[i]["e_tok_max"] = "nan"
        self.refuse((meta, cells, dom, split, sweep))

    def test_inf_e_tok_med(self):
        meta, cells, dom, split, sweep = fresh()
        i = next(i for i, c in enumerate(cells) if c["arm"] == "T1")
        cells[i]["e_tok_med"] = "inf"
        self.refuse((meta, cells, dom, split, sweep))

    def test_reject_on_clamping_arm(self):
        meta, cells, dom, split, sweep = fresh()
        i = next(i for i, c in enumerate(cells) if c["arm"] == "T3")
        cells[i]["rejects"] = "1"
        self.refuse((meta, cells, dom, split, sweep))

    def test_inconsistent_meta_layers(self):
        meta, cells, dom, split, sweep = fresh()
        meta["layers"] = meta["layers"][:-1] + [63]
        self.refuse((meta, cells, dom, split, sweep))

    def test_inconsistent_meta_prompts(self):
        meta, cells, dom, split, sweep = fresh()
        meta["prompts"] = sorted(meta["prompts"][:-1] + ["p10-other"])
        self.refuse((meta, cells, dom, split, sweep))

    def test_inconsistent_meta_fixture_flag(self):
        meta, cells, dom, split, sweep = fresh()
        meta["fixture"] = True
        self.refuse((meta, cells, dom, split, sweep))

    def test_inconsistent_meta_bar(self):
        meta, cells, dom, split, sweep = fresh()
        meta["bar"]["e_cum"] = 0.5
        self.refuse((meta, cells, dom, split, sweep))

    def test_domain_short(self):
        meta, cells, dom, split, sweep = fresh()
        self.refuse((meta, cells, dom[:-1], split, sweep))

    def test_split_short(self):
        meta, cells, dom, split, sweep = fresh()
        self.refuse((meta, cells, dom, split[:-1], sweep))

    def test_sweep_nan(self):
        meta, cells, dom, split, sweep = fresh()
        sweep[0] = dict(sweep[0], e_cum_max="nan")
        self.refuse((meta, cells, dom, split, sweep))

    def test_partial_must_be_declared_and_consistent(self):
        # a registered PARTIAL (first 10 DeltaNet layers): refused undeclared, accepted when declared, refused if declared wrong
        meta, cells, dom, split, sweep = fresh()
        L = SU.DELTANET_LAYERS[:10]; Ls = {str(l) for l in L}
        meta["layers"] = L
        cells = [c for c in cells if c["layer"] in Ls]; dom = [x for x in dom if x["layer"] in L]
        split = [r for r in split if r["layer"] in Ls]; sweep = [r for r in sweep if r["layer"] in Ls]
        args = (meta, cells, dom, split, sweep)
        self.refuse(args)
        self.assertEqual(SM.validate(*args, dict(FULL, partial_layers=10)), "PARTIAL")
        self.refuse(args, dict(FULL, partial_layers=11))
        self.refuse(args, dict(FULL, partial_layers=48))

    def test_fixture_mode_refused_on_registered_meta(self):
        self.refuse(fresh(), dict(FULL, fixture=True))

    def test_cli_refuses_with_exit_2_and_writes_nothing(self):
        # end to end through the command line on a tiny fake directory (astra repro 1, after evaluation)
        with tempfile.TemporaryDirectory() as t:
            d = Path(t)
            meta = dict(json.loads((EVAL / "eval-meta.json").read_text()), layers=[0], prompts=["p01-ordinary-short"])
            (d / "eval-meta.json").write_text(json.dumps(meta))
            def w(name, rows):
                with gzip.open(d / name, "wt", newline="") as fh:
                    wr = csv.DictWriter(fh, fieldnames=list(rows[0])); wr.writeheader(); wr.writerows(rows)
            w("cells.csv.gz", [dict(arm=a, layer=0, head=0, prompt="p01-ordinary-short", T=13, rejects=0, e_tok_max=0, e_tok_med=0, e_cum_max=0, e_logcum_max=0) for a in SU.ARMS])
            w("split-T3.csv.gz", [dict(source=s, layer=0, head=0, prompt="p01-ordinary-short", e_tok_max=0, e_cum_max=0) for s in SU.SPLIT_SOURCES])
            w("sweep-T3-F.csv.gz", [dict(F=f, layer=0, head=0, prompt="p01-ordinary-short", e_tok_max=0, e_cum_max=0) for f in SU.SWEEP_F])
            with gzip.open(d / "domain.json.gz", "wt") as fh: json.dump([dict(layer=0, head=0, n=13)], fh)
            r = subprocess.run([sys.executable, str(HERE / "summarise.py"), str(d)], capture_output=True, text=True)
            self.assertEqual(r.returncode, 2, r.stderr)
            self.assertIn("REFUSED", r.stderr)
            self.assertFalse((d / "summary.json").exists() or (d / "summary.md").exists())


def fake_ar_dir(d, layers, prompts, T=None, heads=SU.N_HEADS, nan=False):
    rng = np.random.default_rng(0); toks = SU.registered_tokens()
    for i in layers:
        arr = {f"ar|{p}": rng.normal(0, 3, size=((T or toks[p]), heads)) for p in prompts}
        if nan: next(iter(arr.values()))[0, 0] = np.nan
        np.savez(Path(d) / f"ar-L{i:02d}.npz", A=np.full(heads, 0.3), dt_bias=np.zeros(heads), **arr)


class LoadLayers(unittest.TestCase):
    P = sorted(SU.registered_tokens())

    def refuse(self, d, mode=FULL):
        with self.assertRaises(SU.Incomplete): DT.load_layers(d, dict(mode))

    def test_complete_synthetic_dir_passes(self):
        with tempfile.TemporaryDirectory() as t:
            fake_ar_dir(t, SU.DELTANET_LAYERS, self.P)
            out = DT.load_layers(t, dict(FULL))
            self.assertEqual([o[0] for o in out], SU.DELTANET_LAYERS)

    def test_astra_tiny_input(self):
        # astra repro 1: one layer, one head, one prompt -> used to evaluate to PASS x4
        with tempfile.TemporaryDirectory() as t:
            np.savez(Path(t) / "ar-L00.npz", A=np.array([0.004]), dt_bias=np.array([0.0]), **{"ar|p01-ordinary-short": np.full((13, 1), -5.0)})
            self.refuse(t)
            r = subprocess.run([sys.executable, str(HERE / "decay_tables.py"), "eval", t, str(Path(t) / "out")], capture_output=True, text=True)
            self.assertEqual(r.returncode, 2, r.stderr)
            self.assertFalse((Path(t) / "out").exists())

    def test_dropped_layer_file(self):
        with tempfile.TemporaryDirectory() as t:
            fake_ar_dir(t, [l for l in SU.DELTANET_LAYERS if l != 30], self.P)
            self.refuse(t)

    def test_dropped_prompt(self):
        with tempfile.TemporaryDirectory() as t:
            fake_ar_dir(t, SU.DELTANET_LAYERS, self.P[:-1])
            self.refuse(t)

    def test_wrong_heads(self):
        with tempfile.TemporaryDirectory() as t:
            fake_ar_dir(t, SU.DELTANET_LAYERS, self.P, heads=47)
            self.refuse(t)

    def test_wrong_token_count(self):
        with tempfile.TemporaryDirectory() as t:
            fake_ar_dir(t, SU.DELTANET_LAYERS, self.P, T=5)
            self.refuse(t)

    def test_nan_ar(self):
        with tempfile.TemporaryDirectory() as t:
            fake_ar_dir(t, SU.DELTANET_LAYERS, self.P, nan=True)
            self.refuse(t)

    def test_partial_declared(self):
        with tempfile.TemporaryDirectory() as t:
            fake_ar_dir(t, SU.DELTANET_LAYERS[:5], self.P)
            self.refuse(t)
            self.assertEqual(len(DT.load_layers(t, dict(FULL, partial_layers=5))), 5)
            self.refuse(t, dict(FULL, partial_layers=6))

    def test_s7_declared(self):
        with tempfile.TemporaryDirectory() as t:
            fake_ar_dir(t, SU.DELTANET_LAYERS, sorted(SU.S7))
            self.refuse(t)
            self.assertEqual(len(DT.load_layers(t, dict(FULL, set="S7"))), 48)

    def test_fixture_mode_internal_only(self):
        with tempfile.TemporaryDirectory() as t:
            np.savez(Path(t) / "ar-L00.npz", A=np.full(48, 0.3), dt_bias=np.zeros(48), **{"ar|fx": np.zeros((5, 48))})
            self.assertEqual(len(DT.load_layers(t, dict(fixture=True, set="S10", partial_layers=None))), 1)


class Reproduce(unittest.TestCase):
    def test_committed_summary_reproduced(self):
        with tempfile.TemporaryDirectory() as t:
            d = Path(t)
            for f in ("eval-meta.json", "cells.csv.gz", "domain.json.gz", "split-T3.csv.gz", "sweep-T3-F.csv.gz"):
                (d / f).write_bytes((EVAL / f).read_bytes())
            S = SM.main(d)
            self.assertEqual((d / "summary.md").read_bytes(), (EVAL / "summary.md").read_bytes())
            self.assertEqual((d / "summary.json").read_bytes(), (EVAL / "summary.json").read_bytes())
            self.assertEqual({a: S["arms"][a]["verdict"] for a in SU.ARMS}, dict(T0="FAIL", T1="FAIL", T2="FAIL", T3="FAIL"))
            self.assertEqual(S["arms"]["T0"]["heads_with_reject"], 978)
            self.assertEqual(S["domain"]["heads_any_x_out"], 939)


if __name__ == "__main__":
    unittest.main(verbosity=2)
