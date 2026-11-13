#!/usr/bin/env python3
"""Qwen pre-norm outputs against the public class 2,047: baseline distribution and three arms, open loop (PREREG.md).

One float64 reference stream (REF) runs closed loop through the layers. For layer i with REF input x_i every arm
starts from the same x_i, so no arm's error compounds across layers. No logits, no proof, no soundness claim.

Per layer:
  a_float = rms0(x_i, input_layernorm)                 the mixer input (DeltaNet in_proj or attention q/k/v)
  m_float = rms0(x_i + mixer, post_attention_layernorm) the MLP input
Baseline: q12 = RNE(2^12 n_float) of both norms on the REF stream, class counters and a bit-length histogram.
Arm (C, S3, S4, S5, W): each norm output n_float is replaced by an integer q (clamped or not, at 2^k); the mixer
gets q / 2^k (float64, everything in the mixer float64, float heads), the MLP gets q itself and is PR #138's M3
integer MLP (DESIGN 5.5, r2) with the gate / up shift s = e + k - 12.

Reused unchanged:
  PR #138 mlp_e2e: to_int_inplace, exponent, amax, TS, constants, GuardError, int_reference, mlp_int (debug check only)
  PR #124 e2e:     head_task (called with path "REF": float64 heads), make_pool, save_state, load_state, log
  PR #88 q1_forward: Ckpt, rms0, deltanet_inputs, attention, mlp, layer_type, FIXTURE
New here: quant (the three quantisers), qstats / base_stats (class counters), with_norm (hands a precomputed norm
output to the unchanged q1_forward mixer functions by swapping rms0 for the input_layernorm call only), mlp_arm
(mlp_int's formulas with m given, the shift s = e + k - 12, all prompts in one call, per-prompt statistics),
the open-loop layer driver and the run loop.

Usage:
  norm_class.py run <scratch> <runs> <full|r33>
  norm_class.py fixture <scratch> <out>     debug: synthetic checks, then the fixture prompt through stock layers 0..3
  norm_class.py synth <out>                 debug: the synthetic checks alone (no weight fetch)
"""
import json, os, sys, time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent
EXP = HERE.parent
sys.path.insert(0, str(EXP / "20261112-132-int-mlp-e2e"))
import mlp_e2e as M      # PR #138, unchanged (imports e2e PR #124, q1_forward PR #88)
E = M.E; F = M.F

PROMPTS = ["p01-ordinary-short", "p07-chat-ordinary", "p08-chat-refusal", "p09-multilingual", "p04-repeat-punct", "p03-repeat-word"]
DET = ["p01-ordinary-short", "p09-multilingual"]
ARMS = {"W": dict(k=12, clamp=None), "C": dict(k=12, clamp=2047), "S3": dict(k=3, clamp=None), "S4": dict(k=4, clamp=None),
        "S5": dict(k=5, clamp=None)}
ARM_ORDER = ["W", "C", "S3", "S4", "S5"]          # W first: d is measured against it
A_PUB = 2047
NL = E.NL
R33 = sorted({i for i in range(NL) if i % 4 in (0, 3)} | {26})
MIX_PROJ = {"linear_attention": ["linear_attn.in_proj_qkv.weight", "linear_attn.in_proj_z.weight", "linear_attn.in_proj_a.weight",
                                 "linear_attn.in_proj_b.weight"],
            "full_attention": ["self_attn.q_proj.weight", "self_attn.k_proj.weight", "self_attn.v_proj.weight"]}
NOTE = ("open loop: every arm starts each layer from the float64 REF stream; arms change only the two pre-norm outputs "
        "(mixer input a, MLP input m); mixer float64 with float heads; MLP = PR #138 integer M3 MLP; no logits; no proof")


def now(): return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def amx(x):
    """max |x| without a temporary"""
    return max(float(x.max()), -float(x.min())) if x.size else 0.0


def cnt_ge(x, mx, thr):
    return 0 if mx < thr else int((np.abs(x) >= thr).sum())


