#!/usr/bin/env python3
"""End-to-end, teacher-forced token agreement with the M3 integer MLP in all 64 layers (PREREG.md).

The MLP lowering is the M3 design's (experiments/20261109-32-qwen-m3-design/DESIGN.md 5.0, 5.1, 5.2, 5.5; PR #70):
  m   = RNE(2^F m_float)                          F = 12, m_float = float64 post-attention RMSNorm output (with gain)
  W   = RNE(2^e W_float), e per tensor = largest e with RNE(2^e max|W|) <= 4095    (bounds.py completeness_check rule)
  gw  = floor(m . Wg / 2^e_g),  u = floor(m . Wu / 2^e_u)
  s   = Ts[floor(gw / 2^(F-8)) + 2048]            pinned v1 table silu-f12.i64le (PR #67); index saturated (counted)
  h   = floor(s u / 2^F)                          r2 rounding (DESIGN 5.5)
  out = floor(h . Wd / 2^e_d),  residual += out / 2^F
in_proj, out_proj, attention, every RMSNorm (including the MLP pre-norm), final norm and lm_head stay float64.
DeltaNet heads: float64 (paths REF, FM) or XS18 (paths XM18, XM18#2; PR #74 engine, PR #88 arm, unchanged).
No proof, no soundness claim. Integer matmuls are float64 BLAS products of integer-valued arrays, guarded exact (< 2^53).

Reused unchanged from PR #124 (experiments/20261111-8-qwen-e2e-agreement/e2e.py): Stream, logits_metrics,
lm_head_chunks, save_state, load_state, log, rel, make_pool; from PR #88 q1_forward: Ckpt, rms0, deltanet_inputs,
head_out, attention, layer_type. e2e.PATH_ORDER is set to this lane's paths in the main process, because
logits_metrics reads it. New here: the integer MLP, the per-layer driver, the range log.

Usage:
  mlp_e2e.py run <scratch> <runs> <full|reduced>
  mlp_e2e.py fixture <scratch> <out>
"""
import json, math, os, struct, sys, time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent
EXP = HERE.parent
REPO = EXP.parent
sys.path.insert(0, str(EXP / "20261111-8-qwen-e2e-agreement"))
import e2e as E          # PR #124, unchanged (imports PR #88 q1_forward, PR #74 scaled_head, PR #68 real_head)
F = E.F

FB = 12                                 # F, DESIGN 5.0
WMAX = 4095                             # |W_int| <= 4095 (honest conversion), class [-4096, 4095] (DESIGN 6, bounds.py W)
A_PUB = 2047                            # M3a public normed input class (DESIGN 3.2, bounds.py A_PUB)
HONEST = 2 ** 18                        # honest cell contract (bounds.py RNG comment, DESIGN 7.4)
RNG = 2 ** 23                           # rng class (bounds.py RNG)
OUT_PUB = 2 ** 31                       # M3a public output class (DESIGN 3.2, bounds.py OUT_PUB)
DOWN_LEDGER = 2 ** 55.023754            # bounds-r3.json row "M3a-MLP down (r2)"
EXACT = 2 ** 53                         # this code's float-exactness guard (PREREG: partial sums < 2^53)
TS = np.array(struct.unpack("<4096q", (REPO / "research/operators/qwen_ops/tables/silu-f12.i64le").read_bytes()), dtype=np.float64)
assert TS.max() == 32741 and TS[2048] == 0

ARMS = E.ARMS
MODE = {"REF": ("REF", None), "FM": ("REF", None), "XM18": ("INT", "XS18"), "XM18#2": ("INT", "XS18")}
INTMLP = {"FM", "XM18", "XM18#2"}
PATH_ORDER = ["REF", "XM18", "FM", "XM18#2"]
REDUCED = ["p01-ordinary-short", "p07-chat-ordinary", "p08-chat-refusal", "p09-multilingual", "p02-ordinary-paragraph",
           "p04-repeat-punct", "p05-code", "p06a-digits-256"]
DET = ["p01-ordinary-short", "p04-repeat-punct", "p09-multilingual"]
NOTE = ("integer M3 MLP (DESIGN 5.5, r2) in every layer for FM, XM18; DeltaNet heads XS18 in XM18, float64 in REF and FM; "
        "in_proj, out_proj, attention, every RMSNorm (incl. the MLP pre-norm), final norm and lm_head float64; no proof")


class GuardError(Exception):
    pass


