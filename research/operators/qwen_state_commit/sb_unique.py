#!/usr/bin/env python3
"""Registered runs of experiments/20261111-34-sb-unique-floor (PREREG there). Reference arithmetic, no proof.

For one SB chunk (sb_ref.chunk_sb arithmetic, recomputed here with every floor exposed) this script
lists every floor N -> (Q, r) of the chunk: decay table G, M, delta, o, S_out. For each floor it checks
(1) the honest witness is accepted by lowering L (sb_unique_lib.accepts), (2) the number of other
accepted witnesses under L's windows (sb_unique_lib.alternatives, exact), (3) the numerator bits
against the proved bound of L's admission. Controls: (a) M1b window |Q| < 2^23 on the M and o floors
must find second witnesses at GB = 18; (b) mutated witnesses must be rejected.
Usage: sb_unique.py --out <json> [--debug] (debug = R1 seed 99 only, not in the registered set)
"""
import argparse, json, pathlib, sys, time
import numpy as np
here = pathlib.Path(__file__).resolve().parent
root = here.parents[2]
sys.path.insert(0, str(here))
import sb_ref as B
import sb_unique_lib as U
R = B.R
F = U.F; DIM = 32; WARM = 64; TOK = 256

def admitted(S0, toks, D):
    NB = U.nb_bound(D); one = 1 << F
    ok = bool(np.abs(S0).max() < U.CONTRACT)
    for t in toks:
        ok &= 0 <= t['a'] <= one and 0 <= t['beta'] <= one and int(np.abs(t['v']).max()) < (1 << 31)
        ok &= int((t['k'].astype(object) ** 2).sum()) <= NB and int((t['q'].astype(object) ** 2).sum()) <= NB
    return bool(ok)

def floors(S0, toks, GB):
    """Every floor of one SB chunk as (kind, N, k). Same arithmetic as sb_ref.chunk_sb."""
    C = len(toks); one = 1 << F; g = 1 << GB; out = []
    G = [[0] * (C + 1) for _ in range(C + 1)]; G[0][0] = g
    for t in range(1, C + 1):
        G[t][t] = g
        for s in range(t):
            N = G[t - 1][s] * toks[t - 1]['a']; out.append(('G', N, F)); G[t][s] = N >> F
    S0o = S0.astype(object); K = [x['k'].astype(object) for x in toks]; Qv = [x['q'].astype(object) for x in toks]
    kq = 2 * F + GB; deltas = []
    for t in range(1, C + 1):
        tok = toks[t - 1]; k = K[t - 1]; q = Qv[t - 1]
        num = one * G[t][0] * k.dot(S0o)
        for s in range(1, t): num = num + G[t][s] * int(k.dot(K[s - 1])) * deltas[s - 1]
        M = [int(x) >> kq for x in num]
        out += [('M', int(x), kq) for x in num]
        dn = [(int(v) - m) * tok['beta'] for v, m in zip(tok['v'], M)]
        out += [('delta', x, F) for x in dn]
        delta = np.array([x >> F for x in dn], dtype=object); deltas.append(delta)
        onum = one * G[t][0] * q.dot(S0o)
        for s in range(1, t + 1): onum = onum + G[t][s] * int(q.dot(K[s - 1])) * deltas[s - 1]
        out += [('o', int(x), kq) for x in onum]
    Sn = one * G[C][0] * S0o
    for s in range(1, C + 1): Sn = Sn + G[C][s] * np.outer(K[s - 1], deltas[s - 1])
    out += [('S_out', int(x), F + GB) for x in Sn.reshape(-1)]
    Sout = np.array([[int(x) >> (F + GB) for x in row] for row in Sn], dtype=np.int64)
    # cross-check against sb_ref.chunk_sb (the #71 reference)
    _, _, _, Sref, _ = B.chunk_sb(S0, toks, F, GB)
    assert np.array_equal(Sout, Sref)
    return out, Sout

KINDS = ('G', 'M', 'delta', 'o', 'S_out')
def new_tally():
    return {k: dict(floors=0, honest_accepted=0, honest_outside_window=0, with_second=0, second_witnesses=0, max_bits=0) for k in KINDS}