# ------------------------------------------------------------------ quantisers and class counters
def quant(n, arm):
    """n float64 norm output -> integer-valued q at 2^k (clamped for arm C). Returns q and the number of clamped entries."""
    a = ARMS[arm]
    q = np.rint(n * 2.0 ** a["k"]); ncl = 0
    if a["clamp"] is not None:
        ncl = int((np.abs(q) > a["clamp"]).sum())
        np.clip(q, -a["clamp"], a["clamp"], out=q)
    return q, ncl


def qstats(q):
    """Class counters of an integer-valued array q (T, 5120)."""
    aq = np.abs(q); over = aq > A_PUB; mx = float(aq.max())
    return dict(n=int(q.size), n_rows=int(q.shape[0]), max=mx, n_over_2047=int(over.sum()), rows_over_2047=int(over.any(1).sum()),
                ch_over_2047=int(over.any(0).sum()), n_ge_2e15=cnt_ge(q, mx, 2 ** 15), n_ge_2e17=cnt_ge(q, mx, 2 ** 17),
                n_ge_2e18=cnt_ge(q, mx, 2 ** 18))


def base_stats(nf):
    """Baseline record of one norm output nf (T, 5120) float64: q12 = RNE(2^12 nf)."""
    q = np.rint(nf * 4096.0); st = qstats(q); aq = np.abs(q)
    st["max_float"] = amx(nf)
    t, c = np.unravel_index(int(aq.argmax()), aq.shape); st["argmax_token"] = int(t); st["argmax_channel"] = int(c)
    _, e = np.frexp(aq)                                   # bit length of |q12| (0 for 0)
    st["hist_bitlen"] = [int(v) for v in np.bincount(e.ravel().astype(np.int64), minlength=22)]
    return st, aq


def top_channels(aq_all, n=8):
    """Pooled over all tokens: the n channels with the largest max |q12|."""
    cm = aq_all.max(0); idx = np.argsort(-cm)[:n]
    return [dict(channel=int(j), max=float(cm[j]), tokens_over_2047=int((aq_all[:, j] > A_PUB).sum()),
                 median_abs=float(np.median(aq_all[:, j]))) for j in idx]


# ------------------------------------------------------------------ norm swap for the unchanged mixer code
def with_norm(target_w, h, fn, *args):
    """Call fn (q1_forward.deltanet_inputs or .attention, unchanged) with its input_layernorm output replaced by h.
    Only the rms0 call whose gain array IS target_w is swapped; the q / k RMSNorms inside attention are untouched."""
    real = F.rms0

    def swapped(x, w):
        return h if w is target_w else real(x, w)
    F.rms0 = swapped
    try:
        return fn(*args)
    finally:
        F.rms0 = real


# ------------------------------------------------------------------ integer MLP with m given
def xmat(a, W, wmax, name):
    """M.exact_matmul with max |W| passed in (it is the same number, computed once per layer by to_int_inplace)."""
    K = a.shape[1]
    if amx(a) * wmax * K >= M.EXACT:
        b = float((np.abs(a) @ np.abs(W).T).max(initial=0.0))
        if b >= M.EXACT:
            raise M.GuardError(f"{name}: exactness bound {b:.3e} >= 2^53")
    return a @ W.T


