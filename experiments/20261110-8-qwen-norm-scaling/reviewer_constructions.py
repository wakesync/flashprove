#!/usr/bin/env python3
"""PREREG amendment A-4: reproduces the counterexample constructions of the two independent reviews of PR #74 against
this experiment's own candidate lowerings (correctness testing of our research code, not an attack on anything built).
Labelled as REVIEWER CONSTRUCTIONS:
  astra: https://github.com/wakesync/flashprove/pull/74#issuecomment-6759241337
  opus:  https://github.com/wakesync/flashprove/pull/74#issuecomment-6759761745
Goldilocks p = 2^64 - 2^32 + 1. Plain Python integers. Nothing here is a forged proof: no proof exists. Each case checks
whether a witness different from the honest one satisfies every relation of the candidate's gated norm modulo p, with
every value inside the range the candidate's COUNTED lowering proves (count_cost.py: b bits = ceil(b / 12) 12-bit keys,
i.e. [0, 2^(12 ceil(b / 12))); RNG cells |x| < 2^23).

Parts:
  A  astra's local alias: all 128 norm inputs = 1, honest sigma, Rc' = floor((2^RC + p) / sigma). C4P (Fo 24, RC 56),
     X3 at Fo 29 (astra's case) and Fo 30 (the smallest X3 shift, smin = 8, gives Fo = 20 + 18 - 8 = 30).
  B  opus's real-value construction: o and cg of all 48 heads at token 12 of prompt p01 (this engine, committed C4P and
     X3 configurations, stock), Rc' as in A, w' from the representative of o Rc' nearest zero, y' from w'.
     Needs the cached in_proj outputs (NS_PREP) of the real weights.
  C  interval bounds of the memory-read floor relation 2^(Fg + Fk) M + r = a P at the honest class and at the proved
     two-limb bound, under both reviewers' bounds on ||k_hat||_1 (opus: sqrt(128) 2^12, from the verifier-recomputed L2
     norm; astra: 128 x 2^12, coordinate-wise only).
Usage: reviewer_constructions.py <cache_dir> <out.json>   (writes the json; prints a summary)"""
import json, math, sys, os
from pathlib import Path
import numpy as np
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
p = 2 ** 64 - 2 ** 32 + 1
K = lambda b: 12 * math.ceil(b / 12)
RNG = 2 ** 23
D = 128

def eps_of(Fo): return round(128 * 1e-6 * 4.0 ** Fo)

def check_norm(o, cg, eps, RC, Fw, Fcg, Fy, sig, Rc, rr, w, rw, y, ry, sig_bits, e_bits, w_cls):
    Vx = sum(x * x for x in o)
    e1 = (Vx + eps - sig * sig) % p; e2 = (sig * sig + 2 * sig - Vx - eps) % p
    gap = (sig - 1 - rr) % p
    shw = RC - Fw; shy = Fw + Fcg - Fy
    ch = {
        "sigma in counted keys": 0 <= sig < 2 ** K(sig_bits),
        "e1 in counted keys": e1 < 2 ** K(e_bits), "e2 in counted keys": e2 < 2 ** K(e_bits),
        "Rc in counted keys": 0 <= Rc < 2 ** K(RC),
        "rr, gap in counted keys": rr < 2 ** K(sig_bits) and gap < 2 ** K(sig_bits),
        "reciprocal rel mod p": (Rc * sig + rr - 2 ** RC) % p == 0,
        "w rel mod p (all j)": all((2 ** shw * wj + rj - oj * Rc) % p == 0 for oj, wj, rj in zip(o, w, rw)),
        "w remainder in counted keys": all(0 <= r < 2 ** K(shw) for r in rw),
        f"w in its class (|w| < {w_cls})": all(abs(x) < w_cls for x in w),
        "y rel mod p (all j)": all((2 ** shy * yj + rj - cj * wj) % p == 0 for cj, wj, yj, rj in zip(cg, w, y, ry)),
        "y remainder in counted keys": all(0 <= r < 2 ** K(shy) for r in ry),
        "y in public class 2^31": all(abs(x) < 2 ** 31 for x in y),
    }
    return ch, dict(reciprocal_over_integers=Rc * sig + rr - 2 ** RC)