def head_task(path, pid, hd):
    mode, arm = MODE[path]
    try:
        cfg = ARMS[arm]["cfg"] if arm else None
        y = F.head_out(hd, mode, cfg)
        relh = None
        if mode == "INT":
            yf = F.head_out(hd, "REF")
            num = np.sqrt(((y - yf) ** 2).sum(axis=(0, 2))); den = np.sqrt((yf ** 2).sum(axis=(0, 2)))
            relh = [float(a / b) if b else float("nan") for a, b in zip(num, den)]
        return path, pid, y, relh, None
    except OverflowError as e:
        return path, pid, None, None, "OverflowError: " + str(e)


# ------------------------------------------------------------------ integer MLP
def exponent(m):
    """bounds.py completeness_check: largest e (0..24) with RNE(2^(e+1) m) <= 4095 failing at e+1."""
    e = 0
    while int(round(2.0 ** (e + 1) * m)) <= WMAX and e < 24:
        e += 1
    return e


def to_int_inplace(W):
    """W float64 -> RNE(2^e W) in place. Returns e and facts."""
    mx = float(np.abs(W).max()); e = exponent(mx)
    W *= 2.0 ** e; np.rint(W, out=W)
    wmax = float(np.abs(W).max())
    return dict(e=e, max_abs_float=mx, max_abs_int=wmax, e_in_1_24=1 <= e <= 24, w_in_class=wmax <= WMAX)


def exact_matmul(a, W, name):
    """a (T, K) integer-valued float64, W (N, K) integer-valued float64. Exact iff every partial sum < 2^53."""
    K = a.shape[1]
    if float(np.abs(a).max(initial=0.0)) * float(np.abs(W).max()) * K >= EXACT:
        b = float((np.abs(a) @ np.abs(W).T).max(initial=0.0))
        if b >= EXACT:
            raise GuardError(f"{name}: exactness bound {b:.3e} >= 2^53")
    return a @ W.T


def amax(x):
    return float(np.abs(x).max(initial=0.0))


def mlp_int(L, x, ex):
    """x (T, 5120) float64 residual. L holds integer-valued MLP weights (converted in place), ex their exponents."""
    hf = F.rms0(x, L["post_attention_layernorm.weight"])
    m = np.rint(hf * 2.0 ** FB)
    accg = exact_matmul(m, L["mlp.gate_proj.weight"], "gate"); gw = np.floor(accg / 2.0 ** ex["g"])
    accu = exact_matmul(m, L["mlp.up_proj.weight"], "up"); u = np.floor(accu / 2.0 ** ex["u"])
    raw = np.floor(gw / 2.0 ** (FB - 8)) + 2048
    sat_lo = int((raw < 0).sum()); sat_hi = int((raw > 4095).sum())
    s = TS[np.clip(raw, 0, 4095).astype(np.int64)]
    if amax(s) * amax(u) >= EXACT:
        raise GuardError(f"s*u: {amax(s) * amax(u):.3e} >= 2^53")
    h = np.floor(s * u / 2.0 ** FB)
    accd = exact_matmul(h, L["mlp.down_proj.weight"], "down"); out = np.floor(accd / 2.0 ** ex["d"])
    st = dict(m=amax(m), gw=amax(gw), u=amax(u), s=amax(s), h=amax(h), acc_down=amax(accd), out=amax(out),
              n_m_over_2047=int((np.abs(m) > A_PUB).sum()),
              n_gw_ge_2e18=int((np.abs(gw) >= HONEST).sum()), n_gw_ge_2e23=int((np.abs(gw) >= RNG).sum()),
              n_u_ge_2e18=int((np.abs(u) >= HONEST).sum()), n_u_ge_2e23=int((np.abs(u) >= RNG).sum()),
              n_h_ge_2e18=int((np.abs(h) >= HONEST).sum()), n_h_ge_2e23=int((np.abs(h) >= RNG).sum()),
              n_silu_sat_lo=sat_lo, n_silu_sat_hi=sat_hi,
              n_acc_down_ge_ledger=int((np.abs(accd) >= DOWN_LEDGER).sum()), n_out_ge_2e31=int((np.abs(out) >= OUT_PUB).sum()),
              n_m=int(m.size), n_hidden=int(gw.size), n_out=int(out.size))
    return out / 2.0 ** FB, st


