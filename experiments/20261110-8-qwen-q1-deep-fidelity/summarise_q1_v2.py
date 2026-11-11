#!/usr/bin/env python3
"""Derived summary v2 (PREREG Amendments, 2026-11-11). Reads the committed run files and writes NEW files
runs/summary-v2.json and runs/summary-v2.md; runs/summary.json / summary.md (v1) are left as committed.

Changes against v1 (summarise_q1.py), all from the two reviews of PR #88:
1. Spread: every distribution also gets the sample SD, sd = sqrt(sum (x - mean)^2 / (n - 1)) (numpy std, ddof = 1).
   It is the spread over the n measured pairs (or prompts, or positions) of ONE deterministic execution, not over
   repeated runs.
2. Classes under the PREREG text. For the X family the registered class is o in [-2^17, 2^17) (half-open). v1 used
   PR #74's summarise.bounds("X1"), o < 2^17 + 1 on max |o|, which admits o = +2^17. Here a row with max |o| == 2^17
   is decided by its signed range from runs/o-sign-recheck.jsonl (recheck_o_sign.py); every other bound is v1's.
   Both counts are reported (in_classes_v1, in_classes).
3. The registered best arm per target ("lowest median rel_y among arms inside their classes") is recomputed from the
   corrected counts. The lowest median over all arms regardless of classes is reported separately and labelled.
4. The abliterated end to end is reported as "partial, not finished (layers 17 to 45)", not "not run".
5. Decay buckets: slow-head sets are taken from v1's summary.json (computed there from the prep files with the
   PREREG definition), so v2 needs no scratch directory.
Post-hoc / exploratory items (not registered quantities) are put under the key "post_hoc" and marked in the markdown.
Usage: summarise_q1_v2.py   (no arguments)"""
import json, sys
from pathlib import Path
import numpy as np
HERE = Path(__file__).resolve().parent
R = HERE / "runs"
sys.path.insert(0, str(HERE.parent / "20261110-8-qwen-norm-scaling"))
import summarise as S0   # PR #74's class bounds, unchanged
EDGE = 2 ** 17
ARMS = json.load(open(HERE / "arms-q1.json"))
V1 = json.load(open(R / "summary.json"))
TARGETS = {"T16": "arms-T16.jsonl", "T20s": "arms-T20s.jsonl", "T20a": "arms-T20a.jsonl"}
SD_NOTE = "sample SD, denominator n - 1, over the n values of one deterministic execution (not repeated runs)"

def bounds_v1(arm):
    if arm.startswith("XS"):
        fs = ARMS[arm]["cfg"]["FS"]
        b = S0.bounds("X1"); b["S"] = 2 ** (fs + 7); b["M"] = 2 ** (fs + 7); return b
    if arm.startswith("C4"): return S0.bounds("C4")
    return S0.bounds("C0")

def stat(v):
    v = np.asarray(v, float)
    if not v.size: return dict(n=0)
    return dict(n=int(v.size), median=float(np.median(v)), min=float(v.min()), max=float(v.max()),
                sd=float(np.std(v, ddof=1)) if v.size > 1 else None)

def load_osign():
    f = R / "o-sign-recheck.jsonl"
    if not f.exists(): sys.exit("runs/o-sign-recheck.jsonl missing: run recheck_o_sign.py first")
    return {(r["target"], r["arm"], r["prompt"], r["head"]): r for r in map(json.loads, open(f))}

