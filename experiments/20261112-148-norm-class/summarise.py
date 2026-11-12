#!/usr/bin/env python3
"""Summarise the registered run against PREREG.md. Reads runs/baseline.jsonl and runs/arms.jsonl only.
Writes runs/summary.json and runs/summary.md. Applies the registered rules as written:
  - k rule for arm S: k* = largest integer k <= 12 with RNE(2^k M) <= 2,047, M = largest |n_float| of the baseline over
    both norms, all 64 layers, all registered tokens. Evaluated only if the baseline covers all 64 layers.
  - class verdict per arm; fidelity bar per layer: median over prompts of r <= 1e-3 and max over prompts of r <= 1e-2.
A partial run gets per-layer rows and no all-layer verdict.
Usage: summarise.py [runs_dir]"""
import json, math, statistics, sys
from pathlib import Path

R = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parent / "runs"
NL = 64; NPROMPT = 6; MED_BAR = 1e-3; MAX_BAR = 1e-2
NORMS = ("input_layernorm", "post_attention_layernorm")
load = lambda n: [json.loads(l) for l in open(R / n)] if (R / n).exists() else []
base = {r["layer"]: r for r in load("baseline.jsonl")}
arms = {r["layer"]: r for r in load("arms.jsonl")}
S = dict(layers_baseline=sorted(base), layers_arms=sorted(arms), baseline_complete=sorted(base) == list(range(NL)),
         arms_complete_64=sorted(arms) == list(range(NL)), bar=dict(median_r=MED_BAR, max_r=MAX_BAR))

# ---------------------------------------------------------------- baseline
B = {}
for name in NORMS:
    rows = []; tot = dict(n=0, over=0, ge15=0, ge17=0, ge18=0, rows=0, rows_over=0); mx = (0.0, None, None); mxf = 0.0
    hist = [0] * 22
    for i in sorted(base):
        d = base[i]["norms"][name]; p = d["pooled"]; per = d["prompts"]
        ge15 = sum(v["n_ge_2e15"] for v in per.values()); ge17 = sum(v["n_ge_2e17"] for v in per.values()); ge18 = sum(v["n_ge_2e18"] for v in per.values())
        lmaxf = max(v["max_float"] for v in per.values()); wp = max(per, key=lambda k: per[k]["max"])
        for v in per.values():
            for b_, c in enumerate(v["hist_bitlen"]): hist[b_] += c
        rows.append(dict(layer=i, type=base[i]["type"], n=p["n"], max_q12=p["max"], max_float=lmaxf, max_prompt=wp, n_over_2047=p["n_over_2047"],
                         share_over_2047=p["n_over_2047"] / p["n"], rows_over_2047=p["rows_over_2047"], n_rows=p["n_rows"],
                         ch_over_2047=p["ch_over_2047"], n_ge_2e15=ge15, n_ge_2e17=ge17, n_ge_2e18=ge18,
                         top_channel=p["top_channels"][0]["channel"], per_prompt_share={k: v["n_over_2047"] / v["n"] for k, v in per.items()}))
        tot["n"] += p["n"]; tot["over"] += p["n_over_2047"]; tot["ge15"] += ge15; tot["ge17"] += ge17; tot["ge18"] += ge18
        tot["rows"] += p["n_rows"]; tot["rows_over"] += p["rows_over_2047"]
        if p["max"] > mx[0]: mx = (p["max"], i, wp)
        mxf = max(mxf, lmaxf)
    sh = [r["share_over_2047"] for r in rows]
    B[name] = dict(layers=rows, total=tot, share_over_2047=tot["over"] / tot["n"] if tot["n"] else None, max_q12=mx[0], max_layer=mx[1], max_prompt=mx[2],
                   max_float=mxf, layers_with_any_over=sum(1 for r in rows if r["n_over_2047"]), n_layers=len(rows),
                   share_per_layer=dict(median=statistics.median(sh), min=min(sh), max=max(sh)) if sh else None, hist_bitlen=hist)
S["baseline"] = B

# ---------------------------------------------------------------- k rule
M = max((B[n]["max_float"] for n in NORMS), default=0.0)
kstar = None
if S["baseline_complete"]:
    kstar = max(k for k in range(-40, 13) if round(2.0 ** k * M) <= 2047)
