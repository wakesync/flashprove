#!/usr/bin/env python3
"""Counted (NOT measured) volumes for the state-commitment strategies, Qwen3.8-27B shapes.

Every number this prints is a count from the formulas below, not a measurement. Shapes from
research/ports/qwen3.8-27b/FEASIBILITY.md section 1: 48 Gated DeltaNet layers, 48 V heads,
D = 128 (state D x D per V head), conv history 3 taps x 10,240 channels per layer.
Writes experiments/20261109-34-qwen-state-commit/runs/count.json.

Per V head, per token, symbols: C chunk size, T tokens.
  S0  per-token commit  carried = D^2 (+ conv 3*10240/48 per head)   witness = w_cell * D^2
  SA  boundary commit   carried = (D^2 + conv)/C                     witness = w_cell * D^2 (unchanged)
  SB  chunked UT form, sumcheck-matmul backend (matrix products reduced by sumcheck, only their
      floored outputs and remainder keys committed):
        per chunk: S_out D^2 + its remainder 2 keys per cell (2F = 24 bits as two 12-bit keys)
                   decay table G: C(C+1)/2; Gram K K^T and Q K^T: 2 C^2
        per token: P0 = S_in^T k and Q0 = S_in^T q outputs: 2D; M, delta_lo, delta_hi, o: 4D;
                   remainder keys of M (3F = 36 bits: 3 keys), delta (1 key), o (3 keys): 7D
        => 3 D^2 / C + 13 D + 2.5 C + 0.5 committed values
  SB' same relation on this repo's product-oracle backend (every product term a committed gate):
        P0, Q0 per token: 2 D^2 gates; S_out accumulation: D^2 C per chunk = D^2 per token;
        intra-chunk M and o sums: D (C - 1)/2 + D (C + 1)/2 = D C; plus SB's committed values
        => 3 D^2 + D C + SB
  SC  checkpoint and recompute: same committed volume as SA (it is a prover memory schedule)
  SD  sumcheck over time: SB with C = T
w_cell: committed product cells per state cell per token in the per-token relation: 17.41 (M1b,
measured statement count, #63) or 6.1 (#66 arm B, counted).
"""
import json, pathlib
root = pathlib.Path(__file__).resolve().parents[3]
L, H, D = 48, 48, 128
CONV = 3 * 10240          # carried conv history words per layer per boundary
T = 1024

def per_token(strategy, C, w_cell=6.1, T=T):
    conv_head = CONV / H
    if strategy == 'S0':
        carried = D * D + conv_head; witness = w_cell * D * D
    elif strategy in ('SA', 'SC'):
        carried = (D * D + conv_head) / C; witness = w_cell * D * D
    elif strategy in ('SB', 'SD'):
        C = T if strategy == 'SD' else C
        carried = (D * D + conv_head) / C; witness = 3 * D * D / C + 13 * D + 2.5 * C + 0.5
    elif strategy == "SB'":
        carried = (D * D + conv_head) / C; witness = 3 * D * D + D * C + 3 * D * D / C + 13 * D + 2.5 * C + 0.5
    else: raise ValueError(strategy)
    return dict(carried=carried * L * H, committed=witness * L * H)

def main():
    rows = []
    for s in ('S0', 'SA', 'SB', "SB'", 'SC', 'SD'):
        for C in ((1,) if s in ('S0',) else (T,) if s == 'SD' else (1, 16, 64, 128)):
            for w in ((17.41, 6.1) if s in ('S0', 'SA', 'SC') else (None,)):
                r = per_token(s, C, w or 6.1)
                rows.append(dict(strategy=s, C=C, w_cell=w, carried_per_token=round(r['carried']), committed_per_token=round(r['committed']),
                                 committed_per_1024_window=round(r['committed'] * T), carried_per_boundary=round((D * D * H + CONV) * L)))
    conv = dict(per_layer_per_boundary=CONV, model_per_boundary=CONV * L, state_model_per_boundary=D * D * H * L,
                conv_fraction_of_state=CONV / (D * D * H))
    out = dict(note='counted, not measured', shapes=dict(L=L, H=H, D=D, conv_words_per_layer=CONV, T=T), rows=rows, conv_history=conv)
    p = root / 'experiments/20261109-34-qwen-state-commit/runs/count.json'; p.write_text(json.dumps(out, indent=1) + '\n')
    for r in rows: print(r)
    print(conv)

if __name__ == '__main__': main()
