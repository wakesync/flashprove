#!/usr/bin/env python3
"""Design-level regression for the derived-value admission rule of the M2 design
(experiments/20261105-32-qwen-deltanet-m2-design/DESIGN.md sections 3.1, 4.4, 4.5 and 7).

What this is. The third review of PR #66 found that DESIGN.md section 4.4 relied on |cg| < 2^24 for
its no-wraparound argument, while nothing made the verifier check the cg it recomputes. With a large
verifier-fixed gain the y floor relation  cg w - 2^F y - r = 0  holds in the Goldilocks field for a
y that is not the integer floor. The review listed 22 such cases. This script:

  A  rebuilds those 22 cases from the design equations alone (plain Python integers, written from
     DESIGN.md section 4.4, not from the review's code), checks every witness range, and shows that
     the rule "reject at derive unless |cg| < 2^24" turns each one into a reject;
  B  checks the boundary: |cg| = 2^24 - 1 is admitted and the floor is then unique, |cg| = 2^24 is
     rejected, on both signs;
  C  checks the no-wrap bound the rule gives, at the extremes and on a fixed random sample;
  D  does the same for the derived v (the audit of DESIGN.md section 3.1 found the same kind of gap
     there: |v| < 2^31 was assumed for a value the verifier recomputes and did not check);
  E  computes the no-wrap ledger of DESIGN.md section 4.4.2: the largest integer magnitude of every
     closed identity under the admitted bounds, and for each derived value the largest bound that
     would still keep every identity below p;
  F  samples the argument that the derived k and q are in class for every input;
  G  finds, over every in-class z, the largest |cg| at gains 1, 1.41, 1.4143 and 2 (about 10 s).

What this is not. No proof is built or verified here. The #66 prototype (admit_proto.cpp) works on
the M1b statement, which has no norm stage and no recompute stage, so there is no C++ guard to
test. These are checks of the design contract: "is there a witness that satisfies every listed
relation and range for a wrong public value". The M2 build must port them to its verifier
(DESIGN.md section 7).

Usage: norm_alias_regression.py [--json out.json] [--check expected.json]
Exit 0 only if every expectation holds (and, with --check, the output equals the expected file,
float fields aside).
"""
import argparse, json, math, pathlib, random, sys

P = 2 ** 64 - 2 ** 32 + 1        # Goldilocks
D, F = 128, 12
ONE = 1 << F
EPS_NORM = 2147                  # round(128 * 1e-6 * 2^24), DESIGN.md 4.4
EPS_L2 = 17
SQRT_D_Q12 = 46341               # round(sqrt(128) * 2^12)
RNG_PROVED = 1 << 23             # what RNG proves of a range cell (soundness side)
CELL = 1 << 18                   # honest contract of a range cell
Y_CLASS = 1 << 31                # public y: |y| < 2^31 (DESIGN.md section 2)
CG_BOUND = 1 << 24               # derived cg: |cg| < 2^24 (DESIGN.md section 3.1)
V_BOUND = 1 << 31                # derived v: |v| < 2^31 (DESIGN.md section 3.1)


# ---- DESIGN.md section 4.4, as written -----------------------------------------------------------
def norm_witness(o):
    """sigma, e1, e2, Rc, rr, gap, w_j and the w remainders, from the witness o (integers)."""
    Vx = sum(x * x for x in o)
    sigma = math.isqrt(Vx + EPS_NORM)
    e1 = Vx + EPS_NORM - sigma * sigma
    e2 = sigma * sigma + 2 * sigma - Vx - EPS_NORM
    Rc = (1 << 36) // sigma
    rr = (1 << 36) - Rc * sigma
    gap = sigma - 1 - rr
    w = [(x * Rc) >> 24 for x in o]                 # floor (Python >> floors negatives)
    rw = [x * Rc - (wj << 24) for x, wj in zip(o, w)]
    return dict(Vx=Vx, sigma=sigma, e1=e1, e2=e2, Rc=Rc, rr=rr, gap=gap, w=w, rw=rw)

