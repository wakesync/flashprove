#!/usr/bin/env python3
"""Summarise the registered run (PREREG "Metric", "Acceptance threshold", validity gates). Light, no scratch needed.
Adapted from PR #202's summarise.py for the arms of this run.

Reads <runs>/e2e-abl.json, ranges-abl.jsonl, divergence-abl.jsonl, errors-abl.jsonl, progress.log.jsonl.
G1 compares REF top-1 with PR #173's committed experiments/20261112-132-int-mlp-e2e/runs-resume150b/runs/e2e-abl.json.
H-C / H-T ratio denominator: M31's committed KL median, experiments/20261114-201-mlp-stage/runs/summary.json
cells.M31.kl.median (PR #202). M31 and M31-S per-prompt values are cited from that file, descriptively.
Writes <runs>/summary.json and <runs>/summary.md. Usage: summarise.py [runs]
"""
import json, math, sys
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent
R = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE / "runs"
PR173 = HERE.parent / "20261112-132-int-mlp-e2e" / "runs-resume150b" / "runs"
PR202 = HERE.parent / "20261114-201-mlp-stage" / "runs" / "summary.json"
PROMPTS = json.load(open(HERE.parent / "20261111-8-qwen-e2e-agreement" / "prompts-e2e.json"))
ORDER = [p["id"] for p in PROMPTS["prompts"]]
ARMS = ["M31-C", "M31-T"]
DUP = "M31-C#2"
DET = ["p01-ordinary-short", "p09-multilingual"]
HYP = (("H-C", "M31-C"), ("H-T", "M31-T"))
TOP1_BAR, KLMED_BAR, KLMAX_BAR = 0.99, 1e-4, 0.1
CNT = ["n_silu_sat_lo", "n_silu_sat_hi", "n_h_ge_2e18", "n_h_ge_2e23", "n_m_over_2047", "n_gw_ge_2e18", "n_gw_ge_2e23",
       "n_u_ge_2e18", "n_u_ge_2e23", "n_acc_down_ge_ledger", "n_out_ge_2e31"]
MAXK = ["m", "gw", "u", "s", "h", "acc_down", "out"]


def jl(p): return [json.loads(l) for l in open(p)] if p.exists() else []
def sd(a): a = np.asarray(a, float); return float(a.std(ddof=1)) if a.size > 1 else None
def dist(a):
    a = np.asarray(a, float)
    return dict(n=int(a.size), median=float(np.median(a)), sd=sd(a), min=float(a.min()), max=float(a.max()),
                p99=float(np.quantile(a, 0.99, method="higher")))


def fmt(v, n=3):
    if v is None: return "-"
    if isinstance(v, bool): return str(v)
    if isinstance(v, float):
        if v == 0: return "0"
        if math.isinf(v): return "inf"
        return f"{v:.{n}g}"
    return str(v)