# ------------------------------------------------------------------ one layer, all paths
def layer_all(i, L, X, pool, runs, leg):
    t0 = time.time(); errname = f"errors-{leg}.jsonl"
    if F.layer_type(i) == "linear_attention":
        pend = []
        for p in PATH_ORDER:
            for pid, x in X.get(p, {}).items():
                if x is None: continue
                pend.append(pool.apply_async(head_task, (p, pid, F.deltanet_inputs(L, x))))
        Wo = L["linear_attn.out_proj.weight"]
        for r in pend:
            p, pid, y, relh, err = r.get()
            if err is not None:
                log(runs, errname, dict(leg=leg, layer=i, path=p, prompt=pid, error=err)); X[p][pid] = None; continue
            X[p][pid] = X[p][pid] + y.reshape(y.shape[0], -1) @ Wo.T
            if relh is not None: log(runs, f"heads-{leg}.jsonl", dict(leg=leg, layer=i, path=p, prompt=pid, rel_y=relh))
    else:
        for p in PATH_ORDER:
            for pid, x in X.get(p, {}).items():
                if x is None: continue
                X[p][pid] = x + F.attention(L, x)
    tmix = time.time() - t0
    # MLP: REF (float weights) first, then the weights are converted in place, then the integer paths
    for pid, x in X["REF"].items():
        if x is not None: X["REF"][pid] = x + F.mlp(L, x)
    conv = {k: to_int_inplace(L[f"mlp.{n}_proj.weight"]) for k, n in (("g", "gate"), ("u", "up"), ("d", "down"))}
    ex = {k: v["e"] for k, v in conv.items()}
    rng_row = dict(leg=leg, layer=i, weights=conv, paths={})
    for p in PATH_ORDER:
        if p not in INTMLP or p not in X: continue
        rng_row["paths"][p] = {}
        for pid, x in X[p].items():
            if x is None: continue
            try:
                d, st = mlp_int(L, x, ex)
            except GuardError as e:
                log(runs, errname, dict(leg=leg, layer=i, path=p, prompt=pid, error="GuardError: " + str(e))); X[p][pid] = None; continue
            X[p][pid] = x + d; rng_row["paths"][p][pid] = st
    log(runs, f"ranges-{leg}.jsonl", rng_row)
    row = dict(leg=leg, layer=i, type=F.layer_type(i), seconds=round(time.time() - t0, 1), mix_s=round(tmix, 1))
    for p in PATH_ORDER:
        if p == "REF" or p not in X: continue
        row[p] = {pid: (rel(x, X["REF"][pid]) if x is not None and X["REF"][pid] is not None else None) for pid, x in X[p].items()}
    row["det_bit_equal"] = {f"XM18#2|{pid}": bool(x is not None and X["XM18"][pid] is not None and np.array_equal(x, X["XM18"][pid]))
                            for pid, x in X.get("XM18#2", {}).items()}
    log(runs, f"divergence-{leg}.jsonl", row)
    return row


log, rel, save_state, load_state = E.log, E.rel, E.save_state, E.load_state


def run_leg(leg, X, i0, layers, ckpts, sc, runs, pool, meta, finish):
    fetch_ex = ThreadPoolExecutor(1)
    sub = lambda k: fetch_ex.submit(ckpts[layers[k][1]].layer, layers[k][0])
    todo = [k for k, (i, _) in enumerate(layers) if i >= i0]
    fut = sub(todo[0]) if todo else None
    for n, k in enumerate(todo):
        i, ck = layers[k]
        tw = time.time(); L = fut.result(); wait = time.time() - tw
        ckpts[ck].save()
        fut = sub(todo[n + 1]) if n + 1 < len(todo) else None
        row = layer_all(i, L, X, pool, runs, leg); del L
        meta.update(leg=leg, next_layer=i + 1); save_state(sc / "ckpt.npz", X, meta)
        if i == 16 and leg == "abl": save_state(sc / "x16.npz", X, dict(after_layer=16))
        log(runs, "progress.log.jsonl", dict(t=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), leg=leg, layer=i, ckpt=ck,
                                              fetch_wait_s=round(wait, 1), layer_s=row["seconds"]))
        print(leg, "layer", i, ck, F.layer_type(i), "wait", round(wait, 1), "s", row["seconds"], flush=True)
    finish(X)


