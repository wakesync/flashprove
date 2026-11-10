#!/usr/bin/env python3
"""Q3/Q4: integer M2 head contract vs float64 on REAL Qwen3.8-27B layer-0 weights, all 48 V heads at once.

Integer path = the M2 contract of research/operators/qwen_deltanet_m2/head_reference.py (which calls the
M1 staged-floor step of research/operators/qwen_deltanet/reference.py), rewritten here batched over heads
in int64 and parameterised by F. At F = 12 it is checked bit for bit against head_reference.py's own
per-token functions on its synthetic suite (`selfcheck`). F-dependent constants: EPS_L2 = rne(1e-6 2^2F),
EPS_NORM = rne(128 1e-6 2^2F), RC_SHIFT = 3F, w = floor(o Rc / 2^2F); conv taps at 2^TAP (12, as DESIGN
section 3 pins; the ablation sets TAP = F). Every int64 product is guarded: a magnitude that could pass
2^62 raises, it never wraps.

Float path = float64 Transformers semantics (modeling_qwen3_5.py e540ae45: recurrent rule L424-483,
GatedDeltaNet.forward L536-650, RMSNormGated L204-220, zero-centred RMSNorm L828-845), sequence start.
Context arm (descriptive) = BF16 casts emulated where the reference casts, FP32 recurrence.

Usage:
  real_head.py selfcheck
  real_head.py run <cache_dir> <stock|abl> <out.jsonl> [--F 12,14,16] [--tap-eq-F]
"""
import argparse, hashlib, json, math, sys, time
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "research/operators/qwen_deltanet_m2"))
sys.path.insert(0, str(ROOT / "research/operators/qwen_deltanet"))

D, NV, NK, HID = 128, 48, 16, 5120
BOUND = 1 << 18
LIM = 1 << 62
P = "model.language_model."

def guard(x, what):
    m = int(np.abs(x).max()) if np.size(x) else 0
    if m >= LIM: raise OverflowError(f"int64 guard: {what} reaches {m}")
    return x

def gmul(a, b, what):
    """a * b in int64, refusing if the product could pass 2^62 (checked from operand maxima)."""
    ma = int(np.abs(a).max()) if np.size(a) else 0; mb = int(np.abs(b).max()) if np.size(b) else 0
    if ma and mb and ma.bit_length() + mb.bit_length() > 62: raise OverflowError(f"int64 guard: {what} {ma} x {mb}")
    return a * b

