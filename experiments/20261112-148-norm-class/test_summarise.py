#!/usr/bin/env python3
"""Regression tests for summarise.py's input validation (PR #152 review round 1). Synthetic fixtures only: every row
here is generated below with self-consistent made-up counters; no registered-run number is read or used.

Each case writes a runs directory (baseline.jsonl, arms.jsonl, progress.log.jsonl) to a temporary directory, runs
summarise.py on it and checks the outcome:
  refuse  exit code 2, a "REFUSED" message, no summary.json written
  ok      exit code 0; optional checks on the verdicts
The mutations are the ones the two round-1 reviewers ran (duplicate rows, changed duplicate, missing arm, missing
prompt, truncation, value change, and the rest of their lists) plus the obvious neighbours.
Usage: test_summarise.py   (exit 0 iff every case behaves as expected; prints one JSON line per case)"""
import copy, json, subprocess, sys, tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from validate_runs import PROMPTS, DET, ARMS, R33, D, H, MIX_PROJ, layer_type

PIDS = list(PROMPTS)


# ---------------------------------------------------------------- synthetic, self-consistent rows
def counters(T, maxq):
    """Class counters for T tokens whose largest |q| is maxq: T*5120-3 entries equal to 1, two equal to 2,048 and one
    equal to maxq if maxq > 2,047; otherwise all entries 1 except one equal to maxq."""
    n = T * D
    if maxq > 2047:
        big = [2048, 2048, maxq]
        c = dict(n=n, n_rows=T, max=float(maxq), n_over_2047=3, rows_over_2047=1, ch_over_2047=2,
                 n_ge_2e15=sum(v >= 2 ** 15 for v in big), n_ge_2e17=sum(v >= 2 ** 17 for v in big), n_ge_2e18=sum(v >= 2 ** 18 for v in big))
    else:
        big = [maxq]
        c = dict(n=n, n_rows=T, max=float(maxq), n_over_2047=0, rows_over_2047=0, ch_over_2047=0, n_ge_2e15=0, n_ge_2e17=0, n_ge_2e18=0)
    hist = [0] * 22; hist[1] = n - len(big)
    for v in big: hist[int(v).bit_length()] += 1
    return c, hist


def base_prompt(T, maxq):
    c, hist = counters(T, maxq)
    return dict(c, max_float=maxq / 4096.0, argmax_token=0, argmax_channel=0, hist_bitlen=hist)


def pooled(P):
    mx = max(v["max"] for v in P.values())
    return dict(n=sum(v["n"] for v in P.values()), n_rows=sum(v["n_rows"] for v in P.values()), max=mx,
                n_over_2047=sum(v["n_over_2047"] for v in P.values()), rows_over_2047=sum(v["rows_over_2047"] for v in P.values()),
                ch_over_2047=max(v["ch_over_2047"] for v in P.values()),
                top_channels=[dict(channel=j, max=mx if j == 0 else 1.0, tokens_over_2047=0, median_abs=1.0) for j in range(8)])


def baseline_row(i, maxq_a, maxq_m):
    norms = {}
    for nn, mq in (("input_layernorm", maxq_a), ("post_attention_layernorm", maxq_m)):
        P = {pid: base_prompt(T, mq) for pid, T in PROMPTS.items()}
        norms[nn] = dict(prompts=P, pooled=pooled(P))
    return dict(layer=i, type=layer_type(i), norms=norms)


