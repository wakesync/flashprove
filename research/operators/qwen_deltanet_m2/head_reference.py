#!/usr/bin/env python3
"""Integer reference for ONE V head of a Qwen3.8 Gated DeltaNet layer, end to end from the in_proj
outputs to the gated-norm output (the M2 statement of DESIGN.md), plus a float64 twin.

Chosen research contract, not the publisher's numerics. The public-only stage (conv1d, SiLU, q/k L2
norm, q scale, decay and beta) is what the M2 verifier RECOMPUTES from public integers; the private
stage (recurrence, o, gated RMSNorm) is what the M2 relation proves. This file measures the ranges
the DESIGN's cell classes must hold (PREREG H4).

Scales: every activation integer is at 2^F, F = 12. Per token t, public:
  xq, xk, xv  in_proj_qkv outputs of this head's channels (128 each), pre-conv, rounded at 2^F
  ar, br      in_proj_a / in_proj_b outputs (scalars), at 2^F
  z           in_proj_z outputs (128), at 2^F
Per head, public: conv kernels (3 x 128 x 4 taps, at 2^12), A = exp(A_log) and dt_bias (float64), gain.
Usage: head_reference.py --suite [--json out.json] [--kernel random|delta] [--steps N]
"""
import argparse, json, math, sys, time, pathlib
import numpy as np
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'qwen_deltanet'))
import reference as R  # M1: step() (the staged-floor recurrence, unchanged), Head, softplus, silu, sigmoid

D, F = 128, 12
ONE = 1 << F
BOUND = 1 << 18
EPS_L2 = 17                                 # rne(1e-6 * 2^2F), l2norm eps of the FLA kernel
EPS_NORM = int(round(D * 1e-6 * 2 ** 24))   # rms_norm_eps 1e-6, times D (sum, not mean), at 2^2F: 2147
SQRT_D_Q12 = int(round(math.sqrt(D) * 4096))  # 46341
RC_SHIFT = 36                               # Rc = floor(2^36 / sigma)

def isqrt_arr(x):
    return np.array([math.isqrt(int(v)) for v in np.asarray(x).reshape(-1)], dtype=object).reshape(np.shape(x))

def conv_int(hist, w):
    """Causal depthwise conv, kernel 4, zero padding: hist[tau] = x_{t - tau} (tau = 0..3), w[ch, tau] at 2^12."""
    acc = sum(w[:, tau] * hist[tau] for tau in range(4))
    return acc // 4096

def silu_int(c):
    """Verifier-recomputed SiLU at 2^F: rne(2^F silu(c / 2^F)) in float64 (no table needed: public)."""
    x = c.astype(np.float64) / ONE
    return np.rint(ONE * (x / (1.0 + np.exp(-x)))).astype(np.int64)

def l2n_int(u, extra=None):
    """|u|-normalised at 2^F, round half up: floor((2 u 2^F S + s) / (2 s)), s = isqrt(sum u^2 + eps) (x sqrt(D) for q)."""
    n2 = int((u.astype(object) ** 2).sum())
    s = math.isqrt(n2 + EPS_L2)
    num = u.astype(object) * ONE
    if extra:  # q: also divide by sqrt(D) (s2 = s * round(sqrt(D) 2^12), numerator x 2^12)
        s = s * extra; num = num * 4096
    out = (2 * num + s) // (2 * s)
    return np.array(out, dtype=np.int64)

def gates_int(ar, br, head):
    a = int(np.rint(ONE * math.exp(-head.A * float(R.softplus(ar / ONE + head.dt_bias)))))
    beta = int(np.rint(ONE * float(R.sigmoid(br / ONE))))
    return a, beta