def mlp_arm(L, m, ex, k, wmax, slices):
    """m (T, 5120) integer-valued at 2^k, rows of all prompts stacked; slices {pid: slice}. PR #138 mlp_int's formulas
    with gate / up shift s = e + k - 12 (k = 12: PR #138 exactly). Returns out (T, 5120) integer-valued at 2^12 and
    per-prompt statistics in mlp_int's format."""
    sg = ex["g"] + k - M.FB; su = ex["u"] + k - M.FB
    accg = xmat(m, L["mlp.gate_proj.weight"], wmax["g"], "gate"); gw = np.floor(accg / 2.0 ** sg); del accg
    accu = xmat(m, L["mlp.up_proj.weight"], wmax["u"], "up"); u = np.floor(accu / 2.0 ** su); del accu
    raw = np.floor(gw / 2.0 ** (M.FB - 8)) + 2048
    s = M.TS[np.clip(raw, 0, 4095).astype(np.int64)]
    if amx(s) * amx(u) >= M.EXACT:
        raise M.GuardError(f"s*u: {amx(s) * amx(u):.3e} >= 2^53")
    h = np.floor(s * u / 2.0 ** M.FB)
    accd = xmat(h, L["mlp.down_proj.weight"], wmax["d"], "down"); out = np.floor(accd / 2.0 ** ex["d"])
    st = {}
    for pid, sl in slices.items():
        mm, g_, u_, s_, h_, a_, o_ = (amx(v[sl]) for v in (m, gw, u, s, h, accd, out))
        rmin, rmax = float(raw[sl].min()), float(raw[sl].max())
        st[pid] = dict(m=mm, gw=g_, u=u_, s=s_, h=h_, acc_down=a_, out=o_,
                       n_m_over_2047=int((np.abs(m[sl]) > A_PUB).sum()) if mm > A_PUB else 0,
                       n_gw_ge_2e18=cnt_ge(gw[sl], g_, M.HONEST), n_gw_ge_2e23=cnt_ge(gw[sl], g_, M.RNG),
                       n_u_ge_2e18=cnt_ge(u[sl], u_, M.HONEST), n_u_ge_2e23=cnt_ge(u[sl], u_, M.RNG),
                       n_h_ge_2e18=cnt_ge(h[sl], h_, M.HONEST), n_h_ge_2e23=cnt_ge(h[sl], h_, M.RNG),
                       n_silu_sat_lo=int((raw[sl] < 0).sum()) if rmin < 0 else 0,
                       n_silu_sat_hi=int((raw[sl] > 4095).sum()) if rmax > 4095 else 0,
                       n_acc_down_ge_ledger=cnt_ge(accd[sl], a_, M.DOWN_LEDGER), n_out_ge_2e31=cnt_ge(out[sl], o_, M.OUT_PUB),
                       n_m=int(m[sl].size), n_hidden=int(gw[sl].size), n_out=int(out[sl].size), shift_g=sg, shift_u=su, shift_d=ex["d"])
    return out, st


# ------------------------------------------------------------------ one layer, REF + baseline + arms (open loop)
def nrm(x): return float(np.linalg.norm(x))


