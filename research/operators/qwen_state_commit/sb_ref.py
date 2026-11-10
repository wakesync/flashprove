#!/usr/bin/env python3
"""Strategy SB (chunked low-rank / UT form): integer reference and range study (no proof).

One Qwen3.8 Gated DeltaNet head at the real shape (D = 128, F = 12), token generator of
research/operators/qwen_deltanet/reference.py (M1, unchanged). Inside a chunk of C tokens the
state is never materialised. With tokens t = 1..C of the chunk and S0 the chunk's input state:

  G[t][t] = 2^F,  G[t][s] = floor(G[t-1][s] * a_t / 2^F)  (s < t)      staged decay products
  P0[t]   = S0^T k_t,  Q0[t] = S0^T q_t                                   exact (matmul outputs)
  M_t     = floor((2^F G[t][0] P0[t] + sum_{s<t}  G[t][s] (k_t.k_s) delta_s) / 2^3F)
  delta_t = floor((v_t - M_t) beta_t / 2^F)                               as M1
  o_t     = floor((2^F G[t][0] Q0[t] + sum_{s<=t} G[t][s] (q_t.k_s) delta_s) / 2^3F)
  S_out   = floor((2^F G[C][0] S0 + sum_s G[C][s] k_s delta_s^T) / 2^2F)

One floor per value, from an exact integer accumulation (Python ints, so the numerator bit
counts reported are exact). At C = 1 this is M1's relation for M, delta and S (o differs: M1
floors S' before the output read). Writes ../../../experiments/20261109-34-qwen-state-commit/runs/sb-ranges.json.
Usage: sb_ref.py [--steps 1024] [--quick]
"""
import argparse, json, math, pathlib, sys, time
import numpy as np
here = pathlib.Path(__file__).resolve().parent
root = here.parents[2]
sys.path.insert(0, str(root / 'research/operators/qwen_deltanet'))
import reference as R

F = 12
BOUND = 1 << 18

def bits(x):
    return int(abs(int(x))).bit_length()

