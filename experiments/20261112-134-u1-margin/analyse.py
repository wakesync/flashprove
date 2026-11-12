#!/usr/bin/env python3
"""Validity gates and D vs E analysis (PREREG.md + A-1). Light, no weights.
Reads runs/d-per-position.json (this lane), runs/manifest-{stock,abl}.json (this lane), and PR #124's committed
runs/e2e-{stock,abl}.json and runs/manifest-{stock,abl}.json. Writes runs/analysis.json and runs/analysis.md."""
import json, math, sys
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent; R = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE / "runs"
P124 = HERE.parent / "20261111-8-qwen-e2e-agreement" / "runs"
TOKYO = 25358

def q(a, p): return float(np.percentile(a, p)) if len(a) else None

def main():
    d = json.load(open(R / "d-per-position.json"))["prompts"]
    es = json.load(open(P124 / "e2e-stock.json"))["prompts"]; ea = json.load(open(P124 / "e2e-abl.json"))["prompts"]
    out = dict(gates={}, prompts={}, pooled={})
    # gate (a)
    p01 = d.get("p01-ordinary-short")
    out["gates"]["a_tokyo"] = None if p01 is None else bool(p01["stock_top1"][-1] == TOKYO and p01["abl_top1"][-1] == TOKYO)
    # gate (b): reproduce PR #124's REF
    bad = []; mmax = 0.0
    for pid, r in d.items():
        for leg, src, top, mar in (("stock", es, "stock_top1", "stock_margin"), ("abl", ea, "abl_top1", "abl_margin")):
            c = src[pid]
            for t in range(r["T"]):
                dm = abs(r[mar][t] - c["ref_margin"][t]); mmax = max(mmax, dm)
                if (c["ref_margin"][t] > 1e-6 and r[top][t] != c["ref_top1"][t]) or dm > 1e-6:
                    bad.append(dict(prompt=pid, leg=leg, t=t, mine=r[top][t], pr124=c["ref_top1"][t], dmargin=dm))
    out["gates"]["b_reproduce"] = dict(ok=not bad, max_abs_margin_diff=mmax, failures=bad[:50], n_fail=len(bad))
    # gate (c): sha256 vs PR #124 manifests
    cm = {}
    for ck in ("stock", "abl"):
        m = json.load(open(R / f"manifest-{ck}.json"))["tensors"]; o = json.load(open(P124 / f"manifest-{ck}.json"))["tensors"]
        both = sorted(set(m) & set(o)); cm[ck] = dict(compared=len(both), mismatch=[n for n in both if m[n]["sha256"] != o[n]["sha256"]],
                                                      not_in_pr124=sorted(set(m) - set(o)))
    out["gates"]["c_manifest"] = dict(ok=all(not v["mismatch"] for v in cm.values()), **cm)
    valid = bool(out["gates"]["a_tokyo"] is not False and out["gates"]["b_reproduce"]["ok"] and out["gates"]["c_manifest"]["ok"])
    out["gates"]["all_ok"] = valid
    # D vs E
    allr = {"XS18": [], "XS20": []}; allD = []; allE = []; rows = []; flips = []
    for pid, r in d.items():
        D = np.array(r["D_kl_stock_abl"])
        pr = dict(T=r["T"], D_median=float(np.median(D)), D_max=float(D.max()), D_min=float(D.min()),
                  top1_differ=int(sum(a != b for a, b in zip(r["stock_top1"], r["abl_top1"]))),
                  top1_differ_pr124=int(sum(a != b for a, b in zip(es[pid]["ref_top1"], ea[pid]["ref_top1"]))),
                  differ_positions=[dict(t=t, stock=r["stock_top1"][t], abl=r["abl_top1"][t], stock_margin=r["stock_margin"][t], D=r["D_kl_stock_abl"][t])
                                    for t in range(r["T"]) if r["stock_top1"][t] != r["abl_top1"][t]])
        for arm in ("XS18", "XS20"):
            Es = es[pid]["paths"][arm]; Ea = ea[pid]["paths"][arm]
            Ev = np.maximum(np.array(Es["kl"]), np.array(Ea["kl"]))
            rr = np.where(Ev > 0, D / np.where(Ev > 0, Ev, 1), np.inf)
            allr[arm] += list(rr)
            lr = np.log10(rr[np.isfinite(rr)])
            pr[arm] = dict(E_median=float(np.median(Ev)), E_max=float(Ev.max()), share_gt10=float((rr > 10).mean()), share_gt100=float((rr > 100).mean()),
                           log10r_median=q(lr, 50), log10r_sd=float(lr.std()) if len(lr) else None, log10r_min=float(lr.min()) if len(lr) else None,
                           log10r_max=float(lr.max()) if len(lr) else None, sumD_over_sumE=float(D.sum() / Ev.sum()), n_E_nonpos=int((Ev <= 0).sum()))
            if arm == "XS18": allE += list(Ev)
            for leg, src in (("stock", es), ("abl", ea)):
                for t, ok in enumerate(src[pid]["paths"][arm]["top1_agree"]):
                    if not ok: flips.append(dict(prompt=pid, leg=leg, arm=arm, t=t, D=float(D[t]), E=float(Ev[t]), r=float(rr[t])))
        allD += list(D); out["prompts"][pid] = pr
    for arm in ("XS18", "XS20"):
        rr = np.array(allr[arm]); lr = np.log10(rr[np.isfinite(rr)])
        out["pooled"][arm] = dict(n=len(rr), share_gt10=float((rr > 10).mean()), share_gt100=float((rr > 100).mean()),
                                  log10r=dict(median=q(lr, 50), sd=float(lr.std()), min=float(lr.min()), max=float(lr.max()),
                                              p1=q(lr, 1), p10=q(lr, 10), p90=q(lr, 90)),
                                  prompts_share10_ge_090=sum(1 for p in out["prompts"].values() if p[arm]["share_gt10"] >= 0.90))
    out["pooled"]["D"] = dict(n=len(allD), median=float(np.median(allD)), max=float(max(allD)), min=float(min(allD)), p10=q(allD, 10), p90=q(allD, 90))
    out["pooled"]["E_XS18"] = dict(median=float(np.median(allE)), max=float(max(allE)))
    out["pooled"]["top1_differ"] = sum(p["top1_differ"] for p in out["prompts"].values())
    out["pooled"]["top1_differ_pr124_same_prompts"] = sum(p["top1_differ_pr124"] for p in out["prompts"].values())
    out["integer_flip_positions"] = flips
    # verdict (XS18 primary)
    P = out["pooled"]["XS18"]; n = len(out["prompts"]); need = math.ceil(0.8 * n)
    c1, c2, c3 = P["share_gt10"] >= 0.95, P["share_gt100"] >= 0.50, P["prompts_share10_ge_090"] >= need
    if not valid: v = "KILLED (validity gate)"
    elif c1 and c2 and c3: v = "PASS"
    elif P["share_gt10"] < 0.50: v = "FAIL (negative in the issue's sense)"
    else: v = "FAIL (mixed)"
    out["verdict"] = dict(verdict=v, c1=bool(c1), c2=bool(c2), c3=bool(c3), prompts_needed=need, prompts_run=n,
                          subset=n < 10)
    (R / "analysis.json").write_text(json.dumps(out, indent=1) + "\n")
    print(json.dumps(dict(verdict=out["verdict"], gates={k: (v if not isinstance(v, dict) else v.get("ok")) for k, v in out["gates"].items()},
                          pooled=out["pooled"]), indent=1))
    for pid, p in out["prompts"].items():
        print(pid, p["T"], "D med %.3g max %.3g" % (p["D_median"], p["D_max"]), "XS18 >10 %.3f >100 %.3f" % (p["XS18"]["share_gt10"], p["XS18"]["share_gt100"]),
              "top1diff", p["top1_differ"], "(pr124", p["top1_differ_pr124"], ")")

if __name__ == "__main__":
    main()
