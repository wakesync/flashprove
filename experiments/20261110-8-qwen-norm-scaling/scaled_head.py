#!/usr/bin/env python3
"""Generalised integer lowering of one Qwen3.8 Gated DeltaNet layer-0 head (all 48 V heads batched), with every
rounding stage switchable to exact, against PR #68's float64 reference. PREREG.md section "The generalised lowering".

Representation: every integer is held in float64 (or long double in the norm) in integer units. All products and
sums are checked against 2^53 (float64) or 2^63 (long double) before they are formed; a value that could pass
raises OverflowError, it never rounds silently. Divisions by non-powers of two (L2 norm, isqrt, reciprocal) are
floors with an exact integer fix-up. With cfg = M2 at F = 12 this reproduces PR #68's IntHead bit for bit
(`check` mode); with every stage exact it reproduces run_float (`check` mode).

Usage:
  scaled_head.py check <cache> <ckpt> <out.json>
  scaled_head.py run   <cache> <ckpt> <arms.json> <out.jsonl> [--jobs 6] [--arms a,b,...]
"""
import argparse, json, math, sys, time, os
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent
SRC = HERE.parent / "20261109-8-qwen-real-weights"
sys.path.insert(0, str(SRC))
import real_head as RH  # PR #68 code, unchanged: loaders, in_proj, head split, run_float, IntHead

D, NV = 128, 48
L53 = float(2 ** 53)
LD = np.longdouble
L63 = LD(2) ** 63
STAGES = ("in_qkv", "in_ab", "in_z", "conv", "silu", "l2n", "gates", "mem", "delta", "state", "o",
          "sigma", "rc", "w", "cg", "y")

M2 = dict(Fx=12, Fab=12, Fz=12, Fc=12, TAP=12, FS=12, Fk=12, Fq=12, Fg=12, Fw=12, Fy=12, Fcg=12, RC=36,
          rnd="floor", ornd="floor", omode="fixed", Fo=12, smin=0, q_unscaled=False, exact=[])

def chk(x, what, lim=L53):
    m = float(np.max(np.abs(x))) if np.size(x) else 0.0
    if m >= lim: raise OverflowError(f"guard {what}: {m:.3g}")
    return x

def p2(m):
    return np.ldexp(1.0, -np.asarray(m, dtype=np.int64)) if np.ndim(m) else math.ldexp(1.0, -int(m))

def R(x, m, mode):
    """floor(x / 2^m) or round-half-up floor((x + 2^(m-1)) / 2^m); m >= 0 scalar or broadcastable array."""
    s = p2(m)
    if mode == "floor": return np.floor(x * s)
    return np.floor(x * s + 0.5)

def fdiv(n, d):
    """floor(n / d) for float64-held integers, |n|, |d| < 2^53, d > 0, exact."""
    q = np.floor(n / d)
    q = np.where(q * d > n, q - 1, q)
    q = np.where((q + 1) * d <= n, q + 1, q)
    return q

def isqrt_f(N):
    """floor(sqrt(N)) exact for 0 <= N < 2^52 held in float64."""
    s = np.floor(np.sqrt(N))
    s = np.where(s * s > N, s - 1, s)
    s = np.where((s + 1) * (s + 1) <= N, s + 1, s)
    return s

def isqrt_ld(N):
    s = np.floor(np.sqrt(N))
    s = np.where(s * s > N, s - 1, s)
    s = np.where((s + 1) * (s + 1) <= N, s + 1, s)
    return s

def fdiv_ld(n, d):
    q = np.floor(n / d)
    q = np.where(q * d > n, q - 1, q)
    q = np.where((q + 1) * d <= n, q + 1, q)
    return q