def arm_prompt(arm, T, r, brow_a, wts, maxq_m):
    k = ARMS[arm]; den, deno = 100.0, 90.0; num = r * den
    if arm == "W":
        qa = {kk: brow_a[kk] for kk in ("n", "n_rows", "max", "n_over_2047", "rows_over_2047", "ch_over_2047", "n_ge_2e15", "n_ge_2e17", "n_ge_2e18")}
        qa["n_clamped"] = 0; qm = dict(counters(T, maxq_m)[0], n_clamped=0)
    elif arm == "C":
        qa = dict(counters(T, 2047)[0], n_clamped=5); qm = dict(counters(T, 2047)[0], n_clamped=4)
    else:
        qa = dict(counters(T, 1500)[0], n_clamped=0); qm = dict(counters(T, 700)[0], n_clamped=0)
    mlp = dict(m=qm["max"], gw=10.0, u=10.0, s=10.0, h=10.0, acc_down=1e6, out=10.0, n_m_over_2047=qm["n_over_2047"], n_gw_ge_2e18=0, n_gw_ge_2e23=0,
               n_u_ge_2e18=0, n_u_ge_2e23=0, n_h_ge_2e18=0, n_h_ge_2e23=0, n_silu_sat_lo=0, n_silu_sat_hi=0, n_acc_down_ge_ledger=0, n_out_ge_2e31=0,
               n_m=T * D, n_hidden=T * H, n_out=T * D, shift_g=wts["g"]["e"] + k - 12, shift_u=wts["u"]["e"] + k - 12, shift_d=wts["d"]["e"])
    return dict(r=r, c=num / deno, d=0.0 if arm == "W" else 0.5 * r, num=num, den_stream=den, den_out=deno, mix_rel=1e-5, mlp_rel=1e-3,
                n_tokens=T, qa=qa, qm=qm, mlp=mlp)


def arm_row(i, brow, r_of):
    """r_of(arm, layer) -> r used for all six prompts of that arm on that layer."""
    wts = {k: dict(e=13, max_abs_float=0.5, max_abs_int=4096.0, e_in_1_24=True, w_in_class=True) for k in ("g", "u", "d")}
    ba = brow["norms"]["input_layernorm"]["prompts"]
    arms = {arm: {pid: arm_prompt(arm, T, r_of(arm, i), ba[pid], wts, 1000) for pid, T in PROMPTS.items()} for arm in ("W", "C", "S3", "S4", "S5")}
    return dict(layer=i, type=layer_type(i), weights=wts, mixer_proj_exponents={n: 13 for n in sorted(MIX_PROJ[layer_type(i)])},
                arms=arms, det_bit_equal={p: True for p in sorted(DET)})


def make_run(n_layers=64, r_of=None, maxq_a=204800, maxq_m=100000):
    """A complete (n_layers = 64) or stopped run on R33. Baseline M = maxq_a / 4096 = 50, so k* = 5 (in the ladder)."""
    r_of = r_of or (lambda arm, i: 5e-4)
    base = [baseline_row(i, maxq_a, maxq_m) for i in range(n_layers)]
    arm_layers = [i for i in R33 if i < n_layers]
    arms = [arm_row(i, base[i], r_of) for i in arm_layers]
    prog = [dict(t="2026-01-01T00:00:00Z", start=True, layer_set="r33")]
    prog += [dict(t="2026-01-01T00:00:00Z", layer=i, arms=5 if i in arm_layers else 0) for i in range(n_layers)]
    if n_layers == 64: prog.append(dict(t="2026-01-01T00:00:00Z", all_done=True))
    return dict(base=base, arms=arms, prog=prog)


def lines(rows): return "".join(json.dumps(r) + "\n" for r in rows)


def write(run, d, raw=None):
    raw = raw or {}
    for key, name in (("base", "baseline.jsonl"), ("arms", "arms.jsonl"), ("prog", "progress.log.jsonl")):
        (d / name).write_text(raw[key] if key in raw else lines(run[key]))


def summarise(d):
    p = subprocess.run([sys.executable, str(HERE / "summarise.py"), str(d)], capture_output=True, text=True)
    S = json.loads((d / "summary.json").read_text()) if (d / "summary.json").exists() else None
    return p.returncode, p.stderr, S


# ---------------------------------------------------------------- cases
C_FAIL_ONE = lambda arm, i: (0.5 if (arm == "C" and i == 3) else (5e-4 if arm == "C" else 5e-3))   # C fails only layer 3; others fail everywhere
CASES = []


def case(name, expect, build, check=None):
    CASES.append((name, expect, build, check))