def witness_ranges_hold(o, nw):
    """Every range the design lists for the norm witness: exact limbs and the range cells."""
    return (all(abs(x) < CELL for x in o) and 0 <= nw['sigma'] < 1 << 24 and 0 <= nw['e1'] < 1 << 24 and 0 <= nw['e2'] < 1 << 24
            and 0 <= nw['Rc'] < 1 << 36 and 0 <= nw['rr'] < 1 << 24 and 0 <= nw['gap'] < 1 << 24
            and all(0 <= r < 1 << 24 for r in nw['rw']) and all(abs(x) < CELL for x in nw['w']))

def floor_solution_mod_p(coef, cell, shift, bound):
    """The (q, r) with |q| < bound, 0 <= r < 2^shift and  coef * cell - 2^shift q - r = 0  (mod p),
    or None. n = 2^shift q + r runs over an interval shorter than p, so there is at most one."""
    lo, hi = -(bound - 1) << shift, ((bound - 1) << shift) + (1 << shift) - 1
    res = (coef * cell) % P
    for n in (res, res - P):
        if lo <= n <= hi:
            return n >> shift, n - ((n >> shift) << shift)
    return None

def admit_cg(cg):
    """THE RULE (DESIGN.md 3.1): every recomputed cg_j is checked before it becomes a coefficient."""
    return all(abs(c) < CG_BOUND for c in cg)

def admit_v(v):
    return all(abs(x) < V_BOUND for x in v)

def norm_verdict(o, cg, y, guard=True):
    """The design contract for the y floor, as an ideal proof system would decide it: 'derive' if
    the guard refuses a coefficient; else 'accept' iff a witness satisfies every relation and range
    for the public y (the rest of the norm witness is pinned by o); else 'relation'."""
    if guard and not admit_cg(cg):
        return 'derive'
    nw = norm_witness(o)
    for cgj, wj, yj in zip(cg, nw['w'], y):
        s = floor_solution_mod_p(cgj, wj, F, Y_CLASS)
        if s is None or s[0] != yj:
            return 'relation'
    return 'accept'


# ---- the public-only stage, enough of it to show the alias statements are complete statements ----
def silu_int(c):
    x = c / ONE
    return int(round(ONE * (x / (1.0 + math.exp(-x)))))  # float at the table point, as head_reference.py