class IntHead:
    """Integer M2 head contract, batched over H heads; arrays have a leading head axis."""
    def __init__(self, F, tap=12, H=NV, q_unscaled=False):
        self.F, self.TAP, self.H, self.q_unscaled = F, tap, H, q_unscaled
        self.ONE = 1 << F
        self.EPS_L2 = int(round(1e-6 * 2 ** (2 * F)))           # 17 at F = 12 (head_reference EPS_L2)
        self.EPS_NORM = int(round(D * 1e-6 * 2 ** (2 * F)))      # 2147 at F = 12 (head_reference EPS_NORM)
        if q_unscaled: self.EPS_NORM *= D                        # head_reference run(q_unscaled=True): eps x D
        self.SQRT_D_Q12 = int(round(math.sqrt(D) * 4096))        # 46341, independent of F
        self.RC_SHIFT = 3 * F                                    # 36 at F = 12
        self.W_SHIFT = 2 * F                                     # 24 at F = 12

    def q(self, x): return np.rint(np.asarray(x, dtype=np.float64) * self.ONE).astype(np.int64)

    def conv(self, hist, w):
        """hist[tau] (H, C) = x_{t-tau}; w (H, C, 4) at 2^TAP. floor(sum / 2^TAP)."""
        acc = sum(gmul(w[:, :, tau], hist[tau], "conv") for tau in range(4))
        return guard(acc, "conv acc") // (1 << self.TAP)

    def silu(self, c):
        x = c.astype(np.float64) / self.ONE
        return np.rint(self.ONE * (x / (1.0 + np.exp(-x)))).astype(np.int64)

    def l2n(self, u, extra=None):
        """Per head: floor((2 u 2^F s' + s) / (2 s)), s = isqrt(sum u^2 + eps) (times extra for q, numerator x 2^12)."""
        n2 = gmul(u, u, "l2 u^2").sum(axis=1)
        guard(n2, "l2 sum")
        s = np.array([math.isqrt(int(v) + self.EPS_L2) for v in n2], dtype=np.int64)
        num = gmul(u, np.int64(self.ONE), "l2 num")
        if extra:
            s = gmul(s, np.int64(extra), "l2 s q"); num = gmul(num, np.int64(4096), "l2 num q")
        return (gmul(num, np.int64(2), "l2 2num") + s[:, None]) // (2 * s[:, None])

    def gates(self, ar, br, A, dt_bias):
        """ar, br (H,) int at 2^F; A = exp(A_log), dt_bias float64 (H,). Verifier-recomputed (float64 at the table points)."""
        x = ar.astype(np.float64) / self.ONE + dt_bias
        a = np.rint(self.ONE * np.exp(-A * np.logaddexp(0.0, x))).astype(np.int64)
        beta = np.rint(self.ONE * (1.0 / (1.0 + np.exp(-(br.astype(np.float64) / self.ONE))))).astype(np.int64)
        return a, beta

    def step(self, S, a, beta, k, v, qv):
        """M1 staged-floor step (reference.step), batched: S (H, D, D) at 2^F, S[h, i, j]."""
        F = self.F
        Smax = int(np.abs(S).max()); kmax = int(np.abs(k).max())
        if (Smax * kmax * D).bit_length() + int(np.abs(a).max()).bit_length() > 62: raise OverflowError("int64 guard: a P")
        Pm = np.einsum("hi,hij->hj", k, S)
        M = (a[:, None] * Pm) // (1 << (2 * F))
        delta = gmul(v - M, beta[:, None], "delta") // (1 << F)
        upd = gmul(k[:, :, None], delta[:, None, :], "k delta")
        Sn = (gmul(a[:, None, None], S, "a S") + upd) // (1 << F)
        if (int(np.abs(Sn).max()) * int(np.abs(qv).max()) * D).bit_length() > 62: raise OverflowError("int64 guard: o")
        o = np.einsum("hi,hij->hj", qv, Sn) // (1 << F)
        return M, delta, Sn, o

    def gated_norm(self, o, z_int, gain):
        """DESIGN 4.4, batched. z_int (H, D) int at 2^F (as float64 for cg); gain (D,) float64."""
        F = self.F; ONE = self.ONE
        Vx = gmul(o, o, "o^2").sum(axis=1); guard(Vx, "Vx")
        sig = np.array([math.isqrt(int(v) + self.EPS_NORM) for v in Vx], dtype=np.int64)
        e1 = Vx + self.EPS_NORM - gmul(sig, sig, "sig^2")
        e2 = gmul(sig, sig, "sig^2") + 2 * sig - Vx - self.EPS_NORM
        Rc = (1 << self.RC_SHIFT) // sig
        rr = (1 << self.RC_SHIFT) - gmul(Rc, sig, "Rc sig")
        gap = sig - 1 - rr
        prod = gmul(o, Rc[:, None], "o Rc")
        w = prod // (1 << self.W_SHIFT); rw = prod - w * (1 << self.W_SHIFT)
        zf = z_int.astype(np.float64)
        cg = np.rint(ONE * gain[None, :] * math.sqrt(D) * (zf / ONE) / (1.0 + np.exp(-(zf / ONE)))).astype(np.int64)
        num = gmul(cg, w, "cg w")
        y = num // ONE; ry = num - y * ONE
        return y, w, dict(sigma=sig, e1=e1, e2=e2, Rc=Rc, rr=rr, gap=gap, Vx=Vx, cg=cg, rw=rw, ry=ry)

CLASSES = ("S", "M", "delta", "delta_lo", "delta_hi", "o", "w", "v", "k_hat", "q_hat", "xin", "ar", "br", "z", "y", "cg",
           "sigma", "e1", "e2", "Rc", "rr", "gap", "Vx")
NEGS = ("e1", "e2", "rr", "gap", "rw", "ry")