def finish_leg(leg, X, C, runs, sc, meta):
    t0 = time.time(); Ln = C.t(F.P + "norm.weight")
    Hn = {p: {pid: (F.rms0(x, Ln) if x is not None else None) for pid, x in d.items()} for p, d in X.items()}
    res = E.logits_metrics(Hn, E.lm_head_chunks(C)); C.save()
    p01 = res["p01-ordinary-short"]
    out = dict(leg=leg, checkpoint=leg, note=NOTE, prompts=res, seconds=round(time.time() - t0, 1),
               sanity_p01_last_top1=p01["ref_top1"][-1], sanity_pass=p01["ref_top1"][-1] == E.TOKYO)
    (Path(runs) / f"e2e-{leg}.json").write_text(json.dumps(out) + "\n")
    meta.setdefault("legs_done", []).append(leg); meta.update(next_layer=None); save_state(sc / "ckpt.npz", X, meta)
    log(runs, "progress.log.jsonl", dict(t=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), leg=leg, logits_done=True,
                                          seconds=out["seconds"], sanity_pass=out["sanity_pass"]))
    print(leg, "logits done", out["seconds"], "sanity", out["sanity_pass"], flush=True)


def init_paths(pr, ids):
    X = {}
    for p in PATH_ORDER:
        use = [k for k in ids if k in DET] if p == "XM18#2" else ids
        X[p] = {pid: pr[pid].copy() for pid in use}
    return X


def cmd_run(scratch, runs, which):
    E.PATH_ORDER = PATH_ORDER          # logits_metrics reads it (main process only)
    sc = Path(scratch); runs = Path(runs); sc.mkdir(parents=True, exist_ok=True); runs.mkdir(parents=True, exist_ok=True)
    prompts = json.load(open(EXP / "20261111-8-qwen-e2e-agreement" / "prompts-e2e.json"))
    use = [p["id"] for p in prompts["prompts"] if which == "full" or p["id"] in REDUCED]
    ckpts = {"stock": F.Ckpt("stock", runs), "abl": F.Ckpt("abl", runs)}
    pool = E.make_pool()
    if (sc / "ckpt.npz").exists():
        X, meta = load_state(sc / "ckpt.npz")
        log(runs, "progress.log.jsonl", dict(t=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), resume=True, meta=meta))
    else:
        toks = sorted({t for p in prompts["prompts"] if p["id"] in use for t in p["token_ids"]})
        emb = ckpts["stock"].emb_rows(toks); ckpts["stock"].save()
        pr = {p["id"]: np.stack([emb[t] for t in p["token_ids"]]) for p in prompts["prompts"] if p["id"] in use}
        X = init_paths(pr, use); meta = dict(leg="abl", next_layer=0, legs_done=[], prompt_set=which)
        log(runs, "progress.log.jsonl", dict(t=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), start=True, prompt_set=which,
                                              paths={p: list(d) for p, d in X.items()}))
    if "abl" not in meta.get("legs_done", []):
        layers = [(i, "stock" if i <= 16 else "abl") for i in range(E.NL)]
        i0 = meta["next_layer"] if meta.get("leg") == "abl" and meta.get("next_layer") is not None else E.NL
        run_leg("abl", X, i0, layers, ckpts, sc, runs, pool, meta, lambda X: finish_leg("abl", X, ckpts["abl"], runs, sc, meta))
    if "stock" not in meta.get("legs_done", []):
        if meta.get("leg") != "stock" or meta.get("next_layer") is None:
            X, _ = load_state(sc / "x16.npz"); meta.update(leg="stock", next_layer=17)
        layers = [(i, "stock") for i in range(17, E.NL)]
        run_leg("stock", X, meta["next_layer"], layers, ckpts, sc, runs, pool, meta,
                lambda X: finish_leg("stock", X, ckpts["stock"], runs, sc, meta))
    pool.close(); pool.join()
    log(runs, "progress.log.jsonl", dict(t=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), all_done=True))


# ------------------------------------------------------------------ debug (PREREG "Runs")
def int_reference(mf, Wg, Wu, Wd, ex):
    """Python-int reference of the same formulas on small synthetic arrays."""
    T, K = mf.shape; N = Wg.shape[0]
    m = [[int(round(v * 2 ** FB)) for v in row] for row in mf]
    out = []
    for t in range(T):
        h = []
        for j in range(N):
            g = sum(m[t][k] * int(Wg[j, k]) for k in range(K)) >> ex["g"]
            uu = sum(m[t][k] * int(Wu[j, k]) for k in range(K)) >> ex["u"]
            idx = min(max((g >> (FB - 8)) + 2048, 0), 4095)
            h.append((int(TS[idx]) * uu) >> FB)
        out.append([sum(h[j] * int(Wd[o, j]) for j in range(N)) >> ex["d"] for o in range(Wd.shape[0])])
    return np.array(out, dtype=np.float64)


