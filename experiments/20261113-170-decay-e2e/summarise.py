#!/usr/bin/env python3
"""Verdicts per arm vs PREREG (PR #124's bar), the control check against PR #124's committed abl numbers, flips with
REF margins, per-prompt numbers, determinism, per-layer seconds, decay error. Writes runs/summary.json and summary.md.
If runs/e2e-abl.json is missing (run stopped before logits), every arm is KILLED and only per-layer progress is summarised.
Usage: summarise.py
"""
import json, math
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent; R = HERE / "runs"
P124 = HERE.parent / "20261111-8-qwen-e2e-agreement" / "runs" / "e2e-abl.json"
ARMS = ["XS18", "XS18+U4", "XS18+U3"]
N_POS = 1461; TOP1_MIN = math.ceil(0.99 * N_POS)
BAR = dict(top1_frac=0.99, kl_median=1e-4, kl_max=0.1)
P03 = "p03-repeat-word"

def jl(p): return [json.loads(l) for l in open(p)] if p.exists() else []

def main():
    div = jl(R / "divergence-abl.jsonl"); errs = jl(R / "errors-abl.jsonl"); dec = jl(R / "decay-err-abl.jsonl")
    out = dict(bar=BAR, n_positions=N_POS, layers_done=len(div), layer_seconds=[dict(layer=r["layer"], type=r["type"], s=r["seconds"]) for r in div],
               guard_errors=errs)
    out["det_bit_equal_all_layers"] = all(all(r["det_bit_equal"].values()) for r in div) if div else None
    # decay error actually used, per path: max over layers / prompts
    de = {}
    for r in dec:
        for p, d in r["max_abs_a_minus_float"].items():
            de.setdefault(p, []).append(max(d.values()))
    out["decay_abs_err_max"] = {p: dict(max=max(v), median_over_layers=float(np.median(v))) for p, v in de.items()}
    # final residual divergence per path / prompt
    if div:
        last = div[-1]; out["resid_rel_last_layer"] = {p: last.get(p) for p in ARMS}; out["last_layer"] = last["layer"]
    e = R / "e2e-abl.json"
    if not e.exists():
        out["verdicts"] = {a: "KILLED (logits not produced)" for a in ARMS}
        write(out); return
    E = json.load(open(e)); P = E["prompts"]
    out["sanity_pass"] = E["sanity_pass"]; out["logits_seconds"] = E["seconds"]
    erred = {(x["path"], x["prompt"]) for x in errs}
    cells = {}
    for a in ARMS:
        top1 = 0; kls = []; flips = []; perp = {}
        for pid, d in sorted(P.items()):
            pp = d["paths"].get(a)
            if pp is None or (a, pid) in erred:
                kls += [math.inf] * d["T"]; perp[pid] = dict(T=d["T"], top1=0, kl_median=math.inf, kl_max=math.inf, guard_error=True); continue
            ag = pp["top1_agree"]; k = pp["kl"]; top1 += sum(ag); kls += k
            for t, ok in enumerate(ag):
                if not ok: flips.append(dict(prompt=pid, pos=t, ref=d["ref_top1"][t], arm=pp["top1_path"][t], ref_margin=d["ref_margin"][t], kl=k[t]))
            perp[pid] = dict(T=d["T"], top1=int(sum(ag)), kl_median=float(np.median(k)), kl_max=float(max(k)),
                             maxdiff_over_std_median=float(np.median(pp["maxdiff_over_std"])))
        kv = np.array(kls); fin = kv[np.isfinite(kv)]
        c = dict(top1=int(top1), top1_frac=top1 / N_POS, kl_median=float(np.median(kv)), kl_p99=float(np.percentile(kv, 99)),
                 kl_max=float(kv.max()), kl_sd_finite=float(fin.std()) if fin.size else None, flips=flips, per_prompt=perp,
                 guard_error=any(v.get("guard_error") for v in perp.values()))
        c["pass"] = bool(not c["guard_error"] and c["top1"] >= TOP1_MIN and c["kl_median"] <= BAR["kl_median"] and c["kl_max"] <= BAR["kl_max"])
        cells[a] = c
    out["cells"] = cells
    # extra flips vs XS18 at REF margin > 0.01
    xf = {(f["prompt"], f["pos"]) for f in cells["XS18"]["flips"]}
    for a in ("XS18+U4", "XS18+U3"):
        cells[a]["extra_flips_vs_xs18_margin_gt_0.01"] = [f for f in cells[a]["flips"] if (f["prompt"], f["pos"]) not in xf and f["ref_margin"] > 0.01]
        cells[a]["extra_flips_vs_xs18_any"] = [f for f in cells[a]["flips"] if (f["prompt"], f["pos"]) not in xf]
    # determinism of logit metrics
    det = {}
    for p2, p1 in (("REF#2", None), ("XS18+U4#2", "XS18+U4")):
        for pid, d in P.items():
            q = d["paths"].get(p2)
            if q is None: continue
            if p1 is None: det[f"{p2}|{pid}"] = bool(max(abs(v) for v in q["kl"]) == 0.0 and all(q["top1_agree"]))
            else: det[f"{p2}|{pid}"] = bool(q == d["paths"][p1] or (q["kl"] == d["paths"][p1]["kl"] and q["top1_path"] == d["paths"][p1]["top1_path"]))
    out["det_logits"] = det
    # control vs PR #124
    C = json.load(open(P124))["prompts"]; ctl = dict(ref_top1_equal=True, xs18_top1_equal=True, max_kl_absdiff=0.0, positions=0)
    for pid, d in P.items():
        c = C[pid]; ctl["positions"] += d["T"]
        ctl["ref_top1_equal"] &= d["ref_top1"] == c["ref_top1"]
        ctl["xs18_top1_equal"] &= d["paths"]["XS18"]["top1_path"] == c["paths"]["XS18"]["top1_path"]
        ctl["max_kl_absdiff"] = max(ctl["max_kl_absdiff"], float(np.abs(np.array(d["paths"]["XS18"]["kl"]) - np.array(c["paths"]["XS18"]["kl"])).max()))
    ctl["reproduced"] = bool(ctl["ref_top1_equal"] and ctl["xs18_top1_equal"] and ctl["max_kl_absdiff"] <= 1e-9 and ctl["positions"] == N_POS)
    out["control"] = ctl
    v = {}
    for a in ARMS:
        if a != "XS18" and not ctl["reproduced"]: v[a] = "KILLED (control did not reproduce PR #124)"
        elif not E["sanity_pass"]: v[a] = "KILLED (forward sanity failed)"
        else: v[a] = "PASS" if cells[a]["pass"] else "FAIL"
    out["verdicts"] = v
    out["H_holds"] = bool(v["XS18+U4"] == "PASS" and not cells["XS18+U4"]["extra_flips_vs_xs18_margin_gt_0.01"])
    write(out)