def run_int(ih, xq, xk, xv, ar, br, z, Wc, A, dt_bias, gain, stats):
    """Generator. Inputs: float in_proj outputs per head, shapes (T, H, D) for xq/xk/xv/z, (T, H) for ar/br; Wc (3, H, D, 4)
    float conv taps in head_reference's tau order (tau = 0 is the current token). Yields per token (S, o, y) as integers;
    per-head maxima and exact-limb minima accumulate in stats['max'], stats['neg']."""
    T, H = xq.shape[0], xq.shape[1]
    Wi = np.rint(Wc * (1 << ih.TAP)).astype(np.int64)
    S = np.zeros((H, D, D), dtype=np.int64)
    hist = [[np.zeros((H, D), dtype=np.int64)] * 4 for _ in range(3)]
    mx = {c: np.zeros(H, dtype=np.int64) for c in CLASSES}
    neg = {c: np.zeros(H, dtype=np.int64) for c in NEGS}
    stats["max"], stats["neg"] = mx, neg
    def upd(name, arr):
        mx[name] = np.maximum(mx[name], np.abs(arr).reshape(H, -1).max(axis=1))
    for t in range(T):
        xs = [ih.q(xq[t]), ih.q(xk[t]), ih.q(xv[t])]
        upd("xin", np.stack([np.abs(x).max(axis=1) for x in xs], 1))
        cs = []
        for c in range(3):
            hist[c] = [xs[c]] + hist[c][:3]
            cs.append(ih.silu(ih.conv(hist[c], Wi[c])))
        qh, kh, v = ih.l2n(cs[0], None if ih.q_unscaled else ih.SQRT_D_Q12), ih.l2n(cs[1]), cs[2]
        ari, bri = ih.q(ar[t]), ih.q(br[t])
        a, beta = ih.gates(ari, bri, A, dt_bias)
        M, delta, S, o = ih.step(S, a, beta, kh, v, qh)
        dhi = delta // BOUND; dlo = delta - dhi * BOUND
        zi = ih.q(z[t])
        y, w, ex = ih.gated_norm(o, zi, gain)
        for n, arr in (("S", S), ("M", M), ("delta", delta), ("delta_lo", dlo), ("delta_hi", dhi), ("o", o), ("w", w), ("v", v),
                       ("k_hat", kh), ("q_hat", qh), ("y", y), ("z", zi), ("ar", ari[:, None]), ("br", bri[:, None]), ("cg", ex["cg"])):
            upd(n, arr)
        for n in ("sigma", "e1", "e2", "Rc", "rr", "gap", "Vx"): upd(n, ex[n][:, None])
        for n in NEGS:
            m = ex[n] if ex[n].ndim == 1 else ex[n].min(axis=1)
            neg[n] = np.minimum(neg[n], m)
        yield S, o, y

def bf16(x):
    """Round float array to bfloat16 (round to nearest even), returned as float64."""
    f = np.asarray(x, dtype=np.float32)
    u = f.view(np.uint32).astype(np.uint64)
    u = (u + 0x7FFF + ((u >> 16) & 1)) & 0xFFFF0000
    return u.astype(np.uint32).view(np.float32).astype(np.float64)

def run_float(xq, xk, xv, ar, br, z, Wc, A, dt_bias, gain, emulate_bf16=False):
    """Generator. float64 (or BF16-cast emulation with FP32 recurrence) Transformers semantics, sequence start, batched
    over heads. Yields per token (S, o, y)."""
    T, H = xq.shape[0], xq.shape[1]
    r = bf16 if emulate_bf16 else (lambda v: v)
    dt = np.float32 if emulate_bf16 else np.float64
    hist = [[np.zeros((H, D))] * 4 for _ in range(3)]
    S = np.zeros((H, D, D), dtype=dt)
    for t in range(T):
        cs = []
        for c, x in enumerate((xq[t], xk[t], xv[t])):
            hist[c] = [r(x)] + hist[c][:3]
            u = r(sum(Wc[c][:, :, tau] * hist[c][tau] for tau in range(4)))
            cs.append(r(u / (1.0 + np.exp(-u))))
        qf = cs[0].astype(dt); kf = cs[1].astype(dt); vf = cs[2].astype(dt)
        qf = qf / np.sqrt((qf * qf).sum(1, keepdims=True) + dt(1e-6)); kf = kf / np.sqrt((kf * kf).sum(1, keepdims=True) + dt(1e-6))
        qf = qf / dt(math.sqrt(D))
        g = -A * np.logaddexp(0.0, r(ar[t]).astype(np.float64) + dt_bias)  # g in float (reference: a.float())
        beta = r(1.0 / (1.0 + np.exp(-r(br[t]))))
        S = S * np.exp(g).astype(dt)[:, None, None]
        mem = np.einsum("hi,hij->hj", kf, S)
        delta = (vf - mem) * beta.astype(dt)[:, None]
        S = S + kf[:, :, None] * delta[:, None, :]
        o = np.einsum("hi,hij->hj", qf, S).astype(np.float64)
        o = r(o)
        zz = r(z[t])
        if emulate_bf16:
            hs = o / np.sqrt((o * o).mean(1, keepdims=True) + 1e-6)
            hs = r(gain[None, :] * r(hs)); y = r(hs * (zz / (1.0 + np.exp(-zz))))
        else:
            y = gain[None, :] * o / np.sqrt((o * o).mean(1, keepdims=True) + 1e-6) * (zz / (1.0 + np.exp(-zz)))
        yield S, o, y