S["k_rule"] = dict(M=M, evaluable=S["baseline_complete"], k_star=kstar, ladder=[3, 4, 5],
                   in_ladder=kstar in (3, 4, 5) if kstar is not None else None,
                   note="k* = largest k <= 12 with RNE(2^k M) <= 2,047; needs the baseline on all 64 layers")
ARM_S = f"S{kstar}" if kstar in (3, 4, 5) else None

# ---------------------------------------------------------------- arms
CLASS = {"W": 2 ** 18, "C": 2048, "S3": 2048, "S4": 2048, "S5": 2048}        # |q| < CLASS
A = {}
for arm in ("C", "S3", "S4", "S5", "W"):
    rows = []; out = dict(n_entries=0, n_out_of_class=0, n_clamped_a=0, n_clamped_m=0, n_ge_2e15=0, n_ge_2e17=0, n_ge_2e18=0, max_qa=0.0, max_qm=0.0,
                          silu_exits=0, n_hidden=0, max_gw=0.0, max_u=0.0, max_h=0.0, max_out=0.0, max_acc_down=0.0, n_gw_ge_2e18=0, n_u_ge_2e18=0,
                          n_h_ge_2e18=0, n_gwuh_ge_2e23=0, n_out_ge_2e31=0, shifts_min=99, shifts_max=-99, errors=0)
    for i in sorted(arms):
        d = arms[i]["arms"].get(arm)
        if d is None: continue
        if any("error" in v for v in d.values()):
            out["errors"] += 1; rows.append(dict(layer=i, type=arms[i]["type"], error=True, passes=False)); continue
        r = [v["r"] for v in d.values()]; c = [v["c"] for v in d.values()]; dd = [v["d"] for v in d.values() if v["d"] is not None]
        k = 12 if arm in ("W", "C") else int(arm[1])
        sh = [v["mlp"]["shift_g"] for v in d.values()] + [v["mlp"]["shift_u"] for v in d.values()] + [e + k - 12 for e in arms[i]["mixer_proj_exponents"].values()]
        ooc = 0
        for v in d.values():
            for q in (v["qa"], v["qm"]):
                out["n_entries"] += q["n"]
                if q["max"] >= CLASS[arm]:
                    ooc += q["n_ge_2e18"] if arm == "W" else q["n_over_2047"]
                out["n_ge_2e15"] += q["n_ge_2e15"]; out["n_ge_2e17"] += q["n_ge_2e17"]; out["n_ge_2e18"] += q["n_ge_2e18"]
            out["n_clamped_a"] += v["qa"]["n_clamped"]; out["n_clamped_m"] += v["qm"]["n_clamped"]
            out["max_qa"] = max(out["max_qa"], v["qa"]["max"]); out["max_qm"] = max(out["max_qm"], v["qm"]["max"])
            m = v["mlp"]; out["silu_exits"] += m["n_silu_sat_lo"] + m["n_silu_sat_hi"]; out["n_hidden"] += m["n_hidden"]
            for a_, b_ in (("max_gw", "gw"), ("max_u", "u"), ("max_h", "h"), ("max_out", "out"), ("max_acc_down", "acc_down")): out[a_] = max(out[a_], m[b_])
            out["n_gw_ge_2e18"] += m["n_gw_ge_2e18"]; out["n_u_ge_2e18"] += m["n_u_ge_2e18"]; out["n_h_ge_2e18"] += m["n_h_ge_2e18"]
            out["n_gwuh_ge_2e23"] += m["n_gw_ge_2e23"] + m["n_u_ge_2e23"] + m["n_h_ge_2e23"]; out["n_out_ge_2e31"] += m["n_out_ge_2e31"]
        out["n_out_of_class"] += ooc; out["shifts_min"] = min(out["shifts_min"], min(sh)); out["shifts_max"] = max(out["shifts_max"], max(sh))
        med = statistics.median(r)
        rows.append(dict(layer=i, type=arms[i]["type"], n_prompts=len(r), n_tokens=sum(v["n_tokens"] for v in d.values()), r_median=med, r_max=max(r), r_min=min(r),
                         r_max_prompt=max(d, key=lambda p: d[p]["r"]), c_median=statistics.median(c), c_max=max(c),
                         d_median=statistics.median(dd) if dd else None, d_max=max(dd) if dd else None,
                         mix_rel_max=max(v["mix_rel"] for v in d.values()), mlp_rel_max=max(v["mlp_rel"] for v in d.values()),
                         clamped_a=sum(v["qa"]["n_clamped"] for v in d.values()), clamped_m=sum(v["qm"]["n_clamped"] for v in d.values()),
                         silu_exits=sum(v["mlp"]["n_silu_sat_lo"] + v["mlp"]["n_silu_sat_hi"] for v in d.values()),
                         shift_min=min(sh), shift_max=max(sh), out_of_class=ooc,
                         passes=bool(len(r) == NPROMPT and med <= MED_BAR and max(r) <= MAX_BAR)))
    ok = [x for x in rows if not x.get("error")]
    shifts_ok = (1 <= out["shifts_min"] and out["shifts_max"] <= 24) if ok else None
    # Arm W's mixer input IS the baseline q12 of input_layernorm, so its class is also checked on every baseline layer
    # (all 64), not only on the layers where the arms ran. C is in class by construction; S by its k rule (M is over 64 layers).
    base_ge18 = sum(B[n]["total"]["ge18"] for n in NORMS)
    out["baseline_ge_2e18_all_baseline_layers"] = base_ge18
    in_class = (out["n_out_of_class"] == 0 and out["errors"] == 0 and (shifts_ok if arm.startswith("S") else True)
                and (base_ge18 == 0 if arm == "W" else True)) if ok else None
    layers_pass = sum(1 for x in rows if x["passes"])
    A[arm] = dict(layers=rows, totals=out, n_layers=len(rows), layers_pass=layers_pass, layers_fail=[x["layer"] for x in rows if not x["passes"]],
                  in_class_on_layers_done=in_class, shifts_in_1_24=shifts_ok,
                  fidelity_bar_on_layers_done=(layers_pass == len(rows)) if rows else None,
                  r_median_over_layers=dict(median=statistics.median([x["r_median"] for x in ok]), min=min(x["r_median"] for x in ok),
                                            max=max(x["r_median"] for x in ok)) if ok else None,
                  r_max_over_layers=max(x["r_max"] for x in ok) if ok else None,
                  worst_layer=max(ok, key=lambda x: x["r_max"])["layer"] if ok else None)