def honest(o, cg, eps, RC, Fw, Fcg, Fy):
    sig = math.isqrt(sum(x * x for x in o) + eps); Rc = 2 ** RC // sig; rr = 2 ** RC - Rc * sig
    shw = RC - Fw; shy = Fw + Fcg - Fy
    w = [(x * Rc) >> shw for x in o]; rw = [x * Rc - (wi << shw) for x, wi in zip(o, w)]
    y = [(c * wi) >> shy for c, wi in zip(cg, w)]; ry = [c * wi - (yi << shy) for c, wi, yi in zip(cg, w, y)]
    return sig, Rc, rr, w, rw, y, ry

def alias(o, cg, sig, RC, Fw, Fcg, Fy):
    Rc, rr = divmod(2 ** RC + p, sig)
    shw = RC - Fw; shy = Fw + Fcg - Fy; w = []; rw = []
    for x in o:
        v = x * Rc
        m = round(v / p) if abs(v) >= p // 2 else 0      # representative of o Rc' nearest zero (opus)
        u = v - m * p; wi = u >> shw; w.append(wi); rw.append(u - (wi << shw))
    y = [(c * wi) >> shy for c, wi in zip(cg, w)]; ry = [c * wi - (yi << shy) for c, wi, yi in zip(cg, w, y)]
    return Rc, rr, w, rw, y, ry

ARMS = {  # name: (RC, Fw, Fcg, Fy, counted sigma bits, counted e bits)   (count_cost.py's widths)
    "C4P": (56, 16, 12, 20, 33, 34),
    "X3": (46, 16, 16, 20, 23, 24),
    "X3-recounted": (46, 16, 16, 20, 24, 25),   # count_cost_r2.py: sigma 24 bits, e1 / e2 25 bits (3 keys) at Fo up to 30
}

def case(arm, o, cg, Fo, w_cls=RNG):
    RC, Fw, Fcg, Fy, sb, eb = ARMS[arm]; eps = eps_of(Fo)
    h = honest(o, cg, eps, RC, Fw, Fcg, Fy)
    hch, _ = check_norm(o, cg, eps, RC, Fw, Fcg, Fy, *h, sb, eb, w_cls)
    a = alias(o, cg, h[0], RC, Fw, Fcg, Fy)
    ach, extra = check_norm(o, cg, eps, RC, Fw, Fcg, Fy, h[0], *a, sb, eb, w_cls)
    return dict(honest_ok=all(hch.values()), honest_failing=[k for k, v in hch.items() if not v],
                alias_all_hold=all(ach.values()), alias_failing=[k for k, v in ach.items() if not v],
                y_differs=a[4] != h[5], max_abs_y_diff=max(abs(x - z) for x, z in zip(a[4], h[5])),
                max_abs_y_diff_real=max(abs(x - z) for x, z in zip(a[4], h[5])) / 2 ** Fy,
                sigma=h[0], Rc_honest=h[1], Rc_alias=a[0], max_abs_w_alias=max(abs(x) for x in a[2]), **extra)

def part_a():
    out = {}
    # X3's shift gadget: s_t > smin requires some |o_j| >= 2^16, so an all-small o is only a legal gadget input at
    # s_t = smin = 8, i.e. Fo = 20 + 18 - 8 = 30. Fo 29 (astra's case) is local to the norm and ignores the gadget.
    for arm, Fo in (("C4P", 24), ("X3", 29), ("X3", 30), ("X3-recounted", 30)):
        RC, Fw, Fcg, Fy, sb, eb = ARMS[arm]
        o = [1] * D; cg = [2 ** Fcg] * D
        out[f"{arm}-Fo{Fo}"] = dict(rng_class=case(arm, o, cg, Fo), tight_w_2_16=case(arm, o, cg, Fo, w_cls=2 ** 16 + 1))
    return out