# ---------------------------------------------------------------- self check against head_reference.py at F = 12
def selfcheck():
    import head_reference as HR
    import reference as R
    ih = IntHead(12, 12, H=1)
    n_tok = 0; t0 = time.time(); rows = []
    for dist in ("R1", "R2", "R3", "R4"):
        for seed in range(1, 6):
            head, W, toks = HR.gen(seed, dist, 1024, "random")
            Wi = np.rint(W * 4096).astype(np.int64)
            q = lambda x: np.rint(np.asarray(x) * HR.ONE).astype(np.int64)
            S = np.zeros((D, D), dtype=np.int64); hist = [[np.zeros(D, dtype=np.int64)] * 4 for _ in range(3)]
            ref = []
            for tk in toks:
                xs = [q(tk["xq"]), q(tk["xk"]), q(tk["xv"])]; cs = []
                for c in range(3):
                    hist[c] = [xs[c]] + hist[c][:3]; cs.append(HR.silu_int(HR.conv_int(hist[c], Wi[c])))
                qh, kh, v = HR.l2n_int(cs[0], HR.SQRT_D_Q12), HR.l2n_int(cs[1]), cs[2]
                a, beta = HR.gates_int(q(tk["ar"]), q(tk["br"]), head)
                M, delta, S, o = R.step(S, dict(a=a, beta=beta, k=kh, v=v, q=qh), 12, check=False)
                y, w, ex = HR.gated_norm_int(o, q(tk["z"]).astype(np.float64), 1.0)
                ref.append((S.copy(), o.copy(), y.copy()))
            st = lambda key: np.array([tk[key] for tk in toks])[:, None, :]
            sc = lambda key: np.array([tk[key] for tk in toks])[:, None]
            Wc = W[:, None, :, :]
            gen = run_int(ih, st("xq"), st("xk"), st("xv"), sc("ar"), sc("br"), st("z"), Wc,
                          np.array([head.A]), np.array([head.dt_bias]), np.ones(D), {})
            ok = all(np.array_equal(Si[0], rS) and np.array_equal(oi[0], ro) and np.array_equal(yi[0], ry)
                     for (Si, oi, yi), (rS, ro, ry) in zip(gen, ref))
            n_tok += len(toks); rows.append(dict(dist=dist, seed=seed, steps=len(toks), bit_identical=ok))
            print(dist, seed, "bit_identical", ok, flush=True)
    res = dict(n=len(rows), identical=sum(r["bit_identical"] for r in rows), tokens=n_tok, seconds=round(time.time() - t0, 1), runs=rows)
    (HERE / "runs" / "selfcheck-f12.json").write_text(json.dumps(res, indent=1) + "\n")
    print(json.dumps({k: v for k, v in res.items() if k != "runs"}))
    return res["identical"] == res["n"]

# ---------------------------------------------------------------- real weights
def load_bf16(path, shape):
    raw = np.fromfile(path, dtype="<u2").astype(np.uint32) << 16
    return raw.view(np.float32).reshape(shape).astype(np.float64)

