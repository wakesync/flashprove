#!/usr/bin/env python3
"""Q3 cost model for a Qwen3.8-27B proof, from merged numbers only (desk, Part of #7).

Registration: experiments/20261112-7-cost-model/PREREG.md. Note: research/cost/Q3-COST-MODEL-1112.md.

Every evidence input (counts, rates, prices, the fit rule, the token and layer counts behind per-token divisions) is
read from a file on main and printed with a label:
  measured      a run on main (results.yaml row, by id and metric name)
  counted       an exact size from a model or builder on main
  extrapolated  a count times a rate taken from another statement or model
  invoiced      a price from a provider invoice on main
  quoted        a price from a saved marketplace offer (offers.json, via results.yaml), not an invoice
  calculated    arithmetic done inside a results.yaml row (a measured rate x a quoted price)
  assumed       a number chosen, not derived
  not established  no evidence on main
Literals left in the code are unit conversions (1,000 tokens, 3,600 s per hour, 1e9 bytes per GB), the windows the
tables are printed at, the sampling fractions f of U2 and the ASSUMED plain rates of section 8.
Nothing this script prints is a measurement of a Qwen proof. No GPU has run any Qwen work.

Usage, from the repository root:   python3 research/cost/q3_cost_model_1112.py [--json OUT]
Deterministic. Needs PyYAML (already required by scripts/update-results.py).
"""
import argparse
import json
import math
import os
import re
import sys

import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
P = lambda *a: os.path.join(ROOT, *a)  # noqa: E731

MODEL = "experiments/20261109-32-qwen-m3-design/runs/model-r3.json"
M2COUNTS = "experiments/20261109-32-qwen-deltanet-lookup-build/runs/counts-vs-model.json"
M2RESULTS = "experiments/20261109-32-qwen-deltanet-lookup-build/RESULTS.md"
LEDGER = "research/results.yaml"
PERF = "guide/performance.md"
REPL1 = "research/gpu/replication-1/README.md"
M3RESULTS = "experiments/20261109-32-qwen-m3-design/RESULTS.md"
WINDOWS = [64, 256, 1024]
MEM_WINDOWS = [64, 128, 256, 1024]
U2_FRACTIONS = (1, 0.1, 0.01, 0.001)


def pow2_floor(x):
    return 2 ** int(math.floor(math.log2(max(1.0, x))))


def die(msg):
    sys.exit("q3_cost_model_1112: " + msg)


def grep(path, pattern, group=1):
    text = open(P(path)).read()
    m = re.search(pattern, text)
    if not m:
        die(f"pattern {pattern!r} not found in {path}: the source text changed, re-check the citation")
    return float(m.group(group).replace(",", ""))


def ledger_metric(rows, rid, name):
    for r in rows:
        if r["id"] == rid:
            for m in r.get("metrics") or []:
                if m["name"] == name:
                    return m
    die(f"results.yaml has no metric {rid}/{name}")