def part_b(prep, pid="p01-ordinary-short", t=12):
    import scaled_head as SH
    f = Path(prep) / f"prep-stock-{pid}.npz"
    if not f.exists(): return dict(skipped=f"no cached in_proj outputs at NS_PREP for {pid}")
    d = np.load(f); xq, xk, xv, ar, br, zz, Wc, A, dtb, gain = (d[k] for k in ("xq", "xk", "xv", "ar", "br", "zz", "Wc", "A", "dtb", "gain"))
    cand = json.load(open(HERE / "arms-cand.json")); res = {}
    for arm in ("C4P", "X3"):
        cfg = dict(SH.M2); cfg.update(cand[arm]["cfg"])
        hd = SH.Head(cand[arm]["cfg"])
        for k, (S, o, y, Fo) in enumerate(hd.run(xq, xk, xv, ar, br, zz, Wc, A, dtb, gain, {})):
            if k == t: break
        zi = np.rint(zz[t] * 2.0 ** cfg["Fz"]); zr = zi / 2.0 ** cfg["Fz"]
        cgm = np.rint(2.0 ** cfg["Fcg"] * gain[None, :] * math.sqrt(D) * zr / (1.0 + np.exp(-zr)))
        heads = []
        for h in range(o.shape[0]):
            oh = [int(x) for x in o[h]]; ch = [int(x) for x in cgm[h]]
            r = case(arm, oh, ch, int(np.asarray(Fo).reshape(-1)[h] if np.ndim(Fo) else Fo))
            heads.append(r)
        n_alias = sum(r["alias_all_hold"] and r["y_differs"] for r in heads)
        fails = {}
        for r in heads:
            for k in r["alias_failing"]: fails[k] = fails.get(k, 0) + 1
        res[arm] = dict(prompt=pid, token=t, heads=len(heads), honest_ok=sum(r["honest_ok"] for r in heads),
                        alias_passes_every_relation_and_counted_range_with_y_changed=n_alias,
                        alias_failing_checks=fails,
                        max_abs_y_diff_real=max((r["max_abs_y_diff_real"] for r in heads if r["alias_all_hold"]), default=None))
    return res

def part_c():
    out = {}
    for arm, Fg, Fk, S_cls, S_proved in (("C4P", 18, 12, 2 ** 18, RNG), ("X3", 18, 12, 2 ** 25, RNG * 2 ** 18 + RNG)):
        a = 2 ** Fg; r = {}
        for tag, k1 in (("opus ||k||_1 <= sqrt(128) 2^12", math.sqrt(D) * 2 ** Fk), ("astra ||k||_1 <= 128 x 2^12", D * 2 ** Fk)):
            r[tag] = {"aP at honest class (log2)": round(math.log2(a * k1 * S_cls), 2), "aP at proved bound (log2)": round(math.log2(a * k1 * S_proved), 2),
                      "wrap possible at proved bound (>= p/2)": a * k1 * S_proved >= p // 2}
        out[arm] = r
    return out

def main():
    prep = os.environ.get("NS_PREP", "")
    res = dict(_label="REVIEWER CONSTRUCTIONS reproduced on this experiment's own lowerings; not results, not a forged proof (none exists).",
               _links=dict(astra="https://github.com/wakesync/flashprove/pull/74#issuecomment-6759241337",
                           opus="https://github.com/wakesync/flashprove/pull/74#issuecomment-6759761745"),
               A_astra_all_ones_alias=part_a(), B_opus_real_value_alias=part_b(prep) if prep else dict(skipped="NS_PREP not set"),
               C_memory_read_interval=part_c())
    Path(sys.argv[2]).write_text(json.dumps(res, indent=1, default=str) + "\n")
    print(json.dumps(res, indent=1, default=str)[:6000])

if __name__ == "__main__": main()
