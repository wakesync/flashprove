#!/usr/bin/env python3
"""Registered run of 20261121-228 (PREREG.md). Also: `selftest` on the synthetic fixture only.

Usage:
  run.py selftest <out.json>
  run.py run <tensor dir> <prompts-inkling.json> <out dir> <tag>

Expert-major: every expert is decoded twice (pass 1: per-tensor maxima for the exponents; pass 2: compute),
never more than one expert in float64 at a time. All prompts' tokens are processed together in the MLP block
(the block is per token; the attention input is computed prompt by prompt)."""
import hashlib, json, math, os, sys, time
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import inkcore as ic

L0 = "model.llm.layers.0."
CFG = dict(H=24, G=8, D=128, d=2304, d_rel=16, rel_extent=1024, window=1024,
           qk_clip=22.627416997969522, rel_clip=8.0, NE=128, K=8, fe=1152, route_scale=8.0)


def rd(tdir, name):
    return open(os.path.join(tdir, name + ".bin"), "rb").read()


def load_attn(tdir):
    b = lambda n, s: ic.bf16(rd(tdir, L0 + n), s)
    W = dict(attn_norm=b("attn_norm.weight", (2304,)),
             wq=b("attn.wq_du.weight", (3072, 2304)), wk=b("attn.wk_dv.weight", (1024, 2304)),
             wv=b("attn.wv_dv.weight", (1024, 2304)), wr=b("attn.wr_du.weight", (384, 2304)),
             wo=b("attn.wo_ud.weight", (2304, 3072)), gate_attn=b("attn.gate_attn.weight", (3072, 2304)),
             sink=b("attn.attn_sink_proj.weight", (24, 2304)),
             q_scale=b("attn.q_l2_clip.scale", (24, 128)), rel_scale=b("attn.rel_l2_clip.scale", (24, 16)),
             rel_proj=b("attn.rel_logits_proj.proj", (16, 1024)),
             k_conv=b("attn.k_sconv.weight", (1024, 4)), v_conv=b("attn.v_sconv.weight", (1024, 4)),
             attn_sconv=b("attn_sconv.weight", (2304, 4)),
             mlp_query=ic.f32(rd(tdir, "model.llm.attn_res.mlp_queries.0"), (2304,)))
    return W


class Experts:
    def __init__(self, tdir):
        P = L0 + "mlp.experts."
        self.c13 = np.frombuffer(rd(tdir, P + "w13_weight"), dtype=np.uint8).reshape(128, 2304, 1152)
        self.s13 = np.frombuffer(rd(tdir, P + "w13_weight_scale"), dtype=np.uint8).reshape(128, 2304, 144)
        self.c2 = np.frombuffer(rd(tdir, P + "w2_weight"), dtype=np.uint8).reshape(128, 2304, 576)
        self.s2 = np.frombuffer(rd(tdir, P + "w2_weight_scale"), dtype=np.uint8).reshape(128, 2304, 72)
        den13 = ic.f32(rd(tdir, P + "w13_weight_outer_scale_denominator"), (1,))[0]
        den2 = ic.f32(rd(tdir, P + "w2_weight_outer_scale_denominator"), (1,))[0]
        self.f13 = ic.f32(rd(tdir, P + "w13_weight_amax"), (128,)) / den13
        self.f2 = ic.f32(rd(tdir, P + "w2_weight_amax"), (128,)) / den2

    def get(self, e):
        w13 = ic.nvfp4_decode(self.c13[e], self.s13[e], self.f13[e])  # [2304 stored rows, 2304]
        gate = w13[0::2]  # Interleave(dim=1) then chunk(2): gate = stored even rows
        up = w13[1::2]
        down = ic.nvfp4_decode(self.c2[e], self.s2[e], self.f2[e])  # [2304, 1152]
        return gate, up, down


def rn32_gain(w, g):
    return (w.astype(np.float32) * g.astype(np.float32)[None, :]).astype(np.float64)


def sha(a):
    return hashlib.sha256(np.ascontiguousarray(a).tobytes()).hexdigest()