def chunk_sb(S0, toks, F, GB=None):
    """S0: int64 (D, D). Returns per-token M, delta, o (lists of int64 arrays), S_out, max numerator bits."""
    C = len(toks); one = 1 << F; GB = F if GB is None else GB; gone = 1 << GB  # G at scale 2^GB (GB = F registered)
    G = [[0] * (C + 1) for _ in range(C + 1)]
    G[0][0] = gone
    for t in range(1, C + 1):
        G[t][t] = gone
        for s in range(t):
            G[t][s] = (G[t - 1][s] * toks[t - 1]['a']) >> F  # floor, operands non-negative
    S0o = S0.astype(object)
    K = [tok['k'].astype(object) for tok in toks]
    Qv = [tok['q'].astype(object) for tok in toks]
    deltas = []; Ms = []; os_ = []; nb = dict(M=0, o=0, S=0, Gram=0)
    for t in range(1, C + 1):
        tok = toks[t - 1]; k = K[t - 1]; q = Qv[t - 1]
        P0 = k.dot(S0o); Q0 = q.dot(S0o)
        num = one * G[t][0] * P0
        for s in range(1, t):
            kk = int(k.dot(K[s - 1])); nb['Gram'] = max(nb['Gram'], bits(kk))
            num = num + G[t][s] * kk * deltas[s - 1]
        nb['M'] = max(nb['M'], max(bits(x) for x in num))
        M = np.array([x // (1 << (2 * F + GB)) for x in num], dtype=object)
        delta = ((tok['v'].astype(object) - M) * tok['beta']) // one
        deltas.append(delta)
        onum = one * G[t][0] * Q0
        for s in range(1, t + 1):
            qk = int(q.dot(K[s - 1]))
            onum = onum + G[t][s] * qk * deltas[s - 1]
        nb['o'] = max(nb['o'], max(bits(x) for x in onum))
        o = np.array([x // (1 << (2 * F + GB)) for x in onum], dtype=object)
        Ms.append(M.astype(np.int64)); os_.append(o.astype(np.int64))
    Snum = one * G[C][0] * S0o
    for s in range(1, C + 1):
        Snum = Snum + G[C][s] * np.outer(K[s - 1], deltas[s - 1])
    nb['S'] = max(bits(x) for x in Snum.reshape(-1))
    Sout = np.array([[x // (1 << (F + GB)) for x in row] for row in Snum], dtype=object).astype(np.int64)
    return Ms, [d.astype(np.int64) for d in deltas], os_, Sout, nb

def run(seed, dist, C, steps, GB=None):
    toks = R.gen_tokens(seed, dist, steps, F)
    D = R.D
    S = np.zeros((D, D), dtype=np.int64); Sf = np.zeros((D, D)); Sm1 = np.zeros((D, D), dtype=np.int64)
    mx = dict(S=0, M=0, delta=0, o=0); nbits = dict(M=0, o=0, S=0, Gram=0)
    eq_m1 = True; first_mismatch = None; div = 0.0; sb_vs_m1 = 0
    over = dict(S=None, M=None, delta_hi=None)
    for c in range(steps // C):
        ch = toks[c * C:(c + 1) * C]
        Ms, ds, os_, Sn, nb = chunk_sb(S, ch, F, GB)
        for k in nbits: nbits[k] = max(nbits[k], nb[k])
        # M1 per-token integer reference over the same chunk, and float64 recurrence
        M1ms, M1ds = [], []
        for tok in ch:
            M, dl, Sm1, _ = R.step(Sm1, tok, F, check=False); M1ms.append(M); M1ds.append(dl)
            Sf, _ = R.float_step(Sf, tok)
        if C == 1 and eq_m1:
            if not (np.array_equal(Ms[0], M1ms[0]) and np.array_equal(ds[0], M1ds[0]) and np.array_equal(Sn, Sm1)):
                eq_m1 = False; first_mismatch = c
        sb_vs_m1 = max(sb_vs_m1, int(np.abs(Sn - Sm1).max()))
        S = Sn
        div = max(div, float(np.abs(S / (1 << F) - Sf).max()))
        for name, arr in (('M', Ms), ('delta', ds), ('o', os_)):
            mx[name] = max(mx[name], max(int(np.abs(x).max()) for x in arr))
        mx['S'] = max(mx['S'], int(np.abs(S).max()))
        dhi = max(int(np.abs(np.floor_divide(x, BOUND)).max()) for x in ds)
        if over['S'] is None and mx['S'] >= BOUND: over['S'] = c
        if over['M'] is None and mx['M'] >= BOUND: over['M'] = c
        if over['delta_hi'] is None and dhi >= BOUND: over['delta_hi'] = c
    fits = all(v is None for v in over.values())
    return dict(seed=seed, dist=dist, C=C, steps=steps, max_abs=mx, max_numerator_bits=nbits,
                first_chunk_over=over, fits_contract=fits, equals_m1_at_C1=(eq_m1 if C == 1 else None),
                first_mismatch_chunk=first_mismatch, max_abs_S_vs_m1_integer=sb_vs_m1,
                divergence_vs_float64_max_abs=div)

def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--steps', type=int, default=1024); ap.add_argument('--quick', action='store_true')
    ap.add_argument('--out', default=str(root / 'experiments/20261109-34-qwen-state-commit/runs/sb-ranges.json'))
    ap.add_argument("--gb", type=int, default=None, help="scale bits of the decay table G (default F, registered); other values are an unregistered arm")
    a = ap.parse_args()
    t0 = time.time(); rows = []
    dists = ('R1',) if a.quick else ('R1', 'R2', 'R3', 'R4'); seeds = (1,) if a.quick else range(1, 6)
    for C in (1, 16, 64):
        for d in dists:
            for s in seeds:
                r = run(s, d, C, a.steps, a.gb); rows.append(r); print(json.dumps(r), flush=True)
    summ = {}
    for C in (1, 16, 64):
        rs = [r for r in rows if r['C'] == C]
        summ[str(C)] = dict(n=len(rs), fits=sum(r['fits_contract'] for r in rs),
                            equals_m1=(sum(bool(r['equals_m1_at_C1']) for r in rs) if C == 1 else None),
                            max_S=max(r['max_abs']['S'] for r in rs), max_M=max(r['max_abs']['M'] for r in rs),
                            max_delta=max(r['max_abs']['delta'] for r in rs), max_o=max(r['max_abs']['o'] for r in rs),
                            max_num_bits={k: max(r['max_numerator_bits'][k] for r in rs) for k in ('M', 'o', 'S', 'Gram')},
                            div_max=max(r['divergence_vs_float64_max_abs'] for r in rs),
                            div_median=float(np.median([r['divergence_vs_float64_max_abs'] for r in rs])),
                            sb_vs_m1_max=max(r['max_abs_S_vs_m1_integer'] for r in rs))
    out = dict(F=F, GB=a.gb if a.gb is not None else F, D=R.D, steps=a.steps, rows=rows, summary=summ, seconds=round(time.time() - t0, 1))
    p = pathlib.Path(a.out); p.parent.mkdir(parents=True, exist_ok=True); p.write_text(json.dumps(out, indent=1) + '\n')
    print(json.dumps(summ, indent=1))

if __name__ == '__main__': main()
