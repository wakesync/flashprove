#!/usr/bin/env python3
"""Parametric fixed-point GLM KDA slice: test vectors, independent references, circuit lowering.

Semantics extend PR19's signed staged-floor contract (bits=4 reproduces its scale-4, [-8,7] ranges)
to key dimension d_k, value dimension d_v, T tokens and H independent heads. Values are signed
`bits`-bit integers with `frac = bits - 2` fractional bits (real range [-2, 2)). Per token, per head:

    D[i,j]   = floor(S[i,j] * g[i] / 2^f)                  every product rounded separately
    mem[j]   = floor(sum_i D[i,j] * k[i] / 2^f)            REDUCTION POLICY: exact integer
    A[j]     = v[j] - mem[j]                                accumulation, ONE floor per output
    delta[j] = floor(A[j] * beta / 2^f)
    U[i,j]   = floor(k[i] * delta[j] / 2^f)
    S'[i,j]  = D[i,j] + U[i,j]
    o[j]     = floor(sum_i S'[i,j] * q[i] / 2^f)           same reduction policy

Every rounded/linear intermediate must lie in [-2^(bits-1), 2^(bits-1)); overflow REJECTS (never
saturates or wraps). g, k, v, beta, q and the initial state are public, already prepared
(post-exp decay, post-l2norm, post-1/sqrt(d_k) query scaling); quantization of the float inputs
to fixed point happens on the host, outside the proof (round to nearest, ties up). Outputs of
every token and the final state are public. This is NOT the publisher's numerical contract.
"""
from array import array
import math, struct
import numpy as np

P = 2**64 - 2**32 + 1
MAX_TERMS = 8  # research/operators/affine_rows/product.h public_fault limit, unchanged


class Overflow(ValueError):
    pass


# ----------------------------------------------------------------------------------------------
# synthetic test vectors shaped like the configured recurrent fallback's inputs (no weights)
def float_vectors(seed, d_k, d_v, tokens, heads, lower_bound=-5.0):
    rng = np.random.default_rng(seed)
    heads_out = []
    for _ in range(heads):
        S0 = rng.uniform(-0.5, 0.5, (d_k, d_v)).astype(np.float32)
        toks = []
        for _ in range(tokens):
            k = rng.standard_normal(d_k); k = k / np.sqrt((k * k).sum() + 1e-6)          # l2norm, eps 1e-6
            q = rng.standard_normal(d_k); q = q / np.sqrt((q * q).sum() + 1e-6) / math.sqrt(d_k)
            v = rng.uniform(-1.0, 1.0, d_v)
            g = np.exp(lower_bound / (1.0 + np.exp(-rng.standard_normal(d_k))))  # exp(lb*sigmoid(x))
            beta = 1.0 / (1.0 + math.exp(-rng.standard_normal()))
            toks.append(tuple(np.float32(x) if np.isscalar(x) else x.astype(np.float32) for x in (g, k, v, beta, q)))
        heads_out.append((S0, toks))
    return heads_out


def float32_reference(S0, toks):
    """Pinned Transformers recurrent_kimi_delta_attention post-gate order, numpy float32.
    numpy's float32 reductions are not bit-identical to torch's; NOT kernel execution."""
    S = S0.astype(np.float32); outs = []
    for g, k, v, beta, q in toks:
        S = (S * g[:, None]).astype(np.float32)
        mem = (S * k[:, None]).sum(axis=0, dtype=np.float32)
        delta = ((v - mem) * beta).astype(np.float32)
        S = (S + k[:, None] * delta[None, :]).astype(np.float32)
        outs.append((S * q[:, None]).sum(axis=0, dtype=np.float32))
    return S, outs


def quantize(x, bits):
    f = bits - 2; lo, hi = -(1 << (bits - 1)), (1 << (bits - 1)) - 1
    raw = np.floor(np.asarray(x, dtype=np.float64) * (1 << f) + 0.5)
    clipped = int(((raw < lo) | (raw > hi)).sum())
    return np.clip(raw, lo, hi).astype(np.int64), clipped


def quantize_head(S0, toks, bits):
    clipped = 0
    S, c = quantize(S0, bits); clipped += c
    qt = []
    for g, k, v, beta, q in toks:
        row = []
        for x in (g, k, v, beta, q):
            y, c = quantize(x, bits); clipped += c; row.append(y)
        row[3] = int(row[3])
        qt.append(tuple(row))
    return S, qt, clipped


def integer_reference(S, toks, bits):
    """numpy int64 floor-division reference; independent of the divmod lowering below."""
    f = bits - 2; lo, hi = -(1 << (bits - 1)), (1 << (bits - 1)) - 1; sc = np.int64(1 << f)
    def ok(x):
        if (np.asarray(x) < lo).any() or (np.asarray(x) > hi).any():
            raise Overflow('overflow: reject, never saturate or wrap')
        return x
    for x in [S] + [z for t in toks for z in t]:
        ok(x)
    S = S.astype(np.int64); outs = []
    for g, k, v, beta, q in toks:
        D = ok(np.floor_divide(S * g[:, None], sc))
        mem = ok(np.floor_divide((D * k[:, None]).sum(axis=0), sc))
        A = ok(v - mem)
        delta = ok(np.floor_divide(A * np.int64(beta), sc))
        U = ok(np.floor_divide(k[:, None] * delta[None, :], sc))
        S = ok(D + U)
        outs.append(ok(np.floor_divide((S * q[:, None]).sum(axis=0), sc)))
    return S, outs