class Head:
    def __init__(self, cfg, H=NV):
        c = dict(M2); c.update(cfg); self.c = c; self.H = H
        self.ex = set(c["exact"])
        for s in self.ex: assert s in STAGES, s
        self.FS = np.broadcast_to(np.asarray(c["FS"], dtype=np.int64), (H,)).copy()
        self.Fo = np.broadcast_to(np.asarray(c["Fo"], dtype=np.int64), (H,)).copy() if c["omode"] == "fixed" else None
        assert c["Fg"] >= c["Fk"]

    def q(self, x, F, stage):
        x = np.asarray(x, dtype=np.float64) * math.ldexp(1.0, F)
        return x if stage in self.ex else np.rint(x)

    def l2n(self, u, Fin, Fout, is_q):
        c = self.c
        uL = u.astype(LD)
        n2L = (uL * uL).sum(axis=1)                                   # long double: exact below 2^63
        if float(n2L.max()) >= float(L63): raise OverflowError("guard l2 n2")
        if "l2n" in self.ex:
            n2 = (u * u).sum(axis=1)
            s = np.sqrt(n2 + 1e-6 * 4.0 ** Fin)
            out = u / s[:, None] * math.ldexp(1.0, Fout)
            if is_q and not c["q_unscaled"]: out = out / math.sqrt(D)
            return out
        s = isqrt_ld(n2L + LD(round(1e-6 * 4.0 ** Fin)))
        num = u.astype(LD) * LD(2) ** Fout
        if is_q and not c["q_unscaled"]:
            s = s * LD(round(math.sqrt(D) * 4096)); num = num * LD(4096)
        num2 = 2 * num + s[:, None]
        if float(np.abs(num2).max()) >= float(L63): raise OverflowError("guard l2 num")
        return fdiv_ld(num2, np.broadcast_to(2 * s[:, None], num2.shape)).astype(np.float64)

    def run(self, xq, xk, xv, ar, br, z, Wc, A, dtb, gain, stats):
        """Generator over tokens: yields (S at 2^FS, o at its scale, y at 2^Fy, Fo per head) as float arrays."""
        c, ex, H = self.c, self.ex, self.H
        T = xq.shape[0]
        Wi = Wc * math.ldexp(1.0, c["TAP"])
        if "conv" not in ex: Wi = np.rint(Wi)
        S = np.zeros((H, D, D))
        hist = [[np.zeros((H, D))] * 4 for _ in range(3)]
        FS = self.FS.astype(np.float64)
        mx = {k: np.zeros(H) for k in ("S", "M", "delta", "o", "Sigma", "w", "v", "k_hat", "q_hat", "xin", "ar", "br", "z", "cg", "y",
                                     "sigma", "Rc", "Vx", "shift", "aP", "oRc", "cgw", "aS", "kd")}
        mn = {k: np.full(H, np.inf) for k in ("shift", "Fo")}
        stats["max"], stats["min"] = mx, mn
        def upd(k, arr): mx[k] = np.maximum(mx[k], np.abs(arr).reshape(H, -1).max(axis=1))
        shC = c["TAP"] + c["Fx"] - c["Fc"]
        gain_ = gain[None, :]
        for t in range(T):
            xs = [self.q(xq[t], c["Fx"], "in_qkv"), self.q(xk[t], c["Fx"], "in_qkv"), self.q(xv[t], c["Fx"], "in_qkv")]
            upd("xin", np.stack([np.abs(x).max(axis=1) for x in xs], 1))
            cs = []
            for ch in range(3):
                hist[ch] = [xs[ch]] + hist[ch][:3]
                acc = chk(sum(Wi[ch][:, :, tau] * hist[ch][tau] for tau in range(4)), "conv acc")
                cv = acc * p2(shC) if "conv" in ex else np.floor(acc * p2(shC))
                xr = cv * math.ldexp(1.0, -c["Fc"])
                sv = math.ldexp(1.0, c["Fc"]) * (xr / (1.0 + np.exp(-xr)))
                cs.append(sv if "silu" in ex else np.rint(sv))
            qh = self.l2n(cs[0], c["Fc"], c["Fq"], True)
            kh = self.l2n(cs[1], c["Fc"], c["Fk"], False)
            v = cs[2] * np.ldexp(1.0, (self.FS - c["Fc"]))[:, None]
            if "silu" not in ex: v = np.rint(v)
            ari, bri = self.q(ar[t], c["Fab"], "in_ab"), self.q(br[t], c["Fab"], "in_ab")
            xa = ari * math.ldexp(1.0, -c["Fab"]) + dtb
            a = math.ldexp(1.0, c["Fg"]) * np.exp(-A * np.logaddexp(0.0, xa))
            beta = math.ldexp(1.0, c["Fg"]) / (1.0 + np.exp(-(bri * math.ldexp(1.0, -c["Fab"]))))
            if "gates" not in ex: a, beta = np.rint(a), np.rint(beta)
            # recurrence (M1 staged floor, generalised scales)
            P = chk(np.matmul(kh[:, None, :], S)[:, 0, :], "P")          # exact in float64 (< 2^53)
            aPl = a.astype(LD)[:, None] * P.astype(LD)                    # long double: exact below 2^64
            if float(np.abs(aPl).max()) >= float(L63): raise OverflowError("guard aP")
            upd("aP", aPl.astype(np.float64))
            if "mem" in ex: M = (aPl * LD(2) ** (-(c["Fg"] + c["Fk"]))).astype(np.float64)
            else:
                Ml = aPl * LD(2) ** (-(c["Fg"] + c["Fk"]))
                M = np.floor(Ml if c["rnd"] == "floor" else Ml + LD(0.5)).astype(np.float64)
            dn = chk((v - M) * beta[:, None], "delta num")
            delta = dn * p2(c["Fg"]) if "delta" in ex else R(dn, c["Fg"], c["rnd"])
            aS = chk(a[:, None, None] * S, "aS")
            kd = chk(kh[:, :, None] * delta[:, None, :] * math.ldexp(1.0, c["Fg"] - c["Fk"]), "k delta")
            Sn = aS + kd
            S = Sn * p2(c["Fg"]) if "state" in ex else R(Sn, c["Fg"], c["rnd"])
            Sig = chk(np.matmul(qh[:, None, :], S)[:, 0, :], "Sigma")   # at 2^(Fq + FS), exact (< 2^53)
            Gs = c["Fq"] + self.FS                                # (H,)
            if c["omode"] == "fixed":
                Fo = self.Fo
                sh = Gs - Fo; assert (sh >= 0).all()
                o = Sig * p2(sh)[:, None] if "o" in ex else R(Sig, sh[:, None], c["ornd"])
            else:  # per-token shift witness: smallest s >= 0 with every |floor(Sig / 2^s)| in [-2^17, 2^17)
                smin = int(c["smin"])
                m = np.abs(Sig).max(axis=1)
                s = np.maximum(smin, np.floor(np.log2(np.maximum(m, 1.0))).astype(np.int64) - 17)
                for _ in range(4):
                    oo = np.floor(Sig * p2(s)[:, None])
                    too_big = ((oo < -2 ** 17) | (oo >= 2 ** 17)).any(axis=1)
                    s = np.where(too_big, s + 1, s)
                for _ in range(4):
                    oo = np.floor(Sig * p2(np.maximum(s - 1, 0))[:, None])
                    can = (s > smin) & ~((oo < -2 ** 17) | (oo >= 2 ** 17)).any(axis=1)
                    s = np.where(can, s - 1, s)
                Fo = Gs - s
                o = Sig * p2(s)[:, None] if "o" in ex else np.floor(Sig * p2(s)[:, None])
                upd("shift", s[:, None]); mn["shift"] = np.minimum(mn["shift"], s)
            mn["Fo"] = np.minimum(mn["Fo"], Fo)
            # gated norm (DESIGN 4.4 generalised), long double
            oL = o.astype(LD)
            Vx = (oL * oL).sum(axis=1)
            if float(Vx.max()) >= float(L63): raise OverflowError("guard Vx")
            # eps' = rne(128 x 1e-6 x 2^(2 Fo)); q unscaled: head_reference's rule eps' x 128 (after rounding)
            eps_r = np.array([128 * 1e-6 * 4.0 ** int(f) for f in Fo])
            mul = 128.0 if c["q_unscaled"] else 1.0
            if "sigma" in ex: sig = np.sqrt(Vx + (eps_r * mul).astype(LD))
            else: sig = isqrt_ld(Vx + (np.rint(eps_r) * mul).astype(LD))
            twoRC = LD(2) ** c["RC"]
            Rc = twoRC / sig if "rc" in ex else fdiv_ld(twoRC, sig)
            oRc = oL * Rc[:, None]
            if float(np.abs(oRc).max()) >= float(L63): raise OverflowError("guard oRc")
            wv = oRc * LD(2) ** (c["Fw"] - c["RC"])
            if "w" not in ex: wv = np.floor(wv)
            zi = self.q(z[t], c["Fz"], "in_z")
            zr = zi * math.ldexp(1.0, -c["Fz"])
            cg = math.ldexp(1.0, c["Fcg"]) * gain_ * math.sqrt(D) * zr / (1.0 + np.exp(-zr))
            if "cg" not in ex: cg = np.rint(cg)
            if float(np.abs(cg).max()) * (2.0 ** c["Fw"] + 1) >= float(L63): raise OverflowError("guard cg w")
            cgw = cg.astype(LD) * wv
            yv = cgw * LD(2) ** (c["Fy"] - c["Fw"] - c["Fcg"])
            if "y" not in ex: yv = np.floor(yv)
            y = yv.astype(np.float64); w = wv.astype(np.float64)
            for k, arr in (("S", S), ("M", M), ("delta", delta), ("o", o), ("Sigma", Sig), ("w", w), ("v", v), ("k_hat", kh), ("q_hat", qh),
                           ("ar", ari[:, None]), ("br", bri[:, None]), ("z", zi), ("cg", cg), ("y", y), ("aS", aS), ("kd", kd)):
                upd(k, arr)
            upd("sigma", sig.astype(np.float64)[:, None]); upd("Rc", Rc.astype(np.float64)[:, None]); upd("Vx", Vx.astype(np.float64)[:, None])
            upd("oRc", oRc.astype(np.float64)); upd("cgw", cgw.astype(np.float64))
            yield S, o, y, Fo