def main():
    B = json.load(open(PR202))
    M31_MED = B["cells"]["M31"]["kl"]["median"]
    S = dict(bars=dict(top1=TOP1_BAR, kl_median_nats=KLMED_BAR, kl_max_nats=KLMAX_BAR),
             m31_kl_median_committed=M31_MED, m31_source="experiments/20261114-201-mlp-stage/runs/summary.json cells.M31.kl.median (PR #202)")
    prog = jl(R / "progress.log.jsonl")
    dec = [r["decision"] for r in prog if "decision" in r]
    S["decision"] = dec[-1] if dec else None
    D = jl(R / "divergence-abl.jsonl"); RG = jl(R / "ranges-abl.jsonl"); errs = jl(R / "errors-abl.jsonl")
    S["errors"] = errs
    S["layers_done"] = [r["layer"] for r in D]
    S["layer_seconds"] = dist([r["seconds"] for r in D]) if D else None
    S["per_layer_seconds"] = {str(r["layer"]): r["seconds"] for r in D}
    S["det_resid_bit_equal_every_layer"] = bool(D) and all(all(r["det_bit_equal"].values()) for r in D)
    rng = {}
    for p in ARMS + [DUP]:
        per_layer = {}; tot = {c: 0 for c in CNT}; mx = {k: (-1.0, None, None) for k in MAXK}
        for r in RG:
            rows = r["paths"].get(p, {})
            per_layer[str(r["layer"])] = {c: sum(st[c] for st in rows.values()) for c in CNT}
            per_layer[str(r["layer"])].update({f"max_{k}": max((st[k] for st in rows.values()), default=None) for k in MAXK})
            for pid, st in rows.items():
                for c in CNT: tot[c] += st[c]
                for k in MAXK:
                    if st[k] > mx[k][0]: mx[k] = (st[k], r["layer"], pid)
        rng[p] = dict(totals=tot, silu_domain_exits=tot["n_silu_sat_lo"] + tot["n_silu_sat_hi"],
                      max={k: dict(value=v[0], log2=(math.log2(v[0]) if v[0] and v[0] > 0 else None), layer=v[1], prompt=v[2]) for k, v in mx.items()},
                      per_layer=per_layer)
    S["ranges"] = rng
    S["pr202_ranges_cited"] = {p: dict(silu_exits_lo=B["ranges"][p]["totals"]["n_silu_sat_lo"], silu_exits_hi=B["ranges"][p]["totals"]["n_silu_sat_hi"],
                                       h_ge_2e18=B["ranges"][p]["totals"]["n_h_ge_2e18"]) for p in ("M31", "M31-S") if p in B.get("ranges", {})}
    S["weight_exponents"] = {str(r["layer"]): {k: v["e"] for k, v in r["weights"].items()} for r in RG}
    if D:
        S["resid_rel_final"] = {p: D[-1].get(p) for p in ARMS}
        S["resid_rel_by_layer_median"] = {p: {str(r["layer"]): float(np.median([v for v in (r.get(p) or {}).values() if v is not None]))
                                              for r in D if r.get(p)} for p in ARMS}
    f = R / "e2e-abl.json"
    S["finished"] = f.exists()
    if f.exists():
        E = json.load(open(f)); P = E["prompts"]; order = [p for p in ORDER if p in P]
        S["prompts"] = order; S["n_positions"] = int(sum(P[p]["T"] for p in order))
        S["sanity_pass"] = E.get("sanity_pass"); S["logits_seconds"] = E.get("seconds")
        cells = {}
        for path in ARMS:
            ag, kl, flips, per, dead = [], [], [], {}, []
            for pid in order:
                m = P[pid]["paths"].get(path); T = P[pid]["T"]
                if m is None:
                    dead.append(pid); per[pid] = dict(T=T, dead=True); continue
                a = np.array(m["top1_agree"]); k = np.array(m["kl"])
                ag += list(a); kl += list(k)
                per[pid] = dict(T=T, agree=int(a.sum()), frac=float(a.mean()), kl=dist(k))
                for t in np.where(~a)[0]:
                    flips.append(dict(prompt=pid, pos=int(t), ref_top1=P[pid]["ref_top1"][t], path_top1=m["top1_path"][t],
                                      ref_margin=P[pid]["ref_margin"][t], kl=float(k[t])))
            ag = np.array(ag, bool); kl = np.array(kl)
            alive = [v for v in per.values() if not v.get("dead")]
            c = dict(n=int(ag.size), agree=int(ag.sum()), frac=float(ag.mean()) if ag.size else None,
                     kl=dist(kl) if kl.size else None, dead_prompts=dead, per_prompt=per, flips=flips,
                     flip_ref_margin=dist([x["ref_margin"] for x in flips]) if flips else None,
                     spread_over_prompts=dict(frac=dist([v["frac"] for v in alive]), kl_median=dist([v["kl"]["median"] for v in alive])) if alive else None)
            if c["kl"]:
                c["bar_descriptive"] = dict(top1=c["frac"] >= TOP1_BAR, kl_median=c["kl"]["median"] <= KLMED_BAR, kl_max=c["kl"]["max"] <= KLMAX_BAR)
            cells[path] = c
        S["cells"] = cells
        old = json.load(open(PR173 / "e2e-abl.json"))["prompts"]
        g1 = {pid: old[pid]["ref_top1"] == P[pid]["ref_top1"] for pid in order}
        eq = {pid: P[pid]["paths"].get("M31-C") is not None and P[pid]["paths"].get("M31-C") == P[pid]["paths"].get(DUP) for pid in DET if pid in P}
        g3 = not any(e["path"] in ARMS for e in errs)
        S["gates"] = dict(G1_ref_top1_equal_pr173=all(g1.values()), G1_per_prompt=g1,
                          G2_dup_bit_equal=bool(S["det_resid_bit_equal_every_layer"] and all(eq.values()) and len(eq) == len(DET)), G2_logits_per_prompt=eq,
                          G3_no_guard_error=g3)
        S["valid"] = bool(S["gates"]["G1_ref_top1_equal_pr173"] and S["gates"]["G2_dup_bit_equal"] and S["gates"]["G3_no_guard_error"])
        hyp = {}
        for h, p in HYP:
            ok = cells[p]["kl"] is not None and not cells[p]["dead_prompts"]
            ratio = cells[p]["kl"]["median"] / M31_MED if ok else None
            hyp[h] = dict(path=p, kl_median=cells[p]["kl"]["median"] if cells[p]["kl"] else None, m31_kl_median=M31_MED, ratio=ratio,
                          verdict=("comparison invalid" if not S["valid"] else ("HOLDS" if ratio is not None and ratio <= 0.5 else
                                                                               ("DOES NOT HOLD" if ratio is not None else "not evaluated"))))
        S["hypotheses"] = hyp
        hc, ht = hyp["H-C"]["verdict"], hyp["H-T"]["verdict"]
        reg = {("HOLDS", "DOES NOT HOLD"): "H-C only: the clip carries the token error; the step alone does not halve it",
               ("DOES NOT HOLD", "HOLDS"): "H-T only: the step carries it; the clip alone does not halve it",
               ("HOLDS", "HOLDS"): "both: each change alone at least halves it; neither is the sole carrier at this threshold",
               ("DOES NOT HOLD", "DOES NOT HOLD"): "neither: the step and the clip only matter together along the trajectory"}
        S["registered_outcome"] = reg.get((hc, ht), "not evaluated")
        if order == [p for p in ORDER]:
            S["pr202_cited_same_prompts"] = {p: dict(agree=B["cells"][p]["agree"], n=B["cells"][p]["n"], kl_median=B["cells"][p]["kl"]["median"],
                                                     kl_max=B["cells"][p]["kl"]["max"], per_prompt={pid: dict(agree=v.get("agree"), kl_median=v["kl"]["median"] if "kl" in v else None)
                                                                                                   for pid, v in B["cells"][p]["per_prompt"].items()})
                                             for p in ("M31", "M31-S")}
    (R / "summary.json").write_text(json.dumps(S, indent=1) + "\n")
    # ---- markdown
    L = ["# Summary: SiLU table step vs domain clip, abliterated layers 31-63 (measured, unreplicated)", ""]
    if S["decision"]: L += [f"Prompt set: {S['decision']['set']} ({S['decision']['n_tokens']} positions); timing probe t_lin {S['decision']['t_lin_s']} s, "
                            f"t_full {S['decision']['t_full_s']} s, projected (10 prompts) {S['decision']['projected_10_s']} s, available {S['decision']['available_s']} s.", ""]
    L.append(f"Layers done: {S['layers_done'][0] if D else '-'}..{S['layers_done'][-1] if D else '-'} ({len(S['layers_done'])}); logits finished: {S['finished']}; "
             f"{DUP} residual bit-equal every layer: {S['det_resid_bit_equal_every_layer']}; guard errors: {len(errs)}")
    if S.get("finished"):
        g = S["gates"]
        L += ["", f"Gates: G1 REF top-1 = PR #173 on every prompt: {g['G1_ref_top1_equal_pr173']}; G2 {DUP} bit-equal to M31-C (residual + logits): "
                  f"{g['G2_dup_bit_equal']}; G3 no guard error in M31-C/M31-T: {g['G3_no_guard_error']}. Valid: {S['valid']}. Sanity p01 Tokyo: {S['sanity_pass']}", ""]
        L += ["| path | n | top-1 agree | KL median | KL p99 | KL max | KL SD | flips | bar (descriptive) |", "|---|---|---|---|---|---|---|---|---|"]
        for p in ARMS:
            c = S["cells"][p]; k = c["kl"]; b = c.get("bar_descriptive", {})
            L.append(f"| {p} | {c['n']} | {c['agree']} ({c['frac']:.4f}) | {fmt(k['median'])} | {fmt(k['p99'])} | {fmt(k['max'])} | {fmt(k['sd'])} | "
                     f"{len(c['flips'])} | top1 {b.get('top1')}, KLmed {b.get('kl_median')}, KLmax {b.get('kl_max')} |")
        for p, v in S.get("pr202_cited_same_prompts", {}).items():
            L.append(f"| {p}, PR #202 (cited) | {v['n']} | {v['agree']} | {fmt(v['kl_median'])} | - | {fmt(v['kl_max'])} | - | - | - |")
        L += ["", "| hypothesis | path | KL median | M31 KL median (PR #202, committed) | ratio | threshold | verdict |", "|---|---|---|---|---|---|---|"]
        for h, v in S["hypotheses"].items():
            L.append(f"| {h} | {v['path']} | {fmt(v['kl_median'], 4)} | {fmt(v['m31_kl_median'], 4)} | {fmt(v['ratio'], 4)} | <= 0.5 | {v['verdict']} |")
        L += ["", f"Registered outcome: {S['registered_outcome']}."]
        L += ["", "| prompt | T | " + " | ".join(f"{p} agree | {p} KL med | {p} KL max" for p in ARMS) + " |", "|---|---|" + "---|" * (3 * len(ARMS))]
        for pid in S["prompts"]:
            cs = [S["cells"][p]["per_prompt"][pid] for p in ARMS]
            L.append(f"| {pid} | {cs[0]['T']} | " + " | ".join("dead | | " if c.get("dead") else f"{c['agree']} | {fmt(c['kl']['median'])} | {fmt(c['kl']['max'])}" for c in cs) + " |")
        for p in ARMS:
            fl = S["cells"][p]["flips"]; L += ["", f"{p} top-1 flips: {len(fl)}" + (f" (REF margin median {fmt(S['cells'][p]['flip_ref_margin']['median'])}, min {fmt(S['cells'][p]['flip_ref_margin']['min'])}, max {fmt(S['cells'][p]['flip_ref_margin']['max'])})" if fl else "")]
            for f_ in fl: L.append(f"- {f_['prompt']} pos {f_['pos']}: ref {f_['ref_top1']} -> {f_['path_top1']}, REF margin {fmt(f_['ref_margin'])}, KL {fmt(f_['kl'])}")
    L += ["", "## Range counters, layers done (totals over prompts and layers)", "",
          "| path | SiLU exits lo | SiLU exits hi | h >= 2^18 | h >= 2^23 | m > 2047 | gw >= 2^18 | u >= 2^18 | max h (log2) | max acc_down (log2) | max out (log2) |", "|---|---|---|---|---|---|---|---|---|---|---|"]
    for p in ARMS + [DUP]:
        t = rng[p]["totals"]; mx = rng[p]["max"]
        L.append(f"| {p} | {t['n_silu_sat_lo']} | {t['n_silu_sat_hi']} | {t['n_h_ge_2e18']} | {t['n_h_ge_2e23']} | {t['n_m_over_2047']} | {t['n_gw_ge_2e18']} | {t['n_u_ge_2e18']} | "
                 f"{fmt(mx['h']['log2'], 4)} | {fmt(mx['acc_down']['log2'], 4)} | {fmt(mx['out']['log2'], 4)} |")
    for p, v in S["pr202_ranges_cited"].items():
        L.append(f"| {p}, PR #202 (cited) | {v['silu_exits_lo']} | {v['silu_exits_hi']} | {v['h_ge_2e18']} | - | - | - | - | - | - | - |")
    L += ["", "(Domain exits are counted on each arm's own trajectory. M31-C replaces them by exact SiLU; M31-T holds them at the domain edge.)", "",
          "## Per layer: seconds, median residual rel L2 vs REF over prompts, domain exits (lo/hi) and h >= 2^18 per arm", "",
          "| layer | s | " + " | ".join(f"{p} rel | {p} exits lo/hi | {p} h>=2^18" for p in ARMS) + " |", "|---|---|" + "---|" * (3 * len(ARMS))]
    for r in D:
        k = str(r["layer"]); cells = []
        for p in ARMS:
            pl = rng[p]["per_layer"].get(k, {})
            cells.append(f"{fmt(S['resid_rel_by_layer_median'][p].get(k))} | {pl.get('n_silu_sat_lo', 0)}/{pl.get('n_silu_sat_hi', 0)} | {pl.get('n_h_ge_2e18', 0)}")
        L.append(f"| {k} | {r['seconds']} | " + " | ".join(cells) + " |")
    (R / "summary.md").write_text("\n".join(L) + "\n"); print("\n".join(L))


if __name__ == "__main__": main()