def l2n_int(u, extra=None):
    s = math.isqrt(sum(x * x for x in u) + EPS_L2); num = [x * ONE for x in u]
    if extra:
        s *= extra; num = [x * 4096 for x in num]
    return [(2 * n + s) // (2 * s) for n in num]

def gates_int(ar, br, A=1.0, dt_bias=0.0):
    x = ar / ONE + dt_bias
    softplus = math.log1p(math.exp(x)) if x < 30 else x
    return int(round(ONE * math.exp(-A * softplus))), int(round(ONE / (1.0 + math.exp(-br / ONE))))

def recurrence_o(S00, q0, a, beta, T=16):
    """The staged-floor recurrence (M1 README) on the sparse statement used by the cases: k = v = 0,
    q = (q0, 0, ..), S0 = S00 at cell (0, 0) and 0 elsewhere. Returns o_t[0] for every token and
    whether the state stayed constant."""
    S = S00; out = []; const = True
    for _ in range(T):
        Pj = 0                                  # k . S = 0
        M = (a * Pj) >> (2 * F)
        delta = ((0 - M) * beta) >> F
        Sn = (a * S + 0 * delta) >> F
        const &= Sn == S00; S = Sn
        out.append((q0 * S) >> F)
    return out, const

def cg_from_gain(gain, z):
    """cg = round(2^F gain sqrt(128) SiLU(z)), float64, the order of operations of head_reference.py."""
    x = z / ONE
    return int(round(ONE * gain * math.sqrt(D) * x / (1.0 + math.exp(-x))))

def gain_for(cg, z):
    g = cg / (ONE * math.sqrt(D) * (z / ONE) / (1.0 + math.exp(-(z / ONE))))
    for step in range(0, 9):                    # the float product may land one ulp off: nudge
        for cand in ([g] if step == 0 else [nudge(g, step), nudge(g, -step)]):
            if cg_from_gain(cand, z) == cg:
                return cand
    return None

def nudge(g, k):
    for _ in range(abs(k)):
        g = math.nextafter(g, math.inf if k > 0 else -math.inf)
    return g


# ---- A: the 22 large-gain aliases ---------------------------------------------------------------
def part_a():
    rows = []
    xq = [4096] + [0] * (D - 1)
    qh = l2n_int([silu_int(x) for x in xq], SQRT_D_Q12)
    a, beta = gates_int(-(2 ** 20 - 1), -(2 ** 20 - 1))
    for ov in (4096, 8192):
        S00 = (ov * 4096 + qh[0] - 1) // qh[0]
        o_seq, const = recurrence_o(S00, qh[0], a, beta)
        o = [ov] + [0] * (D - 1)
        nw = norm_witness(o)
        for e in range(52, 63):
            cgv = 1 << e
            gain = gain_for(cgv, 4096)
            cg = [cgv] + [0] * (D - 1)          # z = (4096, 0, ..): SiLU(0) = 0, so cg_j = 0 for j > 0
            true_y = (cgv * nw['w'][0]) >> F
            alias = floor_solution_mod_p(cgv, nw['w'][0], F, Y_CLASS)
            fake_y = [alias[0]] + [0] * (D - 1) if alias else None
            row = dict(
                o0=ov, cg=cgv, cg_log2=e, gain=gain, gain_reproduces_cg=gain is not None,
                compatible=dict(S0_00=S00, q0=qh[0], a=a, beta=beta, T=16, o_every_token=o_seq == [ov] * 16, state_constant=const),
                sigma=nw['sigma'], e1=nw['e1'], e2=nw['e2'], Rc=nw['Rc'], rr=nw['rr'], gap=nw['gap'], w0=nw['w'][0], rw0=nw['rw'][0],
                witness_ranges_hold=witness_ranges_hold(o, nw),
                true_y=true_y, true_y_in_class=abs(true_y) < Y_CLASS,
                alias_y=alias[0] if alias else None, alias_r=alias[1] if alias else None,
                field_relation_holds=alias is not None and (cgv * nw['w'][0] - ONE * alias[0] - alias[1]) % P == 0,
                integer_relation_holds=alias is not None and cgv * nw['w'][0] == ONE * alias[0] + alias[1],
                verdict_without_rule=norm_verdict(o, cg, fake_y, guard=False) if alias else None,
                verdict_with_rule=norm_verdict(o, cg, fake_y, guard=True) if alias else None)
            row['is_alias'] = bool(row['field_relation_holds'] and not row['integer_relation_holds'] and row['witness_ranges_hold']
                                   and row['alias_y'] != true_y and row['verdict_without_rule'] == 'accept')
            row['as_expected'] = bool(row['is_alias'] and row['verdict_with_rule'] == 'derive' and row['gain_reproduces_cg']
                                      and row['compatible']['o_every_token'] and row['compatible']['state_constant']
                                      and (a, beta, qh[0]) == (4096, 0, 362))
            rows.append(row)
    return rows


# ---- B: the boundary ------------------------------------------------------------------------------
def lcg_o(seed, amp):
    st = seed; out = []
    for _ in range(D):
        st = (st * 6364136223846793005 + 1442695040888963407) % 2 ** 64
        out.append((st >> 33) % (2 * amp + 1) - amp)
    return out

def part_b():
    rows = []
    o = lcg_o(66, 6000)
    nw = norm_witness(o)
    assert witness_ranges_hold(o, nw)
    for name, cgv, want_admit in (('2^24 - 1', CG_BOUND - 1, True), ('-(2^24 - 1)', -(CG_BOUND - 1), True), ('2^24', CG_BOUND, False), ('-2^24', -CG_BOUND, False)):
        for where in ('every channel', 'channel 0 only, others 4096'):
            cg = [cgv] * D if where == 'every channel' else [cgv] + [4096] * (D - 1)
            y = [(c * wj) >> F for c, wj in zip(cg, nw['w'])]
            y_bad = [y[0] + 1] + y[1:]
            got = norm_verdict(o, cg, y)
            got_bad = norm_verdict(o, cg, y_bad)
            # with the rule's bound, the mod-p solution in the class is the integer floor, per channel
            unique = all(floor_solution_mod_p(c, wj, F, Y_CLASS) == ((c * wj) >> F, c * wj - (((c * wj) >> F) << F)) for c, wj in zip(cg, nw['w']))
            rows.append(dict(cg=name, where=where, honest_y=got, honest_y_plus_1_at_channel_0=got_bad, floor_unique_mod_p=unique,
                             max_abs_y=max(abs(v) for v in y),
                             as_expected=(got == 'accept' and got_bad == 'relation' and unique) if want_admit else (got == 'derive' and got_bad == 'derive')))
    return rows


# ---- C: the no-wrap bound under the rule --------------------------------------------------------
def part_c():
    worst = (CG_BOUND - 1) * (RNG_PROVED - 1) + ONE * (Y_CLASS - 1) + (ONE - 1)
    rnd = random.Random(66); bad = 0; n = 200000
    for i in range(n):
        if i < 8:   # the corners
            cg = (CG_BOUND - 1) * (1 if i & 1 else -1); w = (RNG_PROVED - 1) * (1 if i & 2 else -1)
        else:
            cg = rnd.randint(-(CG_BOUND - 1), CG_BOUND - 1); w = rnd.randint(-(RNG_PROVED - 1), RNG_PROVED - 1)
        s = floor_solution_mod_p(cg, w, F, Y_CLASS)
        n_true = cg * w
        want = (n_true >> F, n_true - ((n_true >> F) << F)) if abs(n_true >> F) < Y_CLASS else None
        bad += s != want
    return dict(largest_relation_magnitude=worst, log2=round(math.log2(worst), 4), below_p=worst < P, below_2_48=worst < 1 << 48,
                samples=n, sample_seed=66, samples_where_mod_p_solution_differs_from_integer_floor=bad, as_expected=worst < P and bad == 0)


# ---- D: the same audit for the derived v ------------------------------------------------------
DELTA_BOUND = (RNG_PROVED - 1) * CELL + RNG_PROVED   # |delta| = |2^18 hi + lo| with |hi|, |lo| < 2^23

def part_d():
    """The delta floor of the recurrence:  2^F delta + r - (v - M) beta = 0, r in [0, 2^F), delta two
    RNG limbs. v is a derived value in M2 (SiLU of the conv output). M1b's no-wrap argument used
    |v| < 2^31, which M1b checked at decode because v was a statement word there. Shown here on one
    relation only (M = 0, beta = 2^F): this is an alias of the delta floor, not a whole statement.
    A derived v this large needs a huge verifier-fixed conv tap AND a SiLU that does not clamp."""
    rows = []; beta, M = ONE, 0
    for e in list(range(52, 63)):
        v = 1 << e
        true_delta = ((v - M) * beta) >> F
        s = floor_solution_mod_p(beta, v - M, F, DELTA_BOUND)
        alias = s is not None and s[0] != true_delta
        rows.append(dict(v_log2=e, v=v, true_delta=true_delta, true_delta_fits_limbs=abs(true_delta) < DELTA_BOUND,
                         alias_delta=s[0] if s else None, alias_r=s[1] if s else None, is_alias=alias,
                         verdict_with_rule='derive' if not admit_v([v]) else 'relation', as_expected=alias and not admit_v([v])))
    for name, v, want_admit in (('2^31 - 1', V_BOUND - 1, True), ('-(2^31 - 1)', -(V_BOUND - 1), True), ('2^31', V_BOUND, False), ('-2^31', -V_BOUND, False)):
        worst_M = RNG_PROVED - 1 if v < 0 else -(RNG_PROVED - 1)   # the hostile M that makes |v - M| largest
        n = (v - worst_M) * beta
        s = floor_solution_mod_p(beta, v - worst_M, F, DELTA_BOUND)
        unique = s == (n >> F, n - ((n >> F) << F))
        rows.append(dict(v=name, admitted=admit_v([v]), floor_unique_mod_p_at_worst_M=unique,
                         as_expected=(admit_v([v]) and unique) if want_admit else not admit_v([v])))
    worst = ONE * DELTA_BOUND + (ONE - 1) + (V_BOUND - 1 + RNG_PROVED - 1) * ONE
    return dict(rows=rows, largest_relation_magnitude_under_rule=worst, log2=round(math.log2(worst), 4), below_p=worst < P)


# ---- E: the no-wrap ledger and what each derived value's bound has to be ------------------------
CLASS = dict(cell=RNG_PROVED - 1, k=ONE, q=ONE, a=ONE, beta=ONE, v=V_BOUND - 1, cg=CG_BOUND - 1, y=Y_CLASS - 1, s0=CELL - 1)

def ledger(b):
    """Largest integer magnitude of every closed identity of the M2 lowering (DESIGN.md 4.4.2), with
    every range cell at what RNG proves (2^23 - 1), every exact piece at its exact maximum and every
    public or derived value at the bound b[...]. An identity that holds mod p and whose magnitude is
    below p holds over the integers."""
    c = b['cell']; delta = CELL * c + c; r12, r24 = ONE - 1, (1 << 24) - 1; sig = (1 << 24) - 1; rc = (1 << 36) - 1
    return {
        'I1 M floor: 2^2F M + r - a sum_i S_i k_i': (1 << 24) * c + r24 + b['a'] * D * c * b['k'],
        'I2 delta floor: 2^F delta + r - (v - M) beta': ONE * delta + r12 + (b['v'] + c) * b['beta'],
        'I3 state floor: 2^F S\' + r - a S - k_i delta_j': ONE * c + r12 + b['a'] * c + b['k'] * delta,
        'I4 output floor: 2^F o + r - sum_i S\'_i q_i': ONE * c + r12 + D * c * b['q'],
        'I5 state ends: cell - S0, cell - S_T': c + b['s0'],
        'N1 e1: sum o^2 + eps\' - sigma^2 - e1': D * c * c + EPS_NORM + sig * sig + r24,
        'N2 e2: sigma^2 + 2 sigma - sum o^2 - eps\' - e2': sig * sig + 2 * sig + D * c * c + EPS_NORM + r24,
        'N3 rr: Rc sigma + rr - 2^36': rc * sig + r24 + (1 << 36),
        'N4 gap: sigma - 1 - rr - gap': sig + 1 + r24 + r24,
        'N5 w floor: 2^24 w + r - o Rc': (1 << 24) * c + r24 + c * rc,
        'N6 y floor: cg w - 2^F y - r': b['cg'] * c + ONE * b['y'] + r12,
    }

def part_e():
    led = ledger(CLASS)
    rows = [dict(identity=k, max_magnitude=v, log2=round(math.log2(v), 3), below_p=v < P) for k, v in led.items()]
    need = {}
    for name in ('k', 'q', 'a', 'beta', 'v', 'cg'):
        lo, hi = CLASS[name], 1 << 70                      # largest bound that still keeps every identity below p
        while lo < hi:
            mid = (lo + hi + 1) // 2
            if all(v < P for v in ledger(dict(CLASS, **{name: mid})).values()): lo = mid
            else: hi = mid - 1
        need[name] = dict(class_max=CLASS[name], class_max_log2=round(math.log2(CLASS[name]), 3), largest_bound_without_wrap=lo,
                          largest_bound_without_wrap_log2=round(math.log2(lo), 3), slack_bits=round(math.log2(lo) - math.log2(CLASS[name]), 2))
    return dict(identities=rows, all_below_p=all(r['below_p'] for r in rows), largest=max(rows, key=lambda r: r['max_magnitude'])['identity'],
                derived_value_bounds=need)


# ---- F: the derived k and q are bounded by construction (sampled check of the argument) ---------
def part_f():
    """DESIGN.md 3.1 argues |k| <= 2^F and |q| <= 362 for EVERY input of the L2 norm, because
    |u_i| <= isqrt(sum u^2 + 17). This samples that argument (it is not the proof): one-hot, all-equal
    and random vectors at magnitudes from 1 to 2^40."""
    rnd = random.Random(67); kmax = qmax = 0; n = 0
    for mag in [1, 2, 3, 5, 17, 4096, 1 << 18, 1 << 31, 1 << 40]:
        vecs = [[mag] + [0] * (D - 1), [-mag] + [0] * (D - 1), [mag] * D, [-mag] * D, [mag if i % 2 else -mag for i in range(D)], [0] * D]
        vecs += [[rnd.randint(-mag, mag) for _ in range(D)] for _ in range(40)]
        vecs += [[rnd.randint(-mag, mag) if rnd.random() < 0.05 else 0 for _ in range(D)] for _ in range(40)]
        for u in vecs:
            kmax = max(kmax, max(abs(x) for x in l2n_int(u))); qmax = max(qmax, max(abs(x) for x in l2n_int(u, SQRT_D_Q12))); n += 1
    return dict(vectors=n, sample_seed=67, max_abs_k=kmax, max_abs_q=qmax, k_bound=ONE, q_bound=362, as_expected=kmax <= ONE and qmax <= 362)


# ---- G: for which gains can the cg check fire at all -------------------------------------------
def part_g():
    """Exhaustive over every in-class z (|z| < 2^20), with the float64 formula of head_reference.py:
    the largest |cg| per gain. Shows the check of DESIGN.md 3.1 cannot fire at gain 1 or 1.41, and
    can at 1.4143 and above. Float64 at the table point: a build with pinned tables must redo this
    on its own tables."""
    rows = []
    for gain, want_fit in ((1.0, True), (1.41, True), (1.4143, False), (2.0, False)):
        worst = 0
        for z in range(-(2 ** 20 - 1), 2 ** 20):
            c = abs(cg_from_gain(gain, z))
            if c > worst: worst = c
        rows.append(dict(gain_x10000=int(round(gain * 10000)), max_abs_cg=worst, below_bound=worst < CG_BOUND, as_expected=(worst < CG_BOUND) == want_fit))
    return dict(z_values=2 ** 21 - 1, rows=rows, as_expected=all(r['as_expected'] for r in rows))


def strip_floats(x):
    if isinstance(x, dict): return {k: strip_floats(v) for k, v in x.items() if not isinstance(v, float)}
    if isinstance(x, list): return [strip_floats(v) for v in x]
    return x

def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--json'); ap.add_argument('--check')
    a = ap.parse_args()
    A, B, C, Dd, E, Fq, G = part_a(), part_b(), part_c(), part_d(), part_e(), part_f(), part_g()
    res = dict(
        what='design-level regression of the derived-value admission rule (DESIGN.md 3.1); no proof is built or verified',
        field_p=P, cg_bound=CG_BOUND, v_bound=V_BOUND,
        summary=dict(
            A_large_gain_aliases=dict(cases=len(A), aliases_without_rule=sum(r['is_alias'] for r in A), rejected_at_derive_with_rule=sum(r['verdict_with_rule'] == 'derive' for r in A),
                                      as_expected=sum(r['as_expected'] for r in A)),
            B_boundary=dict(cases=len(B), as_expected=sum(r['as_expected'] for r in B)),
            C_no_wrap=dict(as_expected=C['as_expected'], largest_relation_magnitude_log2=C['log2'], samples=C['samples'], mismatches=C['samples_where_mod_p_solution_differs_from_integer_floor']),
            D_derived_v=dict(cases=len(Dd['rows']), as_expected=sum(r['as_expected'] for r in Dd['rows']), below_p=Dd['below_p']),
            E_no_wrap_ledger=dict(identities=len(E['identities']), all_below_p=E['all_below_p'], largest=E['largest'],
                                  largest_bound_without_wrap_log2={k: v['largest_bound_without_wrap_log2'] for k, v in E['derived_value_bounds'].items()}),
            F_derived_k_q=Fq, G_gain_vs_cg_bound=G),
        A=A, B=B, C=C, D=Dd, E=E, F=Fq, G=G)
    ok = (len(A) == 22 and all(r['as_expected'] for r in A) and all(r['as_expected'] for r in B) and C['as_expected']
          and all(r['as_expected'] for r in Dd['rows']) and Dd['below_p'] and E['all_below_p'] and Fq['as_expected'] and G['as_expected'])
    res['pass_'] = ok
    js = json.dumps(res, indent=1)
    if a.json: pathlib.Path(a.json).write_text(js + '\n')
    print(json.dumps(dict(pass_=ok, **res['summary']), indent=1))
    if a.check:
        want = json.loads(pathlib.Path(a.check).read_text())
        same = strip_floats(want) == strip_floats(res)
        print(json.dumps(dict(matches_expected_output=same)))
        ok = ok and same
    sys.exit(0 if ok else 1)

if __name__ == '__main__':
    main()
