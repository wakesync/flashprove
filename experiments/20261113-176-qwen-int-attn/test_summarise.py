#!/usr/bin/env python3
"""Regression tests for summarise.py's input validation (PR #178 review round 1; PREREG Amendments 2026-11-13).

Synthetic fixtures only: every record is generated below from made-up, self-consistent values. No number of the
registered run is read or used. The only repository file read is the registered prompt list (ids and token counts).

Each case writes a runs directory in a temporary copy of the experiment layout, runs the summariser on it and checks:
  refuse  exit code 2, a "REFUSED" message on stderr, no summary.json and no summary.md written
  ok      exit code 0, plus the checks given on the verdicts
The mutations are the ones the two round-1 reviewers ran (a head id changed into a duplicate, the whole C2047 arm
deleted, a layer's cells missing, a duplicated layer, one value changed) and their neighbours: missing record,
duplicate record, unexpected record, missing arm, missing determinism evidence.

Usage: test_summarise.py [SUMMARISER]   (default: the summarise.py next to this file)
Exit 0 iff every case behaves as expected; one JSON line per case. Run against the summariser as it was at the
registered run (git show c7379d1e:experiments/20261113-176-qwen-int-attn/summarise.py > old.py) the refuse cases fail.
"""
import copy, json, shutil, subprocess, sys, tempfile
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent
PROMPT_DIR = "20261111-8-qwen-e2e-agreement"
SUMMARISER = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else HERE / "summarise.py"
PROMPT_T = {p["id"]: len(p["token_ids"]) for p in json.load(open(HERE.parent / PROMPT_DIR / "prompts-e2e.json"))["prompts"]}
PIDS = list(PROMPT_T)
ATT = [i for i in range(64) if i % 4 == 3]
ARMS = ("C2047", "C1665"); CLAMP = {"C2047": 2047, "C1665": 1665}
DET = ("p01-ordinary-short", "p09-multilingual")
NH, NKV, HD = 24, 4, 256
ORDER = [(l, a) for l in ATT for a in ARMS]


# ---------------------------------------------------------------- synthetic, self-consistent records
def rel_y(arm, layer, pi, h, bump=0.0):
    """Made-up value, well under the bar (0.002 to 0.0045); bump moves a whole layer over the median bar."""
    return 0.002 + 0.00005 * ((7 * h + 3 * pi + layer + (5 if arm == "C1665" else 0)) % 50) + bump


def layer_record(arm, layer, cells, prows, det=True):
    a = np.array([c["rel_y"] for c in cells])
    r = dict(t="2026-01-01T00:00:00Z", arm=arm, layer=layer, clamp=CLAMP[arm], Smax=HD * CLAMP[arm] ** 2, mx_q=0.5, mx_k=10.0, mx_v=7.0,
             Eq=11, Ek=7, Ev=7, sh=10, sh_fit=10, Eq_fit=11, adjust=None)
    for k in ("q_over", "q_n", "k_over", "k_n", "v_over", "v_n", "e_zero", "causal", "wide_over_32767"): r[k] = sum(p[k] for p in prows)
    for k in ("q_maxw", "k_maxw", "v_maxw", "max_abs_s"): r[k] = max(p[k] for p in prows)
    r.update(n_pairs=int(a.size), rel_median=float(np.median(a)), rel_max=float(a.max()), rel_min=float(a.min()),
             n_over_001=int((a > 0.01).sum()), n_over_005=int((a > 0.05).sum()),
             layer_pass=bool(np.median(a) <= 0.01 and a.max() <= 0.05),
             det_bit_equal=({p: det for p in DET} if arm == "C2047" else {}), arm_seconds=1.0)
    return r


def baseline(n_records=len(ORDER), bump_layers=(), det_false_at=None):
    """A run cut after n_records layer records (32 = complete). Lists in the order the run writes them."""
    R = dict(lay=[], cells=[], prow=[], tim=[])
    for n, (layer, arm) in enumerate(ORDER[:n_records]):
        cells, prows = [], []
        for pi, pid in enumerate(PIDS):
            T = PROMPT_T[pid]
            cells += [dict(arm=arm, layer=layer, prompt=pid, head=h, rel_y=rel_y(arm, layer, pi, h, 0.009 if layer in bump_layers else 0.0)) for h in range(NH)]
            prows.append(dict(arm=arm, layer=layer, prompt=pid, T=T, mix_rel=0.001 + 0.0001 * pi, max_abs_s=float(1000000 + 1000 * pi + layer),
                              e_zero=T, causal=NH * T * (T + 1) // 2, q_over=0, q_n=T * NH * HD, k_over=0, k_n=T * NKV * HD, v_over=0, v_n=T * NKV * HD,
                              q_maxw=1000 + pi, k_maxw=1100 + pi, v_maxw=1200 + pi, wide_over_32767=0))
        R["cells"] += cells; R["prow"] += prows
        R["lay"].append(layer_record(arm, layer, cells, prows, det=(layer != det_false_at)))
        if arm == ARMS[-1]:
            R["tim"].append(dict(t="2026-01-01T00:00:00Z", layer=layer, float_s=1.0, ref_attention_s=1.0, total_s=3.0,
                                 mix_bit_equal_q1={p: True for p in PIDS}, peak_rss_gb_self=1.0))
    return R


