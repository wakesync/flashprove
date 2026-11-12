#!/usr/bin/env python3
"""Synthetic N-window chains, the Python sponge commitment, and hostile window witnesses.

The commitment here is an independent Python implementation of the in-circuit sponge in
window.cpp (width 12, rate 8, capacity 4, x^7, 8 full + 22 partial rounds, Cauchy MDS,
SHA-256 counter constants). The suite checks that both agree on every commitment.
No verifier reads anything written by write_witness().
"""
import copy
import hashlib
import pathlib
import sys
import numpy as np

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / 'research/operators/qwen_deltanet'))
import reference as R

P = 0xFFFFFFFF00000001
W, RATE, RF, RP = 12, 8, 8, 22
NROUND = RF + RP
MODEL = hashlib.sha256(b'synthetic-deltanet-SA-M1b-hidden-root-v1').digest()
WEIGHTS = hashlib.sha256(b'synthetic-no-weight-matmul-proved').digest()
POLICY = 1

MDS = [[pow(i + W + j, P - 2, P) for j in range(W)] for i in range(W)]
RC = [[int.from_bytes(hashlib.sha256(b'fp-hidden-root-rc-v1' + (r * W + i).to_bytes(4, 'little')).digest()[:8], 'little') % P
       for i in range(W)] for r in range(NROUND)]

def perm(s):
    for r in range(NROUND):
        s = [(x + RC[r][i]) % P for i, x in enumerate(s)]
        full = r < RF // 2 or r >= RF // 2 + RP
        if full:
            s = [pow(x, 7, P) for x in s]
        else:
            s[0] = pow(s[0], 7, P)
        s = [sum(MDS[i][j] * s[j] for j in range(W)) % P for i in range(W)]
    return s

def le(words):
    return np.asarray(words, dtype='<i8').tobytes()

def cap(F, D, C, N, request, layer, boundary, model=MODEL, weights=WEIGHTS):
    h = hashlib.sha256(b'fp-hidden-root-ctx-v1' + le([F, D, C, N, request, layer, POLICY, boundary]) + model + weights).digest()
    return [int.from_bytes(h[8 * i:8 * i + 8], 'little') % P for i in range(4)]

def commit(S, H, salt, capacity):
    words = [int(x) % P for x in np.asarray(S).reshape(-1)] + [int(x) % P for x in np.asarray(H).reshape(-1)] + [int(salt) % P, 1]
    while len(words) % RATE:
        words.append(0)
    s = [0] * RATE + list(capacity)
    for b in range(0, len(words), RATE):
        for i in range(RATE):
            s[i] = (s[i] + words[b + i]) % P
        s = perm(s)
    return s[:4]

def cbytes(c):
    return b''.join(int(x).to_bytes(8, 'little') for x in c)

def records(S, toks, F):
    rec = []
    for tok in toks:
        M, delta, S, o = R.step(S, tok, F)
        rec.append((M, delta, S.copy(), o))
    return rec

def chain(seed, D, C, N, layer, salt_stream):
    """One layer's chain. All layers of a seed share S0/tokens/history: only context and salts differ."""
    R.D = D
    S0, toks, rec = R.fixture(seed, F=12, T=N * C)
    rng = np.random.default_rng(seed + 10000)
    xs = rng.integers(-1000, 1000, size=(3 + N * C, 3 * D), dtype=np.int64)
    srng = np.random.default_rng([seed, salt_stream])
    salts = [int(x) for x in srng.integers(0, 1 << 62, size=N + 1, dtype=np.int64)]
    S = [S0.copy()] + [rec[(b + 1) * C - 1][2].copy() for b in range(N)]
    H = [xs[b * C:b * C + 3].copy() for b in range(N + 1)]
    ch = dict(seed=seed, D=D, C=C, N=N, F=12, request=117, layer=layer, model=MODEL, weights=WEIGHTS,
              toks=toks, xs=xs, outputs=[r[3] for r in rec], S=S, H=H, salts=salts)
    ch['commit'] = [commit(S[b], H[b], salts[b], cap(12, D, C, N, 117, layer, b)) for b in range(N + 1)]
    return ch

def window_statement(ch, k, layer=None, N=None):
    """Verifier-held statement for window k. Contains no boundary state or history."""
    D, C = ch['D'], ch['C']
    layer = ch['layer'] if layer is None else layer
    N = ch['N'] if N is None else N
    out = b'FPHR0001' + le([D, ch['F'], C, N, k, ch['request'], layer, POLICY]) + ch['model'] + ch['weights']
    for t in ch['toks'][k * C:(k + 1) * C]:
        out += le([t['a'], t['beta']]) + le(t['k']) + le(t['v']) + le(t['q'])
    out += le(ch['xs'][k * C + 3:(k + 1) * C + 3].reshape(-1))
    out += le(np.asarray(ch['outputs'][k * C:(k + 1) * C]).reshape(-1))
    return out

