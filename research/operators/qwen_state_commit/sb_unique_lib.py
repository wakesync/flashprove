#!/usr/bin/env python3
"""Lowering L for the SB floor steps (PREREG experiments/20261111-34-sb-unique-floor): relation
checker, exact second-witness enumerator, proved numerator bounds. Reference arithmetic, no proof.

Every SB floor is Q = floor(N / 2^k). Under L the prover commits Q and r; the checker accepts iff
  2^k Q + r = N (mod p), 0 <= r < 2^k exactly (12-bit limbs), lo <= Q < hi exactly (limbs of Q - lo),
with N recomputed by the checker from the committed operands. Windows (lo, hi):
  M, o, S_out, delta: [-2^18, 2^18)  (contract, reference.BOUND)   G (decay table): [0, 2^GB + 1)
The enumerator lists every (Q', r') != (Q, r) inside the windows with 2^k (Q' - Q) + (r' - r) = m p,
for every m the windows allow (exact, as sb_alias.shifts).
"""
import math
P = 2 ** 64 - 2 ** 32 + 1
F = 12
CONTRACT = 1 << 18
KEY = 12

def window(kind, GB):
    if kind == 'G': return (0, (1 << GB) + 1)
    return (-CONTRACT, CONTRACT)

def window_m1b():
    """#71's M1b-style window: range cell proved only |x| < 2^23 (control a)."""
    return (-(1 << 23) + 1, 1 << 23)

def accepts(N, k, Q, r, win):
    lo, hi = win
    return lo <= Q < hi and 0 <= r < (1 << k) and ((1 << k) * Q + r - N) % P == 0

def alternatives(N, k, win):
    """All accepted (Q', r') for the field residue of N under window win, exact.
    Returns (honest_in_window, list_of_accepted_pairs)."""
    div = 1 << k; lo, hi = win
    Q0 = N // div; r0 = N - Q0 * div
    # any accepted (Q, r) has div Q + r = N + m p with div lo <= N + m p < div hi
    m_lo = -((N - div * lo) // P) - 1; m_hi = (div * hi - N) // P + 1
    out = []
    for m in range(m_lo, m_hi + 1):
        n2 = N + m * P; Q = n2 // div; r = n2 - Q * div
        if lo <= Q < hi:
            assert accepts(N, k, Q, r, win)
            out.append((Q, r))
    return (lo <= Q0 < hi), (Q0, r0), sorted(set(out))

def isqrt_ceil(x):
    s = math.isqrt(x); return s if s * s == x else s + 1

def nb_bound(D):
    """Admitted squared norm bound NB = 2^(2F) + 2^(F+3) (PREREG)."""
    return (1 << (2 * F)) + (1 << (F + 3))

def proved_bounds(D, C, GB):
    """Exact integer upper bounds on |N| implied by L's admission, per floor kind, and k per kind."""
    NB = nb_bound(D); sn = isqrt_ceil(NB); sd = isqrt_ceil(D); S = CONTRACT; g = 1 << GB; one = 1 << F
    colbound = sn * sd * S                      # |k . S_col| <= ||k|| ||S_col|| <= sqrt(NB) sqrt(D) 2^18
    b = dict(
        M=(one * g * colbound + (C - 1) * g * NB * S, 2 * F + GB),
        o=(one * g * colbound + C * g * NB * S, 2 * F + GB),
        S_out=(one * g * S + C * g * sn * S, F + GB),
        delta=(((1 << 31) + S) * one, F),
        G=(g * one, F))
    return b

def bound_ok(Nmax, k, wbits=19):
    return Nmax + (1 << (k + wbits)) < P

def limbs(bits):
    return math.ceil(bits / KEY)