def layer(i, L, X, pool, runs, arms_on, check_w=False, tag=""):
    """X {pid: x_i} (REF stream), replaced in place by x_{i+1}. Logs one baseline row and one arms row."""
    t0 = time.time(); pids = list(X); typ = F.layer_type(i)
    w_in = L["input_layernorm.weight"]; w_post = L["post_attention_layernorm.weight"]
    a_ref = {pid: F.rms0(X[pid], w_in) for pid in pids}
    hin = {("REF", pid): a_ref[pid] for pid in pids}; qa = {}
    for arm in arms_on:
        for pid in pids:
            q, ncl = quant(a_ref[pid], arm)
            qa[(arm, pid)] = dict(qstats(q), n_clamped=ncl); hin[(arm, pid)] = q / 2.0 ** ARMS[arm]["k"]
    if "C" in arms_on:
        for pid in DET:
            if pid in X: hin[("C#2", pid)] = quant(a_ref[pid], "C")[0] / 2.0 ** ARMS["C"]["k"]
    proj_e = {n: M.exponent(float(np.abs(L[n]).max())) for n in MIX_PROJ[typ]} if arms_on else {}
    # mixer (float64, unchanged q1_forward code, float heads)
    mix = {}
    if typ == "linear_attention":
        pend = [pool.apply_async(E.head_task, ("REF", key, with_norm(w_in, h, F.deltanet_inputs, L, X[key[1]]))) for key, h in hin.items()]
        Wo = L["linear_attn.out_proj.weight"]
        for r in pend:
            _, key, y, _, err = r.get(); key = tuple(key)
            if err is not None:
                E.log(runs, f"errors{tag}.jsonl", dict(layer=i, arm=key[0], prompt=key[1], error=err)); mix[key] = None; continue
            mix[key] = y.reshape(y.shape[0], -1) @ Wo.T
    else:
        for key, h in hin.items():
            mix[key] = with_norm(w_in, h, F.attention, L, X[key[1]])
    tmix = time.time() - t0
    # REF: MLP in float64 (float weights), next stream; baseline on both norm outputs
    xm = {key: X[key[1]] + v for key, v in mix.items() if v is not None}
    m_ref = {pid: F.rms0(xm[("REF", pid)], w_post) for pid in pids}
    mlp_ref = {pid: F.mlp(L, xm[("REF", pid)]) for pid in pids}
    out_ref = {pid: mix[("REF", pid)] + mlp_ref[pid] for pid in pids}
    x_next = {pid: X[pid] + out_ref[pid] for pid in pids}
    brow = dict(layer=i, type=typ, norms={})
    for name, d in (("input_layernorm", a_ref), ("post_attention_layernorm", m_ref)):
        per = {}; aqs = []
        for pid in pids:
            st, aq = base_stats(d[pid]); per[pid] = st; aqs.append(aq)
        aq_all = np.concatenate(aqs); over = aq_all > A_PUB
        brow["norms"][name] = dict(prompts=per, pooled=dict(n=int(aq_all.size), n_rows=int(aq_all.shape[0]), max=float(aq_all.max()),
                                   n_over_2047=int(over.sum()), rows_over_2047=int(over.any(1).sum()), ch_over_2047=int(over.any(0).sum()),
                                   top_channels=top_channels(aq_all)))
        del aq_all, over, aqs
    E.log(runs, f"baseline{tag}.jsonl", brow)
    tref = time.time() - t0
    arow = None
    if arms_on:
        conv = {k_: M.to_int_inplace(L[f"mlp.{n}_proj.weight"]) for k_, n in (("g", "gate"), ("u", "up"), ("d", "down"))}
        ex = {k_: v["e"] for k_, v in conv.items()}; wmax = {k_: v["max_abs_int"] for k_, v in conv.items()}
        arow = dict(layer=i, type=typ, weights=conv, mixer_proj_exponents=proj_e, arms={}, det_bit_equal={})
        outs = {}
        for arm in list(arms_on) + (["C#2"] if "C" in arms_on else []):
            base = "C" if arm == "C#2" else arm; k = ARMS[base]["k"]
            use = [pid for pid in pids if (arm, pid) in xm]
            if not use: continue
            qs = {}; qm = {}
            for pid in use:
                q, ncl = quant(F.rms0(xm[(arm, pid)], w_post), base); qs[pid] = q; qm[pid] = dict(qstats(q), n_clamped=ncl)
            sl = {}; o = 0
            for pid in use: sl[pid] = slice(o, o + qs[pid].shape[0]); o += qs[pid].shape[0]
            try:
                outc, st = mlp_arm(L, np.concatenate([qs[pid] for pid in use]), ex, k, wmax, sl)
            except M.GuardError as e:
                E.log(runs, f"errors{tag}.jsonl", dict(layer=i, arm=arm, error="GuardError: " + str(e)))
                if arm != "C#2": arow["arms"][arm] = {pid: dict(error=str(e)) for pid in use}
                continue
            if check_w and arm == "W":                        # debug only: PR #138 mlp_int, unchanged, on the same stream
                for pid in use:
                    dref, _ = M.mlp_int(L, xm[(arm, pid)], ex)
                    assert np.array_equal(dref, outc[sl[pid]] / 2.0 ** M.FB), ("mlp_arm != PR #138 mlp_int", i, pid)
                arow["w_equals_pr138_mlp_int"] = True
            for pid in use:
                outs[(arm, pid)] = mix[(arm, pid)] + outc[sl[pid]] / 2.0 ** M.FB
            if arm == "C#2":
                for pid in use:
                    arow["det_bit_equal"][pid] = bool(("C", pid) in outs and np.array_equal(outs[("C#2", pid)], outs[("C", pid)]))
                continue
            arow["arms"][arm] = {}
            for pid in use:
                oa = outs[(arm, pid)]; num = nrm(oa - out_ref[pid]); den = nrm(x_next[pid]); deno = nrm(out_ref[pid])
                dm = nrm(mix[(arm, pid)] - mix[("REF", pid)]); nm_ = nrm(mix[("REF", pid)])
                dl = nrm(outc[sl[pid]] / 2.0 ** M.FB - mlp_ref[pid]); nl = nrm(mlp_ref[pid])
                dw = nrm(oa - outs[("W", pid)]) if ("W", pid) in outs else None
                arow["arms"][arm][pid] = dict(r=num / den, c=num / deno, d=(dw / den if dw is not None else None), num=num, den_stream=den,
                                              den_out=deno, mix_rel=dm / nm_ if nm_ else None, mlp_rel=dl / nl if nl else None,
                                              n_tokens=int(oa.shape[0]), qa=qa[(arm, pid)], qm=qm[pid], mlp=st[pid])
            del outc
        E.log(runs, f"arms{tag}.jsonl", arow)
    for pid in pids: X[pid] = x_next[pid]
    return dict(layer=i, type=typ, seconds=round(time.time() - t0, 1), mix_s=round(tmix, 1), ref_s=round(tref - tmix, 1),
                arms=list(arms_on))