def honest_witness(ch, k):
    C, D = ch['C'], ch['D']
    toks = copy.deepcopy(ch['toks'][k * C:(k + 1) * C])
    return dict(F=12, S0=ch['S'][k].copy(), toks=toks, rec=records(ch['S'][k], toks, 12), Hin=ch['H'][k].copy(),
                xs=ch['xs'][k * C + 3:(k + 1) * C + 3].copy(), salt_in=ch['salts'][k], salt_out=ch['salts'][k + 1],
                cap_in=cap(12, D, C, ch['N'], ch['request'], ch['layer'], k),
                cap_out=cap(12, D, C, ch['N'], ch['request'], ch['layer'], k + 1))

def hout(w):
    C = len(w['toks'])
    rows = [w['Hin'][C + t] if C + t < 3 else w['xs'][C + t - 3] for t in range(3)]
    return np.asarray(rows)

def claimed_out(w):
    """Commitment of the witness's own final state/history/salt under the witness's own capacity."""
    return commit(w['rec'][-1][2], hout(w), w['salt_out'], w['cap_out'])

def claimed_in(w):
    return commit(w['S0'], w['Hin'], w['salt_in'], w['cap_in'])

def write_witness(d, w):
    d.mkdir(parents=True, exist_ok=True)
    D = w['S0'].shape[0]
    out = le([len(w['toks']), D, w['F']]) + le(w['S0'].reshape(-1))
    for t in w['toks']:
        out += le([t['a'], t['beta']]) + le(t['k']) + le(t['v']) + le(t['q'])
    for M, delta, S, o in w['rec']:
        out += le(M) + le(delta) + le(S.reshape(-1)) + le(o)
    (d / 'w.fx').write_bytes(out)
    pk = le(w['Hin'].reshape(-1)) + le([w['salt_in'], w['salt_out']]) + le(w['xs'].reshape(-1))
    pk += cbytes(w['cap_in']) + cbytes(w['cap_out'])
    (d / 'w.packet').write_bytes(pk)

def redo(w):
    w['rec'] = records(w['S0'], w['toks'], w['F'])

# Window-level named negatives, all at window k=1 of a 3-window layer-3 chain.
# Each returns (witness, claimed C_in handed to the verifier, claimed C_out, statement overrides).
WINDOW_CASES = ['tampered_boundary_state', 'tampered_boundary_history', 'tampered_output_commitment',
                'state_from_other_window', 'other_window_commitment', 'other_layer_state', 'mixed_F_chain',
                'replayed_earlier_window_witness', 'truncated_chain_relabel']

def hostile(name, ch, other):
    k = 1
    w = honest_witness(ch, k)
    cin = ch['commit'][k]
    D, C = ch['D'], ch['C']
    if name == 'tampered_boundary_state':
        w['S0'][0, 0] += 1; redo(w)
    elif name == 'tampered_boundary_history':
        w['Hin'][0, 0] += 1
    elif name == 'tampered_output_commitment':
        c = claimed_out(w); c[0] = (c[0] + 1) % P
        return w, cin, c
    elif name == 'state_from_other_window':
        w['S0'] = ch['S'][2].copy(); w['Hin'] = ch['H'][2].copy(); w['salt_in'] = ch['salts'][2]; redo(w)
    elif name == 'other_window_commitment':
        # Genuine boundary-2 commitment, opened honestly under boundary-2 context.
        w['S0'] = ch['S'][2].copy(); w['Hin'] = ch['H'][2].copy(); w['salt_in'] = ch['salts'][2]
        w['cap_in'] = cap(12, D, C, ch['N'], ch['request'], ch['layer'], 2); redo(w)
        cin = ch['commit'][2]
    elif name == 'other_layer_state':
        # Genuine layer-4 window 1, same state values, honest under layer-4 context, presented to layer 3.
        w = honest_witness(other, k)
        cin = other['commit'][k]
    elif name == 'mixed_F_chain':
        w['F'] = 13; redo(w)
    elif name == 'replayed_earlier_window_witness':
        w = honest_witness(ch, 0)
        cin = ch['commit'][1]
    elif name == 'truncated_chain_relabel':
        w['cap_in'] = cap(12, D, C, 2, ch['request'], ch['layer'], k)
        w['cap_out'] = cap(12, D, C, 2, ch['request'], ch['layer'], k + 1)
        cin = claimed_in(w)
    else:
        raise ValueError(name)
    return w, cin, claimed_out(w)
