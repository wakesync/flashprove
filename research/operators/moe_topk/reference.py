#!/usr/bin/env python3
"""Integer reference for the bias-corrected stable top-k router (MoE top-k slice).

Chosen research contract, NOT publisher numerics (see README.md). Independent of the
C++ witness lowering in test.cpp: this file selects by an explicit Python sort on
(corrected score descending, expert index ascending) and uses Python big-int floor
division; test.cpp builds the witness from one-hot rows, ranges and quotient/remainder
cells and asserts it reproduces these indices, weights and outputs exactly.

Fixture (little-endian int64 stream):
  E k h T RSn RSd
  per token: s[E] b[E] X[E*h] (expert-major) y[h] idx[k] w[k]
"""
import argparse, json, math, random, struct, sys

ARMS = {'glm': dict(E=288, k=8, RSn=5, RSd=2),        # GLM-5.3-Flash: 288 routed, top-8, scale 2.5
        'deepseek': dict(E=384, k=6, RSn=3, RSd=2)}   # DeepSeek-V4.1-Flash: 384 routed, top-6, scale 1.5
WF = 12            # weight fraction bits
SB = 16            # unsigned score bits
BB = 16            # signed bias bits (|b| < 2^15)
XB = 16            # signed expert-output bits

def route(s, b, k):
    """Ordered top-k by corrected score s+b, ties to the lowest expert index."""
    order = sorted(range(len(s)), key=lambda i: (-(s[i] + b[i]), i))
    return order[:k]

def weights(s, idx, RSn, RSd):
    D = sum(s[i] for i in idx)
    if D <= 0:
        raise ValueError('zero denominator: statement inadmissible (fail closed)')
    return [((1 << WF) * RSn * s[i]) // (RSd * D) for i in idx]

def aggregate(X, idx, w, h):
    return [sum(wm * X[i][d] for wm, i in zip(w, idx)) >> WF for d in range(h)]  # floor (>> is floor on ints)

def gen_token(rng, E, k, h):
    """Synthetic scores with forced exact corrected-score ties: one inside the selected set
    (ranks 1,2) and one straddling the k boundary (ranks k, k+1)."""
    while True:
        # sigmoid-like scores in [0, 2^16), centred well inside the range
        s = [min((1 << SB) - 1, max(0, int(round((1 << SB) / (1 + math.exp(-rng.gauss(-1.0, 1.5))))))) for _ in range(E)]
        b = [int(round(rng.gauss(0, 1500))) for _ in range(E)]
        b = [max(-(1 << (BB - 1)), min((1 << (BB - 1)) - 1, x)) for x in b]
        order = sorted(range(E), key=lambda i: (-(s[i] + b[i]), i))
        # tie inside: make rank-1 expert's corrected score equal rank-0's, via its raw score
        a0, a1 = order[0], order[1]
        s[a1] = s[a0] + b[a0] - b[a1]
        # tie at the boundary: rank k and rank k-1 (0-based k-1, k)
        order = sorted(range(E), key=lambda i: (-(s[i] + b[i]), i))
        c0, c1 = order[k - 1], order[k]
        if c1 in (a0, a1):   # c0 may equal a1 when k = 2: a three-way tie then spans the boundary
            continue
        s[c1] = s[c0] + b[c0] - b[c1]
        if not all(0 <= x < (1 << SB) for x in s):
            continue
        idx = route(s, b, k)
        cs = [s[i] + b[i] for i in range(E)]
        inside = any(cs[idx[m]] == cs[idx[m + 1]] for m in range(k - 1))
        rest = [i for i in range(E) if i not in idx]
        straddle = any(cs[i] == cs[idx[-1]] for i in rest)
        unbiased = sorted(range(E), key=lambda i: (-s[i], i))[:k]
        if inside and straddle and sum(s[i] for i in idx) > 0:
            X = [[rng.randrange(-(1 << (XB - 1)), 1 << (XB - 1)) for _ in range(h)] for _ in range(E)]
            return dict(s=s, b=b, X=X, idx=idx, bias_changes_selection=set(unbiased) != set(idx))

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--arm', choices=list(ARMS) + ['enum'], required=True)
    ap.add_argument('--seed', type=int, required=True)
    ap.add_argument('--T', type=int, default=4)
    ap.add_argument('--h', type=int, default=16)
    ap.add_argument('--E', type=int); ap.add_argument('--k', type=int)
    ap.add_argument('--out', required=True)
    a = ap.parse_args()
    cfg = dict(ARMS[a.arm]) if a.arm != 'enum' else dict(E=a.E, k=a.k, RSn=5, RSd=2)
    E, k, RSn, RSd = cfg['E'], cfg['k'], cfg['RSn'], cfg['RSd']
    rng = random.Random(f'moe-topk/{a.arm}/{E}/{k}/{a.seed}')
    words = [E, k, a.h, a.T, RSn, RSd]; meta = []
    for t in range(a.T):
        z = gen_token(rng, E, k, a.h)
        w = weights(z['s'], z['idx'], RSn, RSd)
        y = aggregate(z['X'], z['idx'], w, a.h)
        words += z['s'] + z['b'] + [x for row in z['X'] for x in row] + y + z['idx'] + w
        meta.append(dict(idx=z['idx'], w=w, bias_changes_selection=z['bias_changes_selection']))
    with open(a.out, 'wb') as f:
        f.write(struct.pack(f'<{len(words)}q', *words))
    print(json.dumps(dict(arm=a.arm, seed=a.seed, E=E, k=k, h=a.h, T=a.T, tokens=meta)))

if __name__ == '__main__':
    sys.exit(main())