# ------------------------------------------------------------------ data
_CACHE = {}
def prompt_data(cache, ckpt, pid):
    pre = Path(os.environ.get("NS_PREP", "/nonexistent")) / f"prep-{ckpt}-{pid}.npz"
    if pre.exists():  # cached in_proj outputs (prep), so workers do not load the layer
        d = np.load(pre)
        p = [p for p in json.load(open(SRC / "prompts.json"))["prompts"] if p["id"] == pid][0]
        return p, d["x"], tuple(d[k] for k in ("xq", "xk", "xv", "ar", "br", "zz", "Wc", "A", "dtb", "gain"))
    key = (cache, ckpt)
    if key not in _CACHE:
        L, emb = RH.load_layer(cache, ckpt)
        _CACHE.clear(); _CACHE[key] = (L, emb)
    L, emb = _CACHE[key]
    p = [p for p in json.load(open(SRC / "prompts.json"))["prompts"] if p["id"] == pid][0]
    x, h, qkv, z, a, b = RH.inproj(L, emb, p["token_ids"])
    return p, x, RH.heads(L, qkv, z, a, b)

def float_ref(cache, ckpt, pid, scratch):
    Path(scratch).mkdir(parents=True, exist_ok=True)
    f = Path(scratch) / f"fref-{ckpt}-{pid}.npz"
    if f.exists():
        d = np.load(f); return d["of"], d["yf"], d["Sf"], d["yb"], d["Sb"]
    p, x, (xq, xk, xv, ar, br, zz, Wc, A, dtb, gain) = prompt_data(cache, ckpt, pid)
    of, yf, yb = [], [], []
    for (S1, o1, y1), (S2, o2, y2) in zip(RH.run_float(xq, xk, xv, ar, br, zz, Wc, A, dtb, gain),
                                          RH.run_float(xq, xk, xv, ar, br, zz, Wc, A, dtb, gain, emulate_bf16=True)):
        of.append(o1); yf.append(y1); yb.append(y2)
    out = (np.stack(of), np.stack(yf), S1.astype(np.float64), np.stack(yb), S2.astype(np.float64))
    np.savez(f, of=out[0], yf=out[1], Sf=out[2], yb=out[3], Sb=out[4])
    return out

