"""Core arithmetic for 20261121-228 (see PREREG.md). numpy only.

- decode: NVFP4 (E2M1 codes + float8 e4m3fn block scales + per-expert amax / denominator), BF16, F8.
- float64 layer-0 forward up to the MLP block input m (attention in float64 only).
- float64 MLP block (reference) and the integer MLP block (main's rules + two new tables).
Nothing here reads the network or the filesystem except through the arrays it is given.
"""
import math
import numpy as np

# ---------------------------------------------------------------- decode
E2M1 = np.array([0.0, 0.5, 1.0, 1.5, 2.0, 3.0, 4.0, 6.0,
                 -0.0, -0.5, -1.0, -1.5, -2.0, -3.0, -4.0, -6.0], dtype=np.float64)


def f8e4m3_table():
    """float8 e4m3fn: 1 sign, 4 exponent (bias 7), 3 mantissa; no inf; S.1111.111 = NaN."""
    t = np.empty(256, dtype=np.float64)
    for b in range(256):
        s = -1.0 if b & 0x80 else 1.0
        e = (b >> 3) & 0xF
        m = b & 0x7
        if e == 0xF and m == 0x7:
            t[b] = np.nan
        elif e == 0:
            t[b] = s * (m / 8.0) * 2.0 ** (-6)
        else:
            t[b] = s * (1.0 + m / 8.0) * 2.0 ** (e - 7)
    return t


F8 = f8e4m3_table()


def bf16(raw, shape):
    u = np.frombuffer(raw, dtype=np.uint16).astype(np.uint32) << 16
    return u.view(np.float32).astype(np.float64).reshape(shape)


def f32(raw, shape):
    return np.frombuffer(raw, dtype="<f4").astype(np.float64).reshape(shape)


