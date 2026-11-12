#!/usr/bin/env python3
"""Exact column/relation counts of window.cpp (one window of C tokens), closed form.

Independent of the C++ relation builder; the suite compares these with the built relation.
Not bytes, not memory, not a model-wide or hardware estimate.
"""
import json

W, RATE, RF, RP = 12, 8, 8, 22
SBOX_COLS, SBOX_REL = 4, 8  # input link + 7 wire equalities

def power2(n):
    return 1 << (n - 1).bit_length()

def perm_cost():
    sboxes = RF * W + RP
    mat = RP * (W - 1)
    return dict(cols=sboxes * SBOX_COLS + mat, rel=sboxes * SBOX_REL + mat)

def counts(D, C, F=12):
    DD = D * D
    words = DD + 9 * D + 1          # state, 3-tap history (3 x 3D), salt
    perms = -(-(words + 1) // RATE)  # + one padding word "1", then zeros
    pc = perm_cost()
    hash_cols = 2 * perms * pc['cols']
    hash_rel = 2 * (perms * pc['rel'] + 4)
    rec_cols = C * ((F + 5) * DD + (4 * F + 5) * D)
    # Per-token formula includes the first token's DD initial pins; the last token adds DD final pins.
    # Both sets of public boundary pins are removed: C * formula + DD - 2 DD.
    rec_rel = C * ((2 * F + 9) * DD + (8 * F + 7) * D) - DD
    extra_cols = 18 * D + 3 * C * D + 2 + DD   # Hin, Hout, xs, two salts, S_in range cells
    extra_rel = DD + 3 * C * D + 9 * D         # S_in range links, preconv pins, history shift
    rc = C * (DD + 3 * D) + DD
    core = rec_cols + extra_cols + hash_cols
    size = 16 * power2((rc + 15) // 16)
    laid = ((core - rc + size - 1) // size) * size + size
    rel = rec_rel + extra_rel + hash_rel
    return dict(D=D, C=C, F=F, permutations=2 * perms, perm_columns=pc['cols'], perm_relations=pc['rel'],
                hash_columns=hash_cols, hash_relations=hash_rel, core_columns=core, aligned_columns=laid,
                relations=rel, range_cells=rc, core_columns_per_token=core / C, relations_per_token=rel / C,
                hash_columns_per_token=hash_cols / C, hash_relations_per_token=hash_rel / C,
                hash_column_share=hash_cols / core)

if __name__ == '__main__':
    print(json.dumps({'kind': 'counted; only D8/C2 is built and checked',
                      'rows': [counts(D, C) for D, C in [(8, 2), (32, 2), (128, 2), (128, 64)]]}, indent=2))
