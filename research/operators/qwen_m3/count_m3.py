#!/usr/bin/env python3
"""Counting model and full-model cost model for the Qwen3.8-27B M3 statement (design lane, no proof).

Design: experiments/20261109-32-qwen-m3-design/DESIGN.md. PREREG: same directory (first commit).

Two lowerings are counted. They are different things and are never added together.

1. RESEARCH HARNESS (what M1, M1b and the M2 design use: the wide product oracle with RNG and LKP).
   Counted with the SAME rules as research/operators/qwen_deltanet_m2/count_model.py, which is
   imported, not copied. H1 and H2 check that this file still reproduces the measured M1 / M1b
   statements and the M2 head counts. M3 adds, on top of the M2 head: in_proj outputs as committed
   cells, the 4-tap conv with committed taps, SiLU / softplus / exp / sigmoid as function-table
   lookups, the q/k L2 norm, the gates, and the gated norm's coefficient cg as a committed cell.
   TERM counts are PROVISIONAL: a review of #66 found that the norm's term counts in
   count_model.py do not match one explicit lowering (it reproduced columns, range cells, keys,
   relations and layout independently). Sizing here uses only the reproduced kinds of count.

2. PACKED (the upstream GPU prover's form: committed arrays of byte limbs, three limbs to an entry,
   sumchecks, lookups, the smallness test). The dense family is taken from the upstream planner
   (planner_proxy.py -> runs/planner-proxy.json). The DeltaNet part is a design count, limb by
   limb, below. No packed DeltaNet sub-proof exists: this is the form a CUDA sub-proof would have.

Everything under "extrapolated" is an extrapolation with its assumption stated. Nothing in this
file is a measurement of a Qwen proof.

usage: count_m3.py --planner <runs/planner-proxy.json> [--json out.json]
"""
import argparse, importlib.util, json, math, os

HERE = os.path.dirname(os.path.abspath(__file__))
_spec = importlib.util.spec_from_file_location('count_model', os.path.join(HERE, '..', 'qwen_deltanet_m2', 'count_model.py'))
cm = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(cm)

# ------------------------------------------------------------------------------------------------
# Qwen3.8-27B text shapes (research/ports/qwen3.8-27b/FEASIBILITY.md, section 1)
# ------------------------------------------------------------------------------------------------
Q = dict(d=5120, layers=64, deltanet_layers=48, attention_layers=16, f=17408, V=248320,
         D=128, v_heads=48, qk_heads=16, conv_taps=4, attn_q_heads=24, attn_kv_heads=4, attn_dh=256)
Q['in_proj_qkv'] = 2 * Q['qk_heads'] * Q['D'] + Q['v_heads'] * Q['D']        # 10,240
Q['in_proj_z'] = Q['v_heads'] * Q['D']                                       # 6,144
Q['in_proj_ab'] = 2 * Q['v_heads']                                           # 96
Q['in_proj_out'] = Q['in_proj_qkv'] + Q['in_proj_z'] + Q['in_proj_ab']       # 16,480
TABLE_ROWS = 4096   # rows of a nonlinear table (operators lane, table format v1)


def weights():
    """Committed integer weights, by tensor family. Counts follow from the published shapes."""
    d, f, V = Q['d'], Q['f'], Q['V']
    mlp = 3 * d * f
    dn = dict(in_proj=d * Q['in_proj_out'], conv=Q['in_proj_qkv'] * Q['conv_taps'], out_proj=Q['in_proj_z'] * d,
              head_scalars=2 * Q['v_heads'], mlp=mlp)
    aq = 2 * Q['attn_q_heads'] * Q['attn_dh']          # q_proj emits query + output gate: 12,288
    akv = Q['attn_kv_heads'] * Q['attn_dh']            # 1,024
    at = dict(q_proj=d * aq, k_proj=d * akv, v_proj=d * akv, o_proj=Q['attn_q_heads'] * Q['attn_dh'] * d, mlp=mlp)
    dn_total, at_total = sum(dn.values()), sum(at.values())
    emb = head = V * d
    total = Q['deltanet_layers'] * dn_total + Q['attention_layers'] * at_total + emb + head
    one_v_head = d * (3 * Q['D'] + Q['D'] + 2) + 3 * Q['D'] * Q['conv_taps'] + Q['D'] * d + 2
    return dict(deltanet_layer=dn, deltanet_layer_total=dn_total, attention_layer=at, attention_layer_total=at_total,
                embedding=emb, output_head=head, total=total, bytes_int16_plus_emb32=2 * (total - emb) + 4 * emb,
                m3a_one_v_head=one_v_head, m3a_layer=dn_total, m3b_block=3 * dn_total + at_total,
                maverick_committed=400.71e9, ratio_to_maverick=total / 400.71e9)