def nvfp4_decode(codes_u8, scale_u8, factor):
    """codes_u8: [rows, cols/2] uint8; scale_u8: [rows, cols/16] uint8 (e4m3fn); factor: float.
    Even element in the low nibble (PR 51050 core_model_loading patch: byte & 0xF first, byte >> 4 second)."""
    rows, half = codes_u8.shape
    vals = np.empty((rows, half * 2), dtype=np.float64)
    vals[:, 0::2] = E2M1[codes_u8 & 0xF]
    vals[:, 1::2] = E2M1[codes_u8 >> 4]
    sc = F8[scale_u8]
    vals = (vals.reshape(rows, half * 2 // 16, 16) * sc[:, :, None]).reshape(rows, half * 2)
    return vals * factor


# ---------------------------------------------------------------- float64 helpers
def rms(x, eps=1e-6):
    return x / np.sqrt(np.mean(x * x, axis=-1, keepdims=True) + eps)


def l2clip(x, thr):
    n = np.sqrt(np.sum(x * x, axis=-1, keepdims=True))
    return x * np.minimum(thr / (n + 1e-6), 1.0)


def short_conv(x, w):
    """x [T, C], w [C, K]: depthwise causal conv, zero history, out[t] = sum_i w[:, i] x[t-K+1+i]; then (out+x)/sqrt(K+1)."""
    T, C = x.shape
    K = w.shape[1]
    out = np.zeros_like(x)
    for i in range(K):
        lag = K - 1 - i
        if lag == 0:
            out += x * w[:, i]
        elif lag < T:
            out[lag:] += x[:-lag] * w[:, i]
    return (out + x) / math.sqrt(K + 1)


def sigmoid(x):
    return 1.0 / (1.0 + np.exp(-x))


def softmax_last(z):
    z = z - np.max(z, axis=-1, keepdims=True)
    e = np.exp(z)
    return e / np.sum(e, axis=-1, keepdims=True)


def layer0_mlp_input(x, W, cfg):
    """x: [T, d] = embed_norm(embed rows), float64. W: dict of float64 arrays (layer 0). Returns (u, g):
    u = x_mlpin / rms (normed, no gain), g = mlp_norm gain; m_float = u * g."""
    T, d = x.shape
    H, G, D = cfg["H"], cfg["G"], cfg["D"]
    a = rms(x) * W["attn_norm"]
    q = (a @ W["wq"].T).reshape(T, H, D)
    q = l2clip(q * W["q_scale"][None], cfg["qk_clip"])
    k = short_conv(a @ W["wk"].T, W["k_conv"]).reshape(T, G, D)
    k = l2clip(k, cfg["qk_clip"])
    v = short_conv(a @ W["wv"].T, W["v_conv"]).reshape(T, G, D)
    v = rms(v)
    r = (a @ W["wr"].T).reshape(T, H, cfg["d_rel"])
    r = l2clip(r * W["rel_scale"][None], cfg["rel_clip"])
    rl = np.einsum("thr,re->hte", r, W["rel_proj"])  # [H, T, extent]
    sink = a @ W["sink"].T  # [T, H]
    ti = np.arange(T)
    dist = ti[:, None] - ti[None, :]
    valid = (dist >= 0) & (dist < cfg["window"])
    gidx = np.clip(dist, 0, cfg["rel_extent"] - 1)
    inb = (dist >= 0) & (dist < cfg["rel_extent"])
    o = np.zeros((T, H, D))
    rep = H // G
    for h in range(H):
        g = h // rep
        s = (q[:, h, :] @ k[:, g, :].T) / math.sqrt(D)
        bias = np.take_along_axis(rl[h], gidx, axis=1) * inb
        s = s + bias
        s = np.where(valid, s, -np.inf)
        z = np.concatenate([s, sink[:, h][:, None]], axis=1)
        p = softmax_last(z)[:, :-1]
        o[:, h, :] = p @ v[:, g, :]
    o = o.reshape(T, H * D) * sigmoid(a @ W["gate_attn"].T)
    att = o @ W["wo"].T
    hs = short_conv(att, W["attn_sconv"])
    # block boundary at layer 0: block_states = [x]; stream reset to hs
    st = np.stack([x, hs], axis=1)  # [T, 2, d]
    stn = rms(st)
    sc = np.einsum("tnd,d->tn", stn, W["mlp_query"]) * d ** -0.5
    pw = softmax_last(sc)
    xin = np.einsum("tn,tnd->td", pw, stn)
    u = rms(xin)
    return u, hs


# ---------------------------------------------------------------- tables (docs/model.md section 4 format)
def rha(v):
    v = np.asarray(v, dtype=np.float64)
    return np.where(v >= 0, np.floor(v + 0.5), -np.floor(-v + 0.5))


KEYS = np.arange(-32768, 32768, dtype=np.int64)


def table_from(f, E, eg=8, smax=4095):
    c = np.minimum(np.maximum(KEYS, -64 * 2 ** eg), 64 * 2 ** eg - 1)
    z = c.astype(np.float64) / 2 ** eg
    return np.clip(rha(2.0 ** E * f(z)), -smax, smax).astype(np.int64)


def fA(z):
    return 4.0 * np.tanh(z / 4.0) / (1.0 + np.exp(-z))


def fB(z):
    return 25.0 * np.tanh(z / 25.0)


E_A, E_B = 9, 7
TA = table_from(fA, E_A)
TB = table_from(fB, E_B)


def sig_table():
    g = 1.0 + np.exp(-KEYS.astype(np.float64) / 256.0)
    q = 4096.0 / g
    return (16 * rha(q)).astype(np.int64)


SIG = sig_table()


def tab(t, key):
    return t[key + 32768]


# ---------------------------------------------------------------- integer helpers
def rq(a, k):
    """rq(a, k) = floor((a + 2^(k-1)) / 2^k) for k >= 1; exact a * 2^-k for k <= 0. a int64."""
    if k >= 1:
        return np.floor_divide(a + (1 << (k - 1)), 1 << k)
    return a * (1 << (-k))


def rne(x):
    return np.rint(x)


def exponent_of(mx, largest=4095):
    e = 0
    while np.rint(2.0 ** (e + 1) * mx) <= largest:
        e += 1
    while np.rint(2.0 ** e * mx) > largest:
        e -= 1
    return e


def low8(a):
    return np.mod(a + 128, 256) - 128


class Guard(Exception):
    pass


def imatmul(a_int, w_int, bound_note):
    """Exact integer matmul through float64 BLAS when every partial sum is < 2^53."""
    ma = float(np.max(np.abs(a_int))) if a_int.size else 0.0
    mw = float(np.max(np.abs(w_int))) if w_int.size else 0.0
    n = a_int.shape[-1]
    if ma * mw * n >= 2.0 ** 53:
        raise Guard("bound %s: %g" % (bound_note, ma * mw * n))
    r = a_int.astype(np.float64) @ w_int.astype(np.float64)
    return r.astype(np.int64)


def key_of(w):
    """docs/model.md section 7: g0 = low8(w), gh = (w - g0)/256, gc = clamp(gh; 127), key = 256 gc + g0."""
    g0 = low8(w)
    gh = (w - g0) // 256
    gc = np.clip(gh, -127, 127)
    return 256 * gc + g0, gh


def topk_lowest(score, k):
    """Top-k per row, ties to the lowest index (stable sort on -score)."""
    idx = np.argsort(-score, axis=1, kind="stable")[:, :k]
    return np.sort(idx, axis=1)


def kth_gap(score, k):
    s = -np.sort(-score, axis=1)
    return s[:, k - 1] - s[:, k]
