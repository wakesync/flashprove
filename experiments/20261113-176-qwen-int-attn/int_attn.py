#!/usr/bin/env python3
"""Integer attention (docs/model.md section 6, steps 2 clamp only, 3, 4) on Qwen3.8-27B's 16 full-attention layers,
open loop on a float64 REF stream (PREREG.md, this directory). CPU only, no proof.

REF: PR #88's float64 forward (`q1_forward.py`, imported unchanged): DeltaNet heads by `head_out(.., "REF")` in spawned
workers via PR #124's `e2e.head_task` and `e2e.make_pool` (imported unchanged), REF's own attention by
`q1_forward.attention` (unchanged). At each full-attention layer both arms (C2047, C1665) run on REF's input x_l.

Lowered (both arms): rotated q (score scale 1/16 folded in), k, v -> integer head output o. Float64: projections, input
norm, q/k RMSNorm, partial rotary, sigmoid gate, o_proj (copied from `q1_forward.attention`, checked bit-equal to it).

Usage:
  int_attn.py synth <out.json>             debug: integer core vs a pure Python-int reference, RNE/clamp/fit on synthetic data
  int_attn.py fixture <scratch> <outdir>   debug: "The capital of Italy is" (not in the suite), stock layers 0..3
  int_attn.py run <scratch> <runs>         registered run (resumes from <scratch>/ckpt.npz)
"""
import json, math, os, resource, shutil, sys, time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent
EXP = HERE.parent
sys.path.insert(0, str(EXP / "20261110-8-qwen-q1-deep-fidelity"))
sys.path.insert(0, str(EXP / "20261111-8-qwen-e2e-agreement"))
import q1_forward as F   # PR #88, unchanged
import e2e as E          # PR #124, unchanged (head_task, make_pool)

NH, NKV, HD, ROT, THETA, NL = F.NH, F.NKV, F.HD, F.ROT, F.THETA, F.NL
ARMS = {"C2047": 2047, "C1665": 1665}
EXPS, RX = 12, 8           # softmax table scale and step exponents (the standard form's values)
SH_MIN, SH_MAX = 4, 12     # af-policy-sh
DET_PROMPTS = ("p01-ordinary-short", "p09-multilingual")
DISK_FLOOR = 21e9
ATT_LAYERS = [i for i in range(NL) if F.layer_type(i) == "full_attention"]

def ex_table():
    """EX[u] = rne(2^expS exp(-u / 2^rx)) for u < u0 (docs/model.md section 4, item 2)."""
    t = []
    u = 0
    while True:
        v = float(np.rint(math.ldexp(1.0, EXPS) * math.exp(-u / math.ldexp(1.0, RX))))
        if v == 0: return np.array(t, dtype=np.int64), u
        t.append(int(v)); u += 1

EX, U0 = ex_table()