def gated_norm_int(o, z, gain):
    """The PROVED part after the recurrence (DESIGN.md 4.4). Returns y and the exact quantities."""
    oo = o.astype(object)
    Vx = int((oo ** 2).sum())
    sigma = math.isqrt(Vx + EPS_NORM)
    e1 = Vx + EPS_NORM - sigma * sigma            # >= 0
    e2 = sigma * sigma + 2 * sigma - Vx - EPS_NORM  # >= 0  (so sigma = isqrt exactly)
    Rc = (1 << RC_SHIFT) // sigma
    rr = (1 << RC_SHIFT) - Rc * sigma              # in [0, sigma)
    gap = sigma - 1 - rr                            # >= 0
    prod = oo * Rc
    w = np.array([p // (1 << 24) for p in prod], dtype=object)
    rw = prod - w * (1 << 24)
    cg = np.rint(ONE * gain * math.sqrt(D) * (z / ONE) / (1.0 + np.exp(-(z / ONE)))).astype(np.int64)  # public, verifier-derived
    num = cg.astype(object) * w
    y = np.array([v // ONE for v in num], dtype=object)
    ry = num - y * ONE
    ex = dict(sigma=sigma, e1=e1, e2=e2, Rc=Rc, rr=rr, gap=gap, rw_max=int(max(rw)), rw_min=int(min(rw)), ry_max=int(max(ry)), ry_min=int(min(ry)),
              w_absmax=int(max(abs(v) for v in w)), cg_absmax=int(np.abs(cg).max()), y_absmax=int(max(abs(v) for v in y)), Vx=Vx)
    return np.array(y, dtype=np.int64), np.array(w, dtype=np.int64), ex

def gen(seed, dist, T, kernel):
    """Float in_proj outputs for one head. Pre-conv xq, xk ~ N(0,1); xv from M1's R1..R4 base (so the
    heavy tail of R3 reaches the conv); z, ar, br ~ N(0,1); conv taps U(-0.5, 0.5) or a delta kernel."""
    rng = np.random.default_rng(1000 + seed); head = R.Head(rng); st = {}
    if kernel == 'random':
        W = rng.uniform(-0.5, 0.5, size=(3, D, 4))
    else:  # 'delta': out_t = x_t, a pass-through stress kernel (unregistered, secondary)
        W = np.zeros((3, D, 4)); W[:, :, 0] = 1.0
    toks = []
    for _ in range(T):
        xq = rng.standard_normal(D); xk = rng.standard_normal(D)
        b = dist[1]
        if b == '1': xv = rng.standard_normal(D)
        elif b == '2': xv = 2.0 * rng.standard_normal(D)
        elif b == '3': xv = 2.0 * rng.standard_t(3, D)
        else:
            prev = st.get('ar'); e = rng.standard_normal(D)
            z1 = e if prev is None else 0.9 * prev + math.sqrt(1 - 0.81) * e
            st['ar'] = z1; xv = 2.0 * z1
        toks.append(dict(xq=xq, xk=xk, xv=xv, z=rng.standard_normal(D), ar=float(rng.standard_normal()), br=float(rng.standard_normal())))
    return head, W, toks

def run(seed, dist, T, kernel, gain=1.0, q_unscaled=False):
    """q_unscaled (secondary, unregistered option): drop q's 1/sqrt(D) in the integer path. The gated
    RMSNorm is scale-invariant in o up to eps, so the factor can move into eps (x D); o is then about
    sqrt(D) = 11.3x larger in integer units, i.e. finer."""
    global EPS_NORM
    eps_saved = EPS_NORM
    if q_unscaled: EPS_NORM = eps_saved * D
    try:
        return _run(seed, dist, T, kernel, gain, q_unscaled)
    finally:
        EPS_NORM = eps_saved

def _run(seed, dist, T, kernel, gain, q_unscaled):
    head, W, toks = gen(seed, dist, T, kernel)
    Wi = np.rint(W * 4096).astype(np.int64)
    q = lambda x: np.rint(np.asarray(x) * ONE).astype(np.int64)
    S = np.zeros((D, D), dtype=np.int64); Sf = np.zeros((D, D))
    hist_i = [[np.zeros(D, dtype=np.int64)] * 4 for _ in range(3)]
    hist_f = [[np.zeros(D)] * 4 for _ in range(3)]
    mx = dict(S=0, M=0, delta=0, delta_lo=0, delta_hi=0, o=0, w=0, v=0, k_hat=0, q_hat=0, xin=0, y=0, cg=0,
              sigma=0, e1=0, e2=0, Rc=0, rr=0, gap=0, Vx=0)
    neg = dict(e1=0, e2=0, rr=0, gap=0, rw=0, ry=0)
    div_S = div_y = 0.0
    for t, tk in enumerate(toks):
        xs_i = [q(tk['xq']), q(tk['xk']), q(tk['xv'])]
        mx['xin'] = max(mx['xin'], max(int(np.abs(x).max()) for x in xs_i))
        cs = []
        for c in range(3):
            hist_i[c] = [xs_i[c]] + hist_i[c][:3]
            cs.append(silu_int(conv_int(hist_i[c], Wi[c])))
        qh, kh, v = l2n_int(cs[0], None if q_unscaled else SQRT_D_Q12), l2n_int(cs[1]), cs[2]
        a, beta = gates_int(q(tk['ar']), q(tk['br']), head)
        tok = dict(a=a, beta=beta, k=kh, v=v, q=qh)
        M, delta, S, o = R.step(S, tok, F, check=False)
        dhi = delta // BOUND; dlo = delta - dhi * BOUND
        z_i = q(tk['z'])
        y, w, ex = gated_norm_int(o, z_i.astype(np.float64), gain)
        for k_, arr in (('S', S), ('M', M), ('delta', delta), ('delta_lo', dlo), ('delta_hi', dhi), ('o', o), ('w', w), ('v', v), ('k_hat', kh), ('q_hat', qh), ('y', y)):
            mx[k_] = max(mx[k_], int(np.abs(arr).max()))
        for k_ in ('sigma', 'e1', 'e2', 'Rc', 'rr', 'gap', 'Vx'): mx[k_] = max(mx[k_], ex[k_])
        mx['cg'] = max(mx['cg'], ex['cg_absmax'])
        for k_ in ('e1', 'e2', 'rr', 'gap'): neg[k_] = min(neg[k_], ex[k_])
        neg['rw'] = min(neg['rw'], ex['rw_min']); neg['ry'] = min(neg['ry'], ex['ry_min'])
        # float twin
        csf = []
        for c, key in enumerate(('xq', 'xk', 'xv')):
            hist_f[c] = [np.asarray(tk[key])] + hist_f[c][:3]
            u = sum(W[c][:, tau] * hist_f[c][tau] for tau in range(4))
            csf.append(u / (1 + np.exp(-u)))
        qf = csf[0] / math.sqrt((csf[0] ** 2).sum() + 1e-6) / math.sqrt(D)
        kf = csf[1] / math.sqrt((csf[1] ** 2).sum() + 1e-6)
        af = math.exp(-head.A * float(R.softplus(tk['ar'] + head.dt_bias))); bf = float(R.sigmoid(tk['br']))
        Sf = Sf * af; df = bf * (csf[2] - kf @ Sf); Sf = Sf + np.outer(kf, df); of = qf @ Sf
        zf = tk['z']; yf = gain * of / math.sqrt((of ** 2).mean() + 1e-6) * zf / (1 + np.exp(-zf))
        div_S = max(div_S, float(np.abs(S / ONE - Sf).max())); div_y = max(div_y, float(np.abs(y / ONE - yf).max()))
    fit = dict(
        rng_cells=all(mx[k] < BOUND for k in ('S', 'M', 'delta_lo', 'delta_hi', 'o', 'w')),
        delta_split_needed=mx['delta'] >= BOUND,
        sigma_24=mx['sigma'] < 2 ** 24, e1_24=mx['e1'] < 2 ** 24 and neg['e1'] >= 0, e2_24=mx['e2'] < 2 ** 24 and neg['e2'] >= 0,
        Rc_36=mx['Rc'] < 2 ** 36, rr_24=mx['rr'] < 2 ** 24 and neg['rr'] >= 0, gap_24=mx['gap'] < 2 ** 24 and neg['gap'] >= 0,
        rw_24=neg['rw'] >= 0, ry_12=neg['ry'] >= 0,
        public_v_31=mx['v'] < 2 ** 31, public_y_31=mx['y'] < 2 ** 31, public_cg_24=mx['cg'] < 2 ** 24, public_x_31=mx['xin'] < 2 ** 31)
    return dict(seed=seed, dist=dist, steps=T, kernel=kernel, max=mx, min_exact=neg, fit=fit, all_fit=all(v for k, v in fit.items() if k != 'delta_split_needed'),
                div_S=div_S, div_y=div_y)

def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--suite', action='store_true'); ap.add_argument('--json')
    ap.add_argument('--kernel', default='random'); ap.add_argument('--steps', type=int, default=1024)
    ap.add_argument('--q-unscaled', action='store_true')
    a = ap.parse_args()
    t0 = time.time(); runs = []
    for dist in ('R1', 'R2', 'R3', 'R4'):
        for seed in range(1, 6):
            r = run(seed, dist, a.steps, a.kernel, q_unscaled=a.q_unscaled); runs.append(r)
            print(json.dumps(dict(dist=dist, seed=seed, all_fit=r['all_fit'], S=r['max']['S'], delta=r['max']['delta'], o=r['max']['o'], w=r['max']['w'],
                                  sigma=r['max']['sigma'], Rc=r['max']['Rc'], div_S=round(r['div_S'], 4), div_y=round(r['div_y'], 4))), flush=True)
    agg = {k: max(r['max'][k] for r in runs) for k in runs[0]['max']}
    res = dict(kernel=a.kernel, q_unscaled=a.q_unscaled, steps=a.steps, n=len(runs), fit=sum(r['all_fit'] for r in runs), max=agg,
               worst_div_S=max(r['div_S'] for r in runs), worst_div_y=max(r['div_y'] for r in runs), seconds=round(time.time() - t0, 1), runs=runs)
    print(json.dumps({k: v for k, v in res.items() if k != 'runs'}))
    if a.json: pathlib.Path(a.json).write_text(json.dumps(res, indent=1) + '\n')

if __name__ == '__main__':
    main()