BASE = baseline()


def fresh(): return copy.deepcopy(BASE)
def drop(R, name, pred): R[name] = [x for x in R[name] if not pred(x)]


def drop_arm(R, arm):
    for name in ("lay", "cells", "prow"): drop(R, name, lambda x: x["arm"] == arm)


def drop_layer(R, layer, arm=None):
    for name in ("lay", "cells", "prow"): drop(R, name, lambda x: x["layer"] == layer and (arm is None or x["arm"] == arm))
    if arm is None: drop(R, "tim", lambda x: x["layer"] == layer)


# ---------------------------------------------------------------- cases
def c_ok_complete(R): pass
def c_head_changed_to_duplicate(R): R["cells"][0]["head"] = 1                      # reviewer mutation: 240 rows stay, head 0 missing
def c_cell_duplicated(R): R["cells"].append(dict(R["cells"][0]))
def c_cell_duplicated_changed(R): R["cells"].append(dict(R["cells"][0], rel_y=0.0031))
def c_cell_missing(R): del R["cells"][5]
def c_layer_cells_missing(R): drop(R, "cells", lambda x: x["layer"] == 31 and x["arm"] == "C1665")
def c_cell_unknown_prompt(R): R["cells"][3]["prompt"] = "p99-not-registered"
def c_cell_head_out_of_range(R): R["cells"][3]["head"] = 24
def c_cell_unknown_arm(R): R["cells"].append(dict(R["cells"][0], arm="C1024"))
def c_cell_non_attention_layer(R): R["cells"].append(dict(R["cells"][0], layer=4))
def c_cell_nan(R): R["cells"][7]["rel_y"] = float("nan")
def c_cell_value_changed(R): R["cells"][0]["rel_y"] = 0.2
def c_cell_extra_field(R): R["cells"][0]["note"] = "x"
def c_arm_c2047_missing(R): drop_arm(R, "C2047")                                   # reviewer mutation: determinism was vacuously true
def c_arm_c1665_missing(R): drop_arm(R, "C1665")
def c_det_evidence_empty(R): R["lay"][0]["det_bit_equal"] = {}
def c_det_evidence_one_prompt(R): R["lay"][2]["det_bit_equal"] = {DET[0]: True}
def c_det_evidence_wrong_prompt(R): R["lay"][2]["det_bit_equal"] = {DET[0]: True, "p05-code": True}
def c_det_evidence_on_c1665(R): R["lay"][1]["det_bit_equal"] = {p: True for p in DET}
def c_det_evidence_not_boolean(R): R["lay"][0]["det_bit_equal"] = {p: "yes" for p in DET}
def c_layer_record_duplicated(R): R["lay"].append(dict(R["lay"][4]))
def c_layer_record_missing_middle(R): drop(R, "lay", lambda x: x["layer"] == 31 and x["arm"] == "C2047")
def c_layer_hole(R): drop_layer(R, 31)
def c_layer_record_unknown_layer(R): R["lay"].append(dict(R["lay"][0], layer=5))
def c_layer_record_field_missing(R): del R["lay"][0]["rel_median"]
def c_layer_totals_changed(R): R["lay"][0]["q_over"] = 3
def c_layer_clamp_changed(R): R["lay"][1]["clamp"] = 2047
def c_layer_pass_flag_flipped(R): R["lay"][0]["layer_pass"] = False
def c_prompt_row_missing(R): del R["prow"][4]
def c_prompt_row_duplicated(R): R["prow"].append(dict(R["prow"][4]))
def c_prompt_row_wrong_T(R): R["prow"][4]["T"] += 1
def c_timing_row_duplicated(R): R["tim"].append(dict(R["tim"][0]))
def c_timing_row_missing_middle(R): del R["tim"][3]
def c_timing_row_unknown_layer(R): R["tim"].append(dict(R["tim"][0], layer=4))


def k_complete_pass(S):
    return all(S["arms"][a]["verdict"] == "PASS" and S["arms"][a]["determinism_ok"] is True and S["arms"][a]["layers_pass"] == 16
               and S["arms"][a]["pooled"]["n"] == 16 * 240 for a in ARMS) and "interrupted" not in S


def k_complete_fail(S):
    return all(S["arms"][a]["verdict"] == "FAIL" and S["arms"][a]["determinism_ok"] is True and S["arms"][a]["layers_pass"] == 14 for a in ARMS)


def k_det_false(S): return all(S["arms"][a]["verdict"] == "FAIL (determinism)" and S["arms"][a]["determinism_ok"] is False for a in ARMS)


def k_partial(n_c2047, n_c1665, interrupted=None):
    def k(S):
        A = S["arms"]
        return (len(A["C2047"]["layers_done"]) == n_c2047 and len(A["C1665"]["layers_done"]) == n_c1665
                and all(A[a]["verdict"].startswith("PARTIAL") and A[a]["determinism_ok"] is None for a in ARMS)
                and A["C2047"]["pooled"]["n"] == 240 * n_c2047 and A["C1665"]["pooled"]["n"] == 240 * n_c1665
                and (S.get("interrupted") or {}).get("layer") == interrupted)
    return k


