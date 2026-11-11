#!/usr/bin/env python3
"""Summarise the Q1 run (PREREG.md): per target and arm, rel_y / rel_S stats, pass vs the A2 bar, pairs in the stated
honest classes, slow / fast decay buckets, and the U1 reading; the end-to-end tables. Writes runs/summary.json and
prints markdown. Decay per head is computed from the prep files (float in_proj outputs) in <scratch>.
Usage: summarise_q1.py <scratch>"""
import json, math, sys
from pathlib import Path
import numpy as np
HERE = Path(__file__).resolve().parent
R = HERE / "runs"
sys.path.insert(0, str(HERE.parent / "20261110-8-qwen-norm-scaling"))
import summarise as S0   # PR #74's stated-class predicate, unchanged
B18 = 2 ** 18
TARGETS = {"T16": ("arms-T16.jsonl", "prep-L16", "stock-L16"), "T20s": ("arms-T20s.jsonl", "prep-L20", "stock-L20"),
           "T20a": ("arms-T20a.jsonl", "prep-abl-L20", "abl-L20")}
ARMS = json.load(open(HERE / "arms-q1.json"))

def bounds(arm):
    if arm.startswith("XS"):
        fs = ARMS[arm]["cfg"]["FS"]
        b = S0.bounds("X1"); b["S"] = 2 ** (fs + 7); b["M"] = 2 ** (fs + 7); return b
    if arm.startswith("C4"): return S0.bounds("C4")
    return S0.bounds("C0")

def stat(v):
    v = np.asarray(v, float)
    return dict(n=int(v.size), median=float(np.median(v)), min=float(v.min()), max=float(v.max())) if v.size else dict(n=0)

def passes(s_y, s_S, err, inb, n):
    return bool(n == 480 and not err and inb == 480 and s_y["median"] <= 0.01 and s_y["max"] <= 0.05 and s_S["median"] <= 0.01 and s_S["max"] <= 0.05)

def decay(scratch, prepdir, label, pids):
    """d_h = median over prompts of median over tokens of 1 - a (float64), PREREG definition."""
    per = []
    for pid in pids:
        d = np.load(Path(scratch) / prepdir / f"prep-{label}-{pid}.npz")
        a = np.exp(-d["A"][None, :] * np.logaddexp(0.0, d["ar"] + d["dtb"][None, :]))
        per.append(np.median(1.0 - a, axis=0))
    return np.median(np.stack(per), axis=0)