def load_layer(cache, ckpt):
    c = Path(cache) / ckpt; man = json.load(open(HERE / "runs" / f"fetch-{ckpt}.json"))
    L = {}
    for name, m in man["tensors"].items():
        L[name.replace(P + "layers.0.", "")] = load_bf16(c / (name + ".bin"), m["shape"])
    ids = json.load(open(c / "embed_rows.ids.json"))
    E = load_bf16(c / "embed_rows.bin", (len(ids), HID))
    return L, {t: E[i] for i, t in enumerate(ids)}

def inproj(L, emb, ids):
    x = np.stack([emb[t] for t in ids])                               # (T, 5120), BF16 values exact in float64
    w = L["input_layernorm.weight"]
    h = x / np.sqrt((x * x).mean(1, keepdims=True) + 1e-6) * (1.0 + w)  # zero-centred RMSNorm, float64
    qkv = h @ L["linear_attn.in_proj_qkv.weight"].T                   # (T, 10240)
    z = h @ L["linear_attn.in_proj_z.weight"].T
    a = h @ L["linear_attn.in_proj_a.weight"].T; b = h @ L["linear_attn.in_proj_b.weight"].T
    return x, h, qkv, z, a, b

def heads(L, qkv, z, a, b):
    """Split into per-V-head arrays. q/k channel blocks: [0, 2048) q, [2048, 4096) k, [4096, 10240) v.
    V head h reads K head h // 3 (repeat_interleave(3) on the head axis, L631-633)."""
    T = qkv.shape[0]
    kh = np.arange(NV) // (NV // NK)
    qch = (kh[:, None] * D + np.arange(D)[None, :])                   # (48, 128)
    kch = 2048 + qch; vch = 4096 + np.arange(NV)[:, None] * D + np.arange(D)[None, :]
    cw = L["linear_attn.conv1d.weight"][:, 0, :]                      # (10240, 4); torch tap j multiplies x_{t - 3 + j}
    Wc = np.stack([cw[ch][:, :, ::-1] for ch in (qch, kch, vch)])    # (3, 48, 128, 4) in tau order: tau = 3 - j
    xq, xk, xv = qkv[:, qch], qkv[:, kch], qkv[:, vch]                # (T, 48, 128)
    zz = z.reshape(T, NV, D)
    A = np.exp(L["linear_attn.A_log"]); dtb = L["linear_attn.dt_bias"]; gain = L["linear_attn.norm.weight"]
    return xq, xk, xv, a, b, zz, Wc, A, dtb, gain

def rel(a, b):
    nb = float(np.linalg.norm(b)); return float(np.linalg.norm(a - b)) / nb if nb else float("nan")