# ------------------------------------------------------------------------------------------------
# 1. Research-harness lowering
# ------------------------------------------------------------------------------------------------

def flookup(c, n=1):
    """A function-table lookup y = Tab[idx], idx = floor(x / step) + offset, out of domain rejected.
    Arm B: one key pair (idx, y) of a function LKP instance (2 cells, laid like key cells), and the
    index remainder r in [0, step) shown by two range keys (r and step - 1 - r), one relation
    x = step (idx - offset) + r, one for the second key.
    Arm A (no extra lookup instance): a one-hot selector over the table's rows, as the operators
    lane's first backend. Per lookup: TABLE_ROWS boolean columns with 2 relations each, 3 relations
    of TABLE_ROWS + 1 terms (sum s = 1, idx = sum i s_i, y = sum Tab_i s_i), 4 remainder bits."""
    if c.arm == 'B':
        c.fpairs += n; c.col(2 * n); c.key(2 * n); c.rel(4, n); c.rel(2, n)
    elif getattr(c, 'two_level', False):
        # descriptive, not registered: idx = 64 hi + lo, one-hot hi and lo (64 boolean columns
        # each), u_h = sum_l Tab[h][l] s_l (64 relations of 65 terms), y = sum_h s_h * u_h (64 gates)
        c.col(128 * n); c.rel(2, 2 * 128 * n); c.rel(65, 2 * n)
        c.rel(65, 64 * n); c.col(64 * n); c.rel(2, 2 * 64 * n); c.rel(65, n); c.rel(129, n)
        w = c.bits(4, n); c.rel(3 + w, n)
    else:
        c.col(TABLE_ROWS * n); c.rel(2, 2 * TABLE_ROWS * n)
        c.rel(TABLE_ROWS + 1, 3 * n)
        w = c.bits(4, n); c.rel(3 + w, n)


def l2_norm(c, D, n=1):
    """q/k L2 norm of one head's D channels, in relation (DESIGN.md 5.3). The isqrt and reciprocal
    scalars of count_model.gated_norm, and out = floor(x Rc / 2^24) per channel as a range cell."""
    for _ in range(n):
        if c.arm == 'B': c.key(13)
        else: c.bits(24 + 24 + 24 + 36 + 24 + 24)
        c.col(2); c.rel(3, 2); c.rel(4, 2)
        c.rel(D + 4 if c.arm == 'B' else D + 26)
        c.rel(D + 5 if c.arm == 'B' else D + 27)
        c.rel(4 if c.arm == 'B' else 38)
        c.rel(6 if c.arm == 'B' else 50)
        for _j in range(D):
            c.col(2); c.rel(2, 2); c.rel(2, 1); c.rel(4, 1)
            c.rcell()
            r = c.rem(24); c.rel(2 + r)


def head_extras(c, T, D=128, F=12):
    """What M3a-head adds to the M2 head emission. One V head with its own Q/K path.
    Matmuls (in_proj, out_proj) add NO gate column and no per-cell relation: each is one batched
    claim on the committed weight table (LIN) after a sumcheck. Their outputs are range cells with
    exact rounding remainders."""
    n_in = 3 * D + D + 2          # xq, xk, xv, z, ar, br
    n_conv = 3 * D
    for _t in range(T):
        c.rcell(n_in); c.rem(24, n_in)                               # in_proj outputs, rq remainder
        c.col(4 * n_conv); c.rel(2, 8 * n_conv)                      # conv: tap (weight cell) x input
        c.rcell(n_conv); r = c.rem(F, n_conv); c.rel(5 + r, n_conv)  # c = floor(acc / 2^12)
        flookup(c, n_conv)                                           # SiLU
        l2_norm(c, D, 2)                                             # q and k
        flookup(c, 3)                                                # softplus, exp(-x), sigmoid
        c.col(1); c.rel(2, 2); c.rcell(1); r = c.rem(F, 1); c.rel(2 + r, 1)   # cA * softplus, floor
        # gated norm output, with the gain a committed weight (not a public coefficient): NO derived
        # coefficient cg. s = Ts[z] (table-bounded), t = floor(s w / 2^F), y = floor(gain t / 2^F).
        # The M2 emission already has the last floor relation and its remainder; M3 adds the rest.
        flookup(c, D)                                                # s = Ts[z]
        c.col(D); c.rel(2, 2 * D)                                    # gate s * w
        c.rcell(D); r = c.rem(F, D); c.rel(2 + r, D)                 # t, its floor
        c.col(D); c.rel(2, 2 * D)                                    # gate gain * t
        c.rcell(D)                                                   # y is a cell, no longer public
    c.col(4 * n_conv + D + 2)     # weight cells read in gates: conv taps, gain, cA, dt_bias (once)
    c.rcell(3 * n_conv)           # conv history H, committed (3 inputs a channel)


