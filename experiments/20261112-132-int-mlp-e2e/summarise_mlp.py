#!/usr/bin/env python3
"""Summarise the registered run (PREREG "Metric", "Acceptance threshold", range verdict). Light, no scratch needed.
Reads runs/e2e-{abl,stock}.json, runs/ranges-*.jsonl, runs/divergence-*.jsonl, runs/heads-*.jsonl, runs/errors-*.jsonl.
Also compares REF top-1 lists with PR #124's committed runs (post hoc consistency check, no bar).
Writes runs/summary.json and runs/summary.md. Usage: summarise_mlp.py [runs]"""
import json, math, sys
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent
R = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE / "runs"
PR124 = HERE.parent / "20261111-8-qwen-e2e-agreement"
PROMPTS = json.load(open(PR124 / "prompts-e2e.json"))
ORDER_ALL = [p["id"] for p in PROMPTS["prompts"]]
DET = ["p01-ordinary-short", "p04-repeat-punct", "p09-multilingual"]
TOP1_BAR, KLMED_BAR, KLMAX_BAR = 0.99, 1e-4, 0.1
NOTE = ("integer M3 MLP (DESIGN 5.5, r2) in every layer for FM, XM18; DeltaNet heads XS18 in XM18, float64 in REF and FM; "
        "in_proj, out_proj, attention, every RMSNorm (incl. the MLP pre-norm), final norm and lm_head float64; no proof")
BOUNDS = [  # (stat key, count key(s), bound text)
    ("m", ["n_m_over_2047"], "|m| <= 2,047 (DESIGN 3.2, A_PUB)"),
    ("gw", ["n_gw_ge_2e18", "n_gw_ge_2e23", "n_silu_sat_lo", "n_silu_sat_hi"], "honest < 2^18, rng < 2^23; SiLU domain [-2^15, 2^15)"),
    ("u", ["n_u_ge_2e18", "n_u_ge_2e23"], "honest < 2^18, rng < 2^23"),
    ("s", [], "|s| <= 32,741 (table image)"),
    ("h", ["n_h_ge_2e18", "n_h_ge_2e23"], "honest < 2^18, rng < 2^23"),
    ("acc_down", ["n_acc_down_ge_ledger"], "ledger 2^55.02 (bounds-r3 'M3a-MLP down (r2)'); float guard 2^53"),
    ("out", ["n_out_ge_2e31"], "|out| < 2^31 (DESIGN 3.2, OUT_PUB)"),
]


def sd(a): a = np.asarray(a, float); return float(a.std(ddof=1)) if a.size > 1 else None
def dist(a):
    a = np.asarray(a, float)
    return dict(n=int(a.size), median=float(np.median(a)), sd=sd(a), min=float(a.min()), max=float(a.max()),
                p99=float(np.quantile(a, 0.99, method="higher")))
def jl(path): return [json.loads(l) for l in open(path)] if path.exists() else []


def ranges(leg_files):
    rows = [r for f in leg_files for r in jl(f)]
    out = {}
    for path in ("XM18", "FM"):
        q = {}
        for key, cnts, txt in BOUNDS:
            best = (-1.0, None, None)
            tot = {c: 0 for c in cnts}; where = {c: set() for c in cnts}
            for r in rows:
                for pid, st in r["paths"].get(path, {}).items():
                    if st[key] > best[0]: best = (st[key], r["layer"], pid)
                    for c in cnts:
                        tot[c] += st[c]
                        if st[c]: where[c].add(r["layer"])
            q[key] = dict(max_abs=best[0], log2=(math.log2(best[0]) if best[0] > 0 else None), at_layer=best[1], at_prompt=best[2],
                          bound=txt, counts=tot, layers_with_events={c: sorted(v) for c, v in where.items()})
        # per-layer max of acc_down and out (for the table)
        q["per_layer_max"] = {str(r["layer"]) + ":" + r["leg"]: {k: max((st[k] for st in r["paths"].get(path, {}).values()), default=None)
                                                                 for k in ("m", "gw", "u", "h", "acc_down", "out")} for r in rows}
        out[path] = q
    w = {}
    for r in rows:
        w[f"{r['leg']}:{r['layer']}"] = {k: v for k, v in r["weights"].items()}
    es = [v["e"] for x in w.values() for v in x.values()]
    out["weights"] = dict(per_layer=w, e_min=min(es) if es else None, e_max=max(es) if es else None,
                          all_e_in_1_24=all(1 <= e <= 24 for e in es), all_w_in_class=all(v["w_in_class"] for x in w.values() for v in x.values()))
    n_events = 0
    for key, cnts, _ in BOUNDS:
        for c in cnts:
            if c in ("n_gw_ge_2e18", "n_u_ge_2e18", "n_h_ge_2e18"): continue   # honest contract: reported, not a class edge
            n_events += out["XM18"][key]["counts"][c]
    out["XM18_out_of_class_events"] = n_events
    out["verdict"] = "IN-BOUND" if n_events == 0 and out["weights"]["all_e_in_1_24"] and out["weights"]["all_w_in_class"] else "OUT-OF-BOUND"
    return out