def main():
    osign = load_osign(); out = dict(version=2, sd_definition=SD_NOTE, targets={}, post_hoc={}); md = []
    md.append("# Q1 derived summary v2 (summarise_q1_v2.py)\n")
    md.append(f"SD = {SD_NOTE}. Classes: PREREG text, X-family o in [-2^17, 2^17) on the signed range (runs/o-sign-recheck.jsonl); "
              "`v1` = the PR #74 predicate used by summary.json (admits o = +2^17).\n")
    for tg, f in TARGETS.items():
        rows = [json.loads(l) for l in open(R / f)]
        slow = set(V1["targets"][tg]["slow_heads"])
        T = dict(n_slow=len(slow), slow_heads=sorted(slow), arms={})
        md.append(f"\n## {tg}; slow heads {len(slow)} of 48\n")
        md.append("| arm | n | err | rel_y median / min / max / SD | rel_S median / max / SD | in classes (v1) | layer rel_y median / SD (n=10) | resid frob median / SD | slow rel_y med / max / SD | fast rel_y med / max / SD | pass |")
        md.append("|---|---|---|---|---|---|---|---|---|---|---|")
        for arm in ARMS:
            rs = [r for r in rows if r["arm"] == arm and "error" not in r]; errs = [r for r in rows if r["arm"] == arm and "error" in r]
            bd = bounds_v1(arm)
            def in_v1(r): return all(r["max"].get(k, 0) < lim for k, lim in bd.items() if k in r["max"])
            out_pairs = []
            def in_text(r):
                if not in_v1(r): return False
                if arm.startswith("XS") and r["max"].get("o", 0) == EDGE:
                    k = (tg, arm, r["prompt"], r["head"])
                    if k not in osign: sys.exit(f"no signed recheck for {k}")
                    ok = osign[k]["in_prereg_class"]
                    if not ok: out_pairs.append(dict(prompt=r["prompt"], head=r["head"], o_max=osign[k]["o_max"], o_min=osign[k]["o_min"]))
                    return ok
                return True
            iv1 = int(sum(in_v1(r) for r in rs)); itx = int(sum(in_text(r) for r in rs))
            sy, sS = stat([r["rel_y"] for r in rs]), stat([r["rel_S"] for r in rs])
            lay = [r["layer"] for r in rs if "layer" in r]
            sl = [r for r in rs if r["head"] in slow]; fa = [r for r in rs if r["head"] not in slow]
            d = dict(n=len(rs), errors=len(errs), rel_y=sy, rel_S=sS, in_classes=itx, in_classes_v1=iv1, out_of_class_o_plus=out_pairs,
                     pairs_le_005=int(sum(r["rel_y"] <= 0.05 for r in rs)),
                     layer_rel_y=stat([l["rel_y"] for l in lay]), resid_frob=stat([l["resid"]["frob"] for l in lay]),
                     bf16_rel_y=stat([r["bf16_rel_y"] for r in rs]),
                     slow_rel_y=stat([r["rel_y"] for r in sl]), slow_rel_S=stat([r["rel_S"] for r in sl]),
                     fast_rel_y=stat([r["rel_y"] for r in fa]), fast_rel_S=stat([r["rel_S"] for r in fa]))
            d["pass"] = bool(len(rs) == 480 and not errs and itx == 480 and sy["median"] <= 0.01 and sy["max"] <= 0.05
                             and sS["median"] <= 0.01 and sS["max"] <= 0.05)
            d["slow_pass"] = bool(not errs and sl and d["slow_rel_y"]["median"] <= 0.01 and d["slow_rel_y"]["max"] <= 0.05
                                  and d["slow_rel_S"]["median"] <= 0.01 and d["slow_rel_S"]["max"] <= 0.05)
            T["arms"][arm] = d
            g = lambda s, k: "-" if not s.get("n") or s.get(k) is None else f"{s[k]:.3g}"
            md.append(f"| {arm} | {len(rs)} | {len(errs)} | {g(sy,'median')} / {g(sy,'min')} / {g(sy,'max')} / {g(sy,'sd')} | "
                      f"{g(sS,'median')} / {g(sS,'max')} / {g(sS,'sd')} | {itx} ({iv1}) | {g(d['layer_rel_y'],'median')} / {g(d['layer_rel_y'],'sd')} | "
                      f"{g(d['resid_frob'],'median')} / {g(d['resid_frob'],'sd')} | {g(d['slow_rel_y'],'median')} / {g(d['slow_rel_y'],'max')} / {g(d['slow_rel_y'],'sd')} | "
                      f"{g(d['fast_rel_y'],'median')} / {g(d['fast_rel_y'],'max')} / {g(d['fast_rel_y'],'sd')} | {'PASS' if d['pass'] else 'fail'} |")
        inc = {a: d for a, d in T["arms"].items() if d["n"] == 480 and not d["errors"] and d["in_classes"] == 480}
        best = min(inc, key=lambda a: inc[a]["rel_y"]["median"])
        low = min(T["arms"], key=lambda a: T["arms"][a]["rel_y"]["median"])
        T["best_arm_registered"] = dict(arm=best, rule="lowest median rel_y among arms with 480/480 pairs inside the PREREG classes (PREREG Acceptance threshold)",
                                        rel_y=T["arms"][best]["rel_y"], rel_S=T["arms"][best]["rel_S"])
        T["lowest_median_any_class"] = dict(arm=low, in_classes=T["arms"][low]["in_classes"], rel_y=T["arms"][low]["rel_y"],
                                            note="descriptive, not the registered pick when it is out of class")
        T["bf16_context_rel_y"] = stat([r["bf16_rel_y"] for r in rows if r["arm"] == "C0" and "error" not in r])
        md.append(f"\nRegistered best arm (in classes): **{best}** rel_y median {T['arms'][best]['rel_y']['median']:.3g}, max {T['arms'][best]['rel_y']['max']:.3g}. "
                  f"Lowest median over all arms: {low} ({T['arms'][low]['rel_y']['median']:.3g}, {T['arms'][low]['in_classes']}/480 in classes).")
        cls = {a: d["out_of_class_o_plus"] for a, d in T["arms"].items() if d["out_of_class_o_plus"]}
        md.append(f"Pairs with o = +2^17 (out of the PREREG class): {sum(len(v) for v in cls.values())}, " + "; ".join(f"{a} {[(p['prompt'], p['head']) for p in v]}" for a, v in cls.items()))
        # post hoc: pairs over 0.05, scope XS18 and XS20 only (as v1)
        ph = {}
        for arm in ("XS18", "XS20"):
            rs = sorted([r for r in rows if r["arm"] == arm and "error" not in r and r["rel_y"] > 0.05], key=lambda r: -r["rel_y"])
            ph[arm] = dict(count=len(rs), prompts=sorted({r["prompt"] for r in rs}), heads=sorted({r["head"] for r in rs}),
                           slow_heads=sorted({r["head"] for r in rs if r["head"] in slow}))
            md.append(f"POST HOC (not registered), {arm} pairs with rel_y > 0.05 (computed for XS18 and XS20 only): {len(rs)}, prompts {ph[arm]['prompts']}, heads {ph[arm]['heads']}")
        out["post_hoc"][f"over_005_{tg}"] = ph
        out["targets"][tg] = T
    fsr = {}
    for fs in (12, 14, 16, 18, 20):
        arm = f"XS{fs}"; ok = [T["arms"][arm]["slow_pass"] for T in out["targets"].values() if T["n_slow"]]
        fsr[arm] = bool(ok) and all(ok)
    out["slow_state_rule"] = fsr
    out["smallest_FS_slow"] = next((int(a[2:]) for a, v in fsr.items() if v), None)
    out["H1_XS18_all_targets"] = all(T["arms"]["XS18"]["pass"] for T in out["targets"].values())
    out["arms_passing"] = sum(d["pass"] for T in out["targets"].values() for d in T["arms"].values())
    out["cells"] = sum(len(T["arms"]) for T in out["targets"].values())
    u1 = [json.loads(l) for l in open(R / "u1-layer20.jsonl")]
    out["u1_layer20"] = dict(mix_diff_frob=stat([r["mix_diff_frob"] for r in u1]), resid_in_diff_frob=stat([r["resid_in_diff_frob"] for r in u1]),
                             note="descriptive size comparison (registered without threshold), not detection")
    e = json.load(open(R / "e2e-stock.json")); es = dict(sanity_pass=e.get("sanity_pass"), paths={})
    for path in ("INT", "BF16H"):
        ag, kl, mdv = [], [], []
        for pid, d in e["prompts"].items():
            if d[path] is None: continue
            ag += d[path]["top1_agree"]; kl += d[path]["kl"]; mdv += d[path]["maxdiff_over_std"]
        es["paths"][path] = dict(positions=len(ag), top1_agree=int(sum(ag)), kl=stat(kl), maxdiff_over_std=stat(mdv))
    out["e2e_stock"] = es
    dv = [json.loads(l) for l in open(R / "e2e-abl-divergence.jsonl")]
    out["e2e_abl"] = dict(status="partial, not finished", divergence_rows=len(dv),
                          note="stage E stopped after abl layer 45 of 63 (owning session lost); residual divergence only, no logits, no top-1, no KL")
    (R / "summary-v2.json").write_text(json.dumps(out, indent=1) + "\n")
    md.append(f"\nH1 (XS18 passes all targets): {out['H1_XS18_all_targets']}. Cells passing: {out['arms_passing']} of {out['cells']}. "
              f"Slow-state rule: {fsr}, smallest FS: {out['smallest_FS_slow']}.")
    k = es["paths"]["INT"]["kl"]; m = out["u1_layer20"]["mix_diff_frob"]
    md.append(f"\nStock e2e INT: top-1 {es['paths']['INT']['top1_agree']}/{es['paths']['INT']['positions']}, KL median {k['median']:.3g}, max {k['max']:.3g}, SD {k['sd']:.3g} nats (n = {k['n']} positions).")
    md.append(f"U1 layer 20 mixer difference over residual: median {m['median']:.4g}, min {m['min']:.4g}, max {m['max']:.4g}, SD {m['sd']:.4g} (n = {m['n']}).")
    md.append(f"Abliterated e2e: {out['e2e_abl']['status']} ({len(dv)} divergence rows, layers 17 to 45).")
    (R / "summary-v2.md").write_text("\n".join(md) + "\n")
    print("\n".join(md))

if __name__ == "__main__": main()