def rel(a, b):
    nb = float(np.linalg.norm(b)); return float(np.linalg.norm(a - b)) / nb if nb else float("nan")

def prep(cache, ckpt, outdir):
    """Cache x and the per-head in_proj outputs of every prompt (PR #68's inproj() and heads(), unchanged)."""
    Path(outdir).mkdir(parents=True, exist_ok=True)
    for p in json.load(open(SRC / "prompts.json"))["prompts"]:
        _, x, hd = prompt_data(cache, ckpt, p["id"])
        np.savez(Path(outdir) / f"prep-{ckpt}-{p['id']}.npz", x=x, **dict(zip(("xq", "xk", "xv", "ar", "br", "zz", "Wc", "A", "dtb", "gain"), hd)))
        print("prep", ckpt, p["id"], flush=True)

# ------------------------------------------------------------------ checks
def check(cache, ckpt, out, scratch):
    prompts = [p["id"] for p in json.load(open(SRC / "prompts.json"))["prompts"]]
    res = dict(bit_identical={}, all_exact={})
    for pid in prompts:
        p, x, (xq, xk, xv, ar, br, zz, Wc, A, dtb, gain) = prompt_data(cache, ckpt, pid)
        ih = RH.IntHead(12, 12)
        ok = True; n = 0
        for (Si, oi, yi), (Sn, on, yn, _) in zip(RH.run_int(ih, xq, xk, xv, ar, br, zz, Wc, A, dtb, gain, {}),
                                                 Head({}).run(xq, xk, xv, ar, br, zz, Wc, A, dtb, gain, {})):
            ok &= np.array_equal(Si.astype(np.float64), Sn) and np.array_equal(oi.astype(np.float64), on) and np.array_equal(yi.astype(np.float64), yn)
            n += 1
        res["bit_identical"][pid] = dict(tokens=n, identical=bool(ok))
        of, yf, Sf, _, _ = float_ref(cache, ckpt, pid, scratch)
        ys = []
        for Sn, on, yn, _ in Head(dict(exact=list(STAGES))).run(xq, xk, xv, ar, br, zz, Wc, A, dtb, gain, {}):
            ys.append(yn)
        ys = np.stack(ys) / 4096.0
        ry = max(rel(ys[:, h], yf[:, h]) for h in range(NV)); rs = max(rel(Sn[h] / 4096.0, Sf[h]) for h in range(NV))
        res["all_exact"][pid] = dict(max_rel_y=ry, max_rel_S=rs)
        print(pid, res["bit_identical"][pid], res["all_exact"][pid], flush=True)
    res["pass_a"] = all(v["identical"] for v in res["bit_identical"].values())
    res["pass_b"] = all(v["max_rel_y"] < 1e-9 and v["max_rel_S"] < 1e-9 for v in res["all_exact"].values())
    Path(out).write_text(json.dumps(res, indent=1) + "\n"); print(res["pass_a"], res["pass_b"])
    return res["pass_a"] and res["pass_b"]

