#!/usr/bin/env python3
"""Mechanism numbers for the localisation (PREREG: one mechanism number per named step). Light: public stage only
(in_proj, conv, SiLU, L2 norm, gates) plus the cached float reference; no integer recurrence. Single core.

Per (prompt, head), at the M2 scales (F = 12):
  decay: 1 - a in units of 2^-12 (float), share of tokens where rne(2^12 a) = 2^12 (the decay rounds to "no decay"),
         relative error of the rounded per-token decay exponent, and the float decay itself;
  q_hat, k_hat: median |entry| in integer units (the relative rounding error of an entry is about 0.5 / that);
  o: float o RMS per token in units of 2^-12 (median, min over tokens);
  y: float |y| median in units of 2^-12;
  v: float |v| median in units of 2^-12.
Usage: diag_mech.py <cache> <fref_dir> <out.json>"""
import json, math, sys
from pathlib import Path
import numpy as np
HERE = Path(__file__).resolve().parent
SRC = HERE.parent / "20261109-8-qwen-real-weights"
sys.path.insert(0, str(SRC))
import real_head as RH

D, NV, ONE = 128, 48, 4096.0
cache, fref, out = sys.argv[1], Path(sys.argv[2]), sys.argv[3]
L, emb = RH.load_layer(cache, "stock")
rows = []
for p in json.load(open(SRC / "prompts.json"))["prompts"]:
    x, h, qkv, z, a, b = RH.inproj(L, emb, p["token_ids"])
    xq, xk, xv, ar, br, zz, Wc, A, dtb, gain = RH.heads(L, qkv, z, a, b)
    T = xq.shape[0]
    af = np.exp(-A[None, :] * np.logaddexp(0.0, ar + dtb[None, :]))          # (T, 48) float decay
    ai = np.rint(ONE * np.exp(-A[None, :] * np.logaddexp(0.0, np.rint(ar * ONE) / ONE + dtb[None, :])))
    # float conv + silu + l2 norm for q, k
    def conv_silu(xx, w):
        xp = np.concatenate([np.zeros((3,) + xx.shape[1:]), xx], 0)
        u = sum(w[None, :, :, tau] * xp[3 - tau:3 - tau + T] for tau in range(4))
        return u / (1.0 + np.exp(-u))
    cq, ck, cv = conv_silu(xq, Wc[0]), conv_silu(xk, Wc[1]), conv_silu(xv, Wc[2])
    qh = cq / np.sqrt((cq * cq).sum(-1, keepdims=True) + 1e-6) / math.sqrt(D) * ONE
    kh = ck / np.sqrt((ck * ck).sum(-1, keepdims=True) + 1e-6) * ONE
    d = np.load(fref / f"fref-stock-{p['id']}.npz")
    of, yf = d["of"], d["yf"]
    orms = np.sqrt((of ** 2).mean(-1)) * ONE                                   # (T, 48)
    for hh in range(NV):
        one_minus = (1.0 - af[:, hh]) * ONE
        # cumulative decay over the prompt: product of a (float) vs product of rounded a / 2^12
        cum_f = float(np.sum(np.log(af[:, hh]))); cum_i = float(np.sum(np.log(np.maximum(ai[:, hh], 1.0) / ONE)))
        rows.append(dict(prompt=p["id"], head=hh, T=T,
                         one_minus_a_int_median=float(np.median(one_minus)), one_minus_a_int_min=float(one_minus.min()),
                         share_tokens_a_rounds_to_one=float(np.mean(ai[:, hh] == ONE)),
                         share_tokens_one_minus_a_below_half=float(np.mean(one_minus < 0.5)),
                         share_tokens_one_minus_a_below_8=float(np.mean(one_minus < 8.0)),
                         log_cum_decay_float=cum_f, log_cum_decay_int=cum_i,
                         q_hat_abs_median_int=float(np.median(np.abs(qh[:, hh]))), k_hat_abs_median_int=float(np.median(np.abs(kh[:, hh]))),
                         o_rms_int_median=float(np.median(orms[:, hh])), o_rms_int_min=float(orms[:, hh].min()),
                         share_tokens_o_rms_below_4=float(np.mean(orms[:, hh] < 4.0)),
                         y_abs_median_int=float(np.median(np.abs(yf[:, hh])) * ONE), v_abs_median_int=float(np.median(np.abs(cv[:, hh])) * ONE)))
def st(k):
    v = np.array([r[k] for r in rows]); return dict(n=int(v.size), median=float(np.median(v)), min=float(v.min()), max=float(v.max()))
summ = {k: st(k) for k in rows[0] if k not in ("prompt", "head", "T")}
summ["pairs_o_rms_median_below_4"] = int(sum(r["o_rms_int_median"] < 4.0 for r in rows))
summ["pairs_o_rms_median_below_16"] = int(sum(r["o_rms_int_median"] < 16.0 for r in rows))
summ["pairs_with_any_token_a_rounding_to_one"] = int(sum(r["share_tokens_a_rounds_to_one"] > 0 for r in rows))
Path(out).write_text(json.dumps(dict(summary=summ, rows=rows), indent=1) + "\n")
print(json.dumps(summ, indent=1))