def check_chunk(fl, GB, tally, ctrl=None, mut=None):
    """Floors are in dependency order (G, then per token M, delta, o, then S_out). At the first floor whose
    honest quotient leaves L's window the chunk is rejected: that floor is still checked (its operands are
    all in-window), later floors are not, because their numerators use a value no witness of L can commit."""
    for kind, N, k in fl:
        T = tally[kind]; T['floors'] += 1; T['max_bits'] = max(T['max_bits'], abs(N).bit_length())
        win = U.window(kind, GB)
        inside, (Q, r), acc = U.alternatives(N, k, win)
        if inside and U.accepts(N, k, Q, r, win): T['honest_accepted'] += 1
        if not inside: T['honest_outside_window'] += 1; tally.setdefault('_rejected_at', kind)
        others = [w for w in acc if w != (Q, r)]
        if others:
            T['with_second'] += 1; T['second_witnesses'] += len(others)
            T.setdefault('example', dict(N=N, k=k, honest=[Q, r], second=list(others[0])))
        if ctrl is not None and kind in ('M', 'o'):
            _, _, acc2 = U.alternatives(N, k, U.window_m1b())
            ctrl['floors'] += 1; ctrl['with_second'] += len([w for w in acc2 if w != (Q, r)]) > 0
        if mut is not None and inside:
            d = 1 << k
            for Q2, r2 in ((Q + 1, r - d), (Q - 1, r + d), (Q, r + 1), (Q + (1 << 22), r)):
                mut['tried'] += 1; mut['accepted'] += U.accepts(N, k, Q2, r2, win)
        if not inside: return False
    return True

def count_L(D, C, GB):
    """Committed values per head per token under L (counted, not measured), #71 convention:
    one count per committed value, a remainder of w bits is ceil(w / 12) keys. Compared with
    count_r2.per_head's formula at the same D (which uses delta_lo/hi and no quotient range limbs)."""
    import count_r2 as CR
    CR.D = D
    ks, km, items, extras = CR.per_head(GB, C)
    base = sum(items.values())
    L = dict(
        S_out_cells=D * D / C, S_out_remainder_keys=U.limbs(F + GB) * D * D / C,
        S_out_range_limbs=2 * D * D / C,
        decay_table_entries=(C + 1) / 2, decay_table_remainder_keys=(C + 1) / 2,
        decay_table_range_limbs=U.limbs(GB + 1) * (C + 1) / 2,
        gram_KK_QK=2 * C, P0_Q0=2 * D,
        M_delta_o=3 * D, remainder_keys_M=U.limbs(2 * F + GB) * D, remainder_keys_delta=D,
        remainder_keys_o=U.limbs(2 * F + GB) * D, quotient_range_limbs_M_delta_o=3 * 2 * D,
        norm_cells_k_q=2, norm_slack_range_limbs=2 * U.limbs(U.nb_bound(D).bit_length()))
    tot = sum(L.values())
    return dict(D=D, C=C, GB=GB, count_r2_formula_per_head_per_token=base, L_per_head_per_token=tot,
                extra_per_head_per_token=tot - base, L_items=L,
                note='counted, not measured; per V head; excludes committed operands k, q, v, a, beta and all sumcheck/lookup/commitment overhead, as count_r2 base formula does')