# ------------------------------------------------------------------ registered run
def cmd_run(scratch, runs, which):
    sc = Path(scratch); runs = Path(runs); sc.mkdir(parents=True, exist_ok=True); runs.mkdir(parents=True, exist_ok=True)
    prompts = json.load(open(EXP / "20261111-8-qwen-e2e-agreement" / "prompts-e2e.json"))
    pr = {p["id"]: p["token_ids"] for p in prompts["prompts"] if p["id"] in PROMPTS}
    assert list(pr) and set(pr) == set(PROMPTS)
    ckpts = {"stock": F.Ckpt("stock", runs), "abl": F.Ckpt("abl", runs)}
    pool = E.make_pool()
    if (sc / "ckpt.npz").exists():
        S, meta = E.load_state(sc / "ckpt.npz"); X = {pid: S["REF"][pid] for pid in PROMPTS}
        E.log(runs, "progress.log.jsonl", dict(t=now(), resume=True, meta=meta))
    else:
        toks = sorted({t for ids in pr.values() for t in ids})
        emb = ckpts["stock"].emb_rows(toks); ckpts["stock"].save()
        X = {pid: np.stack([emb[t] for t in pr[pid]]) for pid in PROMPTS}; meta = dict(next_layer=0, layer_set=which)
        E.log(runs, "progress.log.jsonl", dict(t=now(), start=True, layer_set=which, prompts={p: len(pr[p]) for p in PROMPTS}, note=NOTE))
    which = meta["layer_set"]
    ck = lambda i: "stock" if i <= 16 else "abl"
    fetch_ex = ThreadPoolExecutor(1); sub = lambda i: fetch_ex.submit(ckpts[ck(i)].layer, i)
    i0 = meta["next_layer"]; fut = sub(i0) if i0 < NL else None
    for i in range(i0, NL):
        tw = time.time(); L = fut.result(); wait = time.time() - tw
        ckpts[ck(i)].save()
        fut = sub(i + 1) if i + 1 < NL else None
        arms_on = ARM_ORDER if (which == "full" or i in R33) else []
        row = layer(i, L, X, pool, runs, arms_on); del L
        meta.update(next_layer=i + 1); E.save_state(sc / "ckpt.npz", {"REF": X}, meta)
        free = os.statvfs(str(sc)); free_gb = free.f_bavail * free.f_frsize / 1e9      # decimal GB, the unit of the host's disk watcher
        E.log(runs, "progress.log.jsonl", dict(t=now(), layer=i, ckpt=ck(i), fetch_wait_s=round(wait, 1), layer_s=row["seconds"],
                                                mix_s=row["mix_s"], ref_s=row["ref_s"], arms=len(arms_on), disk_free_gb=round(free_gb, 1)))
        print("layer", i, ck(i), row["type"], "wait", round(wait, 1), "s", row["seconds"], "mix", row["mix_s"], flush=True)
        if free_gb < 21.0:
            E.log(runs, "progress.log.jsonl", dict(t=now(), stop="free disk under 21 GB", disk_free_gb=round(free_gb, 1)))
            pool.close(); pool.join(); raise SystemExit(4)
    pool.close(); pool.join()
    E.log(runs, "progress.log.jsonl", dict(t=now(), all_done=True))