def scaling_extras(c, T, D, out_path=False, state=False):
    """Sensitivity only (DESIGN.md 7.4). The head-output and norm scaling is an open parameter: on
    real layer-0 weights the integer head output misses the fidelity threshold at F = 12, 14, 16
    (PR #68, draft, unreviewed). Two ways the fix can land on the sizing:
      out_path  o, t and y carry 4 to 8 more bits: each becomes two cells (as delta is), the high
                limb bounded exactly by two 12-bit keys, and o's floor remainder gets a second key
                because its divisor drops below 2^12
      state     S' and M carry more bits too (a larger F on the recurrence): each becomes two cells
    Both are counted as extra cells, keys and relations at an unchanged F = 12 gate structure. A
    larger F on the recurrence also needs wider products than one field element holds (bounds.py),
    so 'state' is a LOWER bound on that case, not a design for it."""
    for _t in range(T):
        if out_path:
            c.rcell(3 * D); c.rel(3, 3 * D); c.key(2 * 3 * D); c.rel(2, 3 * D); c.key(D); c.rel(2, D)
        if state:
            c.rcell(D * D + D); c.rel(3, D * D + D); c.key(2 * (D * D + D)); c.rel(2, D * D + D)


def m3_head(arm, T=16, D=128, F=12, extras=True, o_witness=True, norm=True, two_level=False, out_path=False, state=False):
    c = cm.head(arm, D=D, T=T, F=F, o_witness=o_witness, norm=norm)
    c.fpairs = 0; c.two_level = two_level
    if extras:
        head_extras(c, T, D, F)
    if out_path or state:
        scaling_extras(c, T, D, out_path, state)
    return c


def mlp_statement(arm, T=16, d=Q['d'], f=Q['f'], F=12):
    """M3a's second statement kind: one SwiGLU MLP, m (public in M3a) -> ad (public in M3a).
    Per hidden unit: gate key gw and up value u (range cells, exact rq remainders), s = Ts[gw]
    (function lookup), one gate s * u. The down projection is one sumcheck against the table."""
    c = cm.C(arm); c.fpairs = 0
    for _t in range(T):
        c.rcell(2 * f); c.rem(24, 2 * f)
        flookup(c, f)
        c.col(f); c.rel(2, 2 * f)
        c.rem(24, d)              # the public output's rounding remainder
    return c


def summarize(c, arm, T, per=None):
    lay = cm.layout(c, arm, T)
    out = dict(arm=arm, T=T, gate_columns=c.cols, range_cells=c.rcells, lkp_keys=c.keys, function_lookups=c.fpairs,
               relations=c.rels, terms_PROVISIONAL=c.terms, laid_columns=lay['columns_used'], log_length=lay['log_length'],
               fits_log22=lay['log_length'] <= 22 and c.rels <= 2 ** 23)
    return out


def times(c, k):
    o = cm.C(c.arm)
    o.cols, o.rels, o.terms, o.rcells, o.keys, o.fpairs = (k * x for x in (c.cols, c.rels, c.terms, c.rcells, c.keys, c.fpairs))
    return o


def plus(a, b):
    o = cm.C(a.arm)
    o.cols, o.rels, o.terms, o.rcells, o.keys, o.fpairs = (x + y for x, y in zip(
        (a.cols, a.rels, a.terms, a.rcells, a.keys, a.fpairs), (b.cols, b.rels, b.terms, b.rcells, b.keys, b.fpairs)))
    return o


def max_T(make, arm, cap=64):
    T = 0
    while T < cap:
        s = summarize(make(arm, T + 1), arm, T + 1)
        if not s['fits_log22']: break
        T += 1
    return T


