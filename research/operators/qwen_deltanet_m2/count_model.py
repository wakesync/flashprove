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
M2 adds (DESIGN.md section 4): head output o as a witness RNG cell (not in the statement; computable from public inputs at M2), the proved gated RMSNorm of o
(o*o and o*Rc gates, isqrt and reciprocal scalars with exact limbs, w RNG cell, y floor), T = 16.
The norm is counted relation by relation for the lowering written out in DESIGN.md section 4.4.1.
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

def head(arm, D=128, T=4, F=12, o_witness=False, norm=False):
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
            if o_witness:
                c.rcell(); c.rel(D + r + 1)            # -2^F o (cell) + sum g4.c - r = 0
            else:
                c.rel(D + r)                           # target -2^F o
        if norm:
            gated_norm(c, D, F)
        if t == T - 1:
            c.rel(1, D * D)                            # S_T target
    return c

def gated_norm(c, D, F):
    """Proved gated RMSNorm of the witness o (DESIGN.md section 4.4). Per token:
    Vx = sum o^2; sigma = isqrt(Vx + eps); Rc = floor(2^36 / sigma); w = floor(o Rc / 2^24);
    y = floor(cg w / 2^F) with cg public (verifier-derived from gain, SiLU(z), sqrt(D)); y public."""
    # THE LOWERING IS DESIGN.md section 4.4.1, relation by relation (third review of #66, should-fix
    # S1: the earlier term counts did not implement one stated lowering). Columns, relations, range
    # cells and keys are the same as before; only the terms per relation changed.
    # Exact pieces of a non-negative integer (c.rem): arm B = one key cell per 12 bits, arm A = one
    # [x, x, x] bit column per bit with its 2 two-term boolean relations. The value returned is the
    # number of terms the pieces add to a relation that sums them.
    n_sigma, n_e1, n_e2 = c.rem(24), c.rem(24), c.rem(24)
    n_Rc, n_rr, n_gap = c.rem(36), c.rem(24), c.rem(24)
    c.col(2)                      # gates G_ss = [sigma, sigma, sigma^2] and G_rs = [Rc, sigma, Rc sigma]
    c.rel(1 + n_sigma)            # S1  G_ss.a - pieces(sigma) = 0
    c.rel(2)                      # S2  G_ss.b - G_ss.a = 0
    c.rel(1 + n_Rc)               # S3  G_rs.a - pieces(Rc) = 0
    c.rel(2)                      # S4  G_rs.b - G_ss.a = 0
    c.rel(D + 1 + n_e1)           # S5  sum_j G_oo_j.c - G_ss.c - pieces(e1) = -eps'
    c.rel(D + 2 + n_e2)           # S6  G_ss.c + 2 G_ss.a - sum_j G_oo_j.c - pieces(e2) = eps'
    c.rel(1 + n_rr)               # S7  G_rs.c + pieces(rr) = 2^36
    c.rel(1 + n_rr + n_gap)       # S8  G_ss.a - pieces(rr) - pieces(gap) = 1
    for _ in range(D):
        c.col(2)                  # G_oo_j = [o_j, o_j, o_j^2] and G_oR_j = [o_j, Rc, o_j Rc]
        c.rel(2, 3)               # C1..C3  G_oo_j.a, G_oo_j.b, G_oR_j.a each = the o_j range cell
        c.rel(2)                  # C4  G_oR_j.b - G_rs.a = 0 (the Rc operand cell is reused, not rebuilt from pieces)
        c.rcell()                 # w_j (|w| <= 2^12 honest)
        c.rel(2 + c.rem(2 * F))   # C5  2^24 w_j + pieces(rw_j) - G_oR_j.c = 0
        c.rel(1 + c.rem(F))       # C6  cg_j w_j - pieces(ry_j) = 2^F y_j  (cg_j derived and admitted, y_j public)

def norm_terms_closed_form(arm, D):
    """Terms of the gated norm per token for the lowering of DESIGN.md 4.4.1, by hand:
    arm B: S1..S4 = 3 + 2 + 4 + 2, S5..S8 = (D + 3) + (D + 4) + 3 + 5, C1..C6 = 14 per channel.
    arm A: S1..S4 = 25 + 2 + 37 + 2, S5..S8 = (D + 25) + (D + 26) + 25 + 49, C1..C6 = 47 per channel,
           plus 4 terms per bit for the boolean relations: 4 x 156 scalar bits, 4 x 36 per channel."""
    return 16 * D + 26 if arm == 'B' else 193 * D + 815

def norm_only(arm, D=128, F=12):
    c = C(arm); gated_norm(c, D, F)
    return dict(gate_columns=c.cols, relations=c.rels, terms=c.terms, range_cells=c.rcells, lkp_keys=c.keys, terms_closed_form=norm_terms_closed_form(arm, D),
                closed_form_matches=c.terms == norm_terms_closed_form(arm, D))

# Counts at the M2 head, T = 16, that three independent derivations agree on (this model, the second
# review's cross-check and the third review's closed forms). The term-count fix must not move them.
FROZEN_T16 = {'A': dict(gate_columns=4_377_056, range_cells=272_384, lkp_keys=0, relations=9_042_944, columns_used=4_655_584, log_length=23),
              'B': dict(gate_columns=1_056_800, range_cells=272_384, lkp_keys=276_688, relations=2_402_432, columns_used=1_613_856, log_length=21)}