# ------------------------------------------------------------------ debug (PREREG "Runs"): fixture and synthetic only
def debug_synth():
    o = {}
    # 1. synthetic: mlp_arm against the Python-int reference of PR #138, at k = 12 and at k = 4 (shifted)
    rng = np.random.default_rng(0); T, K, N = 3, 64, 48
    nf = rng.normal(size=(T, K)) * 2.0; nf[0, 0] = 9.5; nf[1, 3] = -40.25
    Wf = {k: rng.normal(size=s) * 0.05 for k, s in (("g", (N, K)), ("u", (N, K)), ("d", (K, N)))}
    Ls = {"mlp.gate_proj.weight": Wf["g"].copy(), "mlp.up_proj.weight": Wf["u"].copy(), "mlp.down_proj.weight": Wf["d"].copy()}
    conv = {k: M.to_int_inplace(Ls[f"mlp.{n}_proj.weight"]) for k, n in (("g", "gate"), ("u", "up"), ("d", "down"))}
    ex = {k: v["e"] for k, v in conv.items()}; wmax = {k: v["max_abs_int"] for k, v in conv.items()}
    syn = {}
    for arm in ("W", "C", "S4", "S3", "S5"):
        k = ARMS[arm]["k"]; q, ncl = quant(nf, arm)
        outc, st = mlp_arm(Ls, q, ex, k, wmax, {"a": slice(0, 2), "b": slice(2, 3)})
        exk = dict(g=ex["g"] + k - 12, u=ex["u"] + k - 12, d=ex["d"])
        ref = M.int_reference(q / 4096.0, Ls["mlp.gate_proj.weight"], Ls["mlp.up_proj.weight"], Ls["mlp.down_proj.weight"], exk)
        syn[arm] = dict(equal_python_int=bool(np.array_equal(outc, ref)), n_clamped=ncl, shifts=exk, max_m=amx(q),
                        sat=[st["a"]["n_silu_sat_lo"] + st["a"]["n_silu_sat_hi"], st["b"]["n_silu_sat_lo"] + st["b"]["n_silu_sat_hi"]])
    # counters on values with known counts: 3 entries over 2,047 at 2^12 (in 2 rows, 3 channels), one of them >= 2^15, none >= 2^17
    z = np.zeros((4, 5120)); z[0, 1] = 0.6; z[0, 7] = -0.75; z[2, 9] = 8.5; z[3, 0] = 0.49975
    st, _ = base_stats(z); qc, ncl = quant(z, "C")
    o["counters"] = dict(n_over=st["n_over_2047"], rows=st["rows_over_2047"], ch=st["ch_over_2047"], ge15=st["n_ge_2e15"], ge17=st["n_ge_2e17"],
                         max=st["max"], argmax=[st["argmax_token"], st["argmax_channel"]], clamped=ncl, clamp_max=amx(qc),
                         hist_nonzero={b: c for b, c in enumerate(st["hist_bitlen"]) if c and b},
                         ok=bool(st["n_over_2047"] == 3 and st["rows_over_2047"] == 2 and st["ch_over_2047"] == 3 and st["n_ge_2e15"] == 1
                                 and st["n_ge_2e17"] == 0 and st["max"] == 34816 and ncl == 3 and amx(qc) == 2047))
    o["synthetic"] = syn
    o["synthetic_ok"] = bool(all(v["equal_python_int"] for v in syn.values()) and o["counters"]["ok"])
    return o