def run_set(GB, C, dists, seeds, tally, ctrl, mut, rows):
    for dist in dists:
        for seed in seeds:
            toks = R.gen_tokens(seed, dist, WARM + TOK, F)
            S = np.zeros((DIM, DIM), dtype=np.int64)
            for tok in toks[:WARM]: S = R.step(S, tok, F, check=False)[2]
            adm = admitted(S, toks[WARM:], DIM); rt = new_tally()
            for c in range(TOK // C):
                fl, S = floors(S, toks[WARM + c * C: WARM + (c + 1) * C], GB)
                check_chunk(fl, GB, rt, ctrl, mut)
            ok = all(rt[k]['honest_accepted'] == rt[k]['floors'] for k in KINDS)
            for k in KINDS:
                for f in ('floors', 'honest_accepted', 'honest_outside_window', 'with_second', 'second_witnesses'): tally[k][f] += rt[k][f]
                tally[k]['max_bits'] = max(tally[k]['max_bits'], rt[k]['max_bits'])
                if 'example' in rt[k]: tally[k].setdefault('example', rt[k]['example'])
            rows.append(dict(dist=dist, seed=seed, admitted=adm, honest_all_accepted=ok,
                             second=sum(rt[k]['with_second'] for k in KINDS), max_bits={k: rt[k]['max_bits'] for k in KINDS}))
            print(json.dumps(dict(GB=GB, C=C, **rows[-1])), flush=True)

def adversarial(GB, C, n, rng):
    """#71 edge inputs at D = 32 plus n random admitted chunks with operands at the edges of admission."""
    NB = U.nb_bound(DIM); one = 1 << F; e = int(np.sqrt(NB / DIM)); tally = new_tally(); cases = []
    def mk(S0, ks, qs, a, beta, v):
        return S0, [dict(a=a[i], beta=beta[i], k=ks[i], q=qs[i], v=v[i]) for i in range(C)]
    S1 = np.full((DIM, DIM), (1 << 18) - 1, dtype=np.int64); kh = np.zeros(DIM, dtype=np.int64); kh[0] = one
    qe = np.full(DIM, e, dtype=np.int64); vmax = np.full(DIM, (1 << 31) - 1, dtype=np.int64)
    cases.append(('edge1', mk(S1, [kh] * C, [qe] * C, [one] * C, [0] * C, [vmax] * C)))
    S2 = np.full((DIM, DIM), (1 << 16) - 1, dtype=np.int64)
    cases.append(('edge2', mk(S2, [qe] * C, [qe] * C, [one] * C, [0] * C, [vmax] * C)))
    for i in range(n):
        S0 = rng.choice([-(1 << 18) + 1, (1 << 18) - 1], size=(DIM, DIM)).astype(np.int64)
        ks = [rng.choice([-e, e], size=DIM).astype(np.int64) for _ in range(C)]
        qs = [rng.choice([-e, e], size=DIM).astype(np.int64) for _ in range(C)]
        a = [int(x) for x in rng.choice([0, one], size=C)]; b = [int(x) for x in rng.choice([0, one], size=C)]
        v = [rng.choice([-(1 << 31) + 1, (1 << 31) - 1], size=DIM).astype(np.int64) for _ in range(C)]
        cases.append((f'rand{i}', mk(S0, ks, qs, a, b, v)))
    rows = []
    for name, (S0, toks) in cases:
        assert admitted(S0, toks, DIM), name
        rt = new_tally()
        try: fl, _ = floors(S0, toks, GB)
        except AssertionError: raise
        check_chunk(fl, GB, rt)
        for k in KINDS:
            for f in ('floors', 'honest_accepted', 'honest_outside_window', 'with_second', 'second_witnesses'): tally[k][f] += rt[k][f]
            tally[k]['max_bits'] = max(tally[k]['max_bits'], rt[k]['max_bits'])
            if 'example' in rt[k]: tally[k].setdefault('example', rt[k]['example'])
        rows.append(dict(case=name, rejected_honest=any(rt[k]['honest_outside_window'] for k in KINDS),
                         second=sum(rt[k]['with_second'] for k in KINDS), max_bits=max(rt[k]['max_bits'] for k in KINDS)))
    return tally, rows

def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--out', required=True); ap.add_argument('--debug', action='store_true')
    ap.add_argument('--adv', type=int, default=200)
    a = ap.parse_args(); t0 = time.time()
    R.D = DIM  # token generator at D = 32 (PREREG); generator otherwise unchanged
    dists, seeds = (('R1',), (99,)) if a.debug else (('R1', 'R2', 'R3', 'R4'), range(1, 6))
    arms = []
    for GB in (12, 18):
        for C in (16, 64):
            tally = new_tally(); ctrl = dict(floors=0, with_second=0); mut = dict(tried=0, accepted=0); rows = []
            run_set(GB, C, dists, seeds, tally, ctrl, mut, rows)
            rng = np.random.default_rng(1111)
            adv_t, adv_rows = adversarial(GB, C, 2 if a.debug else a.adv, rng)
            pb = U.proved_bounds(DIM, C, GB)
            bounds = {k: dict(bound_bits=v[0].bit_length(), k=v[1], window_bits=19, fits_field=U.bound_ok(v[0], v[1], 19 if k != 'G' else GB + 1))
                      for k, v in pb.items()}
            honest_ok = sum(r['honest_all_accepted'] for r in rows)
            second = sum(tally[k]['with_second'] for k in KINDS) + sum(adv_t[k]['with_second'] for k in KINDS)
            verdict = 'PASS' if (second == 0 and all(b['fits_field'] for b in bounds.values()) and honest_ok == len(rows)) else 'FAIL'
            arms.append(dict(GB=GB, C=C, D=DIM, runs=len(rows), honest_runs_all_accepted=honest_ok, registered=tally,
                             adversarial=dict(n=len(adv_rows), tally=adv_t,
                                              honest_outside_window=sum(r['rejected_honest'] for r in adv_rows),
                                              max_bits=max(r['max_bits'] for r in adv_rows)),
                             proved_bounds=bounds, control_a_m1b_window=ctrl, control_b_mutations=mut,
                             floors_with_second_witness=second, count=count_L(DIM, C, GB), verdict=verdict,
                             run_bits={k: dict(median=float(np.median([r['max_bits'][k] for r in rows])),
                                               min=min(r['max_bits'][k] for r in rows), max=max(r['max_bits'][k] for r in rows)) for k in KINDS}))
            print(json.dumps(dict(GB=GB, C=C, verdict=verdict, second=second, ctrl=ctrl, mut=mut,
                                  bounds={k: (v['bound_bits'], v['fits_field']) for k, v in bounds.items()})), flush=True)
    out = dict(note='reference arithmetic and a relation checker, no proof, no backend; volumes are counted, not measured',
               experiment='20261111-34-sb-unique-floor', debug=a.debug, field_p=U.P, F=F, D=DIM, warmup=WARM, tokens=TOK,
               arms=arms, seconds=round(time.time() - t0, 1))
    p = pathlib.Path(a.out); p.parent.mkdir(parents=True, exist_ok=True); p.write_text(json.dumps(out, indent=1, default=int) + '\n')
    print('wrote', p.name, out['seconds'], 's')

if __name__ == '__main__': main()