def run_real(cache, ckpt, out, Fs, tap_eq_F, q_unscaled=False):
    L, emb = load_layer(cache, ckpt)
    prompts = json.load(open(HERE / "prompts.json"))["prompts"]
    fo = open(out, "w"); t0 = time.time()
    for p in prompts:
        ids = p["token_ids"]; T = len(ids)
        x, h, qkv, z, a, b = inproj(L, emb, ids)
        xq, xk, xv, ar, br, zz, Wc, A, dtb, gain = heads(L, qkv, z, a, b)
        # float64 and BF16-emulation passes: keep o, y per token (T x 48 x 128) and the final state only
        of, yf, ob, yb = [], [], [], []
        for (S1, o1, y1), (S2, o2, y2) in zip(run_float(xq, xk, xv, ar, br, zz, Wc, A, dtb, gain),
                                              run_float(xq, xk, xv, ar, br, zz, Wc, A, dtb, gain, emulate_bf16=True)):
            of.append(o1); yf.append(y1); ob.append(o2); yb.append(y2)
        Sl_f, Sl_b = S1.astype(np.float64), S2.astype(np.float64)
        of_a, yf_a, ob_a, yb_a = (np.stack(v) for v in (of, yf, ob, yb))  # (T, H, D)
        ctx = dict(x_absmax=float(np.abs(x).max()), h_absmax=float(np.abs(h).max()), qkv_absmax=float(np.abs(qkv).max()),
                   z_absmax=float(np.abs(z).max()), a_absmax=float(np.abs(a).max()), b_absmax=float(np.abs(b).max()))
        for F in Fs:
            ih = IntHead(F, F if tap_eq_F else 12, q_unscaled=q_unscaled)
            # norm-only arm: the integer gated norm on the float64 o rounded to 2^F (isolates the norm's own error)
            ih_n = IntHead(F)
            yn = np.stack([ih_n.gated_norm(ih_n.q(of_a[t]), ih_n.q(zz[t]), gain)[0] for t in range(T)]) / ih_n.ONE
            t1 = time.time()
            # the float64 pass is rerun in lockstep so the per-token state error needs no stored states
            stats = {}; oi, yi = [], []; maxS = np.zeros(NV); err = None
            try:
                for (Si, o_, y_), (Sf, _, _) in zip(run_int(ih, xq, xk, xv, ar, br, zz, Wc, A, dtb, gain, stats),
                                                    run_float(xq, xk, xv, ar, br, zz, Wc, A, dtb, gain)):
                    maxS = np.maximum(maxS, np.abs(Si / ih.ONE - Sf).reshape(NV, -1).max(1))
                    oi.append(o_); yi.append(y_); Sl_i = Si / ih.ONE
            except OverflowError as e:
                err = str(e)
            if err:
                fo.write(json.dumps(dict(ckpt=ckpt, prompt=p["id"], F=F, tap=ih.TAP, error=err)) + "\n"); continue
            mx, neg = stats["max"], stats["neg"]
            o_div = math.sqrt(D) if q_unscaled else 1.0
            oi_a = np.stack(oi) / ih.ONE / o_div; yi_a = np.stack(yi) / ih.ONE
            o_rms_int = np.sqrt((of_a ** 2).mean(2)) * ih.ONE * o_div          # (T, H) float o RMS in integer units
            for hh in range(NV):
                row = dict(ckpt=ckpt, prompt=p["id"], kind=p["kind"], T=T, F=F, tap=ih.TAP, q_unscaled=q_unscaled, head=hh,
                           norm_only_rel_y=rel(yn[:, hh], yf_a[:, hh]),
                           o_rms_int_median=float(np.median(o_rms_int[:, hh])), o_rms_int_min=float(o_rms_int[:, hh].min()),
                           rel_S=rel(Sl_i[hh], Sl_f[hh]), max_S=float(maxS[hh]), S_f_absmax=float(np.abs(Sl_f[hh]).max()),
                           rel_o=rel(oi_a[:, hh], of_a[:, hh]), max_o=float(np.abs(oi_a[:, hh] - of_a[:, hh]).max()),
                           rel_y=rel(yi_a[:, hh], yf_a[:, hh]), max_y=float(np.abs(yi_a[:, hh] - yf_a[:, hh]).max()),
                           y_f_absmax=float(np.abs(yf_a[:, hh]).max()),
                           bf16_rel_o=rel(ob_a[:, hh], of_a[:, hh]), bf16_rel_y=rel(yb_a[:, hh], yf_a[:, hh]),
                           bf16_rel_S=rel(Sl_b[hh], Sl_f[hh]),
                           max={c: int(mx[c][hh]) for c in CLASSES}, min_exact={c: int(neg[c][hh]) for c in NEGS})
                if hh == 0:
                    row["ctx"] = ctx
                    # layer level (descriptive, added after the first run, Amendment A2): all 48 heads together, i.e. the
                    # 6,144-wide input of out_proj, so small-output heads weigh by their size
                    row["layer"] = dict(rel_y=rel(yi_a, yf_a), rel_o=rel(oi_a, of_a), bf16_rel_y=rel(yb_a, yf_a),
                                        norm_only_rel_y=rel(yn, yf_a))
                fo.write(json.dumps(row) + "\n")
            print(ckpt, p["id"], "T", T, "F", F, "tap", ih.TAP, "s", round(time.time() - t1, 1), flush=True)
        fo.flush()
    fo.close(); print(ckpt, "done", round(time.time() - t0, 1), "s")

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("cmd"); ap.add_argument("args", nargs="*")
    ap.add_argument("--F", default="12,14,16"); ap.add_argument("--tap-eq-F", action="store_true")
    ap.add_argument("--q-unscaled", action="store_true")
    a = ap.parse_args()
    if a.cmd == "selfcheck": sys.exit(0 if selfcheck() else 1)
    if a.cmd == "run":
        cache, ckpt, out = a.args
        run_real(cache, ckpt, out, [int(f) for f in a.F.split(",")], a.tap_eq_F, a.q_unscaled)

if __name__ == "__main__": main()
