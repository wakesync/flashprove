#!/usr/bin/env python3
"""SB floors in the Goldilocks field: second solutions under an M1b-style range check, and edge traces.

Reference arithmetic only. There is no SB proof, so nothing here is a forged proof. The script asks a
narrower question that both reviews of PR #71 raised: IF the SB floors were lowered the way M1b lowers
its floors (the quotient is a range cell, for which the RNG range check proves only |x| < 2^23 although
honest values are below 2^18; the remainder is exact in [0, divisor); the relation
divisor * quotient + remainder = numerator is checked in the field, p = 2^64 - 2^32 + 1), does the
relation pin the quotient?

Part 1, second solutions. For a divisor 2^k, a second pair (M + d, r + e) satisfies the same field
relation iff 2^k d + e = 0 (mod p). With |d| < 2^24 and |e| < 2^k that means 2^k d + e = m p for a small
integer m, so all candidates are enumerated exactly (function shifts). They are then tested on the
honest numerators of real SB tokens (sb_ref.chunk_sb arithmetic, D = 128, the first chunk of 64 tokens
after a 64-token warm-up), for the M floor and the o floor (divisor 2^(2F+GB)) and the S_out floor
(divisor 2^(F+GB)), at GB = 12 (registered), 15 and 18.

Part 2, edge traces. Complete SB chunks (sb_ref.chunk_sb, exact integers) on constant inputs that
pass the public admission of chunk.cpp (|k|, |q| entries <= 2^F, a, beta in [0, 2^F], |v| < 2^31,
|S_in| < 2^18) and whose quotients stay inside the stated contracts. The numerator bit lengths are
compared with 62 (the registered no-wrap line; p / 2 is about 2^63). The two inputs are the ones the
astra review of PR #71 describes; the numbers below are this script's own.

Part 3, interval boxes. Upper bounds of the numerators when every admitted value sits at the edge of
its range at once. These are bounds, not traces: no claim that one input reaches them.

Writes experiments/20261109-34-qwen-state-commit/runs/sb-alias-gb18.json.
"""
import json, pathlib, sys, time
import numpy as np
here = pathlib.Path(__file__).resolve().parent
root = here.parents[2]
sys.path.insert(0, str(here))
import sb_ref as B
R = B.R
P = 2 ** 64 - 2 ** 32 + 1
F = 12; D = R.D
RNG_PROVED = 1 << 23      # what the M1b RNG range check proves for a range cell
CONTRACT = 1 << 18        # the honest contract of a range cell
VBOUND = 1 << 31          # public admission of v and o in chunk.cpp

