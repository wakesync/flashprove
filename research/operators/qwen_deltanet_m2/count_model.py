#!/usr/bin/env python3
"""Counting model of the Qwen DeltaNet lowering on the wide product oracle (M2 design, H1-H3).

It walks the SAME emission order as the builders in research/operators/qwen_deltanet/test.cpp (M1, arm
'm1') and research/operators/qwen_deltanet_lookup/test.cpp (M1b, arm 'm1b'), and counts product
columns, relations, relation terms, RNG range cells and LKP keys. No proof is built. H1 checks the
counts against the measured #47 / #63 statements. Arms 'A' and 'B' are the M2 lowering (DESIGN.md):
  A  remainders as exact bits (as M1b)
  B  remainders lookup-exact: each 12-bit remainder limb is ONE product cell that is a direct LKP key
     into the 2^12 range table; a 24-bit remainder is two such limbs (coefficients 1 and 2^12) in the
     floor relation itself, so no recomposition relation is needed.
M2 adds (DESIGN.md section 4): private head output o (RNG cell), the proved gated RMSNorm of o
(o*o and o*Rc gates, isqrt and reciprocal scalars with exact limbs, w RNG cell, y floor), T = 16.
Usage: count_model.py [--json out.json]
"""
import argparse, json, math

M1_MEASURED = dict(columns_used=2_338_816, log_length=22, relations=4_761_088, terms=11_430_400, range_cells=0)
M1B_MEASURED = dict(columns_used=1_310_720, columns_nonregion=1_074_176, log_length=21, relations=2_231_808, terms=5_174_272, range_cells=67_072)
P2 = lambda n: 1 << max(0, math.ceil(math.log2(n))) if n > 0 else 0