# ------------------------------------------------------------------ arms
def resolve(arm, pid, calib):
    """Fill per-head calibrated scales (leave-one-prompt-out) from C0 rows."""
    cfg = dict(arm["cfg"])
    if "Fo_loo" in arm:  # C2: Fo_h = min(cap, 12 + floor(log2(2^17 / maxo_h)))
        cap = arm["Fo_loo"]["cap"]; base = arm["Fo_loo"].get("base", 12)
        m = np.array([max(calib[(q, h)]["o"] for q in calib["prompts"] if q != pid) for h in range(NV)], dtype=float)
        cfg["Fo"] = [int(min(cap, base + math.floor(math.log2(2 ** 17 / max(v, 1.0))))) for v in m]
    if "FS_loo" in arm:  # X1: FS_h = 12 + min(cap, floor(log2(2^17 / max(S, M, delta, v)_h)))
        cap = arm["FS_loo"]["cap"]
        m = np.array([max(max(calib[(q, h)][k] for k in ("S", "M", "delta", "v")) for q in calib["prompts"] if q != pid) for h in range(NV)], dtype=float)
        cfg["FS"] = [int(12 + max(0, min(cap, math.floor(math.log2(2 ** 17 / max(v, 1.0)))))) for v in m]
    return cfg

def load_calib():
    rows = [json.loads(l) for l in open(SRC / "runs" / "real-stock.jsonl")]
    rows = [r for r in rows if r["F"] == 12 and "error" not in r]
    cal = {(r["prompt"], r["head"]): r["max"] for r in rows}
    cal["prompts"] = sorted({r["prompt"] for r in rows})
    return cal