def run(tdir, prompts_path, out_dir, tag):
    t0 = time.time()
    os.makedirs(out_dir, exist_ok=True)
    pj = json.load(open(prompts_path))
    em = json.load(open(os.path.join(tdir, "embed_rows.json")))
    rows = ic.bf16(open(os.path.join(tdir, "embed_rows.bin"), "rb").read(), (em["n"], 2304))
    rix = {t: i for i, t in enumerate(em["ids"])}
    g_emb = ic.bf16(rd(tdir, "model.llm.embed_norm.weight"), (2304,))
    g_mlp = ic.bf16(rd(tdir, L0 + "mlp_norm.weight"), (2304,))
    Wr = ic.bf16(rd(tdir, L0 + "mlp.gate.weight"), (128, 2304))
    bias = ic.f32(rd(tdir, L0 + "mlp.gate.bias"), (128,))
    W = load_attn(tdir)
    # ---- float64 input, prompt by prompt
    U, spans = [], []
    s = 0
    for p in pj["prompts"]:
        x = ic.rms(rows[[rix[t] for t in p["token_ids"]]]) * g_emb
        u, _ = ic.layer0_mlp_input(x, W, CFG)
        U.append(u)
        spans.append((p["id"], s, s + len(u)))
        s += len(u)
    U = np.concatenate(U)
    T = U.shape[0]
    del W
    m_f = U * g_mlp
    t_in = time.time() - t0
    # ---- float reference routing
    logit_f = m_f @ Wr.T
    s_f = ic.sigmoid(logit_f)
    sel_f = ic.topk_lowest(s_f + bias, 8)
    sw_f = np.take_along_axis(s_f, sel_f, 1)
    w_f = 8.0 * sw_f / (sw_f.sum(1, keepdims=True) + 1e-20)
    # ---- integer m
    mx_u = float(np.max(np.abs(U)))
    Em = 9
    while mx_u * 2.0 ** Em > 2047:
        Em -= 1
    m_r = ic.rne(2.0 ** Em * U).astype(np.int64)
    m_clamp = int((np.abs(m_r) > 2047).sum())
    m_i = np.clip(m_r, -2047, 2047)
    # ---- pass 1: exponents (gain folded, RN32), over all experts together
    EX = Experts(tdir)
    Wr_pi = rn32_gain(Wr, g_mlp)
    mx = dict(r=float(np.max(np.abs(Wr_pi))), g=0.0, u=0.0, d=0.0)
    for e in range(128):
        gate, up, down = EX.get(e)
        mx["g"] = max(mx["g"], float(np.max(np.abs(rn32_gain(gate, g_mlp)))))
        mx["u"] = max(mx["u"], float(np.max(np.abs(rn32_gain(up, g_mlp)))))
        mx["d"] = max(mx["d"], float(np.max(np.abs(down))))
    ex = {k: ic.exponent_of(v) for k, v in mx.items()}
    kr = Em + ex["r"] - 8
    kg = Em + ex["g"] - 8
    ku = Em + ex["u"] - 8
    kd = (ic.E_A + ic.E_B) + ex["d"] - 12
    # ---- integer router
    Wr_i = ic.rne(2.0 ** ex["r"] * Wr_pi).astype(np.int64)
    acc = ic.imatmul(m_i, Wr_i.T, "router")
    lw = ic.rq(acc, kr)
    ly = np.floor_divide(lw, 8)
    l3 = lw - 8 * ly
    lr = 8 * np.clip(ly, -2047, 2047) + l3
    st = dict(ly_clamp=int((np.abs(ly) > 2047).sum()), ly_cond5=int(((ly < -32768) | (ly > 32767)).sum()),
              sig_out=int(((lr < -16384) | (lr > 16383)).sum()), router_den=int(lw.size))
    s_i = ic.tab(ic.SIG, lr)
    b_i = ic.rne(2.0 ** 16 * bias).astype(np.int64)
    sc_i = s_i + b_i[None, :]
    sel_i = ic.topk_lowest(sc_i, 8)
    sw_i = np.take_along_axis(s_i, sel_i, 1)
    S = sw_i.sum(1, keepdims=True)
    w_i = np.floor_divide(2 * 8 * (2 ** 13) * sw_i + S, 2 * S)
    # ---- pass 2: experts
    out_f = np.zeros((T, 2304))
    out_acc = np.zeros((T, 2304), dtype=np.int64)
    out_attr = np.zeros((T, 2304))  # integer expert arithmetic, float set and float weights
    cnt = dict(gh_clamp=0, gh_cond6=0, keyA_dom=0, uh_clamp=0, uh_cond6=0, keyB_dom=0, uw_cond7=0, units=0)
    wst = dict(g=[0, 0], u=[0, 0], d=[0, 0], r=[int(((Wr_pi != 0) & (Wr_i == 0)).sum()), int((Wr_pi != 0).sum())])
    w13bits = dict(r=int((np.abs(Wr_i) > 4095).sum()), g=0, u=0, d=0)
    maxabs = dict(acc_down=0, y=0)
    hint = []
    for e in range(128):
        gate, up, down = EX.get(e)
        tf = np.nonzero((sel_f == e).any(1))[0]
        ti = np.nonzero((sel_i == e).any(1))[0]
        if len(tf):
            gg = m_f[tf] @ gate.T
            uu = m_f[tf] @ up.T
            hh = ic.fA(gg) * ic.fB(uu)
            ye = hh @ down.T
            we = (w_f[tf] * (sel_f[tf] == e)).sum(1)
            out_f[tf] += we[:, None] * ye
        gp, upi = rn32_gain(gate, g_mlp), rn32_gain(up, g_mlp)
        Wg = ic.rne(2.0 ** ex["g"] * gp).astype(np.int64)
        Wu = ic.rne(2.0 ** ex["u"] * upi).astype(np.int64)
        Wd = ic.rne(2.0 ** ex["d"] * down).astype(np.int64)
        for k, a, b in (("g", gp, Wg), ("u", upi, Wu), ("d", down, Wd)):
            nz = a != 0
            wst[k][0] += int((nz & (b == 0)).sum())
            wst[k][1] += int(nz.sum())
            w13bits[k] += int((np.abs(b) > 4095).sum())
        tu = np.union1d(tf, ti)
        if len(tu) == 0:
            continue
        gw = ic.rq(ic.imatmul(m_i[tu], Wg.T, "gate"), kg)
        uw = ic.rq(ic.imatmul(m_i[tu], Wu.T, "up"), ku)
        keyA, gh = ic.key_of(gw)
        keyB, uh = ic.key_of(uw)
        isel = np.isin(tu, ti)
        for nm, kk, hh_ in (("A", keyA, gh), ("B", keyB, uh)):
            pre = "g" if nm == "A" else "u"
            cnt[pre + "h_clamp"] += int((np.abs(hh_[isel]) > 127).sum())
            cnt[pre + "h_cond6"] += int(((hh_[isel] < -16384) | (hh_[isel] > 16383)).sum())
            cnt["key" + nm + "_dom"] += int(((kk[isel] < -16384) | (kk[isel] >= 16384)).sum())
        cnt["uw_cond7"] += int(((uw[isel] < -32768) | (uw[isel] > 32767)).sum())
        cnt["units"] += int(isel.sum() * 1152)
        prod = ic.tab(ic.TA, keyA) * ic.tab(ic.TB, keyB)
        accd = ic.imatmul(prod, Wd.T, "down")
        maxabs["acc_down"] = max(maxabs["acc_down"], int(np.abs(accd).max()))
        y = ic.rq(accd, kd)
        maxabs["y"] = max(maxabs["y"], int(np.abs(y).max()))
        # integer arm (its own set and weights)
        pos_i = np.nonzero(isel)[0]
        wi_e = (w_i[tu[pos_i]] * (sel_i[tu[pos_i]] == e)).sum(1)
        out_acc[tu[pos_i]] += wi_e[:, None] * y[pos_i]
        # attribution arm (float set and float weights, integer expert output)
        isf = np.isin(tu, tf)
        pos_f = np.nonzero(isf)[0]
        wf_e = (w_f[tu[pos_f]] * (sel_f[tu[pos_f]] == e)).sum(1)
        out_attr[tu[pos_f]] += wf_e[:, None] * (y[pos_f] / 2.0 ** 12)
        hint.append(e)
    if np.abs(out_acc).max() >= 2 ** 53:
        raise ic.Guard("weighted sum")
    out_i = ic.rq(out_acc, 13)
    out_int = out_i / 2.0 ** 12
    # ---- metrics
    diff_set = ~(sel_f == sel_i).all(1)
    gap_f = ic.kth_gap(s_f + bias, 8)
    gap_i = ic.kth_gap(sc_i.astype(np.float64), 8) / 2.0 ** 16
    per = []
    for pid, a, b in spans:
        of, oi, oa = out_f[a:b], out_int[a:b], out_attr[a:b]
        rel = float(np.linalg.norm(oi - of) / np.linalg.norm(of))
        tok = np.linalg.norm(oi - of, axis=1) / np.linalg.norm(of, axis=1)
        agree = ~diff_set[a:b]
        rel_agree = float(np.linalg.norm((oi - of)[agree]) / np.linalg.norm(of[agree])) if agree.any() else None
        rel_attr = float(np.linalg.norm(oa - of) / np.linalg.norm(of))
        per.append(dict(id=pid, n_tokens=b - a, rel_y=rel, tok_rel_median=float(np.median(tok)),
                        tok_rel_p99=float(np.quantile(tok, 0.99)), tok_rel_max=float(tok.max()),
                        set_diff=int(diff_set[a:b].sum()), rel_y_sets_agree=rel_agree, rel_y_attr=rel_attr))
    flips = [dict(token=int(t), gap_float=float(gap_f[t]), gap_int=float(gap_i[t]),
                  n_differ=int(8 - len(np.intersect1d(sel_f[t], sel_i[t])))) for t in np.nonzero(diff_set)[0]]
    rels = np.array([p["rel_y"] for p in per])
    res = dict(tag=tag, n_tokens=int(T), prompts=per,
               pooled=dict(rel_y=float(np.linalg.norm(out_int - out_f) / np.linalg.norm(out_f)),
                           rel_y_median_over_prompts=float(np.median(rels)), rel_y_max_over_prompts=float(rels.max()),
                           rel_y_min_over_prompts=float(rels.min()),
                           set_diff_tokens=int(diff_set.sum()), set_diff_frac=float(diff_set.mean()),
                           rel_y_attr=float(np.linalg.norm(out_attr - out_f) / np.linalg.norm(out_f))),
               flips=flips,
               exponents=dict(Em=Em, mx_u=mx_u, weights=ex, weight_max=mx, kr=kr, kg=kg, ku=ku, kd=kd,
                              E_A=ic.E_A, E_B=ic.E_B),
               ranges=dict(m_clamp=m_clamp, m_den=int(m_r.size), **st, **cnt, **maxabs),
               weights=dict(to_zero={k: v[0] for k, v in wst.items()}, nonzero={k: v[1] for k, v in wst.items()},
                            outside_13bit=w13bits),
               hashes=dict(m_i=sha(m_i), lr=sha(lr), sel_i=sha(sel_i), w_i=sha(w_i), out_i=sha(out_i),
                           out_f=sha(out_f)),
               seconds=dict(input=round(t_in, 1), total=round(time.time() - t0, 1)))
    json.dump(res, open(os.path.join(out_dir, "result-%s.json" % tag), "w"), indent=1)
    print(json.dumps(res["pooled"]), flush=True)
    return res