# ----------------------------------------------------------------------------------------------
# same-oracle lowering: product cells a*b=c, shared-wire equalities, sparse affine rows (<=8 terms)
class Builder:
    def __init__(self, bits):
        self.bits = bits; self.frac = bits - 2
        self.a = []; self.b = []; self.c = []
        self.coords = []                 # (row, col, value)
        self.wires = array('Q')          # lr, lc, rr, rc
        self.rel_len = array('Q'); self.rel_target = []; self.terms = []  # terms: (row, col, coef)
        self.rounds = []; self.bit_cols = []; self.max_abs = 0

    def val(self, x):
        r, c = x
        return (self.a, self.b, self.c)[r][c]

    def new_col(self, a, b):
        self.a.append(a); self.b.append(b); self.c.append(a * b)
        self.max_abs = max(self.max_abs, abs(a * b))
        return len(self.a) - 1

    def rel(self, terms, target=0):
        assert 1 <= len(terms) <= MAX_TERMS
        self.rel_len.append(len(terms)); self.rel_target.append(target)
        for (r, c), coef in terms:
            self.terms.append((r, c, coef))
        return len(self.rel_len) - 1

    def public(self, row, col, value):
        return self.rel([((row, col), 1)], value)

    def gate(self, x, y):
        """x, y: private cell (row, col) or ('pub', int). Public operands get a unit affine row."""
        av = x[1] if x[0] == 'pub' else self.val(x)
        bv = y[1] if y[0] == 'pub' else self.val(y)
        col = self.new_col(av, bv)
        for row, z in enumerate((x, y)):
            if z[0] == 'pub':
                self.public(row, col, z[1])
            else:
                self.wires.extend((z[0], z[1], row, col))
        return (2, col)

    def private(self, n):
        col = self.new_col(n, 1)
        self.public(1, col, 1)  # multiplication by one anchors linear storage
        return (0, col)

    def linear_eq(self, terms, target):
        """sum coef*cell = target, split into <=8-term rows via exact partial-sum storage cells."""
        terms = list(terms)
        while len(terms) > MAX_TERMS:
            head, terms = terms[:MAX_TERMS - 1], terms[MAX_TERMS - 1:]
            s = self.private(sum(self.val(x) * k for x, k in head))
            self.rel([(s, 1)] + [(x, -k) for x, k in head], 0)
            terms = [(s, 1)] + terms
        self.rel(terms, target)

    def bounded(self, x, width, signed):
        offset = 1 << (width - 1) if signed else 0
        n = self.val(x) + offset
        if not 0 <= n < (1 << width):
            raise Overflow('range')
        terms = [(x, 1)]
        for i in range(width):
            bit = (n >> i) & 1
            col = self.new_col(bit, bit)
            self.wires.extend((0, col, 1, col))
            self.rel([((2, col), 1), ((0, col), -1)], 0)
            self.bit_cols.append(col)
            terms.append(((0, col), -(1 << i)))
        self.linear_eq(terms, -offset)

    def rounded_sum(self, pairs):
        prods = [self.gate(x, y) for x, y in pairs]
        raw = sum(self.val(p) for p in prods)
        self.max_abs = max(self.max_abs, abs(raw))
        qv, rv = divmod(raw, 1 << self.frac)
        q = self.private(qv); r = self.private(rv)
        self.bounded(q, self.bits, True); self.bounded(r, self.frac, False)
        self.linear_eq([(p, 1) for p in prods] + [(q, -(1 << self.frac)), (r, -1)], 0)
        self.rounds.append((q[1], r[1]))
        return q

    def linear_val(self, terms, const):
        x = self.private(sum(self.val(z) * k for z, k in terms) + const)
        self.linear_eq([(x, 1)] + [(z, -k) for z, k in terms], const)
        self.bounded(x, self.bits, True)
        return x