S["arms"] = A
det = [all(r["det_bit_equal"].values()) and len(r["det_bit_equal"]) == 2 for r in arms.values()]
S["determinism"] = dict(layers_checked=len(det), all_bit_equal=bool(det) and all(det))

# ---------------------------------------------------------------- verdicts (only for the registered layer set, complete)
done = sorted(arms)
R33 = sorted({i for i in range(NL) if i % 4 in (0, 3)} | {26})
layer_set = "full" if done == list(range(NL)) else ("r33" if done == R33 else "partial")
S["layer_set_done"] = layer_set
V = {}
for name, arm in (("C", "C"), ("S", ARM_S), ("W", "W")):
    if layer_set == "partial" or not S["baseline_complete"] or not S["determinism"]["all_bit_equal"]:
        V[name] = dict(arm=arm, verdict="NO VERDICT", why="run incomplete, baseline incomplete or determinism not shown")
    elif arm is None:
        V[name] = dict(arm=None, verdict="NO VERDICT", why="arm S not measured at the rule's k (k* outside the ladder 3, 4, 5)")
    else:
        a = A[arm]
        V[name] = dict(arm=arm, in_class=a["in_class_on_layers_done"], fidelity=a["fidelity_bar_on_layers_done"],
                       verdict="PASS" if (a["in_class_on_layers_done"] and a["fidelity_bar_on_layers_done"]) else "FAIL", layers_measured=a["n_layers"])
S["verdicts"] = V
S["H_holds"] = (any(v["verdict"] == "PASS" for v in V.values()) if all(v["verdict"] != "NO VERDICT" for v in V.values())
                else (True if any(v["verdict"] == "PASS" for v in V.values()) else None))
(R / "summary.json").write_text(json.dumps(S, indent=1) + "\n")

# ---------------------------------------------------------------- markdown
f = lambda x: "n/a" if x is None else (f"{x:.3g}" if isinstance(x, float) else f"{x:,}" if isinstance(x, int) else str(x))
L = [f"# Summary (generated by summarise.py from baseline.jsonl and arms.jsonl)", "",
     f"Baseline layers: {len(base)} of 64. Arm layers: {len(arms)} (set: {layer_set}). Determinism (arm C twice on p01, p09): "
     f"{'bit-equal in all ' + str(len(det)) + ' layers' if S['determinism']['all_bit_equal'] else 'NOT shown'}.", "",
     f"k rule: M = {M:.6g} (largest |norm output| in the baseline), k* = {kstar}; arm S = {ARM_S}.", "", "## Verdicts", "",
     "| arm | measured as | in class | fidelity bar | verdict |", "|---|---|---|---|---|"]
