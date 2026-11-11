#!/usr/bin/env python3
"""Integer reference for the M2 head statement (one V head of a Gated DeltaNet layer, T = 16, F = 12),
from the head's in_proj outputs to its gated-norm output, on SYNTHETIC inputs.

Independent of the C++ lowering (head.h, public_stage.h): numpy / Python integers here, explicit
checked quotient and remainder arithmetic there. m2.cpp checks both agree value by value.

The lowering is PR #66's (DESIGN.md), with pinned integer tables in place of float64:
  conv    acc = sum_tau W[ch, tau] x_(t - tau)[ch], c = floor(acc / 2^12); x_(-1 - tau) = H[tau]
  SiLU    silu-f12 table, row floor(c / 16) + 2048, domain [-8, 8), no clamp
  k       floor((2 s 2^12 + sig) / (2 sig)), sig = isqrt(sum s^2 + 17)
  q       the same with sig * 46341 and numerator * 2^12 (the 1 / sqrt(128) of q)
  a       decay-one-f12 at ar + dt_bias (A = 1: the pinned tables carry no learned A)
  beta    sigmoid-f12 at br
  cg      floor(G * silu[z] / 2^12), G a public head constant at 2^12 (46341 = sqrt(128) at gain 1)
  recurrence   research/operators/qwen_deltanet/reference.py step(), unchanged
  norm    sigma = isqrt(sum o^2 + 2147), Rc = floor(2^36 / sigma), w = floor(o Rc / 2^24), y = floor(cg w / 2^12)
This is a chosen research contract on synthetic weights. It is not the publisher's numerics, and
PR #68 (unreviewed) reports that this lowering does not meet the fidelity threshold on real weights.
"""
import argparse, math, pathlib, sys
import numpy as np
here = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(here.parents[0] / 'qwen_deltanet'))
sys.path.insert(0, str(here))
import reference as R
import tables as TB

D, F, T, WARM = 128, 12, 16, 64
ONE = 1 << F
BOUND = 1 << 18
EPS_L2, EPS_NORM, SQRT_D = 17, 2147, 46341
SILU, SIG, DECAY = (np.array(TB.load(n), dtype=np.int64) for n in ('silu', 'sigmoid', 'decay_one'))

def key(x):
    k = np.asarray(x, dtype=np.int64) // 16 + 2048
    if (k < 0).any() or (k >= 4096).any(): raise OverflowError('table input outside [-8, 8): reject, never clamp')
    return k

def conv(hist, w):
    return sum(w[:, tau] * hist[tau] for tau in range(4)) // 4096

def l2n(s, extra=None):
    so = [int(v) for v in s]
    sig = math.isqrt(sum(v * v for v in so) + EPS_L2)
    num = [v * ONE for v in so]
    if extra: sig, num = sig * extra, [v * 4096 for v in num]
    return np.array([(2 * v + sig) // (2 * sig) for v in num], dtype=np.int64)

def norm(o, cg):
    oo = [int(v) for v in o]
    n = sum(v * v for v in oo) + EPS_NORM
    sigma = math.isqrt(n); e1 = n - sigma * sigma; e2 = sigma * sigma + 2 * sigma - n
    Rc = (1 << 36) // sigma; rr = (1 << 36) - Rc * sigma; gap = sigma - 1 - rr
    assert e1 >= 0 and e2 >= 0 and rr >= 0 and gap >= 0 and max(sigma, e1, e2, rr, gap) < 1 << 24 and Rc < 1 << 36
    w = [(v * Rc) >> 24 for v in oo]
    y = [(int(c) * v) >> 12 for c, v in zip(cg, w)]
    if max(abs(v) for v in oo) >= BOUND or max(abs(v) for v in w) >= BOUND: raise OverflowError('o or w outside its contract')
    return np.array(w, dtype=np.int64), np.array(y, dtype=np.int64)

def run(seed):
    rng = np.random.default_rng(2000 + seed)
    W = np.rint(rng.uniform(-0.5, 0.5, size=(3, D, 4)) * 4096).astype(np.int64)
    dt_bias = int(np.rint(rng.uniform(-3.0, -1.0) * ONE))
    G = np.full(D, SQRT_D, dtype=np.int64)
    q12 = lambda x: np.rint(np.asarray(x) * ONE).astype(np.int64)
    S = np.zeros((D, D), dtype=np.int64)
    hist = [[np.zeros(D, dtype=np.int64)] * 4 for _ in range(3)]
    S0 = H = None; toks = []; ref = []
    for t in range(WARM + T):
        if t == WARM:
            S0 = S.copy()
            H = np.concatenate([np.concatenate([hist[c][tau] for c in range(3)]) for tau in range(3)])  # H[tau * 3D + c * D + ch] = x_(-1 - tau)
        x = [q12(rng.standard_normal(D)) for _ in range(3)]
        z = q12(rng.standard_normal(D)); ar = int(q12(rng.standard_normal())); br = int(q12(rng.standard_normal()))
        s = []
        for c in range(3):
            hist[c] = [x[c]] + hist[c][:3]
            s.append(SILU[key(conv(hist[c], W[c]))])
        qh, kh, v = l2n(s[0], SQRT_D), l2n(s[1]), s[2]
        a = int(DECAY[key(ar + dt_bias)]); beta = int(SIG[key(br)])
        M, delta, S, o = R.step(S, dict(a=a, beta=beta, k=kh, v=v, q=qh), F)
        cg = (G * SILU[key(z)]) // 4096
        w, y = norm(o, cg)
        if t >= WARM:
            toks.append((x[0], x[1], x[2], ar, br, z))
            ref.append((a, beta, kh, v, qh, cg, M, delta, S.copy(), o, w, y))
    return W, dt_bias, G, S0, H, toks, ref

def write_fixture(path, seed):
    """Layout (int64 LE): T, D, F | W[3 D 4] dt_bias G[D] | S0[D D] | H[3 * 3D] | per token: xq, xk, xv, ar, br, z |
    per token (reference): a, beta, k, v, q, cg, M, delta, S, o, w, y."""
    W, dt_bias, G, S0, H, toks, ref = run(seed)
    i1 = lambda v: np.array([v], dtype=np.int64)
    arr = [np.array([T, D, F], dtype=np.int64), W.reshape(-1), i1(dt_bias), G, S0.reshape(-1), H]
    for xq, xk, xv, ar, br, z in toks: arr += [xq, xk, xv, i1(ar), i1(br), z]
    for a, beta, k, v, q, cg, M, delta, S, o, w, y in ref: arr += [i1(a), i1(beta), k, v, q, cg, M, delta, S.reshape(-1), o, w, y]
    np.concatenate(arr).astype('<i8').tofile(path)
    mx = lambda i: int(max(np.abs(r[i]).max() for r in ref))
    return dict(seed=seed, dt_bias=dt_bias, S0_max_abs=int(np.abs(S0).max()), S_max_abs=mx(8), M_max_abs=mx(6), delta_max_abs=mx(7), o_max_abs=mx(9),
                w_max_abs=mx(10), y_max_abs=mx(11), cg_max_abs=mx(5), a=[r[0] for r in ref], beta=[r[1] for r in ref])

if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('--seed', type=int, required=True); ap.add_argument('--out', required=True)
    a = ap.parse_args(); print(write_fixture(a.out, a.seed))
