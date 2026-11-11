#!/usr/bin/env python3
"""Reference arithmetic and committed integer lowerings for the #8 reference-divergence harness.

Definitions are those registered in PREREG.md ("Reference definitions", "Integer pipeline conversion").
- round_to_format: generic RNE rounding of float64 to a binary float format with subnormals.
- BF16: 7 stored mantissa bits, emin -126, max (2 - 2^-7) * 2^127, no saturation (overflow counted).
- E4M3 (OCP OFP8, E4M3FN): 3 stored mantissa bits, emin -6, max 448, satfinite.
The integer lowerings mirror research/operators/qwen_ops (proof.cpp / crosscheck.py) and read the committed tables.
"""
import pathlib

import numpy as np

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[1]
TABLES = ROOT / 'research/operators/qwen_ops/tables'
NONLINEAR = ('silu', 'sigmoid', 'softplus', 'decay-half', 'decay-one', 'decay-two')
OPS = NONLINEAR + ('conv', 'l2', 'rms', 'rotary')
FS = (12, 14, 16)
THETA = 10000000.0

BF16 = dict(mant=7, emin=-126, maxv=(2 - 2.0 ** -7) * 2.0 ** 127)
E4M3 = dict(mant=3, emin=-6, maxv=448.0)


def round_to_format(v, mant, emin, maxv, saturate):
    """RNE of float64 v to the format. Returns (rounded float64, overflow/saturation count, underflow-to-zero count)."""
    v = np.asarray(v, dtype=np.float64)
    _, e = np.frexp(v)                     # v = f * 2^e, |f| in [0.5, 1)
    exp = np.maximum(e - 1, emin)          # unbiased exponent of the binade, subnormals share emin
    quantum = np.ldexp(1.0, exp - mant)
    r = np.rint(v / quantum) * quantum     # v / quantum exact (power of two); np.rint is ties-to-even
    r = np.where(v == 0, 0.0, r)
    over = np.abs(r) > maxv
    if saturate:
        # PREREG: |v| > max maps to sign * max and is counted (counted on the input, before rounding).
        n_over = int((np.abs(v) > maxv).sum())
        r = np.where(over, np.copysign(maxv, v), r)
    else:
        n_over = int(over.sum())
        r = np.where(over, np.copysign(np.inf, v), r)
    n_under = int(((v != 0) & (r == 0)).sum())
    return r, n_over, n_under


def bf16(v):
    return round_to_format(v, saturate=False, **BF16)


def fp8_quant(v, scale):
    """q = E4M3(RNE, satfinite)(v * s); dequantized v' = q / s in FP32."""
    s = np.float32(scale)
    scaled = (np.asarray(v, dtype=np.float64) * np.float64(s))
    q, n_sat, n_under = round_to_format(scaled, saturate=True, **E4M3)
    return (q.astype(np.float32) / s).astype(np.float32), n_sat, n_under


# ---------------------------------------------------------------- float semantics

def nonlinear_f(name, x, dt):
    x = x.astype(dt)
    one = dt(1)
    sig = one / (one + np.exp(-x))
    sp = np.log1p(np.exp(x))
    return {'silu': x * sig, 'sigmoid': sig, 'softplus': sp, 'decay-half': np.exp(-dt(0.5) * sp),
            'decay-one': np.exp(-sp), 'decay-two': np.exp(-dt(2) * sp)}[name]


def seq_sum(terms, dt):
    """Sequential left-to-right sum over the last axis in dtype dt."""
    acc = terms[..., 0].astype(dt)
    for j in range(1, terms.shape[-1]):
        acc = (acc + terms[..., j].astype(dt)).astype(dt)
    return acc


def conv_f(inputs, taps, dt):
    """inputs [n,7] (3 history + 4 new), taps [n,4] -> [n,4]; y[t] = sum_j w[j]*in[t+j]."""
    inputs = inputs.astype(dt)
    taps = taps.astype(dt)
    out = []
    for t in range(4):
        prods = np.stack([(inputs[:, t + j] * taps[:, j]).astype(dt) for j in range(4)], axis=-1)
        out.append(seq_sum(prods, dt))
    return np.stack(out, axis=-1)


def norm_f(op, x, dt):
    x = x.astype(dt)
    energy = seq_sum((x * x).astype(dt), dt)
    if op == 'rms':
        energy = (energy / dt(x.shape[-1])).astype(dt)
    inv = (dt(1) / np.sqrt(energy)).astype(dt)
    return (x * inv[:, None]).astype(dt)


def rotary_angles(pos, dt):
    j = np.arange(32, dtype=dt)
    inv_freq = (dt(1) / (dt(THETA) ** (j / dt(32)))).astype(dt)
    return (pos.astype(dt)[:, None] * inv_freq[None, :]).astype(dt)


def rotary_f(x, cos, sin, dt):
    """Rotate-half on the 64-coordinate prefix; returns the 64 rotated coordinates [n,64]."""
    x = x.astype(dt)
    a, b = x[:, :32], x[:, 32:64]
    y1 = (a * cos - b * sin).astype(dt)
    y2 = (b * cos + a * sin).astype(dt)
    return np.concatenate([y1, y2], axis=-1)


# ---------------------------------------------------------------- committed integer lowerings

_tables = {}


def table(name, f):
    key = (name, f)
    if key not in _tables:
        fn = f'rotary-f{f}.i64le' if name == 'rotary' else f'{name}-f{f}.i64le'
        _tables[key] = np.frombuffer((TABLES / fn).read_bytes(), dtype='<i8').astype(np.int64)
    return _tables[key]


def int_nonlinear(name, X, f):
    S = 1 << f
    key = X // (S // 256) + 2048
    assert key.min() >= 0 and key.max() < 4096
    return table(name, f)[key]


def int_conv(inputs, taps, f):
    S = 1 << f
    return np.stack([sum(inputs[:, t + j] * taps[:, j] for j in range(4)) // S for t in range(4)], axis=-1)


def int_norm(op, X, f):
    """Returns (y [n,D] int64, key [n]); rows with key outside [0,4096) are out of domain (y undefined)."""
    S = 1 << f
    D = X.shape[-1]
    E = (X * X).sum(axis=-1)
    key = (1024 * E) // (D * S * S) - 256
    ok = (key >= 0) & (key < 4096)
    coef = table('l2-128' if op == 'l2' else 'rsqrt', f)[np.where(ok, key, 0)]
    return (X * coef[:, None]) // S, key


def int_rotary(X, pos, f):
    """Full 256-word output (the C++ fixture layout); coordinates 64..255 unchanged."""
    S = 1 << f
    tab = table('rotary', f)
    j = np.arange(32)
    idx = 64 * pos.astype(np.int64)[:, None] + 2 * j[None, :]
    C, U = tab[idx], tab[idx + 1]
    a, b = X[:, :32], X[:, 32:64]
    y = X.copy()
    y[:, :32] = (a * C - b * U) // S
    y[:, 32:64] = (b * C + a * U) // S
    return y


def to_int(x, f, lo_mult, hi_mult):
    """X = RNE(x * S), clamped to [lo_mult*S, hi_mult*S - 1]. Returns (X int64, clamp count)."""
    S = 1 << f
    X = np.rint(np.asarray(x, dtype=np.float64) * S)
    lo, hi = lo_mult * S, hi_mult * S - 1
    n = int(((X < lo) | (X > hi)).sum())
    return np.clip(X, lo, hi).astype(np.int64), n