def partial_with_interrupted():
    """Cut inside layer 31, arm C2047: 14 layer records, then 3 prompts of the interrupted arm (cells and prompt rows)."""
    R = baseline(14); full = baseline(15)
    R["cells"] += [c for c in full["cells"] if c["layer"] == 31 and c["prompt"] in PIDS[:3]]
    R["prow"] += [p for p in full["prow"] if p["layer"] == 31 and p["prompt"] in PIDS[:3]]
    return R


def partial_stray_cells():
    """Cells of layer 39 while the records stop at layer 27: not the interrupted layer, so refused."""
    R = baseline(14); full = baseline(20)
    R["cells"] += [c for c in full["cells"] if c["layer"] == 39 and c["arm"] == "C2047"]
    return R


REFUSE = [c_head_changed_to_duplicate, c_cell_duplicated, c_cell_duplicated_changed, c_cell_missing, c_layer_cells_missing,
          c_cell_unknown_prompt, c_cell_head_out_of_range, c_cell_unknown_arm, c_cell_non_attention_layer, c_cell_nan,
          c_cell_value_changed, c_cell_extra_field, c_arm_c2047_missing, c_arm_c1665_missing, c_det_evidence_empty,
          c_det_evidence_one_prompt, c_det_evidence_wrong_prompt, c_det_evidence_on_c1665, c_det_evidence_not_boolean,
          c_layer_record_duplicated, c_layer_record_missing_middle, c_layer_hole, c_layer_record_unknown_layer,
          c_layer_record_field_missing, c_layer_totals_changed, c_layer_clamp_changed, c_layer_pass_flag_flipped,
          c_prompt_row_missing, c_prompt_row_duplicated, c_prompt_row_wrong_T, c_timing_row_duplicated,
          c_timing_row_missing_middle, c_timing_row_unknown_layer]


def cases():
    yield "ok_complete_all_pass", fresh(), "ok", k_complete_pass, None
    yield "ok_complete_two_layers_over_median", baseline(bump_layers=(31, 35)), "ok", k_complete_fail, None
    yield "ok_determinism_false_on_one_layer", baseline(det_false_at=39), "ok", k_det_false, None
    yield "ok_partial_cut_after_layer_27", baseline(14), "ok", k_partial(7, 7), None
    yield "ok_partial_cut_between_arms_of_layer_31", baseline(15), "ok", k_partial(8, 7), None
    yield "ok_partial_cut_inside_layer_31", partial_with_interrupted(), "ok", k_partial(7, 7, interrupted=31), None
    yield "refuse_partial_with_cells_of_a_later_layer", partial_stray_cells(), "refuse", None, None
    for f in REFUSE:
        R = fresh(); f(R)
        yield "refuse_" + f.__name__[2:], R, "refuse", None, None
    yield "refuse_cells_file_missing", fresh(), "refuse", None, "cells.jsonl"
    yield "refuse_layers_file_missing", fresh(), "refuse", None, "layers.jsonl"
    yield "refuse_prompt_rows_file_missing", fresh(), "refuse", None, "prompt-rows.jsonl"
    yield "refuse_cells_file_truncated_mid_line", fresh(), "refuse", None, "truncate"


FILES = dict(lay="layers.jsonl", cells="cells.jsonl", prow="prompt-rows.jsonl", tim="attn-timing.jsonl")


def run_case(name, R, expect, check, special):
    with tempfile.TemporaryDirectory(prefix="t176-") as d:
        d = Path(d); exp = d / "exp"; runs = exp / "runs"; runs.mkdir(parents=True)
        (d / PROMPT_DIR).mkdir(); shutil.copy(HERE.parent / PROMPT_DIR / "prompts-e2e.json", d / PROMPT_DIR / "prompts-e2e.json")
        shutil.copy(SUMMARISER, exp / "summarise.py")
        for k, fn in FILES.items():
            if special == fn: continue
            (runs / fn).write_text("".join(json.dumps(x) + "\n" for x in R[k]))
        if special == "truncate":
            t = (runs / "cells.jsonl").read_text(); (runs / "cells.jsonl").write_text(t[:len(t) - 25])
        p = subprocess.run([sys.executable, str(exp / "summarise.py")], capture_output=True, text=True)
        wrote = (runs / "summary.json").exists() or (runs / "summary.md").exists()
        if expect == "refuse":
            ok = p.returncode == 2 and "REFUSED" in p.stderr and not wrote
        else:
            ok = p.returncode == 0 and wrote and bool(check(json.load(open(runs / "summary.json"))))
        return dict(case=name, expect=expect, rc=p.returncode, wrote_summary=wrote, ok=bool(ok))


def main():
    bad = 0; n = 0
    for name, R, expect, check, special in cases():
        r = run_case(name, R, expect, check, special); n += 1; bad += not r["ok"]
        print(json.dumps(r), flush=True)
    print(json.dumps(dict(summariser=SUMMARISER.name, cases=n, failed=bad)))
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