def mut(fn, base_run=None):
    def b():
        run = copy.deepcopy(base_run or make_run(r_of=C_FAIL_ONE)); raw = fn(run)
        return run, (raw if isinstance(raw, dict) and set(raw) <= {"base", "arms", "prog"} and all(isinstance(v, str) for v in raw.values()) else {})
    return b


def V(S): return {k: v["verdict"] for k, v in S["verdicts"].items()}


# controls: a complete synthetic run is accepted; the validator does not block a legitimate PASS or FAIL
case("control_complete_C_fails_layer_3", "ok", mut(lambda r: None),
     lambda S: V(S)["C"] == "FAIL" and S["arms"]["C"]["n_layers"] == 33 and S["arms"]["C"]["layers_fail"] == [3])
case("control_complete_C_passes", "ok", lambda: (make_run(r_of=lambda a, i: 5e-4 if a == "C" else 5e-3), {}),
     lambda S: V(S)["C"] == "PASS" and S["H_holds"] is True)
case("control_stopped_run_is_partial", "ok", lambda: (make_run(n_layers=52, r_of=C_FAIL_ONE), {}),
     lambda S: S["layer_set_done"] == "partial" and all(v == "NO VERDICT" for v in V(S).values()))

# astra's case: deleting arm C's object from its one failing layer used to give C PASS with 32 layers
case("astra_missing_arm_C_on_failing_layer", "refuse", mut(lambda r: r["arms"][1]["arms"].pop("C")))
case("missing_arm_W", "refuse", mut(lambda r: r["arms"][5]["arms"].pop("W")))
case("extra_arm", "refuse", mut(lambda r: r["arms"][0]["arms"].__setitem__("S6", copy.deepcopy(r["arms"][0]["arms"]["S5"]))))

# duplicates (both reviewers)
case("dup_baseline_row_identical", "refuse", mut(lambda r: r["base"].append(copy.deepcopy(r["base"][43]))))
case("dup_arm_row_identical", "refuse", mut(lambda r: r["arms"].append(copy.deepcopy(r["arms"][0]))))
def _dup_changed(r):
    x = copy.deepcopy(r["arms"][1]); x["arms"]["W"]["p01-ordinary-short"]["r"] = 1e-9; r["arms"].append(x)
case("dup_arm_row_changed_value", "refuse", mut(_dup_changed))
def _dup_changed_consistent(r):
    x = copy.deepcopy(r["arms"][1])
    for v in x["arms"]["C"].values(): v["r"] = 1e-5; v["num"] = 1e-5 * v["den_stream"]; v["c"] = v["num"] / v["den_out"]
    r["arms"].append(x)
case("dup_arm_row_changed_consistently", "refuse", mut(_dup_changed_consistent))
def _dup_inserted(r): r["base"].insert(10, copy.deepcopy(r["base"][10]))
case("dup_baseline_row_adjacent", "refuse", mut(_dup_inserted))

# prompts (opus: dropping p03 from one norm of one baseline row used to keep the pooled n)
def _drop_p03_keep_pooled(r): r["base"][10]["norms"]["post_attention_layernorm"]["prompts"].pop("p03-repeat-word")
case("opus_missing_prompt_baseline_pooled_kept", "refuse", mut(_drop_p03_keep_pooled))
def _drop_prompt_fix_pooled(r):
    d = r["base"][10]["norms"]["input_layernorm"]; d["prompts"].pop("p03-repeat-word"); d["pooled"] = pooled(d["prompts"])
case("missing_prompt_baseline_pooled_recomputed", "refuse", mut(_drop_prompt_fix_pooled))
case("missing_prompt_arm", "refuse", mut(lambda r: r["arms"][2]["arms"]["S4"].pop("p08-chat-refusal")))
def _extra_prompt(r):
    d = r["base"][0]["norms"]["input_layernorm"]; d["prompts"]["p05-code"] = copy.deepcopy(d["prompts"]["p01-ordinary-short"])
case("extra_prompt_baseline", "refuse", mut(_extra_prompt))
def _renamed_prompt(r):
    d = r["arms"][0]["arms"]["W"]; d["p02-ordinary-paragraph"] = d.pop("p01-ordinary-short")
