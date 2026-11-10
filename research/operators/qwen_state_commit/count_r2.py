#!/usr/bin/env python3
"""Recount of the SB volume formulas with the remainder widths of each decay-table scale GB (r2).

Counted, NOT measured. No SB proof and no SB backend exist in this repository. Writes
experiments/20261109-34-qwen-state-commit/runs/count-r2.json. The registered output runs/count.json
(count.py, unchanged) stays as it is; this script checks that its GB = 12 column reproduces it.

Why. count.py hard-codes the remainder key counts of the registered arm GB = F = 12: the S_out floor
divides by 2^(F+GB) = 2^24 (two 12-bit keys), the M and o floors by 2^(2F+GB) = 2^36 (three keys).
sb_ref.py at GB = 18 divides by 2^30 and 2^42, so the same layout needs three and four keys. Both
reviews of PR #71 pointed this out.

Convention (count.py's, kept): one count per committed value; a quotient is one value whatever its
width; a remainder of w bits is ceil(w / 12) lookup keys. Per V head, chunk of C tokens:
  per chunk  S_out cells D^2, their remainder keys ks D^2, decay table entries C (C + 1) / 2,
             Gram K K^T and Q K^T 2 C^2
  per token  P0, Q0 2 D; M, delta_lo, delta_hi, o 4 D; remainder keys of M (km), delta (1), o (km)
  => (1 + ks) D^2 / C + (7 + 2 km) D + 2.5 C + 0.5    with ks = ceil((F + GB) / 12), km = ceil((2 F + GB) / 12)
GB = 12 gives count.py's 3 D^2 / C + 13 D + 2.5 C + 0.5; GB = 18 gives 4 D^2 / C + 15 D + 2.5 C + 0.5.

Still not counted by that formula (inventory; the two items below are added in the column
`with_listed_extras`, which is still not a complete count of an SB proof):
  - the floor that defines each decay-table entry, G[t][s] = floor(G[t-1][s] a_t / 2^F): one F-bit
    remainder key per entry, C (C + 1) / 2 per chunk
  - the operands of the matrix products when they are committed and not public, as they must be once
    the layer inputs come from the previous segment: k_t, q_t, v_t (3 D per token) and a_t, beta_t (2)
Not counted anywhere here: range checks of the quotients themselves, whatever exact range or multi-word
relation a sound GB = 18 lowering needs (runs/sb-alias-gb18.json shows the M1b-style one is not sound),
conv, gates, norms, projections, the output path, attention layers, the head, and any sumcheck, lookup
or commitment overhead. The formulas are per V head; sharing of Q, K and the Gram matrices across the V
heads of a layer is not modelled.
"""
import json, math, pathlib
root = pathlib.Path(__file__).resolve().parents[3]
E = root / 'experiments/20261109-34-qwen-state-commit/runs'
L, H, D, F, KEY = 48, 48, 128, 12, 12

def per_head(GB, C):
    ks = math.ceil((F + GB) / KEY); km = math.ceil((2 * F + GB) / KEY)
    items = dict(
        S_out_cells=D * D / C, S_out_remainder_keys=ks * D * D / C,
        decay_table_entries=(C + 1) / 2, gram_KK_QK=2 * C,
        P0_Q0=2 * D, M_delta_lo_hi_o=4 * D, remainder_keys_M=km * D, remainder_keys_delta=D, remainder_keys_o=km * D)
    extras = dict(decay_table_floor_remainder_keys=(C + 1) / 2, committed_operands_k_q_v_a_beta=3 * D + 2)
    return ks, km, items, extras

def main():
    rows = []
    for GB in (12, 18):
        for C in (16, 64, 128):
            ks, km, items, extras = per_head(GB, C)
            sb = sum(items.values()); ex = sum(extras.values())
            rows.append(dict(GB=GB, C=C, registered_arm=(GB == 12), S_out_keys=ks, M_o_keys=km,
                             formula=f'{1 + ks} D^2 / C + {7 + 2 * km} D + 2.5 C + 0.5',
                             per_head_per_token=sb, per_head_items=items, per_head_extras=extras,
                             sb_keys_widened_per_token=round(sb * L * H),
                             sb_with_listed_extras_per_token=round((sb + ex) * L * H),
                             sb_on_product_oracle_per_token=round((3 * D * D + D * C + sb) * L * H)))
    # self-check against the registered count.json (GB = 12 arm, unchanged)
    old = json.loads((E / 'count.json').read_text())['rows']
    def old_row(s, C): return [r for r in old if r['strategy'] == s and r['C'] == C][0]['committed_per_token']
    check = {}
    for r in rows:
        if r['GB'] == 12:
            check[f'SB C={r["C"]}'] = (r['sb_keys_widened_per_token'], old_row('SB', r['C']))
            check[f"SB' C={r['C']}"] = (r['sb_on_product_oracle_per_token'], old_row("SB'", r['C']))
    assert all(a == b for a, b in check.values()), check
    base = dict(per_token_6p1=old_row('SA', 64), per_token_17p41=[r for r in old if r['strategy'] == 'SA' and r['C'] == 64 and r['w_cell'] == 17.41][0]['committed_per_token'])
    base['per_token_6p1'] = [r for r in old if r['strategy'] == 'SA' and r['C'] == 64 and r['w_cell'] == 6.1][0]['committed_per_token']
    r12 = [r for r in rows if r['GB'] == 12 and r['C'] == 64][0]; r18 = [r for r in rows if r['GB'] == 18 and r['C'] == 64][0]
    out = dict(
        note='counted, not measured; no SB proof and no SB backend exist in this repository; the GB = 12 column is the registered arm, which failed H4(c); the GB = 18 arm is unregistered and has no sound lowering here',
        shapes=dict(L=L, H=H, D=D, F=F, key_bits=KEY), rows=rows,
        gb12_reproduces_count_json={k: dict(count_r2=a, count_json=b) for k, a_b in check.items() for a, b in [a_b]},
        per_token_baselines_from_count_json=base,
        product_oracle_vs_per_token_arm_B_at_C64=dict(
            what='the same stated formula on the research product oracle (3 D^2 + D C + SB per head), divided by the 6.1-per-cell per-token count; both are counts for the backend this repository has, neither is a built SB proof',
            gb12=dict(sb_on_product_oracle=r12['sb_on_product_oracle_per_token'], per_token_arm_B=base['per_token_6p1'], fraction=round(r12['sb_on_product_oracle_per_token'] / base['per_token_6p1'], 4)),
            gb18=dict(sb_on_product_oracle=r18['sb_on_product_oracle_per_token'], per_token_arm_B=base['per_token_6p1'], fraction=round(r18['sb_on_product_oracle_per_token'] / base['per_token_6p1'], 4))))
    (E / 'count-r2.json').write_text(json.dumps(out, indent=1) + '\n')
    for r in rows: print({k: v for k, v in r.items() if not k.startswith('per_head_')})
    print(out['product_oracle_vs_per_token_arm_B_at_C64'])

if __name__ == '__main__': main()