_WO = {}
def task(args):
    cache, ckpt, name, arm, pid, scratch = args
    t0 = time.time()
    p, x, (xq, xk, xv, ar, br, zz, Wc, A, dtb, gain) = prompt_data(cache, ckpt, pid)
    of, yf, Sf, yb, Sb = float_ref(cache, ckpt, pid, scratch)
    if ckpt not in _WO:
        man = json.load(open(HERE / "runs" / f"fetch-{ckpt}.json"))
        nm = "model.language_model.layers.0.linear_attn.out_proj.weight"
        _WO[ckpt] = RH.load_bf16(Path(cache) / ckpt / (nm + ".bin"), man["tensors"][nm]["shape"]).astype(np.float32)
    Wo = _WO[ckpt]
    cfg = resolve(arm, pid, load_calib()) if ("Fo_loo" in arm or "FS_loo" in arm) else arm["cfg"]
    hd = Head(cfg); st = {}
    T = len(p["token_ids"]); ys = []; os_ = []; err = None
    try:
        for S, o, y, Fo in hd.run(xq, xk, xv, ar, br, zz, Wc, A, dtb, gain, st):
            ys.append(y)
    except OverflowError as e:
        err = str(e)
    if err:
        return [dict(arm=name, ckpt=ckpt, prompt=pid, error=err)]
    c = hd.c
    yi = np.stack(ys) * math.ldexp(1.0, -c["Fy"])
    Si = S * np.ldexp(1.0, -hd.FS)[:, None, None]
    rows = []
    mx, mn = st["max"], st["min"]
    for h in range(NV):
        rows.append(dict(arm=name, ckpt=ckpt, prompt=pid, T=T, head=h, rel_y=rel(yi[:, h], yf[:, h]), rel_S=rel(Si[h], Sf[h]),
                         bf16_rel_y=rel(yb[:, h], yf[:, h]), bf16_rel_S=rel(Sb[h], Sf[h]),
                         FS=int(hd.FS[h]), Fo_min=float(mn["Fo"][h]),
                         max={k: float(v[h]) for k, v in mx.items()}, shift_min=float(mn["shift"][h]) if np.isfinite(mn["shift"][h]) else None))
    # layer level and residual stream (descriptive)
    X = x.astype(np.float32); nx = np.linalg.norm(X, axis=1)
    def resid(Y):
        E = (Y.reshape(T, -1).astype(np.float32) - yf.reshape(T, -1).astype(np.float32)) @ Wo.T
        e = np.linalg.norm(E, axis=1) / nx
        return dict(frob=float(np.linalg.norm(E) / np.linalg.norm(X)), tok_median=float(np.median(e)), tok_max=float(e.max()))
    Rf = (yf.reshape(T, -1).astype(np.float32) @ Wo.T)
    rows[0]["layer"] = dict(rel_y=rel(yi, yf), bf16_rel_y=rel(yb, yf),
                            resid=resid(yi), resid_bf16=resid(yb),
                            mixer_over_resid=dict(frob=float(np.linalg.norm(Rf) / np.linalg.norm(X)),
                                                  tok_median=float(np.median(np.linalg.norm(Rf, axis=1) / nx))),
                            seconds=round(time.time() - t0, 1))
    return rows