case("renamed_prompt_arm", "refuse", mut(_renamed_prompt))
case("det_flag_missing_prompt", "refuse", mut(lambda r: r["arms"][4]["det_bit_equal"].pop("p09-multilingual")))

# truncation
def _trunc_json(r):
    s = lines(r["arms"]); return {"arms": s[:-40] + "\n"}
case("truncated_json_last_arm_line", "refuse", mut(_trunc_json))
def _trunc_noeol(r):
    s = lines(r["base"]); return {"base": s[:-1]}
case("truncated_missing_final_newline", "refuse", mut(_trunc_noeol))
case("truncated_last_arm_row_dropped", "refuse", mut(lambda r: r["arms"].pop()))
case("truncated_last_baseline_row_dropped", "refuse", mut(lambda r: r["base"].pop()))
case("dropped_middle_arm_row", "refuse", mut(lambda r: r["arms"].pop(5)))
case("dropped_middle_baseline_row", "refuse", mut(lambda r: r["base"].pop(20)))
def _trunc_all(r):
    r["base"].pop(); r["prog"] = [p for p in r["prog"] if p.get("layer") != 63 and not p.get("all_done")]
    r["arms"] = [a for a in r["arms"] if a["layer"] != 63]
case("truncated_consistently_becomes_partial", "ok", mut(_trunc_all),
     lambda S: S["layer_set_done"] == "partial" and all(v == "NO VERDICT" for v in V(S).values()))
case("all_done_without_64_layers", "refuse", mut(lambda r: r["prog"].append(dict(all_done=True)), make_run(n_layers=52, r_of=C_FAIL_ONE)))
case("empty_arms_file", "refuse", mut(lambda r: {"arms": ""}))
case("blank_line", "refuse", mut(lambda r: {"arms": lines(r["arms"][:3]) + "\n" + lines(r["arms"][3:])}))
case("extra_layer_99", "refuse", mut(lambda r: r["base"].append(dict(copy.deepcopy(r["base"][0]), layer=99))))
case("arms_off_registered_set", "refuse", mut(lambda r: r["arms"].__setitem__(1, dict(copy.deepcopy(r["arms"][1]), layer=2, type=layer_type(2)))))

# value changes
def _flip_r(r): r["arms"][0]["arms"]["W"]["p03-repeat-word"]["r"] = 1e-5
case("value_change_r_only", "refuse", mut(_flip_r))
def _flip_c_consistent(r):
    for v in r["arms"][1]["arms"]["C"].values(): v["r"] = 1e-5; v["num"] = 1e-5 * v["den_stream"]; v["c"] = v["num"] / v["den_out"]
case("value_change_consistent_is_visible", "ok", mut(_flip_c_consistent),
     lambda S: V(S)["C"] == "PASS" and S["arms"]["C"]["layers_fail"] == [])     # forged but consistent: changes the output, never silent
def _flip_pooled(r): r["base"][0]["norms"]["input_layernorm"]["pooled"]["n_over_2047"] += 1
case("opus_pooled_over_changed", "refuse", mut(_flip_pooled))
def _flip_prompt_counter(r): r["base"][0]["norms"]["input_layernorm"]["prompts"]["p01-ordinary-short"]["n_over_2047"] += 1
case("astra_prompt_counter_changed", "refuse", mut(_flip_prompt_counter))
def _flip_hist(r): h = r["base"][7]["norms"]["post_attention_layernorm"]["prompts"]["p04-repeat-punct"]["hist_bitlen"]; h[1] -= 1; h[2] += 1
case("histogram_changed_tail_kept_is_visible", "ok", mut(_flip_hist),
     lambda S: S["baseline"]["post_attention_layernorm"]["hist_bitlen"][2] == 1)     # below 2,048 no counter sees it; the summary shows it