def inputs():
    d = json.load(open(P(MODEL)))
    rows = yaml.safe_load(open(P(LEDGER)))["results"]
    I = {}

    def put(key, value, label, source, note=""):
        I[key] = {"value": value, "label": label, "source": source, "note": note}

    pls = d["packed"]["per_token_layer_segments"]
    ept = pls["T1024"]["entries_per_token"]
    put("entries_per_token_packed", ept["all_layers"], "counted",
        MODEL + " packed.per_token_layer_segments.T1024.entries_per_token.all_layers",
        "plan of record (packed limbs, every state committed); the DeltaNet sub-proof is NOT built")
    put("deltanet_share", pls["T1024"]["deltanet_mixer_share"], "counted", MODEL)
    put("deltanet_mixer_entries_per_layer_token", ept["deltanet_mixer_one_layer"], "counted", MODEL)
    put("segments_per_window", pls["T1024"]["segments_per_window"], "counted", MODEL)
    put("segment_cap", d["H5_r2"]["cp_verify_segment_cap"], "counted", MODEL + " H5_r2.cp_verify_segment_cap")
    for T in WINDOWS:
        e = pls[f"T{T}"]
        x = e["extrapolated"]
        put(f"largest_segment_entries_T{T}", e["largest_segment_entries"], "counted", MODEL)
        put(f"prove_s_T{T}", {"central": x["prove_s"]["central"], "high": x["prove_s"]["high_all_in"],
                              "small_example": x["prove_s"]["upper_bound_small_example"]},
            "extrapolated", MODEL + f" packed.per_token_layer_segments.T{T}.extrapolated.prove_s",
            "PR #70: central/high from a fit to upstream's four Maverick H100 rates (records not in this repo); "
            "small-example from this fork's 2.35 s cp_prove on the tiny synthetic example (mostly start-up). Not bounds")
        put(f"proof_mb_T{T}", x["proof_mb"], "extrapolated", MODEL)
    put("weights_resident_gb", pls["T1024"]["extrapolated"]["weights_resident_gb"], "counted", MODEL)
    bpe = d["vram_calibration_descriptive"]["bytes_per_entry"]
    put("bytes_per_entry", {"low": bpe["low"], "central": bpe["central_registered"],
                            "high": bpe["high_registered"], "own_rate": bpe["small_example_face_value"]},
        "extrapolated", MODEL + " vram_calibration_descriptive.bytes_per_entry",
        "central from one upstream Maverick point; own_rate = this fork's 5,293 MiB on the small example (500 ms "
        "samples, not a true peak); upstream's full-size dense point contradicts own_rate for the dense family; "
        "nothing decides it for DeltaNet")
    put("commit_minutes", d["extrapolated_commit"]["commit_minutes"], "extrapolated", MODEL,
        "linear in committed weights from upstream's ~39 min for Maverick; fixed costs ignored")

    # Built M2 head (#73): the only DeltaNet lowering built at the real head shape (D = 128), CPU harness.
    m2 = json.load(open(P(M2COUNTS)))["stage2"]["rows"]
    put("m2_head_laid_columns_T16", m2["columns_used"]["built"], "counted",
        M2COUNTS + " stage2.rows.columns_used.built", "one head, T = 16, built and equal to the #66 model")
    put("m2_head_tokens", grep(M2RESULTS, r"## Stage 2: the M2 head \(T = (\d+)\)"), "counted",
        M2RESULTS + " ('## Stage 2: the M2 head (T = 16)')", "tokens in the built stage 2 statement")
    sh = d["qwen_shapes"]
    put("deltanet_layers", sh["deltanet_layers"], "counted", MODEL + " qwen_shapes.deltanet_layers")
    put("v_heads", sh["v_heads"], "counted", MODEL + " qwen_shapes.v_heads")
    put("deltanet_head_layers", sh["v_heads"] * sh["deltanet_layers"], "counted", MODEL + " qwen_shapes")
    put("fit_rule_gb", d["H5_r2"]["own_small_example_rate"]["fit_rule_gb"], "assumed",
        MODEL + " H5_r2.own_small_example_rate.fit_rule_gb", "PR #70's one-H200 fit rule, a chosen headroom")
    put("m2_prove_s", ledger_metric(rows, "qwen-deltanet-two-lookup-build", "stage2_prove_wall_after_stop")["value"],
        "measured", LEDGER + " qwen-deltanet-two-lookup-build/stage2_prove_wall_after_stop",
        "CPU research harness, shared loaded VM, after the lane's stop time")
    put("m2_prove_s_estimate", grep(M2RESULTS, r"#66 estimated about (\d+) s prove"), "extrapolated",
        M2RESULTS + " ('#66 estimated about 39 s prove')", "#66's straight line in table length")
    put("m2_verify_s", ledger_metric(rows, "qwen-deltanet-two-lookup-build", "stage2_verify_wall_after_stop")["value"],
        "measured", LEDGER + " qwen-deltanet-two-lookup-build/stage2_verify_wall_after_stop", "CPU, one head, 16 tokens")

    # Measured proving cost on main, at full size, dense family (Maverick shape, synthetic weights), #44.
    bnote = ledger_metric(rows, "h200-memory-lever", "tb1_batch_interval")["note"]
    bm = re.search(r"(\d+) x ([\d,]+) tokens per interval", bnote)
    if not bm:
        die("h200-memory-lever/tb1_batch_interval note no longer states the tokens per interval")
    batch_tokens = int(bm.group(1)) * int(bm.group(2).replace(",", ""))
    put("maverick_tokens_per_batch", batch_tokens, "counted",
        LEDGER + " h200-memory-lever/tb1_batch_interval note ('24 x 1,024 tokens per interval')")
    for arm, rid in (("h100", "ca1"), ("h200", "tb1")):
        iv = ledger_metric(rows, "h200-memory-lever", f"{rid}_batch_interval")["value"]
        put(f"maverick_tok_per_s_{arm}", batch_tokens / iv, "measured",
            LEDGER + f" h200-memory-lever/{rid}_batch_interval (tokens per batch / interval)",
            "one session per arm, two hosts, H100 host 14% below upstream; Maverick shape, synthetic weights")
        put(f"maverick_usd_per_mtok_{arm}",
            ledger_metric(rows, "h200-memory-lever", f"usd_per_mtok_{rid[:2]}")["value"], "calculated",
            LEDGER + " h200-memory-lever", "calculated in the row from a measured rate and a quoted price")
    put("maverick_entries_per_request", grep("experiments/20261109-32-qwen-m3-design/RESULTS.md",
                                             r"\| Maverick \(stored configuration\) \| 25 \| ([\d,]+) \|"),
        "counted", "experiments/20261109-32-qwen-m3-design/RESULTS.md H4 table (cp_verify -plan arrays)",
        "one 1,024-token request")

    # Prices.
    put("usd_h100_invoice", grep(REPL1, r"at \$([\d.]+)/h"), "invoiced", REPL1 + " (invoice, H100)")
    h100box = ledger_metric(rows, "h200-memory-lever", "price_per_hour_h100_box")
    gm = re.search(r"(\d+)-GPU box", h100box["note"])
    if not gm:
        die("h200-memory-lever/price_per_hour_h100_box note no longer states the GPUs per box")
    put("h100_box_gpus", int(gm.group(1)), "counted", LEDGER + " h200-memory-lever/price_per_hour_h100_box note")
    put("usd_h100_quote_per_gpu", h100box["value"] / int(gm.group(1)), "quoted",
        LEDGER + " h200-memory-lever/price_per_hour_h100_box / GPUs per box", "a quote for a 2-GPU box, not an invoice")
    put("usd_h200_quote", ledger_metric(rows, "h200-memory-lever", "price_per_hour_h200_box")["value"],
        "quoted", LEDGER + " h200-memory-lever/price_per_hour_h200_box", "a quote incl. 100 GB storage; not Tinfoil")
    put("usd_assumed", grep(M3RESULTS, r"At an \*\*assumed\*\* ([\d.]+) USD per GPU-hour"), "assumed",
        M3RESULTS + " (PR #70: 'At an **assumed** 3 USD per GPU-hour')")

    # Upstream's proving-vs-serving multiples (Maverick; records not in this repository).
    put("upstream_multiple_prefill", grep(PERF, r"proving at 24 per batch is ([\d.]+) times slower"),
        "measured upstream", PERF + " Cost paragraph", "calculated upstream vs stock vLLM FP8 on 8 H100s")
    put("upstream_multiple_decode", grep(PERF, r"One pass is ([\d.]+) times slower"),
        "measured upstream", PERF + " Cost paragraph", "one pass vs decoding at 512 streams; a pass checks one token")
    put("upstream_startup_s", [grep(PERF, r"start-up of ([\d.]+) to ([\d.]+) seconds", 1),
                               grep(PERF, r"start-up of ([\d.]+) to ([\d.]+) seconds", 2)],
        "measured upstream", PERF)
    put("upstream_steady_tok_s_b24", grep(PERF, r"\| 24 \| ([\d.]+) \u00b1"), "measured upstream",
        PERF + " rate table, 24 per batch", "Maverick, one H100, records not in this repository")
    put("plain_qwen_tok_per_s", None, "not established", "search of main",
        "no plain-inference rate for Qwen3.8-27B on any card is on main")
    return I


