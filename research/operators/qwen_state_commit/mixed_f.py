#!/usr/bin/env python3
"""How far the mixed-precision chain of the hostile suite (case n1) is from the honest chain. Arithmetic only.

Case n1 of record.py proves chunk 1 of the seed-1 window in the same relation at F = 13 and the later
chunks at F = 12 from its output. The chain check of the registered runs accepted that chain; the pinned
one rejects it on the fixture's F. This script recomputes the public words of that chain (no proof) and
reports, per C, the largest difference from the honest F = 12 chain in the output state of the F = 13
chunk, in the outputs o of that chunk, and in the final state of the window.

Writes experiments/20261109-34-qwen-state-commit/runs/mixed-f-states.json.
"""
import json, pathlib, sys
import numpy as np
here = pathlib.Path(__file__).resolve().parent
root = here.parents[2]
sys.path.insert(0, str(here))
import window as W
R = W.R

def run(S, toks, F):
    outs = []
    for tok in toks:
        M, d, S, o = R.step(S, tok, F, check=False); outs.append(o)
    return S, outs

def main():
    rows = []
    for C in (1, 16, 64):
        T = W.T if C < 64 else 128; n = T // C; c = 1
        S0, toks, _ = W.gen_window(1, T)
        tk = lambda j: toks[j * C:(j + 1) * C]
        Sh = S0
        for j in range(c): Sh, _ = run(Sh, tk(j), W.F)
        S12, o12 = run(Sh, tk(c), W.F); S13, o13 = run(Sh, tk(c), 13)
        Sa, Sb = S12, S13
        for j in range(c + 1, n):
            Sa, _ = run(Sa, tk(j), W.F); Sb, _ = run(Sb, tk(j), W.F)
        rows.append(dict(C=C, T=T, chunks=n, chunk_at_F13=c, tokens_after_that_chunk=T - (c + 1) * C,
                         chunk_output_state_max_abs_diff=int(np.abs(S12 - S13).max()),
                         chunk_outputs_o_max_abs_diff=int(max(np.abs(a - b).max() for a, b in zip(o12, o13))),
                         final_state_max_abs_diff=int(np.abs(Sa - Sb).max())))
        print(json.dumps(rows[-1]), flush=True)
    out = dict(note='arithmetic only, no proof; the words of hostile case n1 (record.py), seed 1, D = 32', rows=rows)
    (root / 'experiments/20261109-34-qwen-state-commit/runs/mixed-f-states.json').write_text(json.dumps(out, indent=1) + '\n')

if __name__ == '__main__': main()
