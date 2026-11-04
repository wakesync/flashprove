#!/usr/bin/env python3
# Sweeps the pre-registered (C, theta, cap) grid over the per-seed cost files of score_seed.py and writes
# numbers.json (PREREG.md). Pure Python, no model: every number here is a score, not a verification.
#
# usage: analyze.py OUT_numbers.json seed2026.json [seed2027.json ...] [--spot cp_verify_spot.json]
import json
import math
import statistics
import sys

args = sys.argv[1:]
spot = None
if "--spot" in args:
    i = args.index("--spot")
    spot = json.load(open(args[i + 1]))
    del args[i: i + 2]
explore = []
if "--explore" in args:
    i = args.index("--explore")
    explore = args[i + 1:]
    del args[i:]
out_path, files = args[0], args[1:]
seeds = [json.load(open(f)) for f in files]
# Exploratory classes (PREREG amendment 2026-11-04T01:30Z, not pre-registered): merged per seed, marked.
EXPLORATORY = []
for f in explore:
    e = json.load(open(f))
    for s in seeds:
        if s["seed"] == e["seed"]:
            for name, v in e["classes"].items():
                s["classes"][name] = v
                if name not in EXPLORATORY:
                    EXPLORATORY.append(name)

GROSS = ["fp2nd-4", "fp2nd-8", "fp2nd-16", "int2nd-4", "int2nd-8", "int2nd-16", "rand-1", "rand-2", "rand-4",
         "rand-8", "rand-16", "rand-reply", "other-prompt"]
# PREREG "gross" = k >= 4 swaps, random tokens, whole random reply, other prompt. rand-1/rand-2 are
# "random tokens" and so gross by the PREREG text; reported both ways below.
GROSS_STRICT = [c for c in GROSS if c not in ("rand-1", "rand-2")]


def pct(sorted_vals, q):
    """ceil(q N)-th smallest, as fit_limits.py takes its percentile."""
    n = len(sorted_vals)
    return sorted_vals[max(0, min(n - 1, math.ceil(q * n) - 1))]