def model(I):
    v = lambda k: I[k]["value"]  # noqa: E731
    out = {}
    # 1. GPU-seconds per 1,000 window tokens, by T and time rate (PR #70's three rates).
    gps = {}
    for T in WINDOWS:
        gps[T] = {r: s / T * 1000 for r, s in v(f"prove_s_T{T}").items()}
    out["gpu_s_per_1k"] = gps
    # 2. Factor: the built lowering's volume vs the plan of record. Units differ (CPU harness laid columns vs
    #    GPU prover committed entries); the ratio is reported as a volume multiplier with that caveat.
    built_per_head_token = v("m2_head_laid_columns_T16") / v("m2_head_tokens")
    built_per_token = built_per_head_token * v("deltanet_head_layers")
    plan_mixer_per_token = v("deltanet_mixer_entries_per_layer_token") * v("deltanet_layers")
    out["built_vs_plan_mixer"] = built_per_token / plan_mixer_per_token
    dense_rest = v("entries_per_token_packed") - plan_mixer_per_token
    out["built_vs_plan_total"] = (built_per_token + dense_rest) / v("entries_per_token_packed")
    out["built_mixer_columns_per_token"] = built_per_token
    out["built_mixer_columns_per_layer_token"] = built_per_head_token * v("v_heads")
    # 3. Estimator miss seen on main (#73): measured / estimated prove time of the M2 head.
    out["estimate_miss"] = v("m2_prove_s") / v("m2_prove_s_estimate")
    # 4. Prices.
    prices = {"h100_invoice": v("usd_h100_invoice"), "h100_quote_per_gpu": v("usd_h100_quote_per_gpu"),
              "assumed": v("usd_assumed"), "h200_quote": v("usd_h200_quote")}
    out["prices"] = prices
    pmin, pmax = min(prices.values()), max(prices.values())
    # 5. USD per 1,000 window tokens.
    usd = {T: {r: {k: g / 3600 * p for k, p in prices.items()} for r, g in gps[T].items()} for T in WINDOWS}
    out["usd_per_1k"] = usd
    # 6. Memory of the largest segment, and the largest power-of-two window under the fit rule, for BOTH volume
    #    scenarios. The largest segment is one DeltaNet layer (model-r3.json: largest_segment_entries / T equals the
    #    per-layer mixer entries). Plan: the plan of record's mixer entries per token. Built: the built M2 head's laid
    #    columns per token x v_heads, the same laid-columns-to-entries transfer the built-volume time factor uses.
    fit_gb = v("fit_rule_gb")
    mem = {T: {k: v(f"largest_segment_entries_T{T}") * b / 1e9 for k, b in v("bytes_per_entry").items()}
           for T in WINDOWS}
    out["largest_segment_gb"] = mem
    per_T_entries = v("largest_segment_entries_T1024") / 1024  # linear in T (per-layer DeltaNet segment)
    if not math.isclose(per_T_entries, v("deltanet_mixer_entries_per_layer_token"), rel_tol=1e-9):
        die("largest segment is no longer one DeltaNet layer's mixer in model-r3.json; re-check the memory model")
    seg_per_token = {"plan": per_T_entries, "built": out["built_mixer_columns_per_layer_token"]}
    out["largest_segment_entries_per_token"] = seg_per_token
    out["largest_segment_gb_built"] = {T: {k: seg_per_token["built"] * T * b / 1e9
                                          for k, b in v("bytes_per_entry").items()} for T in MEM_WINDOWS}

    def fits(per_tok):
        f = {}
        for k, b in v("bytes_per_entry").items():
            tmax = fit_gb * 1e9 / (b * per_tok)
            tres = (fit_gb - v("weights_resident_gb")) * 1e9 / (b * per_tok)
            f[k] = {"t_max": tmax, "t_pow2": pow2_floor(tmax), "t_max_resident": tres,
                    "with_resident_weights_t_pow2": pow2_floor(tres)}
        return f
    fit = fits(seg_per_token["plan"])
    out["fit_window"] = fit
    out["fit_window_built"] = fits(seg_per_token["built"])
    # 7. Anchor: the only measured full-size proving rate on main (Maverick shape, #44), per token.
    mav = {a: 1.0 / v(f"maverick_tok_per_s_{a}") for a in ("h100", "h200")}
    out["maverick_gpu_s_per_token"] = mav
    out["qwen_central_over_maverick_h100"] = gps[1024]["central"] / 1000 / mav["h100"]
    out["entries_qwen_over_maverick"] = v("entries_per_token_packed") * 1024 / v("maverick_entries_per_request")
    # 8. Selected scenarios (product of the extreme factors on main), T = 1,024 where it fits, else the largest fit.
    #    Not bounds on actual Qwen cost. The high case uses the built volume for time AND for memory, so its window is
    #    the largest power of two that fits at the own rate with the built volume. The small-example rate is flat per
    #    token in T (PR #70: 2.35 s per small example, scaled linearly in entries), so the window does not change its USD.
    low = gps[1024]["central"] * pmin / 3600
    fb = out["fit_window_built"]["own_rate"]["t_pow2"]
    high_T = 1024 if fb >= 1024 else fb
    if high_T not in WINDOWS:
        die(f"high-case window {high_T} is not one of the tabulated windows {WINDOWS}")
    high = gps[high_T]["small_example"] * out["built_vs_plan_total"] * pmax / 3600
    out["small_example_per_token_flat"] = (max(g["small_example"] for g in gps.values())
                                           / min(g["small_example"] for g in gps.values()))
    out["envelope_usd_per_1k"] = {"low": low, "high": high, "ratio": high / low, "high_window": high_T,
                                  "high_window_plan_volume_own_rate": fit["own_rate"]["t_pow2"]}
    out["envelope_central"] = gps[1024]["central"] * v("usd_assumed") / 3600
    # 9. Gap ranking: spread of one factor, others central.
    gaps = [
        ("G-time: which GPU-s per entry a DeltaNet entry costs (central vs small-example rate)",
         gps[1024]["small_example"] / gps[1024]["central"], "USD and GPU-s"),
        ("G-mem: bytes per entry of a DeltaNet segment (16 vs 220)",
         v("bytes_per_entry")["own_rate"] / v("bytes_per_entry")["low"], "GPU memory; USD only if it forces T down"),
        ("G-price: USD per GPU-hour (H100 invoice vs H200 quote)", pmax / pmin, "USD"),
        ("G-volume: entries of the lowering that gets built (plan of record vs built M2 volume)",
         out["built_vs_plan_total"], "USD, GPU-s and memory (unit caveat)"),
        ("G-window: per-token share of fixed passes (T = 64 vs 1,024, central)",
         gps[64]["central"] / gps[1024]["central"], "USD and GPU-s"),
        ("G-estimate: estimator miss seen on main (#73 measured / #66 estimate)", out["estimate_miss"],
         "USD and GPU-s (CPU evidence, transferred)"),
        ("G-fidelity: wider recurrence if F12 is replaced (+17%, a lower bound)",
         d_sens(), "USD, GPU-s and memory"),
        ("G-plain: plain-inference rate for the multiple", float("inf"), "the multiple only; not on main"),
        ("G-H200: H200 speed vs H100 (assumed equal)", float("nan"), "USD and GPU-s; not quantified on main"),
    ]
    out["gaps"] = sorted(gaps, key=lambda g: (-(g[1] if g[1] == g[1] else -1)))
    # 10. U2 and fixed costs.
    out["u2"] = {f: {r: gps[1024][r] * f for r in gps[1024]} for f in U2_FRACTIONS}  # plan volume only
    # Same selected scenarios as section 8, per 1,000 served window tokens: low = central rate at plan volume,
    # T = 1,024; high = small-example rate x built volume at the built-volume own-rate window.
    out["u2_scenarios"] = {f: {"low_gpu_s": gps[1024]["central"] * f, "low_usd": low * f,
                               "high_gpu_s": gps[high_T]["small_example"] * out["built_vs_plan_total"] * f,
                               "high_usd": high * f, "high_window": high_T} for f in U2_FRACTIONS}
    out["startup_vs_window_central"] = [s / v("prove_s_T1024")["central"] for s in v("upstream_startup_s")]
    # 11. Multiple of plain inference at assumed plain rates (labelled assumed).
    assumed_plain = [1000.0, 5000.0, 10000.0]
    out["multiple_at_assumed_plain"] = {p: {r: gps[1024][r] / 1000 * p for r in gps[1024]} for p in assumed_plain}
    out["maverick_implied_plain_prefill_tok_s"] = v("upstream_steady_tok_s_b24") * v("upstream_multiple_prefill")
    return out