def main():
    scratch = sys.argv[1]; out = dict(targets={}); md = []
    for tg, (f, prepdir, label) in TARGETS.items():
        fp = R / f
        if not fp.exists(): out["targets"][tg] = "not run"; continue
        rows = [json.loads(l) for l in open(fp)]
        pids = sorted({r["prompt"] for r in rows})
        dh = decay(scratch, prepdir, label, pids); slow = set(int(h) for h in np.where(dh < 2 ** -9)[0])
        T = dict(n_slow=len(slow), slow_heads=sorted(slow), decay_median=float(np.median(dh)), decay_min=float(dh.min()), arms={})
        md.append(f"\n### {tg} ({label}); slow heads (median 1 - a < 2^-9): {len(slow)} of 48\n")
        md.append("| arm | n | errors | rel_y median (min / max) | rel_S median (max) | pairs rel_y <= 0.05 | in classes | layer rel_y | resid frob (med) | slow rel_y med / max | slow rel_S med / max | fast rel_y med / max | pass |")
        md.append("|---|---|---|---|---|---|---|---|---|---|---|---|---|")
        for arm in ARMS:
            rs = [r for r in rows if r["arm"] == arm and "error" not in r]; errs = [r for r in rows if r["arm"] == arm and "error" in r]
            if not rs and not errs: T["arms"][arm] = "not run"; md.append(f"| {arm} | not run |"); continue
            sy, sS = stat([r["rel_y"] for r in rs]), stat([r["rel_S"] for r in rs])
            bd = bounds(arm)
            inb = sum(all(r["max"].get(k, 0) < lim for k, lim in bd.items() if k in r["max"]) for r in rs)
            lay = [r["layer"] for r in rs if "layer" in r]
            sl = [r for r in rs if r["head"] in slow]; fa = [r for r in rs if r["head"] not in slow]
            d = dict(n=len(rs), errors=[(e["prompt"], e["error"]) for e in errs], rel_y=sy, rel_S=sS, in_classes=int(inb),
                     pairs_le_005=int(sum(r["rel_y"] <= 0.05 for r in rs)),
                     layer_rel_y=stat([l["rel_y"] for l in lay]), resid_frob=stat([l["resid"]["frob"] for l in lay]),
                     resid_bf16_frob=stat([l["resid_bf16"]["frob"] for l in lay]), bf16_rel_y=stat([r["bf16_rel_y"] for r in rs]),
                     slow_rel_y=stat([r["rel_y"] for r in sl]), slow_rel_S=stat([r["rel_S"] for r in sl]),
                     fast_rel_y=stat([r["rel_y"] for r in fa]), fast_rel_S=stat([r["rel_S"] for r in fa]),
                     over_class={k: int(sum(r["max"].get(k, 0) >= lim for r in rs)) for k, lim in bd.items()},
                     max={k: max(r["max"][k] for r in rs) for k in rs[0]["max"]} if rs else {})
            d["pass"] = passes(sy, sS, errs, inb, len(rs))
            d["slow_pass"] = bool(not errs and sl and d["slow_rel_y"]["median"] <= 0.01 and d["slow_rel_y"]["max"] <= 0.05
                                  and d["slow_rel_S"]["median"] <= 0.01 and d["slow_rel_S"]["max"] <= 0.05)
            T["arms"][arm] = d
            g = lambda s, k: f"{s[k]:.3g}" if s.get("n") else "-"
            md.append(f"| {arm} | {len(rs)} | {len(errs)} | {g(sy,'median')} ({g(sy,'min')} / {g(sy,'max')}) | {g(sS,'median')} ({g(sS,'max')}) | {d['pairs_le_005']} | {inb} | {g(d['layer_rel_y'],'median')} | {g(d['resid_frob'],'median')} | {g(d['slow_rel_y'],'median')} / {g(d['slow_rel_y'],'max')} | {g(d['slow_rel_S'],'median')} / {g(d['slow_rel_S'],'max')} | {g(d['fast_rel_y'],'median')} / {g(d['fast_rel_y'],'max')} | {'PASS' if d['pass'] else 'fail'} |")
        # descriptive: the pairs over 0.05 for the finest X arms (which heads limit the max)
        T["over_005"] = {}
        for arm in ("XS18", "XS20"):
            rs = sorted([r for r in rows if r["arm"] == arm and "error" not in r and r["rel_y"] > 0.05], key=lambda r: -r["rel_y"])
            T["over_005"][arm] = [dict(prompt=r["prompt"], head=r["head"], slow=r["head"] in slow, rel_y=r["rel_y"], rel_S=r["rel_S"],
                                        bf16_rel_y=r["bf16_rel_y"], o_max=r["max"].get("o"), decay=float(dh[r["head"]])) for r in rs]
            hs = sorted({r["head"] for r in rs})
            md.append(f"\n{arm} pairs with rel_y > 0.05: {len(rs)}, heads {hs}, prompts {sorted({r['prompt'] for r in rs})}")
        T["bf16_context_rel_y"] = stat([r["bf16_rel_y"] for r in rows if r["arm"] == "C0" and "error" not in r])
        out["targets"][tg] = T
    # state precision rule
    fsr = {}
    for fs in (12, 14, 16, 18, 20):
        arm = f"XS{fs}"; ok = []
        for tg, T in out["targets"].items():
            if not isinstance(T, dict) or not T["n_slow"]: continue
            a = T["arms"].get(arm)
            ok.append(isinstance(a, dict) and a["slow_pass"])
        fsr[arm] = bool(ok) and all(ok)
    out["slow_state_rule"] = fsr
    out["smallest_FS_slow"] = next((int(a[2:]) for a, v in fsr.items() if v), None)
    out["H1_XS18_all_targets"] = all(isinstance(T, dict) and isinstance(T["arms"].get("XS18"), dict) and T["arms"]["XS18"]["pass"] for T in out["targets"].values())
    # U1 reading
    u1 = R / "u1-layer20.jsonl"
    if u1.exists():
        rows = [json.loads(l) for l in open(u1)]; out["u1_layer20"] = dict(rows=rows,
            mix_diff_frob=stat([r["mix_diff_frob"] for r in rows]), resid_in_diff_frob=stat([r["resid_in_diff_frob"] for r in rows]))
    # end to end
    for ck in ("stock", "abl"):
        f = R / f"e2e-{ck}.json"
        if not f.exists(): out[f"e2e_{ck}"] = "not run"; continue
        e = json.load(open(f)); summ = dict(sanity_pass=e.get("sanity_pass"), sanity_p01_last_top1=e.get("sanity_p01_last_top1"), paths={})
        for path in ("INT", "BF16H"):
            agree = []; kl = []; md_ = []; failed = []
            for pid, d in e["prompts"].items():
                if d[path] is None: failed.append(pid); continue
                agree += d[path]["top1_agree"]; kl += d[path]["kl"]; md_ += d[path]["maxdiff_over_std"]
            summ["paths"][path] = dict(positions=len(agree), top1_agree=int(sum(agree)), kl=stat(kl), maxdiff_over_std=stat(md_), failed_prompts=failed,
                                       per_prompt={pid: (None if d[path] is None else dict(T=d["T"], agree=int(sum(d[path]["top1_agree"])), kl_median=float(np.median(d[path]["kl"])), kl_max=float(max(d[path]["kl"])))) for pid, d in e["prompts"].items()})
        out[f"e2e_{ck}"] = summ
        dv = R / f"e2e-{ck}-divergence.jsonl"
        if dv.exists():
            rows = [json.loads(l) for l in open(dv)]
            out[f"e2e_{ck}"]["resid_rel_final_layer"] = {p: rows[-1][p] for p in ("INT", "BF16H")}
    (R / "summary.json").write_text(json.dumps(out, indent=1) + "\n")
    print("\n".join(md))
    print("\nH1 (XS18 passes all targets):", out["H1_XS18_all_targets"], "| slow-state rule:", fsr, "| smallest FS:", out["smallest_FS_slow"])
    for ck in ("stock", "abl"):
        e = out.get(f"e2e_{ck}")
        if isinstance(e, dict):
            print(f"\ne2e {ck}: sanity {e['sanity_pass']}")
            for p, s in e["paths"].items():
                print(f"  {p}: top1 {s['top1_agree']}/{s['positions']}, KL median {s['kl'].get('median')}, max {s['kl'].get('max')}, failed {s['failed_prompts']}")
    if "u1_layer20" in out: print("\nU1 layer 20 stock-vs-abl mixer diff over resid (frob, per prompt):", out["u1_layer20"]["mix_diff_frob"])

if __name__ == "__main__": main()