def fmt(x): return "inf" if x == math.inf else f"{x:.3g}"

def write(out):
    (R / "summary.json").write_text(json.dumps(out, indent=1) + "\n")
    L = ["# summary (generated by summarise.py)", "", f"layers done: {out['layers_done']} of 64", ""]
    L += [f"- {a}: **{out['verdicts'][a]}**" for a in ARMS]
    if "cells" in out:
        L += ["", "| arm | top-1 | KL median | KL p99 | KL max | flips | verdict |", "|---|---|---|---|---|---|---|"]
        for a in ARMS:
            c = out["cells"][a]
            L.append(f"| {a} | {c['top1']} / {N_POS} | {fmt(c['kl_median'])} | {fmt(c['kl_p99'])} | {fmt(c['kl_max'])} | {len(c['flips'])} | {out['verdicts'][a]} |")
        L += ["", "Flips:"]
        for a in ARMS:
            for f in out["cells"][a]["flips"]:
                L.append(f"- {a}: {f['prompt']} pos {f['pos']}, REF {f['ref']} -> {f['arm']}, REF margin {f['ref_margin']:.4g}, KL {f['kl']:.3g}")
        L += ["", "| prompt | T | " + " | ".join(f"{a} top-1 / KL med / KL max" for a in ARMS) + " |", "|---|---|" + "---|" * len(ARMS)]
        for pid in sorted(out["cells"]["XS18"]["per_prompt"]):
            r = [out["cells"][a]["per_prompt"][pid] for a in ARMS]
            L.append(f"| {pid}{' (**p03**)' if pid == P03 else ''} | {r[0]['T']} | " + " | ".join(f"{x['top1']} / {fmt(x['kl_median'])} / {fmt(x['kl_max'])}" for x in r) + " |")
        L += ["", f"control: {json.dumps(out['control'])}", f"H holds: {out['H_holds']}"]
    (R / "summary.md").write_text("\n".join(L) + "\n")
    print("\n".join(L))

if __name__ == "__main__":
    main()