def harness():
    res = {}
    # H1: the recurrence, with every M3 addition off, at the measured shapes
    m1 = cm.summary('m1'); m1b = cm.summary('m1b')
    c1 = m3_head('m1', T=4, extras=False, o_witness=False, norm=False)
    c1b = m3_head('m1b', T=4, extras=False, o_witness=False, norm=False)
    l1, l1b = cm.layout(c1, 'm1', 4), cm.layout(c1b, 'm1b', 4)
    got = [('m1.columns_used', l1['columns_used'], cm.M1_MEASURED['columns_used']), ('m1.log_length', l1['log_length'], cm.M1_MEASURED['log_length']),
           ('m1.relations', c1.rels, cm.M1_MEASURED['relations']), ('m1.terms', c1.terms, cm.M1_MEASURED['terms']),
           ('m1b.columns_used', l1b['columns_used'], cm.M1B_MEASURED['columns_used']), ('m1b.columns_nonregion', l1b['columns_nonregion'], cm.M1B_MEASURED['columns_nonregion']),
           ('m1b.log_length', l1b['log_length'], cm.M1B_MEASURED['log_length']), ('m1b.relations', c1b.rels, cm.M1B_MEASURED['relations']),
           ('m1b.terms', c1b.terms, cm.M1B_MEASURED['terms']), ('m1b.range_cells', c1b.rcells, cm.M1B_MEASURED['range_cells'])]
    res['H1'] = dict(checks=[dict(quantity=q, model=a, measured=b, match=a == b) for q, a, b in got], pass_=all(a == b for _, a, b in got),
                     note='the recurrence emission is imported from qwen_deltanet_m2/count_model.py, so this guards against drift; it is not an independent derivation. m1.terms and m1b.terms match the measured builders; the NORM term counts (not in M1/M1b) are provisional.')
    # H2: M3 with extras off = the #66 M2 head, arm B, T = 16
    c2 = m3_head('B', T=16, extras=False); s2 = summarize(c2, 'B', 16)
    want = dict(gate_columns=1_056_800, range_cells=272_384, lkp_keys=276_688, relations=2_402_432, log_length=21)
    res['H2'] = dict(model={k: s2[k] for k in want}, expected=want, pass_=all(s2[k] == v for k, v in want.items()),
                     note='expected values are the #66 counts that the second review reproduced with independent closed forms')
    # H3: M3a-head
    hB = summarize(m3_head('B', 16), 'B', 16); hA = summarize(m3_head('A', 16), 'A', 16)
    hA1 = summarize(m3_head('A', 1), 'A', 1)
    m2B = summarize(m3_head('B', 16, extras=False), 'B', 16)
    hB['added_over_m2_head'] = {k: hB[k] - m2B[k] for k in ('gate_columns', 'range_cells', 'lkp_keys', 'relations', 'laid_columns')}
    a2 = lambda arm, T: m3_head(arm, T, two_level=True)
    tA2 = max_T(a2, 'A')
    res['H3'] = dict(m3a_head_armB_T16=hB, m3a_head_armA_T16=hA, m3a_head_armA_T1=hA1,
                     max_T_armB=max_T(m3_head, 'B'), max_T_armA=max_T(m3_head, 'A'), pass_=hB['fits_log22'],
                     descriptive_unregistered=dict(
                         fallback='arm A with a two-level one-hot table (64 x 64) in place of the 4,096-row one-hot',
                         max_T=tA2, at_max_T=summarize(a2('A', max(tA2, 1)), 'A', max(tA2, 1)), at_T16=summarize(a2('A', 16), 'A', 16)))
    # M3a's second statement kind and the whole layer
    mB = summarize(mlp_statement('B', 16), 'B', 16)
    res['m3a_mlp'] = dict(armB_T16=mB, max_T_armB=max_T(mlp_statement, 'B'), armA_T1=summarize(mlp_statement('A', 1), 'A', 1))
    for T in (1, 16):
        layer = plus(times(m3_head('B', T), Q['v_heads']), mlp_statement('B', T))
        res['one_layer_single_statement_armB_T%d' % T] = summarize(layer, 'B', T)
    res['m3a_layer_as_separate_statements'] = dict(
        head_statements=Q['v_heads'], mlp_statements=1, each_fits_log22=hB['fits_log22'] and mB['fits_log22'],
        product_columns_total=Q['v_heads'] * hB['laid_columns'] + mB['laid_columns'],
        relations_total=Q['v_heads'] * hB['relations'] + mB['relations'],
        prove_s_estimate_each_head=cm.estimate_prove_s(hB['log_length'], hB['relations']),
        note='48 head statements (each with its own Q/K path, duplicated 3x across the V heads that share it) plus one MLP statement; the verifier adds the public head contributions, rounds, and recomputes the two norms from public stream values. prove_s_estimate is #66\'s linear interpolation in table length, indicative only.')
    # full model in this lowering (the only DeltaNet lowering that has been built)
    per_tok = Q['v_heads'] * (hB['gate_columns'] + hB['range_cells'] + hB['lkp_keys']) // 16
    res['wide_oracle_full_model'] = dict(
        product_columns_per_token_per_deltanet_layer=per_tok,
        product_columns_per_token_48_layers=Q['deltanet_layers'] * per_tok,
        field_elements_per_1024_window=3 * 1024 * Q['deltanet_layers'] * per_tok,
        bytes_raw_per_1024_window=8 * 3 * 1024 * Q['deltanet_layers'] * per_tok,
        note='three oracle rows (a, b, c) per product column, 8 bytes an element, before encoding; DeltaNet mixers only')
    return res