# ---------------------------------------------------------------- synthetic fixture (debug only)
def selftest(out):
    rng = np.random.default_rng(228)
    r = {}
    # rq vs python ints
    a = rng.integers(-2 ** 40, 2 ** 40, size=1000)
    for k in (1, 5, 13, 20):
        ref = [((int(v) + (1 << (k - 1))) // (1 << k)) for v in a]
        assert list(ic.rq(a, k)) == ref
    r["rq"] = "ok"
    # imatmul vs python ints
    m = rng.integers(-2047, 2048, size=(5, 64))
    w = rng.integers(-4095, 4096, size=(64, 32))
    got = ic.imatmul(m, w, "t")
    ref = [[sum(int(m[i, k]) * int(w[k, j]) for k in range(64)) for j in range(32)] for i in range(5)]
    assert got.tolist() == ref
    r["imatmul"] = "ok"
    # key_of vs docs/model.md section 7 written with python ints
    gw = rng.integers(-2 ** 17, 2 ** 17, size=500)
    k_, gh_ = ic.key_of(gw)
    for v, kk, hh in zip(gw, k_, gh_):
        v = int(v)
        g0 = ((v + 128) % 256) - 128
        h = (v - g0) // 256
        assert hh == h and kk == 256 * max(min(h, 127), -127) + g0
    r["key_of"] = "ok"
    # tables: Ts format reproduces docs/model.md table 3 at E = 6 for SiLU (spot values)
    Ts = ic.table_from(lambda z: z / (1 + np.exp(-z)), 6)
    assert ic.tab(Ts, np.array([0]))[0] == 0 and ic.tab(Ts, np.array([16383]))[0] == 4095
    r["TA_range"] = [int(ic.TA.min()), int(ic.TA.max())]
    r["TB_range"] = [int(ic.TB.min()), int(ic.TB.max())]
    r["SIG_0"] = int(ic.tab(ic.SIG, np.array([0]))[0])
    assert r["SIG_0"] == 32768
    # nvfp4 decode vs a slow loop on synthetic bytes
    codes = rng.integers(0, 256, size=(4, 16), dtype=np.uint8)
    scl = rng.integers(0, 0x7E, size=(4, 2), dtype=np.uint8)
    fast = ic.nvfp4_decode(codes, scl, 0.5)
    for i in range(4):
        for j in range(32):
            byte = int(codes[i, j // 2])
            c = byte & 0xF if j % 2 == 0 else byte >> 4
            assert fast[i, j] == ic.E2M1[c] * ic.F8[scl[i, j // 16]] * 0.5
    r["nvfp4"] = "ok"
    # f8 e4m3fn spot values
    assert ic.F8[0x38] == 1.0 and ic.F8[0x7E] == 448.0 and np.isnan(ic.F8[0x7F]) and ic.F8[0x01] == 2.0 ** -9
    r["f8"] = "ok"
    # short_conv vs naive
    x = rng.standard_normal((7, 3))
    wc = rng.standard_normal((3, 4))
    sc = ic.short_conv(x, wc)
    for t in range(7):
        for c in range(3):
            acc = sum(wc[c, i] * (x[t - 3 + i, c] if t - 3 + i >= 0 else 0.0) for i in range(4))
            assert abs(sc[t, c] - (acc + x[t, c]) / math.sqrt(5)) < 1e-12
    r["short_conv"] = "ok"
    # float attention on synthetic weights (small shape) runs and is causal
    cfg = dict(H=4, G=2, D=8, d=16, d_rel=4, rel_extent=8, window=8, qk_clip=22.6, rel_clip=8.0)
    Wsyn = dict(attn_norm=np.ones(16), wq=rng.standard_normal((32, 16)), wk=rng.standard_normal((16, 16)),
                wv=rng.standard_normal((16, 16)), wr=rng.standard_normal((16, 16)), wo=rng.standard_normal((16, 32)),
                gate_attn=rng.standard_normal((32, 16)), sink=rng.standard_normal((4, 16)),
                q_scale=np.ones((4, 8)), rel_scale=np.ones((4, 4)), rel_proj=rng.standard_normal((4, 8)),
                k_conv=rng.standard_normal((16, 4)), v_conv=rng.standard_normal((16, 4)),
                attn_sconv=rng.standard_normal((16, 4)), mlp_query=rng.standard_normal(16))
    x = rng.standard_normal((10, 16))
    u1, _ = ic.layer0_mlp_input(x, Wsyn, cfg)
    u2, _ = ic.layer0_mlp_input(x[:6], Wsyn, cfg)
    assert np.allclose(u1[:6], u2, atol=1e-12)
    r["attention_causal"] = "ok"
    # synthetic MoE through the integer path: top-k ties to lowest index
    sc_ = np.array([[5, 7, 7, 1, 7]])
    assert ic.topk_lowest(sc_, 2).tolist() == [[1, 2]]
    r["topk_ties"] = "ok"
    json.dump(r, open(out, "w"), indent=1)
    print(json.dumps(r))


if __name__ == "__main__":
    if sys.argv[1] == "selftest":
        selftest(sys.argv[2])
    else:
        run(sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5])