SUPERSEDED_TERMS_T16 = {'A': 21_110_960, 'B': 4_786_704}   # runs/model.json at 8ec7c799, before the lowering was specified

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
    # Multiplicity planes (post-review, #66 should-fix 1). Each LKP instance sends its multiplicities
    # as planes x 2^d places in row 0 of a message (rng_planes_places in blocks/iop/rng.h). RNG's
    # digit lookup (rng_lookup): one part of 2^(1 + log dc + log Np) keys, d = max(b0, b1) + 1 = 13,
    # planes = part + 1. The remainder lookup (arm B): parts as above, one function, d = 12, planes =
    # the least with all keys < 2^planes (lkp_fault). The design puts both planes vectors in ONE
    # multiplicity row (RNG's message 3, the remainder planes after RNG's), so that row must hold
    # their sum; a separate message would need only the larger of the two. Either way it bounds L.
    rng_mult = rem_mult = 0
    if dc:
        v = 1 + int(math.log2(dc)) + 4
        rng_mult = (v + 1) << 13
    if key_parts:
        nkeys = sum(key_parts); planes = nkeys.bit_length()  # least planes with nkeys < 2^planes
        assert all(int(math.log2(p)) < planes for p in key_parts)
        rem_mult = planes << 12
    mult_row = rng_mult + rem_mult
    L = max(L, math.ceil(math.log2(mult_row)) if mult_row else 0)
    return dict(columns_used=total, columns_nonregion=c.cols, rng_rows=rng_rows, key_parts=key_parts, digit_entries=2 * sum(rng_rows) * 10,
                rng_multiplicity_places=rng_mult, remainder_multiplicity_places=rem_mult, multiplicity_row_places=mult_row, log_length=L)

def single_part_layout(c):
    """Review cross-check (#66): arm B with the keys as ONE power-of-two part (no LkpPublic::parts),
    padded up. Returns the laid length and log-length, with the same block placement as layout()."""
    def pieces(n, quantum):
        n = math.ceil(n / quantum) * quantum; out = []; b = 1 << n.bit_length()
        while n:
            b >>= 1
            if n & b: out.append(b); n -= b
        return out
    rng_rows = pieces(math.ceil(c.rcells / 16), 1024)
    blocks = sorted([r * 16 for r in rng_rows] + [P2(c.keys)], reverse=True)
    pos = 0
    for b in blocks: pos = math.ceil(pos / b) * b + b
    total = pos + c.cols
    return dict(key_part=P2(c.keys), columns_used=total, log_length=math.ceil(math.log2(total)))

def summary(arm, **kw):
    c = head(arm, **kw); D, T = kw.get('D', 128), kw.get('T', 4)
    lay = layout(c, arm, T)
    cells = D * D * T
    per_cell = (c.cols + c.rcells + c.keys) / cells
    return dict(arm=arm, D=D, T=T, o_witness=kw.get('o_witness', False), norm=kw.get('norm', False),
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
    m2 = dict(D=128, o_witness=True, norm=True)
    A16 = summary('A', T=16, **m2); B16 = summary('B', T=16, **m2)
    maxT = {}; maxT_nocap = {}
    for arm in ('A', 'B'):
        # The relations <= 2^23 condition is lookup_size()'s own guard; it was not in the PREREG's
        # metric text (a deviation, listed in RESULTS.md). maxT_nocap drops it to show it does not bind.
        T = 1
        while summary(arm, T=T + 1, **m2)['log_length'] <= 22 and summary(arm, T=T + 1, **m2)['relations'] <= 2 ** 23: T += 1
        maxT[arm] = T
        T = 1
        while summary(arm, T=T + 1, **m2)['log_length'] <= 22: T += 1
        maxT_nocap[arm] = T
    layer = {arm: dict(relations_per_token_per_layer=48 * s['relations'] // 16) for arm, s in (('A', A16), ('B', B16))}
    for arm, s in (('A', A16), ('B', B16)):
        layer[arm]['columns_per_token_per_layer'] = 48 * (s['gate_columns'] + s['range_cells'] + s['lkp_keys']) // 16
        layer[arm]['columns_per_token_48_deltanet_layers'] = 48 * layer[arm]['columns_per_token_per_layer']
        s['prove_s_estimate'] = estimate_prove_s(s['log_length'], s['relations']) if s['log_length'] <= 22 else None
    B16['single_part_layout'] = single_part_layout(head('B', T=16, **m2))
    frozen = {arm: {k: (s[k], v, s[k] == v) for k, v in FROZEN_T16[arm].items()} for arm, s in (('A', A16), ('B', B16))}
    frozen_ok = all(x[2] for d in frozen.values() for x in d.values()) and maxT == {'A': 14, 'B': 41}
    norm = {arm: norm_only(arm) for arm in ('A', 'B')}
    res['norm_terms'] = dict(
        lowering='DESIGN.md section 4.4.1 (gate operand cells reused for sigma and Rc)', per_token=norm,
        closed_forms_match=all(n['closed_form_matches'] for n in norm.values()),
        terms_T16={'A': A16['terms'], 'B': B16['terms']}, terms_T16_superseded=SUPERSEDED_TERMS_T16,
        terms_T16_change={arm: s['terms'] - SUPERSEDED_TERMS_T16[arm] for arm, s in (('A', A16), ('B', B16))},
        frozen_counts_T16=frozen, frozen_counts_unchanged=frozen_ok,
        note='counted for one stated lowering; no builder exists to check it. A build that reuses operands differently has a different, equally valid total.')
    assert res['norm_terms']['closed_forms_match'], 'norm term count differs from the closed form of DESIGN.md 4.4.1'
    assert frozen_ok, 'a gate, range, key, relation or layout count moved: stop and report'
    res['H3'] = dict(armA_T16=A16, armB_T16=B16, max_T_log22=maxT, max_T_log22_without_relation_cap=maxT_nocap, layer_extrapolation=layer,
                     fits_2_21_armB_T16=B16['log_length'] <= 21, pass_=B16['log_length'] <= 22,
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