for name, v in V.items():
    L.append(f"| {name} | {v.get('arm')} | {v.get('in_class', 'n/a')} | {v.get('fidelity', 'n/a')} | {v['verdict']}{' (' + v['why'] + ')' if 'why' in v else ''} |")
L += ["", f"H holds: {S['H_holds']}", "", "## Baseline: share of entries with |RNE(2^12 n)| > 2,047", "",
      "| norm | layers | entries | over 2,047 | share | per-layer share median (min to max) | layers with any | max \\|q12\\| | at layer, prompt | >= 2^15 | >= 2^17 | >= 2^18 |",
      "|---|---|---|---|---|---|---|---|---|---|---|---|"]
for name in NORMS:
    b = B[name]; t = b["total"]; s = b["share_per_layer"]
    if not b["n_layers"]: continue
    L.append(f"| {name} | {b['n_layers']} | {t['n']:,} | {t['over']:,} | {100 * b['share_over_2047']:.2f}% | {100 * s['median']:.2f}% ({100 * s['min']:.2f}% to {100 * s['max']:.2f}%) | "
             f"{b['layers_with_any_over']} | {int(b['max_q12']):,} | {b['max_layer']}, {b['max_prompt']} | {t['ge15']:,} | {t['ge17']:,} | {t['ge18']:,} |")
L += ["", "## Arms: totals over the layers measured", "",
      "| arm | layers | layers passing the bar | r median per layer: median (min to max) | r max | worst layer | entries | out of class | clamped (a / m) | max \\|q\\| a / m | shifts | SiLU exits / hidden | max gw, u, h |",
      "|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
for arm, a in A.items():
    if not a["n_layers"]: continue
    t = a["totals"]; rm = a["r_median_over_layers"]
    L.append(f"| {arm} | {a['n_layers']} | {a['layers_pass']} | {f(rm['median'])} ({f(rm['min'])} to {f(rm['max'])}) | {f(a['r_max_over_layers'])} | {a['worst_layer']} | {t['n_entries']:,} | "
             f"{t['n_out_of_class']:,} | {t['n_clamped_a']:,} / {t['n_clamped_m']:,} | {int(t['max_qa']):,} / {int(t['max_qm']):,} | {t['shifts_min']} to {t['shifts_max']} | "
             f"{t['silu_exits']:,} / {t['n_hidden']:,} | {int(t['max_gw']):,}, {int(t['max_u']):,}, {int(t['max_h']):,} |")
L += ["", "## Per layer", "", "| layer | type | a: share over 2,047 | a: max | m: share over 2,047 | m: max | "
      + " | ".join(f"{a} r med / max" for a in A if A[a]["n_layers"]) + " |", "|---|---|---|---|---|---|" + "---|" * sum(1 for a in A if A[a]["n_layers"])]
bl = {n: {r["layer"]: r for r in B[n]["layers"]} for n in NORMS}
al = {a: {r["layer"]: r for r in A[a]["layers"]} for a in A}
for i in sorted(base):
    ra, rm_ = bl[NORMS[0]][i], bl[NORMS[1]][i]
    cells = []
    for a in A:
        if not A[a]["n_layers"]: continue
        x = al[a].get(i); cells.append("not run" if x is None else ("error" if x.get("error") else f"{f(x['r_median'])} / {f(x['r_max'])}{'' if x['passes'] else ' F'}"))
    L.append(f"| {i} | {'attn' if ra['type'] == 'full_attention' else 'delta'} | {100 * ra['share_over_2047']:.2f}% | {int(ra['max_q12']):,} | {100 * rm_['share_over_2047']:.2f}% | "
             f"{int(rm_['max_q12']):,} | " + " | ".join(cells) + " |")
L += ["", "F marks a layer that fails the registered bar (median over prompts of r <= 1e-3 and max <= 1e-2).", ""]
(R / "summary.md").write_text("\n".join(L))
print(json.dumps(dict(layer_set=layer_set, baseline_layers=len(base), arm_layers=len(arms), M=M, k_star=kstar, verdicts=V, H=S["H_holds"],
                      det=S["determinism"])))