def cmd_synth(out):
    """Synthetic checks only: no weight fetch, no model data."""
    o = debug_synth(); Path(out).write_text(json.dumps(o, indent=1) + "\n"); print(json.dumps(o, indent=1))


def cmd_fixture(scratch, out):
    sc = Path(scratch); sc.mkdir(parents=True, exist_ok=True); t0 = time.time(); o = debug_synth()
    # 2. fixture prompt, stock layers 0..3, all arms, with the PR #138 mlp_int equality check; save / load
    C = F.Ckpt("stock", sc); pool = E.make_pool()
    emb = C.emb_rows(F.FIXTURE); x0 = np.stack([emb[t] for t in F.FIXTURE])
    X = {"p01-ordinary-short": x0.copy(), "p09-multilingual": x0.copy()}      # two copies under DET names: exercises C#2 (fixture tokens only)
    Xt = {"tile512": np.tile(x0, (103, 1))[:512].copy()}                      # timing probe only (PREREG: fixture tokens tiled to 512)
    times = []
    for i in range(4):
        tf = time.time(); L = C.layer(i); tfe = time.time() - tf
        if i in (0, 3):                                    # timing probe first (needs float MLP weights), numbers not results
            Lc = {k: (v.copy() if k.startswith("mlp.") else v) for k, v in L.items()}
            trow = layer(i, Lc, Xt, pool, sc, ARM_ORDER, tag="-timing"); del Lc
        else:
            trow = None                                    # the probe's stream is not advanced through layers 1, 2 (timing only)
        row = layer(i, L, X, pool, sc, ARM_ORDER, check_w=True, tag="-fx"); del L
        times.append(dict(layer=i, type=row["type"], fetch_s=round(tfe, 1), fixture_layer_s=row["seconds"],
                          probe_512tok_layer_s=trow["seconds"] if trow else None, probe_mix_s=trow["mix_s"] if trow else None,
                          probe_ref_s=trow["ref_s"] if trow else None))
        E.log(sc, "timing-fx.jsonl", times[-1])             # per layer, so a lost process keeps the timing
    E.save_state(sc / "fx.npz", {"REF": X}, dict(a=1)); X2, m2 = E.load_state(sc / "fx.npz")
    o["save_load_equal"] = bool(all(np.array_equal(X[k], X2["REF"][k]) for k in X) and m2 == dict(a=1))
    pool.close(); pool.join()
    rows = [json.loads(l) for l in open(sc / "arms-fx.jsonl")]
    o["w_equals_pr138_mlp_int"] = [r.get("w_equals_pr138_mlp_int", False) for r in rows]
    o["det_bit_equal"] = [r["det_bit_equal"] for r in rows]
    o["fixture_r"] = [{a: r["arms"][a]["p01-ordinary-short"]["r"] for a in r["arms"]} for r in rows]
    o["fixture_clamped_m"] = [r["arms"]["C"]["p01-ordinary-short"]["qm"]["n_clamped"] for r in rows]
    o["timing"] = times; o["seconds"] = round(time.time() - t0, 1)
    o["ok"] = bool(o["synthetic_ok"] and o["save_load_equal"]
                   and all(o["w_equals_pr138_mlp_int"]) and all(all(d.values()) and len(d) == 2 for d in o["det_bit_equal"]))
    Path(out).write_text(json.dumps(o, indent=1) + "\n"); print(json.dumps(o, indent=1))


if __name__ == "__main__":
    if sys.argv[1] == "run": cmd_run(sys.argv[2], sys.argv[3], sys.argv[4])
    elif sys.argv[1] == "synth": cmd_synth(sys.argv[2])
    else: cmd_fixture(sys.argv[2], sys.argv[3])