def leg_summary(leg):
    f = R / f"e2e-{leg}.json"
    if not f.exists(): return dict(leg=leg, finished=False)
    E = json.load(open(f)); P = E["prompts"]; order = [p for p in ORDER_ALL if p in P]
    errs = jl(R / f"errors-{leg}.jsonl")
    out = dict(leg=leg, finished=True, prompts=order, sanity_pass=E["sanity_pass"], sanity_p01_last_top1=E["sanity_p01_last_top1"],
               errors=errs, cells={}, determinism={})
    for path in ("XM18", "FM"):
        ag, kl, md, per, flips, dead = [], [], [], {}, [], []
        for pid in order:
            m = P[pid]["paths"].get(path); T = P[pid]["T"]
            if m is None:
                dead.append(pid); ag += [False] * T; kl += [math.inf] * T; per[pid] = dict(T=T, dead=True); continue
            a = np.array(m["top1_agree"]); k = np.array(m["kl"]); d = np.array(m["maxdiff_over_std"])
            ag += list(a); kl += list(k); md += list(d)
            per[pid] = dict(T=T, agree=int(a.sum()), frac=float(a.mean()), kl=dist(k), maxdiff_over_std=dist(d))
            for t in np.where(~a)[0]:
                flips.append(dict(prompt=pid, pos=int(t), ref_top1=P[pid]["ref_top1"][t], path_top1=m["top1_path"][t],
                                  ref_margin=P[pid]["ref_margin"][t], kl=float(k[t])))
        ag = np.array(ag); kl = np.array(kl); fin = kl[np.isfinite(kl)]
        alive = [v for v in per.values() if not v.get("dead")]
        cell = dict(n=int(ag.size), agree=int(ag.sum()), frac=float(ag.mean()), kl_median=float(np.median(kl)), kl_max=float(kl.max()),
                    kl_p99=float(np.quantile(kl, 0.99, method="higher")), kl_sd=sd(fin) if fin.size else None,
                    maxdiff_over_std=dist(md) if md else None, dead_prompts=dead, per_prompt=per, flips=flips,
                    spread_over_prompts=dict(frac=dist([v["frac"] for v in alive]), kl_median=dist([v["kl"]["median"] for v in alive]),
                                             kl_max=dist([v["kl"]["max"] for v in alive])) if alive else None)
        cell["pass"] = dict(top1=cell["frac"] >= TOP1_BAR, kl_median=cell["kl_median"] <= KLMED_BAR, kl_max=cell["kl_max"] <= KLMAX_BAR,
                            no_guard_error=not dead)
        cell["PASS_bar"] = all(cell["pass"].values()) and E["sanity_pass"]
        out["cells"][path] = cell
    eq = []
    for pid in [p for p in DET if p in P]:
        m1 = P[pid]["paths"].get("XM18"); m2 = P[pid]["paths"].get("XM18#2"); eq.append(m1 is not None and m1 == m2)
    D = jl(R / f"divergence-{leg}.jsonl")
    resid = [all(v for v in r["det_bit_equal"].values()) for r in D]
    out["determinism"] = dict(logits_bit_equal=all(eq), resid_bit_equal_every_layer=all(resid), layers=len(resid))
    out["deterministic"] = all(eq) and all(resid)
    for c in out["cells"].values(): c["PASS_bar"] = c["PASS_bar"] and out["deterministic"]
    out["cells"]["FM"]["role"] = "descriptive, no bar"
    if D:
        out["divergence_final"] = {p: D[-1].get(p) for p in ("XM18", "FM")}
        out["divergence_by_layer"] = {p: [dict(layer=r["layer"], **{k: v for k, v in (r.get(p) or {}).items()}) for r in D] for p in ("XM18", "FM")}
    # consistency with PR #124's committed REF (post hoc, no bar)
    old = PR124 / "runs" / f"e2e-{leg}.json"
    if old.exists():
        O = json.load(open(old))["prompts"]
        out["ref_top1_equal_pr124"] = {pid: O[pid]["ref_top1"] == P[pid]["ref_top1"] for pid in order}
        out["pr124_XS18_same_prompts"] = dict(
            agree=int(sum(sum(O[pid]["paths"]["XS18"]["top1_agree"]) for pid in order)), n=int(sum(O[pid]["T"] for pid in order)),
            kl_median=float(np.median([v for pid in order for v in O[pid]["paths"]["XS18"]["kl"]])),
            kl_max=float(max(v for pid in order for v in O[pid]["paths"]["XS18"]["kl"])),
            source=f"experiments/20261111-8-qwen-e2e-agreement/runs/e2e-{leg}.json (PR #124, merged)")
    return out