def clipped_mean_up(costs, C):
    return -(-sum(min(c, C) for c in costs) // len(costs))


def meets(costs, C, theta, cap):
    return sum(min(c, C) for c in costs) <= theta * len(costs) and sum(c > C for c in costs) <= cap


def grid_for(seed):
    fit = [c for c in seed["fit"].values() if c is not None]
    allc = sorted(c for r in fit for c in r)
    Cs = {"exact": 256, "p99": pct(allc, .99), "p99.5": pct(allc, .995), "p99.9": pct(allc, .999), "max": allc[-1],
          "shipped": 9244130}
    pts = []
    for cn, C in Cs.items():
        means = sorted(clipped_mean_up(r, C) for r in fit)
        thetas = {"256": 256, "shipped": 323343}
        for q in (50, 75, 90, 95, 99, 100):
            thetas["p%d" % q] = pct(means, q / 100)
        for tn, th in thetas.items():
            if th > C:
                continue
            for cap in (0, 1, 2, 4):
                pts.append({"label": "C=%s theta=%s cap=%d" % (cn, tn, cap), "C": C, "theta": th, "cap": cap,
                            "theta_eq_C_with_cap": th == C and cap > 0})
    # dedupe by label (kept per seed; values differ across seeds for percentile labels)
    seen, uniq = set(), []
    for p in pts:
        if p["label"] not in seen:
            seen.add(p["label"])
            uniq.append(p)
    return uniq, len(allc)


classes = list(seeds[0]["classes"].keys())
per_seed = []
for s in seeds:
    grid, ncost = grid_for(s)
    res = {}
    for p in grid:
        row = {}
        for c in classes:
            vals = list(s["classes"][c].values())
            scored = [v for v in vals if v is not None]
            acc = sum(meets(v, p["C"], p["theta"], p["cap"]) for v in scored)
            row[c] = {"n": len(scored), "accepted": acc, "no_proof": len(vals) - len(scored),
                      "rate": acc / len(scored) if scored else None}
        res[p["label"]] = {"C": p["C"], "theta": p["theta"], "cap": p["cap"], "flag_theta_eq_C": p["theta_eq_C_with_cap"],
                           "classes": row}
    fitc = [c for c in s["fit"].values() if c is not None]
    allc = sorted(c for r in fitc for c in r)
    fC = pct(allc, .999)
    if fC == s["own_choice"]:
        above = [c for c in allc if c > fC]
        fC = above[0] if above else fC
    fit_rule = {"C": fC, "theta": max(clipped_mean_up(r, fC) for r in fitc), "cap": max(sum(c > fC for c in r) for r in fitc),
                "non_first_choice_tokens": sum(c > s["own_choice"] for c in allc), "fit_tokens": len(allc)}
    per_seed.append({"seed": s["seed"], "fit_costs": ncost, "fit_limits_rule": fit_rule, "grid": res, "sizes": s["sizes"],
                     "fit_no_proof": sum(v is None for v in s["fit"].values()), "timing_s": s.get("timing_s"),
                     "versions": s.get("versions")})

labels = [l for l in per_seed[0]["grid"] if all(l in ps["grid"] for ps in per_seed)]


def stats(xs):
    xs = [x for x in xs if x is not None]
    if not xs:
        return None
    return {"median": statistics.median(xs), "sd": statistics.stdev(xs) if len(xs) > 1 else 0.0, "min": min(xs),
            "max": max(xs), "n_seeds": len(xs)}


agg = {}
for l in labels:
    row = {c: stats([ps["grid"][l]["classes"][c]["rate"] for ps in per_seed]) for c in classes}
    frr = stats([1 - ps["grid"][l]["classes"]["honest"]["rate"] for ps in per_seed])
    agg[l] = {"acceptance": row, "frr": frr,
              "values_per_seed": {ps["seed"]: [ps["grid"][l][k] for k in ("C", "theta", "cap")] for ps in per_seed},
              "flag_theta_eq_C": any(ps["grid"][l]["flag_theta_eq_C"] for ps in per_seed)}


def zero_all(l, cls):
    return all(agg[l]["acceptance"][c] is not None and agg[l]["acceptance"][c]["median"] == 0 for c in cls)


verdict = {}
for name, cls in (("gross", GROSS), ("gross_without_rand1_rand2", GROSS_STRICT)):
    ok = [l for l in labels if zero_all(l, cls) and agg[l]["frr"]["median"] <= 0.05 and not agg[l]["flag_theta_eq_C"]]
    ok_strict = [l for l in ok if all(agg[l]["acceptance"][c]["max"] == 0 for c in cls) and agg[l]["frr"]["max"] <= 0.05]
    verdict[name] = {"points_median": ok, "points_every_seed": ok_strict}
fp1 = [l for l in labels if agg[l]["acceptance"]["fp2nd-1"]["median"] == 0 and agg[l]["frr"]["median"] <= 0.05]
int1 = [l for l in labels if agg[l]["acceptance"]["int2nd-1"]["median"] == 0 and agg[l]["frr"]["median"] <= 0.05]
verdict["clause1_PASS"] = bool(verdict["gross"]["points_median"])
verdict["clause2_holds_no_point_stops_fp2nd1"] = not fp1
verdict["points_stopping_fp2nd1_at_frr_le_5pct"] = fp1
verdict["points_stopping_int2nd1_at_frr_le_5pct"] = int1

# per-seed counts are kept for every grid point but as compact [accepted, n, no_proof] triples
for ps in per_seed:
    for l, g in ps["grid"].items():
        g["classes"] = {c: [v["accepted"], v["n"], v["no_proof"]] for c, v in g["classes"].items()}
json.dump({"experiment": "20261103-6-clipped-gap-rejection", "kind": "score (integer-model package, CPU), not proved",
           "seeds": [ps["seed"] for ps in per_seed], "classes": classes, "exploratory_classes": EXPLORATORY, "gross": GROSS, "per_seed": per_seed,
           "aggregate": agg, "verdict": verdict, "cp_verify_spot": spot}, open(out_path, "w"), separators=(",", ":"), sort_keys=True)
print(json.dumps(verdict, indent=1))