def lower_head(B, S0, toks, d_k, d_v, publish_coordinate):
    """Returns (final state values, outputs per token) computed by the lowering itself."""
    S = [[('pub', int(S0[i, j])) for j in range(d_v)] for i in range(d_k)]
    outs = []; out_rel = None
    for t, (g, k, v, beta, q) in enumerate(toks):
        D = [[B.rounded_sum([(S[i][j], ('pub', int(g[i])))]) for j in range(d_v)] for i in range(d_k)]
        mem = [B.rounded_sum([(D[i][j], ('pub', int(k[i]))) for i in range(d_k)]) for j in range(d_v)]
        A = [B.linear_val([(mem[j], -1)], int(v[j])) for j in range(d_v)]
        delta = [B.rounded_sum([(A[j], ('pub', int(beta)))]) for j in range(d_v)]
        U = [[B.rounded_sum([(('pub', int(k[i])), delta[j])]) for j in range(d_v)] for i in range(d_k)]
        S = [[B.linear_val([(D[i][j], 1), (U[i][j], 1)], 0) for j in range(d_v)] for i in range(d_k)]
        o = [B.rounded_sum([(S[i][j], ('pub', int(q[i]))) for i in range(d_k)]) for j in range(d_v)]
        last = t == len(toks) - 1
        for j in range(d_v):
            if last and j == 0 and publish_coordinate:
                B.coords.append((o[j][0], o[j][1], B.val(o[j])))
            else:
                B.public(o[j][0], o[j][1], B.val(o[j]))
        outs.append([B.val(x) for x in o])
    for i in range(d_k):
        for j in range(d_v):
            r = B.public(S[i][j][0], S[i][j][1], B.val(S[i][j]))
            if out_rel is None:
                out_rel = r
    return [[B.val(S[i][j]) for j in range(d_v)] for i in range(d_k)], outs, out_rel


def build(seed, d_k, d_v, tokens, heads, bits):
    """Quantize vectors, run the integer reference, lower, and cross-check lowering == reference."""
    vecs = float_vectors(seed, d_k, d_v, tokens, heads)
    B = Builder(bits); report = dict(clipped_inputs=0, max_abs_err=0.0, max_abs_err_state=0.0, max_abs_err_output=0.0)
    out_rel = None; sc = float(1 << (bits - 2))
    for h, (S0f, tf) in enumerate(vecs):
        S0, qt, clipped = quantize_head(S0f, tf, bits); report['clipped_inputs'] += clipped
        Sref, oref = integer_reference(S0, qt, bits)
        Sl, ol, r = lower_head(B, S0, qt, d_k, d_v, publish_coordinate=(h == heads - 1))
        assert np.array_equal(np.array(Sl), Sref) and all(np.array_equal(np.array(a), b) for a, b in zip(ol, oref)), 'lowering != reference'
        if out_rel is None:
            out_rel = r
        Sf, of = float32_reference(S0f, tf)
        es = float(np.abs(Sref / sc - Sf).max()); eo = max(float(np.abs(a / sc - b).max()) for a, b in zip(oref, of))
        report['max_abs_err_state'] = max(report['max_abs_err_state'], es)
        report['max_abs_err_output'] = max(report['max_abs_err_output'], eo)
    report['max_abs_err'] = max(report['max_abs_err_state'], report['max_abs_err_output'])
    # every bounded integer identity stays far below P/2: field equality == integer equality
    assert B.max_abs + (1 << (2 * bits)) < (1 << 62), 'field wraparound margin'
    B.out_rel = out_rel
    return B, report


def write_fixture(B, path, meta):
    n = len(B.a); L = max(7, math.ceil(math.log2(n)))
    first_q, first_r = B.rounds[0]
    attack_bit = B.bit_cols[len(B.bit_cols) // 2]
    hdr = [0x4b444153_30303031, L, n, len(B.coords), len(B.wires) // 4, len(B.rel_len), len(B.terms),
           first_q, first_r, attack_bit, B.out_rel, meta['d_k'], meta['d_v'], meta['tokens'], meta['heads'], meta['bits']]
    m = lambda x: x % P
    with open(path, 'wb') as f:
        f.write(struct.pack('<16Q', *hdr))
        for col in (B.a, B.b, B.c):
            f.write(array('Q', (m(x) for x in col)).tobytes())
        f.write(array('Q', (m(x) for c in B.coords for x in c)).tobytes())
        f.write(B.wires.tobytes())
        f.write(B.rel_len.tobytes())
        f.write(array('Q', (m(x) for x in B.rel_target)).tobytes())
        f.write(array('Q', (m(x) for t in B.terms for x in t)).tobytes())
    return dict(log_len=L, columns=n, coordinates=len(B.coords), wires=len(B.wires) // 4, affine_rows=len(B.rel_len),
                affine_terms=len(B.terms), linear_claims=len(B.coords) + len(B.wires) // 4 + len(B.rel_len),
                rounded=len(B.rounds), bit_columns=len(B.bit_cols), max_abs_integer=B.max_abs)


def columns_formula(d_k, d_v, tokens, heads, bits):
    """Closed-form column count of the lowering above (checked against the builder in sweep.py)."""
    f = bits - 2
    def chain(n):  # extra partial-sum cells linear_eq adds for an n-term identity
        x = 0
        while n > MAX_TERMS:
            n -= MAX_TERMS - 2; x += 1
        return x
    rounded = lambda m: m + 2 + bits + f + chain(m + 2) + chain(bits + 1) + chain(f + 1)
    linear = lambda m: 1 + bits + chain(m + 1) + chain(bits + 1)
    per_token = (d_k * d_v * rounded(1) + d_v * rounded(d_k) + d_v * linear(1) + d_v * rounded(1)
                 + d_k * d_v * rounded(1) + d_k * d_v * linear(2) + d_v * rounded(d_k))
    return heads * tokens * per_token