# ------------------------------------------------------------------------------------------------
# 2. Packed lowering (design count for DeltaNet; planner counts for the dense family)
# ------------------------------------------------------------------------------------------------
LANES = 3  # byte limbs in one committed entry (docs/format/11-1-machinery.md, `LANES`)

# byte limbs per value, by class (signed bytes, as the upstream provers write committed cells)
LIMBS = dict(state=3,        # |S'| < 2^18
             rem12=2,        # a 12-bit floor remainder, if committed
             vec3=3, vec2=2, vec4=4)


def deltanet_limbs(strategy, C=64, D=128, remainder_committed=True, state_limbs=3, out_extra_limbs=0):
    """Byte limbs per V head per token. strategy:
      'per_token'   every S_t committed (what M1 / M1b / M2 do)
      'low_rank'    S committed at chunk boundaries only; inside a chunk the state is never laid
                    out: M_t and o_t are computed from S_c, the k_s, delta_s and the chunk's Gram
                    matrix (a different integer semantics, owned by #34; not built, not proved)"""
    per_cell = state_limbs + (LIMBS['rem12'] if remainder_committed else 0)
    state = D * D * per_cell if strategy == 'per_token' else D * D * per_cell / C
    # The in_proj outputs (xq, xk, xv, z, ar, br) are NOT here: they are projection outputs of the
    # layer sub-proof (dense family), counted from the planner's slope in packed().
    # per value channel j of the V head: conv out 3, v 3, M 3, delta 3, o 3, w 2, s 2, t 3, y 4
    vectors = D * (3 + 3 + 3 + 3 + 3 + 2 + 2 + 3 + 4) + D * (state_limbs - 3) + 3 * D * out_extra_limbs   # M widens with the state; o, t, y with the output path
    # the Q/K path of a QK head, shared by 3 V heads: conv out 3 each; SiLU 2 each; q^, k^ 2 each
    qk = D * (3 + 3 + 2 + 2 + 2 + 2) / 3
    gram = (C * LIMBS['vec3'] / 3) if strategy == 'low_rank' else 0   # k_s . k_t for the chunk, per QK head
    scalars = 16
    return dict(state=state, vectors=vectors, qk_path=qk, gram=gram, scalars=scalars,
                total=state + vectors + qk + gram + scalars)


MAV_PROJ_OUT = (40 + 8) * 128 + 8 * 128          # q, k and v outputs of the proxy's layer: 7,168
QWEN_DN_PROJ_OUT = Q['in_proj_out']               # 16,480
QWEN_AT_PROJ_OUT = 2 * 24 * 256 + 2 * 4 * 256     # q (with the output gate), k, v: 14,336