def cmd_fixture(scratch, out):
    E.PATH_ORDER = PATH_ORDER
    sc = Path(scratch); sc.mkdir(parents=True, exist_ok=True); t0 = time.time()
    # 1. synthetic integer check (default_rng(0)); the norm is replaced by the identity for this check only
    rng = np.random.default_rng(0); T, K, N = 3, 64, 48
    mf = rng.normal(size=(T, K)) * 2.0; mf[0, 0] = 9.5                    # one large entry to hit the SiLU saturation
    Wf = {k: rng.normal(size=s) * 0.05 for k, s in (("g", (N, K)), ("u", (N, K)), ("d", (K, N)))}
    Ls = {"mlp.gate_proj.weight": Wf["g"].copy(), "mlp.up_proj.weight": Wf["u"].copy(), "mlp.down_proj.weight": Wf["d"].copy(),
          "post_attention_layernorm.weight": None}
    conv = {k: to_int_inplace(Ls[f"mlp.{n}_proj.weight"]) for k, n in (("g", "gate"), ("u", "up"), ("d", "down"))}
    ex = {k: v["e"] for k, v in conv.items()}
    rms_saved = F.rms0
    F.rms0 = lambda x, w: x
    try:
        d, st = mlp_int(Ls, mf, ex)
    finally:
        F.rms0 = rms_saved
    ref = int_reference(mf, Ls["mlp.gate_proj.weight"], Ls["mlp.up_proj.weight"], Ls["mlp.down_proj.weight"], ex)
    synth = dict(equal=bool(np.array_equal(d * 2 ** FB, ref)), exps=ex, stats=st,
                 float_mlp_vs_int_rel=float(np.linalg.norm(d - (lambda g, u: (g / (1 + np.exp(-g)) * u) @ Wf["d"].T)(mf @ Wf["g"].T, mf @ Wf["u"].T))
                                            / np.linalg.norm((lambda g, u: (g / (1 + np.exp(-g)) * u) @ Wf["d"].T)(mf @ Wf["g"].T, mf @ Wf["u"].T))))
    # guard: an input that breaks exactness must raise
    try:
        exact_matmul(np.full((1, 4), 2.0 ** 50), np.full((1, 4), 4095.0), "probe"); guard = False
    except GuardError:
        guard = True
    # 2. fixture prompt, stock layers 0..3, every path; save/load and determinism
    C = F.Ckpt("stock", sc); pool = E.make_pool()
    emb = C.emb_rows(F.FIXTURE); x0 = np.stack([emb[t] for t in F.FIXTURE])
    X = {p: {"fx": x0.copy()} for p in PATH_ORDER}
    times = []
    for i in range(4):
        tf = time.time(); L = C.layer(i); tfe = time.time() - tf
        row = layer_all(i, L, X, pool, sc, "fx"); del L
        times.append(dict(layer=i, fetch_s=round(tfe, 1), layer_s=row["seconds"]))
    save_state(sc / "fx.npz", X, dict(a=1)); X2, m2 = load_state(sc / "fx.npz")
    rt = all(np.array_equal(X[p][k], X2[p][k]) for p in X for k in X[p]) and m2 == dict(a=1)
    pool.close(); pool.join()
    rows = [json.loads(l) for l in open(sc / "ranges-fx.jsonl")]
    o = dict(synthetic=synth, guard_raises=guard, save_load_equal=rt,
             det_equal=bool(np.array_equal(X["XM18#2"]["fx"], X["XM18"]["fx"])),
             resid_rel_vs_ref={p: rel(X[p]["fx"], X["REF"]["fx"]) for p in X if p != "REF"},
             weights=[r["weights"] for r in rows], ranges_xm18=[r["paths"]["XM18"]["fx"] for r in rows],
             timing=times, seconds=round(time.time() - t0, 1))
    Path(out).write_text(json.dumps(o, indent=1) + "\n"); print(json.dumps(o, indent=1))


if __name__ == "__main__":
    if sys.argv[1] == "run": cmd_run(sys.argv[2], sys.argv[3], sys.argv[4])
    else: cmd_fixture(sys.argv[2], sys.argv[3])
