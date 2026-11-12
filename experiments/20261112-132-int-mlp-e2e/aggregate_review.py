#!/usr/bin/env python3
"""Post-review aggregate receipt (PR #138 round-1 reviews). Reads ONLY the committed raw run files under runs/
(ranges-abl.jsonl, divergence-abl.jsonl, progress.log.jsonl, progress.log); writes runs/aggregate-review.json.
No forward is rerun and no committed run file is modified.

Definitions:
- resid_rel: relative L2 of the residual stream vs REF (float64) after a layer, one value per prompt (divergence-abl.jsonl).
- SD: sample standard deviation with n - 1 in the denominator, over the 10 per-prompt values of one deterministic
  execution (statistics.stdev). It is a spread over prompts, not over repeated runs.
- gap_pp: (XM18 - FM) * 100, in percentage points of resid_rel. A difference between two arms that share the integer MLP,
  not a decomposition of XM18's error (no XS18-only arm was run in this experiment).
- layer_s: wall time per layer from progress.log.jsonl.
Usage: python3 aggregate_review.py   (from any directory)"""
import json, statistics
from pathlib import Path
HERE = Path(__file__).resolve().parent; R = HERE / "runs"
rng = [json.loads(l) for l in open(R / "ranges-abl.jsonl")]
div = [json.loads(l) for l in open(R / "divergence-abl.jsonl")]
prog = [json.loads(l) for l in open(R / "progress.log.jsonl")]
plog = (R / "progress.log").read_text().splitlines()
L = max(d["layer"] for d in div)
out = {"note": __doc__.split("Usage:")[0].strip(), "last_layer": L}

def spread(vals):
    v = list(vals)
    return {"n": len(v), "median": statistics.median(v), "sd_sample_n_minus_1": statistics.stdev(v), "min": min(v), "max": max(v)}

dl = {d["layer"]: d for d in div}
out["resid_rel_last_layer"] = {a: {"per_prompt": dl[L][a], **spread(dl[L][a].values())} for a in ("XM18", "FM")}
out["resid_rel_layer_before_last"] = {"layer": L - 1, **{a: {"per_prompt": dl[L - 1][a], **spread(dl[L - 1][a].values())} for a in ("XM18", "FM")}}

# XM18 - FM gaps
gaps = []
for d in div:
    for p in d["XM18"]:
        gaps.append({"layer": d["layer"], "prompt": p, "xm18": d["XM18"][p], "fm": d["FM"][p],
                     "gap_pp": (d["XM18"][p] - d["FM"][p]) * 100, "fm_over_xm18": d["FM"][p] / d["XM18"][p]})
gl = [g for g in gaps if g["layer"] == L]
out["gap_last_layer"] = {"per_prompt_pp": {g["prompt"]: g["gap_pp"] for g in gl},
                         "max_abs_pp": max(gl, key=lambda g: abs(g["gap_pp"])),
                         "fm_over_xm18_min": min(g["fm_over_xm18"] for g in gl), "fm_over_xm18_max": max(g["fm_over_xm18"] for g in gl)}
out["gap_all_layers_max_abs"] = max(gaps, key=lambda g: abs(g["gap_pp"]))
p03 = "p03-repeat-word"
out["p03_by_layer"] = [{k: g[k] for k in ("layer", "xm18", "fm", "gap_pp", "fm_over_xm18")} for g in gaps if g["prompt"] == p03]
out["layers_with_any_prompt_fm_over_xm18_below_0_8"] = sorted({g["layer"] for g in gaps if g["fm_over_xm18"] < 0.8})

# per-layer time
ls = [r["layer_s"] for r in prog if "layer_s" in r]
lmin = min((r for r in prog if "layer_s" in r), key=lambda r: r["layer_s"]); lmax = max((r for r in prog if "layer_s" in r), key=lambda r: r["layer_s"])
out["layer_s"] = {"n": len(ls), "min": min(ls), "min_layer": lmin["layer"], "max": max(ls), "max_layer": lmax["layer"], "median": statistics.median(ls)}

# hard stop timing
last = max((r for r in prog if "layer" in r and "layer_s" in r), key=lambda r: r["layer"])
out["hard_stop"] = {"registered": "2026-11-12T18:25:00Z", "last_layer_saved": {"layer": last["layer"], "t": last["t"]},
                    "watchdog_lines": [l for l in plog if l.startswith("HARD STOP") or l.startswith("end rc")]}

# m class per layer and without the last layer
def mstats(rows, path="XM18"):
    S = [s for r in rows for s in r["paths"][path].values()]
    c = sum(s["n_m_over_2047"] for s in S); n = sum(s["n_m"] for s in S)
    mx = max((s["m"], r["layer"], p) for r in rows for p, s in r["paths"][path].items())
    return {"n_over": c, "n": n, "frac": c / n, "max": mx[0], "max_layer": mx[1], "max_prompt": mx[2]}
out["m_class"] = {"XM18_layers_0_to_last": mstats(rng), "FM_layers_0_to_last": mstats(rng, "FM"),
                  "XM18_excluding_last_layer": mstats([r for r in rng if r["layer"] < L])}
per = []
for r in rng:
    S = list(r["paths"]["XM18"].values())
    per.append({"layer": r["layer"], "frac": sum(s["n_m_over_2047"] for s in S) / sum(s["n_m"] for s in S)})
out["m_over_frac_per_layer_XM18"] = per
out["m_over_frac_peak_layer"] = max(per, key=lambda x: x["frac"])
ex = [r for r in rng if r["layer"] < L]
out["excluding_last_layer_maxima_XM18"] = {k: max((s[k], r["layer"], p) for r in ex for p, s in r["paths"]["XM18"].items())
                                           for k in ("gw", "u", "h", "acc_down", "out")}
out["silu_exits"] = {a: sum(s["n_silu_sat_lo"] + s["n_silu_sat_hi"] for r in rng for s in r["paths"][a].values()) for a in ("XM18", "FM")}
out["silu_exits_excluding_last_layer_XM18"] = sum(s["n_silu_sat_lo"] + s["n_silu_sat_hi"] for r in ex for s in r["paths"]["XM18"].values())
(R / "aggregate-review.json").write_text(json.dumps(out, indent=1) + "\n")
print(json.dumps({k: out[k] for k in ("resid_rel_last_layer", "resid_rel_layer_before_last", "gap_last_layer", "gap_all_layers_max_abs", "layer_s", "hard_stop", "m_class",
                                      "m_over_frac_peak_layer", "silu_exits", "silu_exits_excluding_last_layer_XM18", "layers_with_any_prompt_fm_over_xm18_below_0_8")}, indent=1))