def d_sens():
    """Entries multiplier if the recurrence widens (PR #70 sensitivity, packed T = 1,024, per-layer segments)."""
    d = json.load(open(P(MODEL)))
    s = d["sensitivity_open_norm_scaling"]["packed_T1024"]
    return s["state_4_limbs"]["per_token_layer_segments"]["entries_vs_base"]


def report(I, M):
    v = lambda k: I[k]["value"]  # noqa: E731
    w = print
    w("Q3 COST MODEL (desk). EXTRAPOLATED, NOT MEASURED: no Qwen work has run on a GPU.")
    w("Inputs (label, value, source):")
    for k, x in I.items():
        val = x["value"]
        if isinstance(val, float):
            val = f"{val:.6g}"
        w(f"  [{x['label']}] {k} = {val}  <- {x['source']}" + (f"  ({x['note']})" if x["note"] else ""))
    w("\n1. GPU-seconds per 1,000 window tokens (PR #70 rates; extrapolated):")
    for T in WINDOWS:
        g = M["gpu_s_per_1k"][T]
        w(f"  T={T}: central {g['central']:.1f}, high {g['high']:.1f}, small-example {g['small_example']:.0f}")
    w("\n2. USD per 1,000 window tokens at T=1024 (extrapolated x price):")
    for r, row in M["usd_per_1k"][1024].items():
        w(f"  {r}: " + ", ".join(f"{k} {M['prices'][k]:.2f}/h -> {u:.4f}" for k, u in row.items()))
    w("\n3. Largest-segment GPU memory, GB (extrapolated) and largest power-of-two window under "
      f"{v('fit_rule_gb'):.0f} GB:")
    w(f"  3a. plan volume ({M['largest_segment_entries_per_token']['plan']:.7g} entries per token in one DeltaNet layer):")
    for T in WINDOWS:
        m = M["largest_segment_gb"][T]
        w(f"  T={T}: " + ", ".join(f"{k} {g:.1f}" for k, g in m.items()))
    for k, f in M["fit_window"].items():
        w(f"  {k}: T_max {f['t_max']:.0f} -> {f['t_pow2']} streamed; {f['with_resident_weights_t_pow2']} "
          "with weights resident")
    w(f"  3b. built volume ({M['largest_segment_entries_per_token']['built']:.7g} CPU-harness laid columns per token in "
      "one DeltaNet layer, read as entries; the high case's volume assumption):")
    for T in MEM_WINDOWS:
        m = M["largest_segment_gb_built"][T]
        w(f"  T={T}: " + ", ".join(f"{k} {g:.2f}" for k, g in m.items()))
    for k, f in M["fit_window_built"].items():
        w(f"  {k}: T_max {f['t_max']:.0f} -> {f['t_pow2']} streamed; T_max {f['t_max_resident']:.0f} -> "
          f"{f['with_resident_weights_t_pow2']} with weights resident")
    w(f"  segments per window {v('segments_per_window')} vs cp_verify cap {v('segment_cap')}")
    w("\n4. Factors from merged results:")
    w(f"  built M2 lowering volume / plan-of-record mixer volume: {M['built_vs_plan_mixer']:.2f}x "
      f"({M['built_mixer_columns_per_token']:.4g} CPU-harness laid columns per token vs "
      f"{v('deltanet_mixer_entries_per_layer_token') * v('deltanet_layers'):.4g} planned entries); whole model {M['built_vs_plan_total']:.2f}x")
    w(f"  estimator miss (#73 measured {v('m2_prove_s'):.1f} s / #66 estimate {v('m2_prove_s_estimate'):.0f} s): "
      f"{M['estimate_miss']:.2f}x (CPU)")
    w(f"  Maverick measured (#44): {1 / M['maverick_gpu_s_per_token']['h100']:.2f} tok/s H100, "
      f"{1 / M['maverick_gpu_s_per_token']['h200']:.2f} tok/s H200; "
      f"{v('maverick_usd_per_mtok_h100'):.2f} / {v('maverick_usd_per_mtok_h200'):.2f} USD per Mtok")
    w(f"  Qwen central GPU-s per token / Maverick measured H100: {M['qwen_central_over_maverick_h100']:.2f}x; "
      f"committed entries per 1,024 window, Qwen packed / Maverick: {M['entries_qwen_over_maverick']:.2f}x")
    e = M["envelope_usd_per_1k"]
    w(f"\n5. Selected conditional scenarios (variable proving cost only, NOT bounds on actual Qwen cost), USD per 1,000 "
      f"window tokens (prompt + reply): low {e['low']:.4f}, central {M['envelope_central']:.4f} "
      f"({v('usd_assumed'):.2f}/h), high {e['high']:.4f} (built volume for time and memory, window {e['high_window']}; "
      f"{e['high_window_plan_volume_own_rate']} at plan volume); ratio {e['ratio']:.0f}x")
    w(f"  small-example GPU-s per token, max/min over T: {M['small_example_per_token_flat']:.9f} (flat, so the high "
      "case's USD does not depend on its window)")
    w("\n6. Gaps ranked by the spread of one factor (others central; ties to two decimals are not ordered):")
    for name, f, scope in M["gaps"]:
        fs = "unbounded (not on main)" if f == float("inf") else ("not quantified" if f != f else f"{f:.2f}x")
        w(f"  {fs:>24}  {name}  [{scope}]")
    w("\n7. U2, proving GPU-s per 1,000 served window tokens, before fixed costs.")
    w("  7a. plan volume only, T=1024 (not the full scenario range):")
    for f, row in M["u2"].items():
        w(f"  f={f}: " + ", ".join(f"{r} {g:.3g}" for r, g in row.items()))
    w("  7b. the selected scenarios of section 5 (low: central, plan volume, T=1024; high: small-example x built volume, "
      f"window {e['high_window']}):")
    for f, row in M["u2_scenarios"].items():
        w(f"  f={f}: low {row['low_gpu_s']:.4g} GPU-s ({row['low_usd']:.4g} USD), "
          f"high {row['high_gpu_s']:.4g} GPU-s ({row['high_usd']:.4g} USD)")
    s = M["startup_vs_window_central"]
    w(f"  upstream start-up / central window proof: {s[0]:.2f}x to {s[1]:.2f}x")
    w("\n8. Multiple of plain inference = GPU-s per token x plain tok/s. Plain Qwen rate NOT ON MAIN.")
    w(f"  (context, calculated upstream: Maverick plain prefill implied ~{M['maverick_implied_plain_prefill_tok_s']:.0f} "
      f"tok/s per GPU = {v('upstream_steady_tok_s_b24')} x {v('upstream_multiple_prefill')}; not a Qwen number)")
    for p, row in M["multiple_at_assumed_plain"].items():
        w(f"  at an ASSUMED {p:.0f} plain tok/s per GPU: " + ", ".join(f"{r} {x:.0f}x" for r, x in row.items()))
    w("\nEXTRAPOLATED, NOT MEASURED (repeated).")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", help="also write inputs and outputs as JSON")
    a = ap.parse_args()
    I = inputs()
    M = model(I)
    report(I, M)
    if a.json:
        def clean(o):
            if isinstance(o, float) and (o != o or o in (float("inf"), float("-inf"))):
                return str(o)
            if isinstance(o, dict):
                return {str(k): clean(x) for k, x in o.items()}
            if isinstance(o, (list, tuple)):
                return [clean(x) for x in o]
            return o
        json.dump(clean({"inputs": I, "model": M}), open(a.json, "w"), indent=1, sort_keys=True)


if __name__ == "__main__":
    main()
