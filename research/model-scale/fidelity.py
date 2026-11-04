#!/usr/bin/env python3
"""Fixed-point divergence vs the float32 reference as a function of bit width.

Uses the SAME integer reference (kda_scale.integer_reference) that the proved lowering is checked
against for every sweep point, so the error measured here is the error of the proved semantics.
Writes results/fidelity.csv and prints the smallest width with max |error| < 1e-2 on every vector.
"""
import csv, json, sys
from pathlib import Path
import numpy as np
here = Path(__file__).resolve().parent
sys.path.insert(0, str(here))
import kda_scale as K

DIMS = (2, 4, 8, 16, 32, 64, 128); TOKENS = (1, 2, 4, 8); SEEDS = range(8); BITS = range(4, 25)
rows = []
for bits in BITS:
    sc = float(1 << (bits - 2))
    for d in DIMS:
        for T in TOKENS:
            es = eo = 0.0; over = clipped = 0
            for seed in SEEDS:
                (S0f, tf), = K.float_vectors(1000 * seed + 17 * d + T, d, d, T, 1)
                S0, qt, c = K.quantize_head(S0f, tf, bits); clipped += c
                try:
                    Sx, ox = K.integer_reference(S0, qt, bits)
                except K.Overflow:
                    over += 1; continue
                Sf, of = K.float32_reference(S0f, tf)
                es = max(es, float(np.abs(Sx / sc - Sf).max()))
                eo = max(eo, max(float(np.abs(a / sc - b).max()) for a, b in zip(ox, of)))
            rows.append(dict(bits=bits, frac_bits=bits - 2, d_k=d, d_v=d, tokens=T, vectors=len(SEEDS), overflow_rejected=over,
                             clipped_inputs=clipped, max_abs_err_state=es, max_abs_err_output=eo, max_abs_err=max(es, eo)))
with open(here / 'results' / 'fidelity.csv', 'w', newline='') as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
summary = {}
for bits in BITS:
    rs = [r for r in rows if r['bits'] == bits]
    summary[bits] = dict(max_abs_err=max(r['max_abs_err'] for r in rs), overflow=sum(r['overflow_rejected'] for r in rs),
                         clipped=sum(r['clipped_inputs'] for r in rs), at_d128_T8=[r for r in rs if r['d_k'] == 128 and r['tokens'] == 8][0]['max_abs_err'])
ok = [b for b in BITS if summary[b]['max_abs_err'] < 1e-2 and summary[b]['overflow'] == 0]
need = min(ok) if ok else None
(here / 'results' / 'fidelity-summary.json').write_text(json.dumps({'by_bits': summary, 'smallest_bits_max_err_below_1e-2': need,
    'vectors_per_bits': len(DIMS) * len(TOKENS) * len(SEEDS), 'reference': 'numpy float32, pinned post-gate operation order; not torch/FLA kernel'}, indent=2) + '\n')
for b in BITS:
    print(b, '%.6g' % summary[b]['max_abs_err'], 'overflow', summary[b]['overflow'], 'clipped', summary[b]['clipped'])
print('smallest width with max error < 1e-2:', need)