# ------------------------------------------------------------------ float attention, split (copy of q1_forward.attention)
def attn_parts(L, x):
    T = x.shape[0]
    h = F.rms0(x, L["input_layernorm.weight"])
    qg = (h @ L["self_attn.q_proj.weight"].T).reshape(T, NH, 2 * HD)
    q, gate = qg[:, :, :HD], qg[:, :, HD:].reshape(T, NH * HD)
    q = F.rms0(q, L["self_attn.q_norm.weight"])
    k = F.rms0((h @ L["self_attn.k_proj.weight"].T).reshape(T, NKV, HD), L["self_attn.k_norm.weight"])
    v = (h @ L["self_attn.v_proj.weight"].T).reshape(T, NKV, HD)
    inv = 1.0 / (THETA ** (np.arange(0, ROT, 2, dtype=np.float64) / ROT))
    fr = np.arange(T, dtype=np.float64)[:, None] * inv[None, :]
    emb = np.concatenate([fr, fr], -1); cos, sin = np.cos(emb)[:, None, :], np.sin(emb)[:, None, :]
    def rope(u):
        r, p = u[..., :ROT], u[..., ROT:]
        rh = np.concatenate([-r[..., ROT // 2:], r[..., :ROT // 2]], -1)
        return np.concatenate([r * cos + rh * sin, p], -1)
    q, k = rope(q), rope(k)
    return q, k, v, gate

def float_o(q, k, v):
    T = q.shape[0]
    kv = np.arange(NH) // (NH // NKV)
    s = np.einsum("thd,uhd->htu", q, k[:, kv]) / math.sqrt(HD)
    s = np.where(np.tril(np.ones((T, T), bool))[None], s, -np.inf)
    s = s - s.max(-1, keepdims=True); p = np.exp(s); p /= p.sum(-1, keepdims=True)
    return np.einsum("htu,uhd->thd", p, v[:, kv])           # (T, NH, HD), before reshape and gate

def finish(L, o, gate):
    T = o.shape[0]
    o = o.reshape(T, NH * HD)
    o = o * (1.0 / (1.0 + np.exp(-gate)))
    return o @ L["self_attn.o_proj.weight"].T

# ------------------------------------------------------------------ integer pieces
def cell_exp(mx, cl):
    """Largest integer E with mx * 2^E <= cl (scales/README.md, 'The exponent of each cell', step 1)."""
    if not (mx > 0): return 30
    E = int(math.floor(math.log2(cl / mx)))
    while mx * math.ldexp(1.0, E + 1) <= cl: E += 1
    while mx * math.ldexp(1.0, E) > cl: E -= 1
    return E

def fit(mxq, mxk, mxv, cl):
    """Per-layer exponents and sh (PREREG step 2, 3). Returns dict with the adjustment logged."""
    Eq, Ek, Ev = cell_exp(mxq, cl), cell_exp(mxk, cl), cell_exp(mxv, cl)
    sh0 = Eq + Ek - RX; adj = None; sh = sh0; Eq0 = Eq
    if sh > SH_MAX: sh = SH_MAX; Eq = RX + SH_MAX - Ek; adj = "sh>12: q coarser"
    elif sh < SH_MIN: sh = SH_MIN; Eq = RX + SH_MIN - Ek; adj = "sh<4: q finer, clamps possible"
    return dict(Eq=Eq, Ek=Ek, Ev=Ev, sh=sh, sh_fit=sh0, Eq_fit=Eq0, adjust=adj)

def quant(x, E, cl):
    w = np.rint(np.ldexp(x, E))                  # RNE, ties to even
    return np.clip(w, -cl, cl), w

def int_core(q, k, v, sh, ex=EX, u0=U0):
    """docs/model.md 6 step 4. q (T,H,dh), k, v (T,G,dh): integer-valued float64 arrays. Returns o (T,H,dh) int64 and
    stats. Scores and accumulators by float64 BLAS: every product and partial sum is an integer below 2^53."""
    T, H, dh = q.shape; G = k.shape[1]; kv = np.arange(H) // (H // G)
    Q = q.transpose(1, 0, 2); K = k[:, kv].transpose(1, 0, 2); V = v[:, kv].transpose(1, 0, 2)
    S = Q @ K.transpose(0, 2, 1)                                 # (H, T, T)
    mask = np.tril(np.ones((T, T), bool))[None]
    smax_abs = float(np.abs(np.where(mask, S, 0)).max())
    assert smax_abs < 2.0 ** 52 and np.array_equal(S, np.rint(S)), "score not an exact integer"
    m = np.where(mask, S, -np.inf).max(-1, keepdims=True)
    d = np.where(mask, m - S, 0.0)
    u = np.floor(np.ldexp(d, -sh)).astype(np.int64)
    inrange = mask & (u < u0)
    e = np.where(inrange, ex[np.minimum(u, u0 - 1)], 0).astype(np.float64)
    zeros = int((mask & ~inrange).sum())
    Z = e.sum(-1)                                                # (H, T)
    acc = e @ V                                                  # (H, T, dh)
    assert float(np.abs(acc).max()) < 2.0 ** 52 and np.array_equal(acc, np.rint(acc)), "acc not an exact integer"
    Zi = Z.astype(np.int64)[..., None]; ai = acc.astype(np.int64)
    o = (2 * ai + Zi) // (2 * Zi)                                # floor division (numpy // floors)
    return o.transpose(1, 0, 2), dict(max_abs_s=smax_abs, e_zero=zeros, causal=int(mask.sum()) * H)

def arm_prompt(q, k, v, ex_, cl):
    """One arm on one prompt: q rotated (T,NH,HD) unscaled; returns o_arm float (T,NH,HD), int o, stats."""
    qq, qw = quant(q / math.sqrt(HD), ex_["Eq"], cl)
    kk, kw = quant(k, ex_["Ek"], cl)
    vv, vw = quant(v, ex_["Ev"], cl)
    o, st = int_core(qq, kk, vv, ex_["sh"])
    st.update(
        q_over=int((np.abs(qw) > cl).sum()), q_n=int(qw.size), k_over=int((np.abs(kw) > cl).sum()), k_n=int(kw.size),
        v_over=int((np.abs(vw) > cl).sum()), v_n=int(vw.size),
        q_maxw=int(np.abs(qw).max()), k_maxw=int(np.abs(kw).max()), v_maxw=int(np.abs(vw).max()),
        wide_over_32767=int((np.abs(qw) > 32767).sum() + (np.abs(kw) > 32767).sum() + (np.abs(vw) > 32767).sum()))
    return np.ldexp(o.astype(np.float64), -ex_["Ev"]), o, st

def rel_heads(a, b):
    num = np.sqrt(((a - b) ** 2).sum(axis=(0, 2))); den = np.sqrt((b ** 2).sum(axis=(0, 2)))
    return [float(x / y) if y else float("nan") for x, y in zip(num, den)]

def rel(a, b):
    nb = float(np.linalg.norm(b)); return float(np.linalg.norm(a - b)) / nb if nb else float("nan")

def log(path, obj):
    with open(path, "a") as f: f.write(json.dumps(obj) + "\n")

def now(): return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

def rss_gb(): return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1e6

# ------------------------------------------------------------------ one attention layer, both arms
def attention_layer(i, L, X, runs, det=True):
    """X: {pid: x}. Records metrics into runs/, returns {pid: REF mix} (from q1_forward.attention, unchanged)."""
    t0 = time.time(); parts = {}; ofl = {}; mixf = {}
    for pid, x in X.items():
        q, k, v, gate = attn_parts(L, x)
        parts[pid] = (q, k, v, gate); ofl[pid] = float_o(q, k, v)
    t_float = time.time() - t0
    ref_mix, bit_eq = {}, {}
    for pid, x in X.items():
        ref_mix[pid] = F.attention(L, x)
        mixf[pid] = finish(L, ofl[pid], parts[pid][3])
        bit_eq[pid] = bool(np.array_equal(mixf[pid], ref_mix[pid]))
    t_ref = time.time() - t0 - t_float
    mxq = max(float(np.abs(p[0]).max()) for p in parts.values()) / math.sqrt(HD)
    mxk = max(float(np.abs(p[1]).max()) for p in parts.values())
    mxv = max(float(np.abs(p[2]).max()) for p in parts.values())
    for arm, cl in ARMS.items():
        ta = time.time(); ex_ = fit(mxq, mxk, mxv, cl); rows = []; allrel = []
        tot = dict(q_over=0, q_n=0, k_over=0, k_n=0, v_over=0, v_n=0, e_zero=0, causal=0, wide_over_32767=0)
        mx = dict(q_maxw=0, k_maxw=0, v_maxw=0, max_abs_s=0.0)
        oint = {}
        for pid in X:
            q, k, v, gate = parts[pid]
            oa, oi, st = arm_prompt(q, k, v, ex_, cl)
            if pid in DET_PROMPTS: oint[pid] = oi
            rh = rel_heads(oa, ofl[pid]); allrel += rh
            mix_rel = rel(finish(L, oa, gate), mixf[pid])
            for h, r in enumerate(rh): log(runs / "cells.jsonl", dict(arm=arm, layer=i, prompt=pid, head=h, rel_y=r))
            log(runs / "prompt-rows.jsonl", dict(arm=arm, layer=i, prompt=pid, T=int(q.shape[0]), mix_rel=mix_rel, **st))
            for kk in tot: tot[kk] += st[kk]
            for kk in mx: mx[kk] = max(mx[kk], st[kk])
        dets = {}
        if det and arm == "C2047":
            for pid in DET_PROMPTS:
                if pid in X:
                    q, k, v, gate = parts[pid]
                    _, oi2, _ = arm_prompt(q, k, v, ex_, cl)
                    dets[pid] = bool(np.array_equal(oi2, oint[pid]))
        a = np.array(allrel)
        row = dict(t=now(), arm=arm, layer=i, clamp=cl, Smax=HD * cl * cl, mx_q=mxq, mx_k=mxk, mx_v=mxv, **ex_, **tot, **mx,
                   n_pairs=int(a.size), rel_median=float(np.median(a)), rel_max=float(a.max()), rel_min=float(a.min()),
                   n_over_001=int((a > 0.01).sum()), n_over_005=int((a > 0.05).sum()),
                   layer_pass=bool(np.median(a) <= 0.01 and a.max() <= 0.05), det_bit_equal=dets,
                   arm_seconds=round(time.time() - ta, 1))
        log(runs / "layers.jsonl", row)
        print(arm, "layer", i, "sh", ex_["sh"], "E", ex_["Eq"], ex_["Ek"], ex_["Ev"], "median", round(row["rel_median"], 5),
              "max", round(row["rel_max"], 5), "pass", row["layer_pass"], flush=True)
    log(runs / "attn-timing.jsonl", dict(t=now(), layer=i, float_s=round(t_float, 1), ref_attention_s=round(t_ref, 1),
                                          total_s=round(time.time() - t0, 1), mix_bit_equal_q1=bit_eq, peak_rss_gb_self=rss_gb()))
    return ref_mix

# ------------------------------------------------------------------ REF forward driver
def deltanet_layer(L, X, pool):
    pend = [pool.apply_async(E.head_task, ("REF", pid, F.deltanet_inputs(L, x))) for pid, x in X.items()]
    Wo = L["linear_attn.out_proj.weight"]
    for r in pend:
        p, pid, y, relh, err = r.get()
        if err is not None: raise RuntimeError(f"REF head error {pid}: {err}")
        x = X[pid] + y.reshape(y.shape[0], -1) @ Wo.T
        X[pid] = x + F.mlp(L, x)

def save_state(path, X, meta):
    tmp = Path(str(path) + ".tmp.npz")
    np.savez(tmp, __meta__=np.frombuffer(json.dumps(meta).encode(), dtype=np.uint8), **X)
    os.replace(tmp, path)

def load_state(path):
    d = np.load(path); meta = json.loads(bytes(d["__meta__"]).decode())
    return {k: d[k] for k in d.files if k != "__meta__"}, meta

def disk_ok(p):
    return shutil.disk_usage(p).free >= DISK_FLOOR

def forward(X, layers, ckpts, sc, runs, pool, meta, last, record=True):
    """layers: list of (i, ckpt). Runs REF; at attention layers records x and runs the arms. Stops after layer `last`."""
    fetch_ex = ThreadPoolExecutor(1)
    todo = [(i, ck) for i, ck in layers if i >= meta["next_layer"] and i <= last]
    sub = lambda n: fetch_ex.submit(ckpts[todo[n][1]].layer, todo[n][0])
    fut = sub(0) if todo else None
    for n, (i, ck) in enumerate(todo):
        tw = time.time(); L = fut.result(); wait = time.time() - tw
        ckpts[ck].save()
        fut = sub(n + 1) if n + 1 < len(todo) else None
        t0 = time.time()
        if F.layer_type(i) == "linear_attention":
            deltanet_layer(L, X, pool)
        else:
            if record: np.savez(Path(sc) / f"xin-{i:02d}.npz", **X)
            mix = attention_layer(i, L, X, runs)
            if i == last: X = None
            else:
                for pid in X:
                    x = X[pid] + mix[pid]; X[pid] = x + F.mlp(L, x)
        del L
        if X is not None:
            meta.update(next_layer=i + 1); save_state(Path(sc) / "ckpt.npz", X, meta)
        free = shutil.disk_usage(sc).free
        log(runs / "progress.log", dict(t=now(), layer=i, ckpt=ck, type=F.layer_type(i), fetch_wait_s=round(wait, 1),
                                         layer_s=round(time.time() - t0, 1), disk_free_gb=round(free / 1e9, 1), peak_rss_gb_self=rss_gb()))
        print("layer", i, ck, F.layer_type(i), "wait", round(wait, 1), "s", round(time.time() - t0, 1), flush=True)
        if free < DISK_FLOOR:
            log(runs / "progress.log", dict(t=now(), stop="disk floor", disk_free_gb=round(free / 1e9, 1))); raise SystemExit(3)
        if X is None: break
    fetch_ex.shutdown()

def cmd_run(scratch, runs):
    sc = Path(scratch); runs = Path(runs); sc.mkdir(parents=True, exist_ok=True); runs.mkdir(parents=True, exist_ok=True)
    if not disk_ok(sc): log(runs / "progress.log", dict(t=now(), stop="disk floor at start")); raise SystemExit(3)
    prompts = json.load(open(EXP / "20261111-8-qwen-e2e-agreement" / "prompts-e2e.json"))
    ckpts = {"stock": F.Ckpt("stock", runs), "abl": F.Ckpt("abl", runs)}
    pool = E.make_pool()
    if (sc / "ckpt.npz").exists():
        X, meta = load_state(sc / "ckpt.npz"); log(runs / "progress.log", dict(t=now(), resume=True, meta=meta))
    else:
        ids = sorted({t for p in prompts["prompts"] for t in p["token_ids"]})
        emb = ckpts["stock"].emb_rows(ids); ckpts["stock"].save()
        X = {p["id"]: np.stack([emb[t] for t in p["token_ids"]]) for p in prompts["prompts"]}
        meta = dict(next_layer=0)
        log(runs / "progress.log", dict(t=now(), start=True, prompts={k: int(v.shape[0]) for k, v in X.items()},
                                         u0=U0, ex0=int(EX[0]), arms=ARMS))
    layers = [(i, "stock" if i <= 16 else "abl") for i in range(NL)]
    forward(X, layers, ckpts, sc, runs, pool, meta, last=ATT_LAYERS[-1])
    pool.close(); pool.join()
    log(runs / "progress.log", dict(t=now(), all_done=True, peak_rss_gb_self=rss_gb()))

def cmd_fixture(scratch, out):
    """Debug only (PREREG): fixture tokens, stock layers 0..3; float split bit-equal to q1_forward.attention; save/load."""
    sc = Path(scratch); out = Path(out); sc.mkdir(parents=True, exist_ok=True); out.mkdir(parents=True, exist_ok=True)
    C = F.Ckpt("stock", out); pool = E.make_pool()
    emb = C.emb_rows(F.FIXTURE); X = {"fx": np.stack([emb[t] for t in F.FIXTURE]), "fx2": np.stack([emb[t] for t in F.FIXTURE])}
    meta = dict(next_layer=0)
    forward(X, [(i, "stock") for i in range(4)], {"stock": C}, sc, out, pool, meta, last=3, record=False)
    pool.close(); pool.join()
    tim = [json.loads(l) for l in open(out / "attn-timing.jsonl")]
    lay = [json.loads(l) for l in open(out / "layers.jsonl")]
    Xs, m2 = load_state(sc / "ckpt.npz")
    ok = all(all(r["mix_bit_equal_q1"].values()) for r in tim) and m2["next_layer"] == 3
    res = dict(ok=bool(ok), mix_bit_equal=[r["mix_bit_equal_q1"] for r in tim],
               layers=[{k: r[k] for k in ("arm", "layer", "sh", "Eq", "Ek", "Ev", "adjust", "rel_median", "rel_max")} for r in lay],
               state_next_layer=m2["next_layer"], peak_rss_gb_self=rss_gb())
    (out / "fixture.json").write_text(json.dumps(res, indent=1) + "\n")
    print(json.dumps(res), flush=True)
    if not ok: raise SystemExit(4)

# ------------------------------------------------------------------ synthetic checks (no weights)
def py_ref(q, k, v, sh, ex, u0):
    T, H, dh = len(q), len(q[0]), len(q[0][0]); G = len(k[0]); o = [[[0] * dh for _ in range(H)] for _ in range(T)]
    for h in range(H):
        g = h // (H // G)
        for i in range(T):
            s = [sum(q[i][h][c] * k[j][g][c] for c in range(dh)) for j in range(i + 1)]
            m = max(s); e = []
            for sj in s:
                u = (m - sj) // (1 << sh); e.append(ex[u] if u < u0 else 0)
            Z = sum(e)
            for c in range(dh):
                acc = sum(e[j] * v[j][g][c] for j in range(i + 1))
                o[i][h][c] = (2 * acc + Z) // (2 * Z)
    return o

def cmd_synth(out):
    rng = np.random.default_rng(0); res = dict(core=[], quant=None, fit=[])
    exl = [int(t) for t in EX]
    for (T, H, G, dh, cl, sh) in [(7, 6, 1, 8, 2047, 4), (9, 6, 2, 16, 1665, 8), (5, 4, 4, 4, 2047, 12), (12, 6, 3, 8, 1665, 6)]:
        q = rng.integers(-cl, cl + 1, (T, H, dh)); k = rng.integers(-cl, cl + 1, (T, G, dh)); v = rng.integers(-cl, cl + 1, (T, G, dh))
        o, st = int_core(q.astype(np.float64), k.astype(np.float64), v.astype(np.float64), sh)
        r = py_ref(q.tolist(), k.tolist(), v.tolist(), sh, exl, U0)
        res["core"].append(dict(T=T, H=H, G=G, dh=dh, clamp=cl, sh=sh, equal=bool(np.array_equal(o, np.array(r))), e_zero=st["e_zero"]))
    x = np.array([0.5, 1.5, 2.5, -0.5, -1.5, 3000.0, -3000.0, 2047.4, 2047.6, 1665.5])
    c, w = quant(x, 0, 1665)
    res["quant"] = dict(w=w.tolist(), clamped=c.tolist(), over=int((np.abs(w) > 1665).sum()),
                        ok=w.tolist() == [0, 2, 2, -0, -2, 3000, -3000, 2047, 2048, 1666] and int((np.abs(w) > 1665).sum()) == 5)
    for mx, cl in [(1.0, 2047), (2047.0, 2047), (2047.0001, 2047), (0.37, 1665), (1665.0, 1665), (3.2, 1665)]:
        E_ = cell_exp(mx, cl); res["fit"].append(dict(mx=mx, cl=cl, E=E_, ok=bool(mx * 2.0 ** E_ <= cl < mx * 2.0 ** (E_ + 1))))
    res["sh_rule"] = [fit(0.37, 30.0, 5.0, 2047), fit(0.002, 0.004, 5.0, 2047), fit(3.0, 3.0, 3.0, 1665)]
    res["u0"] = U0; res["ex0"] = int(EX[0]); res["ex_last"] = int(EX[-1])
    res["ok"] = all(r["equal"] for r in res["core"]) and res["quant"]["ok"] and all(r["ok"] for r in res["fit"]) and U0 == 2307
    Path(out).write_text(json.dumps(res, indent=1) + "\n"); print(json.dumps(res["ok"]))
    if not res["ok"]: raise SystemExit(4)

if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "synth": cmd_synth(sys.argv[2])
    elif cmd == "fixture": cmd_fixture(sys.argv[2], sys.argv[3])
    elif cmd == "run": cmd_run(sys.argv[2], sys.argv[3])
    else: raise SystemExit(__doc__)
