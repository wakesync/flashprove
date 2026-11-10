#!/usr/bin/env python3
"""What the gates of the registered SB failure case look like (R3 seed 3). Descriptive, no proof.

The registered SB arm (GB = 12) misses the drift bound on one run, R3 seed 3. This script records the
decay gate statistics of that run and the staged decay products the SB reference uses at the start of
each chunk, G[C][0] at scale 2^12, so that the write-up can say what is observed. It does not
establish why the drift is larger on this run.

Writes experiments/20261109-34-qwen-state-commit/runs/sb-gates-r3s3.json.
"""
import json, pathlib, sys
import numpy as np
here = pathlib.Path(__file__).resolve().parent
root = here.parents[2]
sys.path.insert(0, str(root / 'research/operators/qwen_deltanet'))
import reference as R
F = 12; STEPS = 1024

def describe(dist, seed):
    head = R.Head(np.random.default_rng(seed))        # gen_tokens draws the head first from the same generator
    toks = R.gen_tokens(seed, dist, STEPS, F)
    fa = [t['fa'] for t in toks]; ia = [t['a'] for t in toks]
    chunks = []
    for C in (16, 64):
        ends = []; zeros = 0; below16 = 0; fl = []
        for c in range(STEPS // C):
            g = 1 << F; fg = 1.0
            for tok in toks[c * C:(c + 1) * C]:
                g = (g * tok['a']) >> F; fg *= tok['fa']; zeros += g == 0; below16 += g < 16
            ends.append(g); fl.append(fg)
        chunks.append(dict(C=C, chunks=len(ends), G_C0_min=min(ends), G_C0_median=float(np.median(ends)), G_C0_max=max(ends),
                           staged_products_equal_to_zero=zeros, staged_products_below_16=below16,
                           float_product_min=min(fl), float_product_max=max(fl)))
    return dict(dist=dist, seed=seed, steps=STEPS, A=head.A, dt_bias=head.dt_bias,
                decay_float=dict(min=min(fa), median=float(np.median(fa)), max=max(fa)),
                decay_integer_scale_4096=dict(min=min(ia), median=float(np.median(ia)), max=max(ia)), chunk_start_products=chunks)

def main():
    rows = [describe('R3', 3)]
    summ = json.loads((root / 'experiments/20261109-34-qwen-state-commit/runs/sb-summary.json').read_text())
    out = dict(note='descriptive gate statistics of the registered failure case; no cause is established by this file',
               F=F, rows=rows,
               registered_drift_of_this_case={C: [x for x in summ[C]['over'] if x[0] == 'R3' and x[1] == 3] for C in ('16', '64')},
               registered_drift_max_at_C1=summ['1']['div']['max'])
    p = root / 'experiments/20261109-34-qwen-state-commit/runs/sb-gates-r3s3.json'
    p.write_text(json.dumps(out, indent=1) + '\n'); print(json.dumps(out, indent=1))

if __name__ == '__main__': main()
