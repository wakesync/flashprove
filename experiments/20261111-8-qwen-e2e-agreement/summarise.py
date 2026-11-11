#!/usr/bin/env python3
"""Summarise the registered run (PREREG "Metric", "Acceptance threshold"). Light, no scratch needed.
Reads runs/e2e-{abl,stock}.json, runs/heads-{abl,stock}.jsonl, runs/divergence-{abl,stock}.jsonl, runs/errors-*.jsonl.
Writes runs/summary.json and runs/summary.md. Usage: summarise.py [runs]"""
import json, math, sys
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent
R = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE / "runs"
PROMPTS = json.load(open(HERE / "prompts-e2e.json"))
ORDER = [p["id"] for p in PROMPTS["prompts"]]
TOP1_BAR, KLMED_BAR, KLMAX_BAR = 0.99, 1e-4, 0.1
NOTE = ("only the DeltaNet head computation is lowered; in_proj, out_proj, full attention, MLP, norms, final norm and "
        "lm_head are float64; no proof; arms are numerical lowerings, not sound relations")

def sd(a): a = np.asarray(a, float); return float(a.std(ddof=1)) if a.size > 1 else None
def dist(a):
    a = np.asarray(a, float)
    return dict(n=int(a.size), median=float(np.median(a)), sd=sd(a), min=float(a.min()), max=float(a.max()),
                p99=float(np.quantile(a, 0.99, method="higher")))

def jl(path):
    return [json.loads(l) for l in open(path)] if path.exists() else []

def leg_summary(leg):
    f = R / f"e2e-{leg}.json"
    if not f.exists(): return dict(leg=leg, finished=False)
    E = json.load(open(f)); P = E["prompts"]
    errs = jl(R / f"errors-{leg}.jsonl")
    out = dict(leg=leg, finished=True, checkpoint=E["checkpoint"], sanity_pass=E["sanity_pass"],
               sanity_p01_last_top1=E["sanity_p01_last_top1"], errors=errs, cells={}, context={}, determinism={})
    for path in ("XS18", "XS20", "BF16H"):
        ids = [pid for pid in ORDER if path in P[pid]["paths"]] if path == "BF16H" else ORDER
        ag, kl, md, per, flips = [], [], [], {}, []
        dead = []
        for pid in ids:
            m = P[pid]["paths"].get(path)
            T = P[pid]["T"]
            if m is None:   # guard error: every position disagrees, KL = inf (PREREG)
                dead.append(pid); ag += [False] * T; kl += [math.inf] * T
                per[pid] = dict(T=T, dead=True); continue
            a = np.array(m["top1_agree"]); k = np.array(m["kl"]); d = np.array(m["maxdiff_over_std"])
            ag += list(a); kl += list(k); md += list(d)
            per[pid] = dict(T=T, agree=int(a.sum()), frac=float(a.mean()), kl=dist(k), maxdiff_over_std=dist(d))
            for t in np.where(~a)[0]:
                flips.append(dict(prompt=pid, pos=int(t), ref_top1=P[pid]["ref_top1"][t], path_top1=m["top1_path"][t],
                                  ref_margin=P[pid]["ref_margin"][t], kl=float(k[t])))
        ag = np.array(ag); kl = np.array(kl)
        fin = kl[np.isfinite(kl)]
        cell = dict(n=int(ag.size), agree=int(ag.sum()), frac=float(ag.mean()), kl_median=float(np.median(kl)),
                    kl_max=float(kl.max()), kl_p99=float(np.quantile(kl, 0.99, method="higher")), kl_sd=sd(fin) if fin.size else None,
                    kl_min=float(kl.min()), maxdiff_over_std=dist(md) if md else None, dead_prompts=dead,
                    per_prompt=per, flips=flips,
                    spread_over_prompts=dict(frac=dist([v["frac"] for v in per.values() if not v.get("dead")]),
                                             kl_median=dist([v["kl"]["median"] for v in per.values() if not v.get("dead")]),
                                             kl_max=dist([v["kl"]["max"] for v in per.values() if not v.get("dead")])))
        if path == "BF16H":
            out["context"][path] = cell
        else:
            cell["pass"] = dict(top1=cell["frac"] >= TOP1_BAR, kl_median=cell["kl_median"] <= KLMED_BAR,
                                kl_max=cell["kl_max"] <= KLMAX_BAR, no_guard_error=not dead)
            cell["PASS"] = all(cell["pass"].values()) and E["sanity_pass"]
            out["cells"][path] = cell
    # determinism: logit metrics and per-layer residuals bit-identical
    for p2, p1 in (("REF#2", "REF"), ("XS18#2", "XS18")):
        logit_eq = []
        for pid in PROMPTS["determinism_subset"]:
            m2 = P[pid]["paths"].get(p2)
            if p1 == "REF":
                logit_eq.append(m2 is not None and all(v == 0.0 for v in m2["kl"]) and all(m2["top1_agree"])
                                and all(v == 0.0 for v in m2["maxdiff_over_std"]))
            else:
                m1 = P[pid]["paths"].get(p1)
                logit_eq.append(m1 is not None and m2 is not None and m1 == m2)
        resid = [all(r["det_bit_equal"].get(f"{p2}|{pid}", False) for pid in PROMPTS["determinism_subset"])
                 for r in jl(R / f"divergence-{leg}.jsonl")]
        out["determinism"][p2] = dict(logits_bit_equal=all(logit_eq), resid_bit_equal_every_layer=all(resid), layers=len(resid))
    det_ok = all(v["logits_bit_equal"] and v["resid_bit_equal_every_layer"] for v in out["determinism"].values())
    out["deterministic"] = det_ok
    for c in out["cells"].values(): c["PASS"] = c["PASS"] and det_ok
    # descriptive: closed-loop per-head local error, where the > 0.05 heads sit
    H = jl(R / f"heads-{leg}.jsonl"); loc = {}
    for path in ("XS18", "XS20"):
        d = {}
        for pid in ORDER:
            rows = [r for r in H if r["path"] == path and r["prompt"] == pid]
            allv = np.array([v for r in rows for v in r["rel_y"]])
            over = [(r["layer"], h, v) for r in rows for h, v in enumerate(r["rel_y"]) if v > 0.05]
            d[pid] = dict(pairs=int(allv.size), median=float(np.median(allv)) if allv.size else None,
                          max=float(allv.max()) if allv.size else None, over_0p05=len(over),
                          layers_over=sorted({l for l, _, _ in over}), n_heads_over=len({(l, h) for l, h, _ in over}),
                          worst=sorted(over, key=lambda x: -x[2])[:5])
        loc[path] = d
    out["heads_local"] = loc
    out["divergence_final"] = {}
    D = jl(R / f"divergence-{leg}.jsonl")
    if D:
        last = D[-1]
        out["divergence_final"] = {p: last.get(p) for p in ("XS18", "XS20", "BF16H")}
    return out