def packed(planner, T=1024, strategy='per_token', C=64, segments='block', remainder_committed=True, state_limbs=3, out_extra_limbs=0):
    """segments: how the DeltaNet sub-proof is cut into segments (one group of oracle messages each).
      'block'  one DeltaNet segment per 4-layer block (3 DeltaNet layers in it)
      'layer'  one DeltaNet segment per DeltaNet layer
    The dense family keeps upstream's cut: one layer link and one attention link per 4-layer block."""
    mav = planner['maverick']; px = planner['dense_f17408_V248320_L64']
    T0 = 1024
    # entries per projection output per token per layer, from the planner: G 8 -> 4 removes 512 key
    # and 512 value outputs from each of the 4 layers of a link
    slope = (planner['dense_f17408']['layer_link_entries_typical'] - planner['dense_f17408_G4']['layer_link_entries_typical']) / (4 * T0 * 1024)
    overhead = 1 + mav['layer_link_other_typical'] / mav['layer_link_cells_typical']   # registered
    limbs = deltanet_limbs(strategy, C, remainder_committed=remainder_committed, state_limbs=state_limbs, out_extra_limbs=out_extra_limbs)
    dn_mixer_per_tok = Q['v_heads'] * limbs['total'] / LANES * overhead                 # entries, one layer, one token
    dense_proxy_per_tok = px['layer_link_entries_typical'] / 4 / T0                     # proxy: norms, projections, MLP
    dense_dn_per_tok = dense_proxy_per_tok + (QWEN_DN_PROJ_OUT - MAV_PROJ_OUT) * slope   # with Qwen's in_proj width
    dense_at_per_tok = dense_proxy_per_tok + (QWEN_AT_PROJ_OUT - MAV_PROJ_OUT) * slope
    attn_per_tok = mav['attention_link_entries'] / 4 / T0                               # per attention LAYER (assumption)
    head_per_tok = px['head_link_entries'] / T0
    dn_layer = dn_mixer_per_tok + dense_dn_per_tok
    at_layer = attn_per_tok + dense_at_per_tok
    per_tok = Q['deltanet_layers'] * dn_layer + Q['attention_layers'] * at_layer + head_per_tok
    seg = dict(layer_link=3 * dense_dn_per_tok + dense_at_per_tok, attention_link=attn_per_tok, output_head=head_per_tok,
               deltanet=dn_mixer_per_tok * (3 if segments == 'block' else 1))
    largest_name = max(seg, key=seg.get)
    return dict(T=T, strategy=strategy, chunk=C if strategy == 'low_rank' else None, deltanet_segments=segments,
                remainder_committed=remainder_committed, limbs_per_v_head_per_token=limbs, overhead_factor=overhead,
                projection_output_slope=slope,
                entries_per_token=dict(deltanet_mixer_one_layer=dn_mixer_per_tok, dense_part_deltanet_layer=dense_dn_per_tok,
                                       dense_part_attention_layer=dense_at_per_tok, attention_one_layer=attn_per_tok,
                                       output_head=head_per_tok, all_layers=per_tok),
                entries_per_window=per_tok * T, deltanet_mixer_share=Q['deltanet_layers'] * dn_mixer_per_tok / per_tok,
                segment_entries={k: v * T for k, v in seg.items()}, largest_segment=largest_name,
                largest_segment_entries=seg[largest_name] * T, largest_segment_rows_at_2e22=math.ceil(seg[largest_name] * T / 2 ** 22),
                segments_per_window=16 * (2 + (1 if segments == 'block' else 3)) + 1,
                m3b_block_entries=(3 * dn_layer + at_layer) * T)

# ------------------------------------------------------------------------------------------------
# Extrapolation (labelled; assumptions in PREREG "Metric")
# ------------------------------------------------------------------------------------------------
P_PASS = 18.161      # s per pass over Maverick's weights (D1: fit of upstream's published rates)
Q_REQ = 4.333        # s per request at Maverick's entry count (D1)
MAV_ALL_IN_24 = 9.206  # s per request at 24 a batch, upstream (sensitivity: all of it charged to entries)
H200_GB, FIT_GB, FIT_S = 141.0, 127.0, 3600.0
USD_PER_GPU_HOUR = 3.0   # ASSUMPTION, a round number for a rented card; not a quote


def extrapolate(pk, planner, w, small_prove_s=2.347):
    mav = planner['maverick']
    q_e = Q_REQ / mav['entries_total']
    q_hi = MAV_ALL_IN_24 / mav['entries_total']
    q_small = small_prove_s / planner['small_roomy']['entries_total']
    passes = 3
    t_weights = P_PASS * passes * w['ratio_to_maverick']
    e = pk['entries_per_window']
    b_c = 80629 * 2 ** 20 / (6 * mav['largest_link_entries'])
    seg = pk['largest_segment_entries']
    vram = {k: b * seg / 1e9 for k, b in (('low_16B', 16.0), ('central', b_c), ('high', 2 * b_c))}
    prove = dict(central=t_weights + q_e * e, high_all_in=q_hi * e + t_weights, upper_bound_small_example=q_small * e)
    fits_c = vram['central'] <= FIT_GB and prove['central'] <= FIT_S
    fits_h = vram['high'] <= FIT_GB and prove['high_all_in'] <= FIT_S
    verdict = 'fits, also on the high estimate' if fits_c and fits_h else 'fits on the central assumption, not robust' if fits_c else 'does not fit'
    return dict(label='EXTRAPOLATED, not measured', committed_entries=e, vram_gb=vram, bytes_per_entry_central=b_c,
                weights_resident_gb=w['bytes_int16_plus_emb32'] / 1e9,
                vram_with_resident_weights_gb_central=vram['central'] + w['bytes_int16_plus_emb32'] / 1e9,
                prove_s=prove, tokens_per_s_central=pk['T'] / prove['central'],
                gpu_s_per_window_token_central=prove['central'] / pk['T'],
                usd_per_1000_window_tokens_central=1000 * prove['central'] / pk['T'] * USD_PER_GPU_HOUR / 3600,
                proof_mb=18.78 * e / mav['entries_total'], verdict=verdict)