class C:
    """Counters; the methods mirror the builder's lambdas col/rel/bits/rcell, plus key() for arm B."""
    def __init__(s, arm):
        s.arm, s.cols, s.rels, s.terms, s.rcells, s.keys = arm, 0, 0, 0, 0, 0
    def col(s, n=1): s.cols += n
    def rel(s, nterms, n=1): s.rels += n; s.terms += nterms * n
    def rcell(s, n=1): s.rcells += n
    def key(s, n=1): s.keys += n
    def bits(s, width, n=1):
        """width-bit unsigned decomposition: width [x,x,x] columns, 2 relations of 2 terms each; returns
        the number of terms it adds to the caller's relation."""
        s.cols += width * n; s.rels += 2 * width * n; s.terms += 4 * width * n
        return width
    def rem(s, width, n=1):
        """An exact remainder in [0, 2^width), width in {12, 24}. Returns the terms added to the
        caller's relation. Arm m1/m1b/A: bits. Arm B: width/12 key cells (each a product column [r,0,0]
        laid in the key region; counted as keys, not as gate columns)."""
        if s.arm in ('m1', 'm1b', 'A'):
            return s.bits(width, n)
        assert width % 12 == 0
        s.key(width // 12 * n)
        return width // 12

def head(arm, D=128, T=4, F=12, o_private=False, norm=False):
    c = C(arm)
    q19 = arm == 'm1'  # M1: 19-bit range decomposition of S', M, delta (no RNG)
    for t in range(T):
        # g1 (decay) and g2 (memory read), per state cell
        c.col(2 * D * D)
        c.rel(1 if t == 0 else 2, D * D)  # g1.a = S0 target (t = 0) or = canonical previous cell
        c.rel(1, D * D)                   # g1.b = a
        c.rel(2, D * D)                   # g2.a = canonical
        c.rel(1, D * D)                   # g2.b = k[i]
        for _ in range(D):  # per value column j
            c.col(1); c.rel(D + 1)        # g5 = P_j * a, with P_j = sum of g2.c
            c.rel(1)                      # g5.b = a
            c.col(1)                      # g6 = (v - M) * beta
            ft = 2 + c.rem(2 * F); c.rel(ft)  # 2^2F (v - g6.a) + r - g5.c = 0
            if q19:
                c.rel(1 + c.bits(19))     # M + 2^18 = bits (M = v - g6.a)
            else:
                c.rcell(); c.rel(2)       # M (range cell) + g6.a = v
            c.rel(1)                      # g6.b = beta
            c.col(1); c.rel(1)            # dcell = k[0] * delta; .a = k[0]
            dt = 2 + c.rem(F); c.rel(dt)  # 2^F delta + r - g6.c = 0
            if q19:
                c.rel(1 + c.bits(19))     # delta + 2^18 = bits
            else:
                c.rcell(2); c.rel(3)      # delta = 2^18 hi + lo
        # update + output gate, per state cell
        c.col(D * D)                                   # g4 = S' * q[i]
        c.col((D - 1) * D); c.rel(1, (D - 1) * D); c.rel(2, (D - 1) * D)  # g3 for i > 0: .a = k[i], .b = dcell
        c.rel(1, D * D)                                # g4.b = q[i]
        w = c.rem(F, D * D); c.rel(3 + w, D * D)       # 2^F g4.a + r - g1.c - g3.c = 0 (w terms per remainder)
        if q19:
            c.bits(19, D * D); c.rel(20, D * D)       # bits(S' + 2^18, 19), then g4.a + 2^18 = bits
        else:
            c.rcell(D * D); c.rel(2, D * D)            # g4.a - range cell = 0
        # output o[j] = floor(sum_i g4.c / 2^F)
        for _ in range(D):
            r = c.rem(F)
            if o_private:
                c.rcell(); c.rel(D + r + 1)            # -2^F o (cell) + sum g4.c - r = 0
            else:
                c.rel(D + r)                           # target -2^F o
        if norm:
            gated_norm(c, D, F)
        if t == T - 1:
            c.rel(1, D * D)                            # S_T target
    return c

def gated_norm(c, D, F):
    """Proved gated RMSNorm of the private o (DESIGN.md section 4.4). Per token:
    Vx = sum o^2; sigma = isqrt(Vx + eps); Rc = floor(2^36 / sigma); w = floor(o Rc / 2^24);
    y = floor(cg w / 2^F) with cg public (verifier-derived from gain, SiLU(z), sqrt(D)); y public."""
    # scalars: sigma (2 exact 12-bit limbs), e1 = Vx + eps - sigma^2 (2 limbs), e2 = sigma^2 + 2 sigma - Vx - eps (2),
    # Rc (3 limbs), rr = 2^36 - Rc sigma (2), sigma - 1 - rr (2)
    if c.arm == 'B':
        c.key(2 + 2 + 2 + 3 + 2 + 2)
    else:
        c.bits(24 + 24 + 24 + 36 + 24 + 24)
    c.col(2)                      # gates sigma*sigma, Rc*sigma
    c.rel(3, 2); c.rel(4, 2)      # their operands tied to the limb sums (2 ties each)
    c.rel(D + 4 if c.arm == 'B' else D + 2 + 24)  # e1 relation: sum o^2 + eps - sigma^2 - e1 = 0
    c.rel(D + 5 if c.arm == 'B' else D + 3 + 24)  # e2 relation
    c.rel(4 if c.arm == 'B' else 2 + 36 + 0)      # rr = 2^36 - Rc sigma (limbs)
    c.rel(6 if c.arm == 'B' else 2 + 48)          # sigma - 1 - rr = limbs
    for _ in range(D):
        c.col(2)                  # o*o and o*Rc
        c.rel(2, 2)               # o*o: .a = o, .b = o
        c.rel(2, 1); c.rel(4 if c.arm == 'B' else 4, 1)  # o*Rc: .a = o, .b = Rc limbs
        c.rcell()                 # w (|w| <= 2^12 honest)
        r = c.rem(2 * F); c.rel(2 + r)   # 2^24 w + r - (o Rc) = 0
        r = c.rem(F); c.rel(1 + r)       # 2^F y + r - cg w = 0, target y (public)

def layout(c, arm, T):
    """Table length. m1: the columns, padded to 2^L. m1b: one aligned RNG region after the gates (as the
    builder). A/B: RNG cells as one 16-column matrix per power-of-two piece (RngShape takes several
    matrices), LKP keys as parts (LkpPublic::parts, one function), regions first in decreasing size,
    each aligned to its size, then the gates."""
    out = {}
    if arm == 'm1':
        used = c.cols; L = max(1, math.ceil(math.log2(used)))
        return dict(columns_used=used, layout=used, log_length=L)
    if arm == 'm1b':
        rows = P2(math.ceil(c.rcells / 16)); size = rows * 16
        base = math.ceil(c.cols / size) * size; total = base + size
        return dict(columns_used=total, columns_nonregion=c.cols, rng_rows=rows, log_length=math.ceil(math.log2(total)))
    def pieces(n, quantum):
        # binary decomposition of n rounded up to a multiple of quantum
        n = math.ceil(n / quantum) * quantum; out = []
        b = 1 << n.bit_length()
        while n:
            b >>= 1
            if n & b: out.append(b); n -= b
        return out
    rng_rows = pieces(math.ceil(c.rcells / 16), 1024)
    key_parts = pieces(c.keys, 16384) if c.keys else []
    blocks = sorted([r * 16 for r in rng_rows] + key_parts, reverse=True)
    pos = 0
    for b in blocks: pos = math.ceil(pos / b) * b + b
    total = pos + c.cols
    L = math.ceil(math.log2(total))
    # RNG digits must fit one row: digit_columns (pow2 of cell rows) x Np (16 at N = 10)
    dc = P2(sum(rng_rows)) if rng_rows else 0
    L = max(L, math.ceil(math.log2(dc * 16)) if dc else 0)
    return dict(columns_used=total, columns_nonregion=c.cols, rng_rows=rng_rows, key_parts=key_parts, digit_entries=2 * sum(rng_rows) * 10, log_length=L)

def summary(arm, **kw):
    c = head(arm, **kw); D, T = kw.get('D', 128), kw.get('T', 4)
    lay = layout(c, arm, T)
    cells = D * D * T
    per_cell = (c.cols + c.rcells + c.keys) / cells
    return dict(arm=arm, D=D, T=T, o_private=kw.get('o_private', False), norm=kw.get('norm', False),
                gate_columns=c.cols, range_cells=c.rcells, lkp_keys=c.keys, relations=c.rels, terms=c.terms,
                product_columns_per_state_cell_per_token=round(per_cell, 3), relations_per_state_cell_per_token=round(c.rels / cells, 3), **lay)

def estimate_prove_s(log_length, relations):
    """Indicative only: linear in the table length from the two measured points (#47: 2^22, 51.4 s;
    #63: 2^21, 39.2 s). Not a measurement."""
    a = (51.43 - 39.18) / (2 ** 22 - 2 ** 21); b = 39.18 - a * 2 ** 21
    return round(a * 2 ** log_length + b, 1)

def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--json'); a = ap.parse_args()
    res = {}
    m1 = summary('m1'); m1b = summary('m1b')
    h1 = {
        'm1': {k: (m1[k], v, m1[k] == v) for k, v in M1_MEASURED.items() if k in m1 or k == 'range_cells'},
        'm1b': {k: (m1b.get(k), v, m1b.get(k) == v) for k, v in M1B_MEASURED.items()},
    }
    h1['m1']['terms'] = (m1['terms'], M1_MEASURED['terms'], m1['terms'] == M1_MEASURED['terms'])
    h1['m1']['relations'] = (m1['relations'], M1_MEASURED['relations'], m1['relations'] == M1_MEASURED['relations'])
    h1_pass = all(x[2] for d in h1.values() for x in d.values())
    res['H1'] = dict(checks=h1, pass_=h1_pass, model_m1=m1, model_m1b=m1b)
    A4 = summary('A', T=4); B4 = summary('B', T=4)
    ratio_cols = B4['product_columns_per_state_cell_per_token'] / A4['product_columns_per_state_cell_per_token']
    ratio_rels = B4['relations'] / A4['relations']
    res['H2'] = dict(armA_m1b_shape=A4, armB_m1b_shape=B4, ratio_columns_per_cell=round(ratio_cols, 3), ratio_relations=round(ratio_rels, 3),
                     ratio_terms=round(B4['terms'] / A4['terms'], 3), pass_=ratio_cols <= 0.5 and ratio_rels <= 0.5,
                     note='arm A at the M1b shape equals M1b (same lowering); arm B swaps exact bits for direct LKP keys')
    m2 = dict(D=128, o_private=True, norm=True)
    A16 = summary('A', T=16, **m2); B16 = summary('B', T=16, **m2)
    maxT = {}
    for arm in ('A', 'B'):
        T = 1
        while summary(arm, T=T + 1, **m2)['log_length'] <= 22 and summary(arm, T=T + 1, **m2)['relations'] <= 2 ** 23: T += 1
        maxT[arm] = T
    layer = {arm: dict(relations_per_token_per_layer=48 * s['relations'] // 16) for arm, s in (('A', A16), ('B', B16))}
    for arm, s in (('A', A16), ('B', B16)):
        layer[arm]['columns_per_token_per_layer'] = 48 * (s['gate_columns'] + s['range_cells'] + s['lkp_keys']) // 16
        layer[arm]['columns_per_token_48_deltanet_layers'] = 48 * layer[arm]['columns_per_token_per_layer']
        s['prove_s_estimate'] = estimate_prove_s(s['log_length'], s['relations']) if s['log_length'] <= 22 else None
    res['H3'] = dict(armA_T16=A16, armB_T16=B16, max_T_log22=maxT, layer_extrapolation=layer, pass_=B16['log_length'] <= 22,
                     note='prove_s_estimate is linear in table length from #47/#63 points; indicative only. Layer extrapolation = 48 V heads x per-head-per-token; DeltaNet recurrence + gated norm only (no matmuls).')
    # remainder savings (hard rule c), at the M2 shape
    res['remainder_savings'] = dict(
        armA_T16_columns=A16['gate_columns'] + A16['range_cells'], armB_T16_columns=B16['gate_columns'] + B16['range_cells'] + B16['lkp_keys'],
        relations_A=A16['relations'], relations_B=B16['relations'], terms_A=A16['terms'], terms_B=B16['terms'])
    js = json.dumps(res, indent=1, default=str)
    print(js)
    if a.json: open(a.json, 'w').write(js + '\n')

if __name__ == '__main__':
    main()