def fmt(v, n=3):
    if v is None: return "-"
    if isinstance(v, float):
        if v == 0: return "0"
        if math.isinf(v): return "inf"
        return f"{v:.{n}g}"
    return str(v)

def main():
    S = dict(note=NOTE, bars=dict(top1=TOP1_BAR, kl_median_nats=KLMED_BAR, kl_max_nats=KLMAX_BAR),
             legs={leg: leg_summary(leg) for leg in ("abl", "stock")})
    H = {}
    for arm, h in (("XS18", "H1"), ("XS20", "H2")):
        cells = [S["legs"][l]["cells"].get(arm) if S["legs"][l].get("finished") else None for l in ("stock", "abl")]
        H[h] = None if any(c is None for c in cells) else all(c["PASS"] for c in cells)
    S["hypotheses"] = H
    (R / "summary.json").write_text(json.dumps(S, indent=1) + "\n")
    L = [f"# Summary ({NOTE})", "", f"Bars: top-1 >= {TOP1_BAR:.0%}, KL median <= {KLMED_BAR} nats, KL max <= {KLMAX_BAR} nats, no guard error.",
         f"H1 (XS18 both): {H['H1']} | H2 (XS20 both): {H['H2']}", ""]
    for leg in ("stock", "abl"):
        s = S["legs"][leg]
        L.append(f"## {leg}")
        if not s.get("finished"): L += ["not finished", ""]; continue
        L.append(f"sanity p01 -> {s['sanity_p01_last_top1']} pass={s['sanity_pass']}; deterministic={s['deterministic']}; errors={len(s['errors'])}")
        L.append(""); L.append("| path | n | top-1 agree | KL median | KL p99 | KL max | KL SD | maxdiff/std median (max) | pass |")
        L.append("|---|---|---|---|---|---|---|---|---|")
        for p in ("XS18", "XS20", "BF16H"):
            c = s["cells"].get(p) or s["context"].get(p)
            md = c["maxdiff_over_std"]
            L.append(f"| {p} | {c['n']} | {c['agree']} ({c['frac']:.4f}) | {fmt(c['kl_median'])} | {fmt(c['kl_p99'])} | {fmt(c['kl_max'])} | "
                     f"{fmt(c['kl_sd'])} | {fmt(md['median']) if md else '-'} ({fmt(md['max']) if md else '-'}) | "
                     f"{c.get('PASS', 'context only')} |")
        L.append(""); L.append("Per prompt (top-1 agree / T, KL median, KL max; local per-head rel_y > 0.05 count [layers]):"); L.append("")
        L.append("| prompt | T | XS18 agree | XS18 KL med | XS18 KL max | XS18 heads>0.05 | XS20 agree | XS20 KL med | XS20 KL max | XS20 heads>0.05 | BF16H KL max |")
        L.append("|---|---|---|---|---|---|---|---|---|---|---|")
        for pid in ORDER:
            row = [pid]
            for p in ("XS18", "XS20"):
                pp = s["cells"][p]["per_prompt"][pid]; hl = s["heads_local"][p][pid]
                if pp.get("dead"): row += ["dead", "-", "-", "-"]; continue
                if p == "XS18": row.insert(1, str(pp["T"]))
                row += [f"{pp['agree']}", fmt(pp["kl"]["median"]), fmt(pp["kl"]["max"]), f"{hl['over_0p05']} {hl['layers_over'][:8]}"]
            b = s["context"]["BF16H"]["per_prompt"].get(pid)
            row.append(fmt(b["kl"]["max"]) if b and not b.get("dead") else "-")
            L.append("| " + " | ".join(row) + " |")
        for p in ("XS18", "XS20"):
            fl = s["cells"][p]["flips"]
            L.append(""); L.append(f"{p} top-1 flips: {len(fl)}")
            for f in fl: L.append(f"- {f['prompt']} pos {f['pos']}: ref {f['ref_top1']} -> {f['path_top1']}, ref margin {fmt(f['ref_margin'])}, KL {fmt(f['kl'])}")
        L.append("")
    (R / "summary.md").write_text("\n".join(L) + "\n"); print("\n".join(L))

if __name__ == "__main__": main()