def shifts(k, window=RNG_PROVED):
    """All (d, e), d != 0, with 2^k d + e = 0 (mod p), |d| < 2 * window, |e| < 2^k. Exact."""
    div = 1 << k; out = []
    m_max = (div * 2 * window + div) // P + 1
    for m in range(-m_max, m_max + 1):
        if m == 0: continue
        for d in {(m * P) // div, (m * P) // div + 1}:
            e = m * P - div * d            # then div * d + e = m p = 0 (mod p): the pair (M + d, r + e) satisfies the same relation
            if d != 0 and abs(d) < 2 * window and abs(e) < div: out.append((d, e))
    return sorted(set(out))

def numerators(S0, toks, GB):
    """Numerators of sb_ref.chunk_sb, recomputed here; checked against chunk_sb's quotients by the caller."""
    C = len(toks); one = 1 << F; gone = 1 << GB
    G = [[0] * (C + 1) for _ in range(C + 1)]; G[0][0] = gone
    for t in range(1, C + 1):
        G[t][t] = gone
        for s in range(t): G[t][s] = (G[t - 1][s] * toks[t - 1]['a']) >> F
    S0o = S0.astype(object); K = [x['k'].astype(object) for x in toks]; Q = [x['q'].astype(object) for x in toks]
    dk = 1 << (2 * F + GB); deltas = []; Mn = []; On = []
    for t in range(1, C + 1):
        tok = toks[t - 1]; k = K[t - 1]; q = Q[t - 1]
        num = one * G[t][0] * k.dot(S0o)
        for s in range(1, t): num = num + G[t][s] * int(k.dot(K[s - 1])) * deltas[s - 1]
        M = np.array([x // dk for x in num], dtype=object)
        delta = ((tok['v'].astype(object) - M) * tok['beta']) // one; deltas.append(delta)
        onum = one * G[t][0] * q.dot(S0o)
        for s in range(1, t + 1): onum = onum + G[t][s] * int(q.dot(K[s - 1])) * deltas[s - 1]
        Mn.append([int(x) for x in num]); On.append([int(x) for x in onum])
    Sn = one * G[C][0] * S0o
    for s in range(1, C + 1): Sn = Sn + G[C][s] * np.outer(K[s - 1], deltas[s - 1])
    return Mn, On, [int(x) for x in Sn.reshape(-1)], deltas

def second_solutions(nums, k, sh, window=RNG_PROVED):
    """For every honest numerator: the honest (M, r) and how many shifted pairs (M', r') satisfy the same
    field relation with |M'| < window and r' in [0, 2^k). Every reported pair is verified in the field."""
    div = 1 << k; with_alias = 0; total = 0; n_pairs = 0; ex = None; max_alt = 0; honest_max = 0
    for n in nums:
        M = n // div; r = n - M * div; total += 1; honest_max = max(honest_max, abs(M)); found = 0
        for d, e in sh:
            Mp = M + d; rp = r + e
            if abs(Mp) < window and 0 <= rp < div:
                assert (div * Mp + rp - n) % P == 0 and Mp != M
                found += 1; max_alt = max(max_alt, abs(Mp))
                if ex is None: ex = dict(numerator=n, honest_quotient=M, honest_remainder=r, second_quotient=Mp, second_remainder=rp, quotient_shift=d, remainder_shift=e)
        with_alias += found > 0; n_pairs += found
    return dict(floors=total, with_second_solution=with_alias, second_solutions=n_pairs, honest_quotient_max_abs=honest_max,
                second_quotient_max_abs=max_alt, example=ex)

def part1():
    out = []
    for dist, seed in (('R1', 1), ('R3', 3)):
        toks = R.gen_tokens(seed, dist, 128, F)
        S = np.zeros((D, D), dtype=np.int64)
        for tok in toks[:64]: S = R.step(S, tok, F, check=False)[2]
        ch = toks[64:128]
        for GB in (12, 15, 18):
            Ms, ds, os_, Sout, nb = B.chunk_sb(S, ch, F, GB)
            Mn, On, Sn, deltas = numerators(S, ch, GB)
            kq = 2 * F + GB; ks = F + GB
            # the recomputed numerators are sb_ref's: their floors equal chunk_sb's outputs
            assert all(Mn[t][j] // (1 << kq) == int(Ms[t][j]) and On[t][j] // (1 << kq) == int(os_[t][j]) for t in range(64) for j in range(D))
            assert [x // (1 << ks) for x in Sn] == [int(x) for x in Sout.reshape(-1)]
            shq = shifts(kq); shs = shifts(ks)
            row = dict(dist=dist, seed=seed, GB=GB, C=64, tokens=64, channels=D,
                       M_floor=dict(divisor_bits=kq, shifts=[dict(quotient_shift=d, remainder_shift=e) for d, e in shq], **second_solutions([x for t in Mn for x in t], kq, shq)),
                       o_floor=dict(divisor_bits=kq, note='o taken as a range cell like M; if o is admitted up to 2^31 as in chunk.cpp the window is wider', **second_solutions([x for t in On for x in t], kq, shq)),
                       S_out_floor=dict(divisor_bits=ks, shifts=len(shs), **second_solutions(Sn, ks, shs)))
            # what a second M does downstream, on the example cell: delta moves, and stays inside its two-limb contract
            ex = row['M_floor']['example']
            if ex:
                idx = [x for t in Mn for x in t].index(ex['numerator']); t, j = divmod(idx, D); tok = ch[t]
                d0 = ((int(tok['v'][j]) - ex['honest_quotient']) * tok['beta']) // (1 << F); d1 = ((int(tok['v'][j]) - ex['second_quotient']) * tok['beta']) // (1 << F)
                ex.update(token=t, channel=j, v=int(tok['v'][j]), beta=tok['beta'], honest_delta=d0, second_delta=d1,
                          second_delta_fits_two_limbs=abs(d1 // CONTRACT) < CONTRACT,
                          second_delta_limbs_inside_rng_bound=abs(d1 // CONTRACT) < RNG_PROVED)
            out.append(row)
            print(json.dumps(dict(dist=dist, seed=seed, GB=GB, M=f"{row['M_floor']['with_second_solution']}/{row['M_floor']['floors']}",
                                  o=f"{row['o_floor']['with_second_solution']}/{row['o_floor']['floors']}",
                                  S_out=f"{row['S_out_floor']['with_second_solution']}/{row['S_out_floor']['floors']}")), flush=True)
    return out

def admissible(S, tok, Ms, os_, Sout):
    one = 1 << F
    return bool(np.abs(S).max() < CONTRACT and 0 <= tok['a'] <= one and 0 <= tok['beta'] <= one and np.abs(tok['k']).max() <= one
                and np.abs(tok['q']).max() <= one and np.abs(tok['v']).max() < VBOUND and max(int(np.abs(o).max()) for o in os_) < VBOUND
                and np.abs(Sout).max() < CONTRACT)

def part2():
    rows = []
    for GB in (12, 18):
        for C in (1, 16, 64):
            for case in ('S at the 2^18 edge, one-hot k, all-ones q', 'S = 2^16 - 1, all-ones k and q'):
                s = (1 << 18) - 1 if case.startswith('S at') else (1 << 16) - 1
                S = np.full((D, D), s, dtype=np.int64); k = np.zeros(D, dtype=np.int64)
                if case.startswith('S at'): k[0] = 1 << F
                else: k[:] = 1 << F
                tok = dict(a=1 << F, beta=0, k=k, v=np.full(D, VBOUND - 1, dtype=np.int64), q=np.full(D, 1 << F, dtype=np.int64))
                Ms, ds, os_, Sout, nb = B.chunk_sb(S, [tok] * C, F, GB)
                mx = lambda a: max(int(np.abs(x).max()) for x in a)
                row = dict(case=case, GB=GB, C=C, S_in_max_abs=s, max_abs=dict(S_out=int(np.abs(Sout).max()), M=mx(Ms), delta=mx(ds), o=mx(os_)),
                           numerator_bits=nb, public_admission_passes=admissible(S, tok, Ms, os_, Sout),
                           M_inside_contract_2_18=mx(Ms) < CONTRACT, M_inside_rng_bound_2_23=mx(Ms) < RNG_PROVED,
                           max_numerator_bits=max(nb['M'], nb['o'], nb['S']), exceeds_62_bits=max(nb['M'], nb['o'], nb['S']) > 62)
                rows.append(row); print(json.dumps({k2: v for k2, v in row.items() if k2 not in ('max_abs',)}), flush=True)
    return rows

def part3():
    out = []; C = 64
    for GB in (12, 18):
        for limb_bits, label in ((18, 'contract: |S_in|, delta limbs < 2^18'), (23, 'RNG proved bound: |S_in|, delta limbs < 2^23')):
            s = (1 << limb_bits) - 1; dl = (1 << 18) * s + s; g = 1 << GB; k = 1 << F
            p0 = D * s * k; gram = D * k * k
            nm = k * g * p0 + (C - 1) * g * gram * dl; no = k * g * p0 + C * g * gram * dl; ns = k * g * s + C * g * k * dl
            out.append(dict(GB=GB, C=C, box=label, M_numerator_bits=nm.bit_length(), o_numerator_bits=no.bit_length(), S_out_numerator_bits=ns.bit_length(),
                            note='interval bound with every admitted value at the edge of its range at once; not a trace'))
    return out

def main():
    t0 = time.time()
    p1 = part1(); p2 = part2(); p3 = part3()
    out = dict(note='reference arithmetic, no proof; second solutions are of the field relation divisor * quotient + remainder = numerator under an M1b-style range check (quotient proved only |x| < 2^23, remainder exact), which is an assumption about a lowering that does not exist',
               field_p=P, F=F, D=D, rng_proved_bound=RNG_PROVED, contract_bound=CONTRACT,
               second_solutions=p1, edge_traces=p2, interval_boxes=p3, seconds=round(time.time() - t0, 1))
    p = root / 'experiments/20261109-34-qwen-state-commit/runs/sb-alias-gb18.json'
    p.write_text(json.dumps(out, indent=1) + '\n')
    print('wrote', p.relative_to(root), out['seconds'], 's')

if __name__ == '__main__': main()