def past(deadline):
    """deadline 'HHMM' UTC today (the lane runs 01:26Z to 04:26Z); '' = none."""
    return bool(deadline) and time.strftime("%H%M", time.gmtime()) >= deadline

def run(cache, ckpt, arms_file, out, jobs, only, scratch, only_prompts=None, deadline="", skip_done=False):
    from multiprocessing import Pool
    arms = json.load(open(arms_file))
    names = [n for n in arms if (not only or n in only)]
    if skip_done and Path(out).exists():  # arms that already have rows in the output file are not run again
        have = {json.loads(l)["arm"] for l in open(out)}
        names = [n for n in names if n not in have]
    if not names: print("nothing to run", flush=True); return
    prompts = json.load(open(SRC / "prompts.json"))["prompts"]
    pids = [p["id"] for p in sorted(prompts, key=lambda p: -len(p["token_ids"])) if not only_prompts or p["id"] in only_prompts]
    with Pool(jobs) as pool:  # float references first (cached in scratch)
        pool.starmap(float_ref, [(cache, ckpt, pid, scratch) for pid in pids])
    # Arms go in groups of `jobs` (file order); inside a group the tasks are longest prompt first. The PREREG cut-off
    # ("no new arm starts after ...") is checked before each group, so every arm that starts runs on all 10 prompts.
    t0 = time.time(); k = 0; total = len(names) * len(pids); started = []
    with open(out, "a") as fo, Pool(jobs) as pool:
        for g in range(0, len(names), jobs):
            grp = names[g:g + jobs]
            if past(deadline):
                print("CUT-OFF", deadline, "UTC: arms not started:", ",".join(names[g:]), flush=True)
                with open(str(out) + ".notrun", "a") as nf: nf.write(json.dumps(names[g:]) + "\n")
                break
            started += grp
            tasks = [(cache, ckpt, n, arms[n], pid, scratch) for pid in pids for n in grp]
            for rows in pool.imap_unordered(task, tasks):
                for r in rows: fo.write(json.dumps(r) + "\n")
                fo.flush(); k += 1
                print(k, "/", total, rows[0]["arm"], rows[0]["prompt"], round(time.time() - t0, 1), "error" in rows[0], flush=True)
    print("arms run:", ",".join(started), flush=True)

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("cmd"); ap.add_argument("args", nargs="*")
    ap.add_argument("--jobs", type=int, default=6); ap.add_argument("--arms", default=""); ap.add_argument("--prompts", default=""); ap.add_argument("--deadline", default=""); ap.add_argument("--skip-done", action="store_true")
    ap.add_argument("--scratch", default=os.environ.get("NS_SCRATCH", "/tmp"))
    a = ap.parse_args()
    if a.cmd == "prep":
        cache, ckpt, outdir = a.args; prep(cache, ckpt, outdir)
    if a.cmd == "check":
        cache, ckpt, out = a.args; sys.exit(0 if check(cache, ckpt, out, a.scratch) else 1)
    if a.cmd == "run":
        cache, ckpt, arms, out = a.args
        run(cache, ckpt, arms, out, a.jobs, set(a.arms.split(",")) if a.arms else None, a.scratch,
            set(a.prompts.split(",")) if a.prompts else None, a.deadline, a.skip_done)

if __name__ == "__main__": main()