def _flip_hist_tail(r): h = r["base"][7]["norms"]["post_attention_layernorm"]["prompts"]["p04-repeat-punct"]["hist_bitlen"]; h[1] -= 1; h[13] += 1
case("histogram_changed_tail", "refuse", mut(_flip_hist_tail))
def _flip_ntok(r): r["arms"][3]["arms"]["S3"]["p07-chat-ordinary"]["n_tokens"] = 24
case("token_count_changed_arm", "refuse", mut(_flip_ntok))
def _flip_nrows(r):
    v = r["base"][2]["norms"]["input_layernorm"]["prompts"]["p01-ordinary-short"]; v["n_rows"] = 12
case("token_count_changed_baseline", "refuse", mut(_flip_nrows))
def _flip_w_qa(r): r["arms"][2]["arms"]["W"]["p01-ordinary-short"]["qa"]["ch_over_2047"] += 1
case("arm_W_mixer_input_differs_from_baseline", "refuse", mut(_flip_w_qa))
def _flip_den(r): v = r["arms"][2]["arms"]["S5"]["p01-ordinary-short"]; v["den_stream"] *= 2; v["r"] = v["num"] / v["den_stream"]
case("denominator_differs_between_arms", "refuse", mut(_flip_den))
def _flip_shift(r): r["arms"][2]["arms"]["S4"]["p01-ordinary-short"]["mlp"]["shift_g"] += 1
case("shift_inconsistent", "refuse", mut(_flip_shift))
def _clamp_w(r): r["arms"][2]["arms"]["W"]["p01-ordinary-short"]["qm"]["n_clamped"] = 1
case("clamp_outside_arm_C", "refuse", mut(_clamp_w))
def _det_false(r): r["arms"][4]["det_bit_equal"]["p09-multilingual"] = False
case("det_flag_false_gives_no_verdict", "ok", mut(_det_false),
     lambda S: S["determinism"]["all_bit_equal"] is False and all(v == "NO VERDICT" for v in V(S).values()))
def _type(r): r["base"][3]["type"] = "linear_attention"
case("layer_type_wrong", "refuse", mut(_type))

# non-finite values
case("nan_in_r", "refuse", mut(lambda r: {"arms": lines(r["arms"]).replace('"r": 0.0005', '"r": NaN', 1)}))
case("infinity_in_num", "refuse", mut(lambda r: {"arms": lines(r["arms"]).replace('"num": ', '"num": Infinity, "x": ', 1)}))
case("overflow_number", "refuse", mut(lambda r: {"base": lines(r["base"]).replace('"max_float": ', '"max_float": 1e999, "y": ', 1)}))
def _neg(r): r["arms"][0]["arms"]["C"]["p01-ordinary-short"]["mix_rel"] = -1.0
case("negative_value", "refuse", mut(_neg))

# injected error (opus): an errored arm is a failing layer, never a smaller denominator
def _err(r): r["arms"][1]["arms"]["C"] = {pid: dict(error="GuardError: synthetic") for pid in PIDS}
case("errored_arm_counts_as_failing", "ok", mut(_err, make_run(r_of=lambda a, i: 5e-4 if a == "C" else 5e-3)),
     lambda S: V(S)["C"] == "FAIL" and S["arms"]["C"]["n_layers"] == 33 and S["arms"]["C"]["totals"]["errors"] == 1)
def _err_partial(r): r["arms"][1]["arms"]["C"]["p01-ordinary-short"] = dict(error="GuardError: synthetic")
case("errored_arm_on_some_prompts_only", "refuse", mut(_err_partial))


def main():
    fails = 0
    for name, expect, build, check in CASES:
        run, raw = build()
        with tempfile.TemporaryDirectory() as td:
            d = Path(td); write(run, d, raw); rc, err, S = summarise(d)
        if expect == "refuse":
            ok = rc == 2 and "REFUSED" in err and S is None
            why = err.strip().splitlines()[-1][:160] if err.strip() else ""
        else:
            ok = rc == 0 and S is not None and (check is None or bool(check(S)))
            why = json.dumps(V(S)) if S else err.strip()[-160:]
        fails += not ok
        print(json.dumps(dict(case=name, expect=expect, rc=rc, ok=ok, detail=why)))
    print(json.dumps(dict(cases=len(CASES), failed=fails)))
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
