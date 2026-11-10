#!/usr/bin/env python3
"""Relative fidelity + quantization degeneracy (fix for PR #42 review must-fix 4).

fidelity.py reports max ABSOLUTE error. The query is pre-scaled by 1/sqrt(d_k), so at d=128 the
float outputs are tiny (|o| about 1e-2) and an absolute threshold of 1e-2 says little about them.
This script reports, per bit width, on the same vectors and the same integer reference:
  - output relative L2 error  ||o_int/2^f - o_f32|| / ||o_f32||, both per token (worst token; unstable when one
    token's float output is tiny) and pooled over all tokens of a vector; worst vector reported
  - final-state relative L2 error (Frobenius)
  - fraction of quantized q and k entries that are exactly 0, fraction of integer outputs == 0
  - max |o_f32| (output scale)
Writes results/fidelity-relative.csv (per bits x d x T over the 8 fidelity seeds),
results/degeneracy-d128.json (the exact seed-7 d=128 sweep fixtures) and prints a summary.
Deterministic; no timing."""
import csv, json, sys
from pathlib import Path
import numpy as np
here = Path(__file__).resolve().parent
sys.path.insert(0, str(here))
import kda_scale as K

DIMS = (2, 4, 8, 16, 32, 64, 128); TOKENS = (1, 2, 4, 8); SEEDS = range(8); BITS = range(4, 25)


def measure(S0f, tf, bits):
    sc = float(1 << (bits - 2))
    S0, qt, _ = K.quantize_head(S0f, tf, bits)
    Sx, ox = K.integer_reference(S0, qt, bits)
    Sf, of = K.float32_reference(S0f, tf)
    rel_o = max(float(np.linalg.norm(a / sc - b) / (np.linalg.norm(b) + 1e-30)) for a, b in zip(ox, of))
    allx = np.concatenate([a / sc for a in ox]); allf = np.concatenate(of)
    rel_pooled = float(np.linalg.norm(allx - allf) / (np.linalg.norm(allf) + 1e-30))
    rel_s = float(np.linalg.norm(Sx / sc - Sf) / (np.linalg.norm(Sf) + 1e-30))
    return dict(rel_l2_err_output=rel_o, rel_l2_err_output_pooled=rel_pooled, rel_l2_err_state=rel_s,
                q_zero_frac=float(np.mean([np.mean(t[4] == 0) for t in qt])), k_zero_frac=float(np.mean([np.mean(t[1] == 0) for t in qt])),
                output_zero_frac=float(np.mean([np.mean(a == 0) for a in ox])), max_abs_output_f32=max(float(np.abs(b).max()) for b in of),
                max_abs_err_output=max(float(np.abs(a / sc - b).max()) for a, b in zip(ox, of)), max_abs_err_state=float(np.abs(Sx / sc - Sf).max()))


rows = []
for bits in BITS:
    for d in DIMS:
        for T in TOKENS:
            ms = []
            for seed in SEEDS:
                (S0f, tf), = K.float_vectors(1000 * seed + 17 * d + T, d, d, T, 1)
                ms.append(measure(S0f, tf, bits))
            rows.append(dict(bits=bits, d_k=d, tokens=T, vectors=len(ms),
                             rel_l2_err_output_max=max(m['rel_l2_err_output'] for m in ms), rel_l2_err_output_pooled_max=max(m['rel_l2_err_output_pooled'] for m in ms), rel_l2_err_state_max=max(m['rel_l2_err_state'] for m in ms),
                             q_zero_frac_mean=float(np.mean([m['q_zero_frac'] for m in ms])), k_zero_frac_mean=float(np.mean([m['k_zero_frac'] for m in ms])),
                             output_zero_frac_mean=float(np.mean([m['output_zero_frac'] for m in ms])),
                             max_abs_output_f32=max(m['max_abs_output_f32'] for m in ms), max_abs_err_output=max(m['max_abs_err_output'] for m in ms)))
with open(here / 'results' / 'fidelity-relative.csv', 'w', newline='') as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)

# the exact d=128 sweep fixtures (seed 7), proved or plan-only
deg = []
for bits in (4, 8, 12, 16):
    for T in (1, 2, 4, 8):
        (S0f, tf), = K.float_vectors(7, 128, 128, T, 1)
        deg.append(dict(d_k=128, tokens=T, bits=bits, seed=7, **measure(S0f, tf, bits)))
(here / 'results' / 'degeneracy-d128.json').write_text(json.dumps(deg, indent=2) + '\n')

print('bits | worst pooled out rel L2 (all) | worst per-token out rel L2 (all) | worst out rel L2 d=128 | worst state rel d=128 | q zero d=128 | k zero d=128 | out zero d=128 | max|o| d=128')
for bits in BITS:
    rs = [r for r in rows if r['bits'] == bits]; r128 = [r for r in rs if r['d_k'] == 128]
    print(f"{bits} | {max(r['rel_l2_err_output_pooled_max'] for r in rs):.4g} | {max(r['rel_l2_err_output_max'] for r in rs):.4g} | {max(r['rel_l2_err_output_max'] for r in r128):.4g} | "
          f"{max(r['rel_l2_err_state_max'] for r in r128):.4g} | {np.mean([r['q_zero_frac_mean'] for r in r128]):.3f} | "
          f"{np.mean([r['k_zero_frac_mean'] for r in r128]):.3f} | {np.mean([r['output_zero_frac_mean'] for r in r128]):.3f} | {max(r['max_abs_output_f32'] for r in r128):.4g}")
for thr in (0.1, 0.01):
    ok = [b for b in BITS if all(r['rel_l2_err_output_pooled_max'] < thr and r['rel_l2_err_state_max'] < thr for r in rows if r['bits'] == b)]
    print(f'smallest width with pooled output AND state rel L2 err < {thr} on every vector:', min(ok) if ok else None)
print('\nseed-7 d=128 sweep fixtures:')
for r in deg:
    print(f"bits {r['bits']:2d} T {r['tokens']}: q zero {r['q_zero_frac']:.2f} k zero {r['k_zero_frac']:.2f} out zero {r['output_zero_frac']:.2f} "
          f"out rel worst-token {r['rel_l2_err_output']:.3f} pooled {r['rel_l2_err_output_pooled']:.3f} state rel {r['rel_l2_err_state']:.4f} max|o| {r['max_abs_output_f32']:.4f}")