def sensitivity(planner, w):
    """How much of the sizing moves with the open head-output / norm scaling. Counted, not built."""
    out = dict(note='the scaling of o, w, t, y (and possibly of the recurrence) is an OPEN parameter; see DESIGN.md 7.4. '
                    'Byte-limb capacity (packed): 3 signed-byte limbs hold |x| < 2^23, 4 hold 2^31. Real layer-0 maxima at F = 12 '
                    '(PR #68, draft): M 202,297, S 175,232, o 23,630; deeper layers are unmeasured.')
    base = summarize(m3_head('B', 16), 'B', 16)
    h = {}
    for name, kw in (('base_F12', {}), ('output_path_two_limbs', dict(out_path=True)), ('state_and_output_two_limbs', dict(out_path=True, state=True))):
        sm = summarize(m3_head('B', 16, **kw), 'B', 16)
        mk = lambda arm, T, kw=kw: m3_head(arm, T, **kw)
        h[name] = dict(laid_columns=sm['laid_columns'], relations=sm['relations'], range_cells=sm['range_cells'], lkp_keys=sm['lkp_keys'],
                       log_length=sm['log_length'], fits_log22=sm['fits_log22'], max_T=max_T(mk, 'B'),
                       laid_columns_vs_base=sm['laid_columns'] / base['laid_columns'])
    out['harness_m3a_head_armB_T16'] = h
    pkd = {}
    for name, kw in (('base_3_limb_state', {}),
                     ('norm_input_plus_4_bits', dict()),                       # o up to 2^18.5 on layer 0: still 3 limbs
                     ('norm_input_plus_8_bits', dict()),                       # o up to 2^22.5 on layer 0: still 3 limbs
                     ('output_path_one_more_limb', dict(out_extra_limbs=1)),   # if deeper layers push o, t, y past 2^23
                     ('state_4_limbs', dict(state_limbs=4)),                   # recurrence at about 5 to 8 more bits
                     ('state_4_limbs_and_output_one_more', dict(state_limbs=4, out_extra_limbs=1))):
        row = {}
        for strat, skw in (('per_token_layer_segments', dict(strategy='per_token', segments='layer')), ('low_rank_c64', dict(strategy='low_rank', C=64, segments='block'))):
            pk = packed(planner, T=1024, **skw, **kw); ex = extrapolate(pk, planner, w)
            row[strat] = dict(entries_per_token=pk['entries_per_token']['all_layers'], largest_segment=pk['largest_segment'],
                              vram_gb_central_EXTRAPOLATED=ex['vram_gb']['central'], vram_gb_high_EXTRAPOLATED=ex['vram_gb']['high'],
                              prove_s_central_EXTRAPOLATED=ex['prove_s']['central'], verdict=ex['verdict'])
        pkd[name] = row
    b0 = pkd['base_3_limb_state']
    for name, row in pkd.items():
        for strat in row:
            row[strat]['entries_vs_base'] = row[strat]['entries_per_token'] / b0[strat]['entries_per_token']
    out['packed_T1024'] = pkd
    return out


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--planner', required=True); ap.add_argument('--json')
    a = ap.parse_args()
    planner = json.load(open(a.planner))
    res = dict(qwen_shapes=Q, weights=weights(), harness=harness(), H4=planner['H4'])
    w = res['weights']
    res['extrapolated_commit'] = dict(label='EXTRAPOLATED, not measured',
                                      commit_minutes=39.0 * w['ratio_to_maverick'],
                                      assumption='linear in committed weights from upstream\'s "about 39 minutes" for Maverick on one H100; ignores fixed costs (this fork measured 18.8 s for a tiny synthetic model)')
    cases = {}
    # POST-HOC CHANGE, disclosed in RESULTS.md ("Deviations"). The first run of this file
    # (runs/model-first-run.json) put the DeltaNet mixer inside the 4-layer layer link, and its
    # verdict for per-token state at T = 1,024 was "does not fit" (138 GB central). After seeing
    # that, the segmentation was changed: the DeltaNet sub-proof is a segment of its own, per block
    # or per layer. That is a design choice made with the result in view, so the first-run verdict
    # is reported next to these. The first run's "2-layer links" case is dropped: upstream allows
    # at most 28 blocks of layers, and 64 layers in blocks of 2 is 32.
    for name, kw in (('per_token_block_segments', dict(strategy='per_token', segments='block')),
                     ('per_token_layer_segments', dict(strategy='per_token', segments='layer')),
                     ('per_token_layer_segments_remainder_as_key', dict(strategy='per_token', segments='layer', remainder_committed=False)),
                     ('low_rank_c64', dict(strategy='low_rank', C=64, segments='block')),
                     ('low_rank_c16', dict(strategy='low_rank', C=16, segments='block'))):
        cases[name] = {}
        for T in (64, 128, 256, 512, 1024):
            pk = packed(planner, T=T, **kw)
            pk['extrapolated'] = extrapolate(pk, planner, w)
            cases[name]['T%d' % T] = pk
    res['packed'] = cases
    # M3b: one 4-layer block (3 DeltaNet + 1 attention), synthetic weights, packed lowering
    m3b = {}
    for name, kw in (('per_token', dict(strategy='per_token')), ('low_rank_c64', dict(strategy='low_rank', C=64))):
        for T in (64, 256, 1024):
            pk = packed(planner, T=T, segments='layer', **kw)
            b_c = 80629 * 2 ** 20 / (6 * planner['maverick']['largest_link_entries'])
            e = pk['m3b_block_entries']; g = pk['largest_segment_entries']
            m3b['%s_T%d' % (name, T)] = dict(committed_entries=e, largest_segment=pk['largest_segment'], largest_segment_entries=g,
                                             largest_segment_rows_at_2e22=pk['largest_segment_rows_at_2e22'],
                                             vram_gb_EXTRAPOLATED=dict(low_16B=16 * g / 1e9, central=b_c * g / 1e9, high=2 * b_c * g / 1e9),
                                             fits_h200_central=b_c * g / 1e9 <= FIT_GB, fits_h200_high=2 * b_c * g / 1e9 <= FIT_GB,
                                             committed_weights=w['m3b_block'])
    res['m3b'] = m3b
    res['sensitivity_open_norm_scaling'] = sensitivity(planner, w)
    # Descriptive, NOT registered: this fork's only own GPU memory reading while proving is the small
    # synthetic example (5,293 MiB sampled at 500 ms, research/gpu/README.md, PR #23). Taken at face
    # value over that example's largest segment it is a bytes-per-entry figure about ten times the
    # registered central one. Upstream's published full-size point contradicts it for the dense
    # family (the check below), so it is read as fixed cost and is not used for a verdict.
    b_small = 5293 * 2 ** 20 / planner['small_roomy']['largest_link_entries']
    b_c = 80629 * 2 ** 20 / (6 * planner['maverick']['largest_link_entries'])
    pl = cases['per_token_layer_segments']; lr = cases['low_rank_c64']
    res['vram_calibration_descriptive'] = dict(
        label='EXTRAPOLATED, descriptive, not registered',
        bytes_per_entry=dict(low=16.0, central_registered=b_c, high_registered=2 * b_c, small_example_face_value=b_small),
        maverick_six_in_pass_at_small_example_rate_gb=6 * planner['maverick']['largest_link_entries'] * b_small / 1e9,
        maverick_published_gb=80629 * 2 ** 20 / 1e9,
        at_small_example_rate_gb={k: {T: v[T]['largest_segment_entries'] * b_small / 1e9 for T in ('T64', 'T256', 'T1024')}
                                  for k, v in (('per_token_layer_segments', pl), ('low_rank_c64', lr))},
        note='the registered range (16 B to 2 x central) is narrower than what this fork has itself measured can rule out for a DeltaNet segment; only an H200 run settles it')
    c = cases['per_token_block_segments']['T1024']['extrapolated']; c1 = cases['per_token_layer_segments']['T1024']['extrapolated']
    c3 = cases['low_rank_c64']['T1024']['extrapolated']
    wide_gb = res['harness']['wide_oracle_full_model']['bytes_raw_per_1024_window'] / 1e9
    res['H5'] = dict(
        decision_rule='central VRAM <= 127 GB at one request per pass, weights streamed, AND central prove time <= 3,600 s per 1,024-token window',
        wide_oracle_per_token_state=dict(raw_gb_before_encoding=wide_gb, verdict='does not fit'),
        packed_per_token_state_one_deltanet_segment_per_block=c['verdict'],
        packed_per_token_state_one_deltanet_segment_per_layer=c1['verdict'],
        packed_low_rank_chunk64=c3['verdict'],
        pass_=any(v.startswith('fits') for v in (c['verdict'], c1['verdict'], c3['verdict'])),
        registered_expectation_held=wide_gb > FIT_GB,
        binding_constraint='the DeltaNet state trace: GPU memory of its largest segment, then total committed entries (share of committed entries that is DeltaNet mixer: %.0f%% at T = 1,024, per-token state)' % (100 * cases['per_token_block_segments']['T1024']['deltanet_mixer_share']))
    js = json.dumps(res, indent=1, default=str)
    if a.json:
        open(a.json, 'w').write(js + '\n')
    brief = dict(H1=res['harness']['H1']['pass_'], H2=res['harness']['H2']['pass_'], H3=res['harness']['H3']['pass_'],
                 H4=res['H4']['pass_'], H5=res['H5'])
    print(json.dumps(brief, indent=1))


if __name__ == '__main__':
    main()