def fmt(v, n=3):
    if v is None: return "-"
    if isinstance(v, float):
        if v == 0: return "0"
        if math.isinf(v): return "inf"
        return f"{v:.{n}g}"
    return str(v)


def main():
    legs = {leg: leg_summary(leg) for leg in ("abl", "stock")}
    rg = {leg: ranges([R / f"ranges-{leg}.jsonl"]) for leg in ("abl", "stock") if (R / f"ranges-{leg}.jsonl").exists()}
    for leg in ("abl", "stock"):
        D = jl(R / f"divergence-{leg}.jsonl")
        if D and not legs[leg].get("finished"):
            legs[leg]["layers_done"] = [r["layer"] for r in D]
            legs[leg]["divergence_by_layer"] = {p: [dict(layer=r["layer"], **{k: v for k, v in (r.get(p) or {}).items()}) for r in D] for p in ("XM18", "FM")}
            legs[leg]["det_bit_equal_every_layer"] = all(all(r["det_bit_equal"].values()) for r in D)
    S = dict(note=NOTE, bars=dict(top1=TOP1_BAR, kl_median_nats=KLMED_BAR, kl_max_nats=KLMAX_BAR), legs=legs, ranges=rg)
    (R / "summary.json").write_text(json.dumps(S, indent=1) + "\n")
    L = [f"# Summary ({NOTE})", "", f"Bars: top-1 >= {TOP1_BAR:.0%}, KL median <= {KLMED_BAR} nats, KL max <= {KLMAX_BAR} nats, no guard error.", ""]
    for leg in ("abl", "stock"):
        s = legs[leg]; L.append(f"## {leg}")
        if not s.get("finished"):
            L += ["logits not finished" + (f"; layers done {s['layers_done'][0]}..{s['layers_done'][-1]}; XM18#2 bit-equal every layer: {s['det_bit_equal_every_layer']}" if s.get("layers_done") else ""), ""]
            if s.get("layers_done"):
                L += ["Residual relative L2 vs REF after the last layer done, per prompt:", "", "| prompt | XM18 | FM |", "|---|---|---|"]
                lx = s["divergence_by_layer"]["XM18"][-1]; lf = s["divergence_by_layer"]["FM"][-1]
                for pid in ORDER_ALL:
                    if pid in lx: L.append(f"| {pid} | {fmt(lx.get(pid))} | {fmt(lf.get(pid))} |")
                L.append("")
        else:
            L.append(f"prompts {len(s['prompts'])}; sanity p01 -> {s['sanity_p01_last_top1']} pass={s['sanity_pass']}; deterministic={s['deterministic']}; errors={len(s['errors'])}")
            L += ["", "| path | n | top-1 agree | KL median | KL p99 | KL max | KL SD | maxdiff/std median (max) | bar |", "|---|---|---|---|---|---|---|---|---|"]
            for p in ("XM18", "FM"):
                c = s["cells"][p]; md = c["maxdiff_over_std"]
                L.append(f"| {p} | {c['n']} | {c['agree']} ({c['frac']:.4f}) | {fmt(c['kl_median'])} | {fmt(c['kl_p99'])} | {fmt(c['kl_max'])} | "
                         f"{fmt(c['kl_sd'])} | {fmt(md['median']) if md else '-'} ({fmt(md['max']) if md else '-'}) | "
                         f"{c['PASS_bar'] if p == 'XM18' else 'descriptive ' + str(c['PASS_bar'])} |")
            if "pr124_XS18_same_prompts" in s:
                x = s["pr124_XS18_same_prompts"]
                L.append(f"| XS18 only (PR #124 committed run, same prompts) | {x['n']} | {x['agree']} | {fmt(x['kl_median'])} | - | {fmt(x['kl_max'])} | - | - | cited |")
                L.append(""); L.append(f"REF top-1 equal to PR #124's committed REF on every prompt: {all(s['ref_top1_equal_pr124'].values())}")
            L += ["", "| prompt | T | XM18 agree | XM18 KL med | XM18 KL max | FM agree | FM KL med | FM KL max | XM18 resid rel (final) |", "|---|---|---|---|---|---|---|---|---|"]
            for pid in s["prompts"]:
                a = s["cells"]["XM18"]["per_prompt"][pid]; b = s["cells"]["FM"]["per_prompt"][pid]
                dv = (s.get("divergence_final") or {}).get("XM18") or {}
                if a.get("dead") or b.get("dead"): L.append(f"| {pid} | {a['T']} | dead? | | | | | | |"); continue
                L.append(f"| {pid} | {a['T']} | {a['agree']} | {fmt(a['kl']['median'])} | {fmt(a['kl']['max'])} | {b['agree']} | {fmt(b['kl']['median'])} | "
                         f"{fmt(b['kl']['max'])} | {fmt(dv.get(pid))} |")
            for p in ("XM18", "FM"):
                fl = s["cells"][p]["flips"]; L.append(""); L.append(f"{p} top-1 flips: {len(fl)}")
                for f in fl[:40]: L.append(f"- {f['prompt']} pos {f['pos']}: ref {f['ref_top1']} -> {f['path_top1']}, ref margin {fmt(f['ref_margin'])}, KL {fmt(f['kl'])}")
                if len(fl) > 40: L.append(f"- ... {len(fl) - 40} more in summary.json")
        if leg in rg and rg[leg]["XM18"]["m"]["max_abs"] >= 0:
            r = rg[leg]; L += ["", f"### ranges ({leg} leg, layers in ranges-{leg}.jsonl); verdict {r['verdict']}, XM18 class events {r['XM18_out_of_class_events']}",
                               f"weight exponents {r['weights']['e_min']}..{r['weights']['e_max']}, all in 1..24: {r['weights']['all_e_in_1_24']}, all |W| <= 4095: {r['weights']['all_w_in_class']}",
                               "", "| path | quantity | max abs | log2 | layer | prompt | bound | counts |", "|---|---|---|---|---|---|---|---|"]
            for p in ("XM18", "FM"):
                for key, _, _ in BOUNDS:
                    q = r[p][key]
                    L.append(f"| {p} | {key} | {fmt(q['max_abs'], 6)} | {fmt(q['log2'], 4)} | {q['at_layer']} | {q['at_prompt']} | {q['bound']} | "
                             + ", ".join(f"{c} {v} (layers {q['layers_with_events'][c][:10]})" for c, v in q["counts"].items()) + " |")
        L.append("")
    (R / "summary.md").write_text("\n".join(L) + "\n"); print("\n".join(L))


if __name__ == "__main__": main()
