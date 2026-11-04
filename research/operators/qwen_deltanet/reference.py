#!/usr/bin/env python3
"""Integer reference for one Qwen3.8 Gated DeltaNet head (staged floor, fixed point).

Chosen research contract, NOT the publisher's numerics (see README.md). Independent
from the C++ witness lowering in test.cpp: numpy int64 floor division here, explicit
quotient/remainder arithmetic there; test.cpp asserts both agree cell by cell.
"""
import argparse, math, struct, sys
import numpy as np

D = 128            # linear_key_head_dim = linear_value_head_dim (PR #28 config)
BOUND = 1 << 18    # smallness bound of docs/format/11-1-machinery.md

def q(x, F):
    """Round a float array to the nearest integer at scale 2^F (input preparation only)."""
    return np.rint(np.asarray(x, dtype=np.float64) * (1 << F)).astype(np.int64)

def softplus(x): return np.logaddexp(0.0, x)
def silu(x): return x / (1.0 + np.exp(-x))
def sigmoid(x): return 1.0 / (1.0 + np.exp(-x))

class Head:
    """Synthetic per-head gate parameters, Mamba2 / Qwen style init ranges."""
    def __init__(self, rng):
        self.A = float(rng.uniform(1.0, 16.0))                     # exp(A_log), A_log = log U(1,16)
        dt = float(math.exp(rng.uniform(math.log(1e-3), math.log(1e-1))))
        self.dt_bias = math.log(math.expm1(dt))                     # softplus^-1(dt)

def token_floats(rng, head, dist, state):
    """One token's real-valued inputs. dist in R1..R4 (realistic) or S1..S4 (stress: a=1, beta=1)."""
    k = rng.standard_normal(D); k /= np.linalg.norm(k)
    qv = rng.standard_normal(D); qv /= np.linalg.norm(qv); qv /= math.sqrt(D)
    base = dist[1]
    if base == '1': z = rng.standard_normal(D)
    elif base == '2': z = 2.0 * rng.standard_normal(D)
    elif base == '3': z = 2.0 * rng.standard_t(3, D)
    elif base == '4':
        prev = state.get('ar')
        e = rng.standard_normal(D)
        z1 = e if prev is None else 0.9 * prev + math.sqrt(1 - 0.81) * e
        state['ar'] = z1; z = 2.0 * z1
    else: raise ValueError(dist)
    v = silu(z)
    if dist[0] == 'S':
        decay, beta = 1.0, 1.0
    else:
        x = float(rng.standard_normal())
        decay = math.exp(-head.A * float(softplus(x + head.dt_bias)))
        beta = float(sigmoid(rng.standard_normal()))
    return decay, beta, k, v, qv

def gen_tokens(seed, dist, T, F):
    rng = np.random.default_rng(seed); head = Head(rng); st = {}
    out = []
    for _ in range(T):
        decay, beta, k, v, qv = token_floats(rng, head, dist, st)
        out.append(dict(a=int(q(decay, F)), beta=int(q(beta, F)), k=q(k, F), v=q(v, F), q=q(qv, F),
                        fa=decay, fbeta=beta, fk=k, fv=v, fq=qv))
    return out

def step(S, tok, F, check=True):
    """S: int64 (D, D), S[i, j], i key index, j value index, scale 2^F."""
    a, beta, k, v, qv = tok['a'], tok['beta'], tok['k'], tok['v'], tok['q']
    P = k @ S                                  # exact, scale 2^2F
    M = (a * P) // (1 << (2 * F))              # decayed memory read, one floor
    delta = ((v - M) * beta) // (1 << F)
    Sn = (a * S + np.outer(k, delta)) // (1 << F)   # decay + rank-1 update, one floor per cell
    o = (qv @ Sn) // (1 << F)
    if check:
        for name, x in (('M', M), ('delta', delta), ('S', Sn)):
            if np.abs(x).max() >= BOUND:
                raise OverflowError(f'{name} out of signed 19-bit range: reject, never saturate')
    return M, delta, Sn, o

def float_step(S, tok):
    a, beta, k, v, qv = tok['fa'], tok['fbeta'], tok['fk'], tok['fv'], tok['fq']
    S = S * a
    delta = beta * (v - k @ S)
    S = S + np.outer(k, delta)
    return S, qv @ S

WARMUP = 64
def fixture(seed, F=12, T=4, dist='R1'):
    toks = gen_tokens(seed, dist, WARMUP + T, F)
    S = np.zeros((D, D), dtype=np.int64)
    for tok in toks[:WARMUP]: S = step(S, tok, F)[2]
    S0 = S.copy(); proved = toks[WARMUP:]; rec = []
    for tok in proved:
        M, delta, S, o = step(S, tok, F); rec.append((M, delta, S.copy(), o))
    return S0, proved, rec

def write_fixture(path, seed, F=12, T=4):
    S0, toks, rec = fixture(seed, F, T)
    arr = [np.array([T, D, F], dtype=np.int64), S0.reshape(-1)]
    for tok in toks:
        arr += [np.array([tok['a'], tok['beta']], dtype=np.int64), tok['k'], tok['v'], tok['q']]
    for M, delta, S, o in rec: arr += [M, delta, S.reshape(-1), o]
    np.concatenate(arr).astype('<i8').tofile(path)
    return dict(seed=seed, S0_max_abs=int(np.abs(S0).max()), S4_max_abs=int(np.abs(rec[-1][2]).max()),
                decays=[t['a'] for t in toks], betas=[t['beta'] for t in toks])

if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('--seed', type=int, required=True); ap.add_argument('--out', required=True)
    ap.add_argument('--dim', type=int, default=128, help='debug only; the M1 fixture is 128')
    a = ap.parse_args(); D = a.dim; print(write_fixture(a.out, a.seed))
