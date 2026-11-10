#!/usr/bin/env python3
"""Bound ledger for the M3 relations (DESIGN.md section 6). No proof is built.

Every relation of the lowering is an equation modulo p = 2^64 - 2^32 + 1. It means the integer
equation only if the integer it sums to stays below p in absolute value for EVERY value a cheating
prover can put in the cells. For each relation this script adds up |term| over ALL terms, both
sides, each factor at the edge of its own class, as an exact integer. That sum bounds the
residual's absolute value. It fails if any row reaches 2^63.

r2 (2026-11-10, after two reviews of PR #70). Changes from r1 (runs/bounds.json):
  - every row is a sum over all terms with every independently ranged limb at its edge, as an exact
    integer (r1 used log2 of the largest term plus one, and missed terms: the sigma^2 side of the
    q/k square row, the low limb of k x delta);
  - the SiLU image is the pinned table's, |s| <= 32,741 < 2^15 (r1 said 4,095 in one row);
  - floors at a tensor's public shift 2^s, s in 1..24, carry the exact class [0, 2^s) (vrem in
    count_m3.py); section B below checks the review's counterexample against both classes;
  - q = floor(362 Rc x / 2^36) (the M2 query scale); the gain floor at 2^sg;
  - M3a-MLP rows: the down projection of r1 (unrounded s x u) wraps, and is kept as a control;
  - the weight-cell class and its batched tie, and the softplus key.
Each bound is PROVED FROM THE CLASSES (arithmetic on enforced class edges), not sampled.

Where a class comes from:
  format   a constant of the format (a power of two, a table step, 362)
  admit    a public statement word, class checked by the verifier at admission (M3a: a, the outputs)
  wclass   a weight cell read by the trace: exact class [-4096, 4095] in the trace, and tied to the
           committed table (DESIGN.md 6.2). The key file's range proof is NOT what bounds it.
  table    the output of a function-table lookup, bounded by the pinned table's image
  key12    an exact 12-bit lookup key: [0, 2^12)
  rng      an RNG cell: |x| < 2^23 against a cheating prover (honest cells are < 2^18)
  implied  follows from an earlier row holding over the integers (named in `then`)

usage: bounds.py [--json out.json]
"""
import argparse, json, math

P = 2 ** 64 - 2 ** 32 + 1
LIMIT = 2 ** 63
F = 12
RNG = 2 ** 23 - 1          # |x| <= 2^23 - 1
W = 4096                   # |w| <= 4,096 (class [-4096, 4095])
SILU = 32741               # largest |entry| of the pinned F = 12 SiLU table (row 4095), < 2^15
UNIT = 2 ** F              # sigmoid, exp(-x): [0, 2^12]
SOFTPLUS = 2 ** 16         # conservative image bound for softplus on [-8, 8) at 2^12
A_PUB = 2047               # M3a public normed input
OUT_PUB = 2 ** 31 - 1      # M3a public outputs
S_MAX = 24                 # largest admitted public shift
R_S = 2 ** S_MAX - 1       # remainder for 2^s
SIG = 2 ** 24 - 1          # sigma, e1, e2, rr, gap: two 12-bit limbs
RC = 2 ** 36 - 1           # Rc: three limbs
EPS = 17                   # epsilon at 2^2F (M2 design)
K_IMP = 2 ** F             # |k| <= 2^12 implied by the k floor (|x| <= sigma)
Q_IMP = 362                # |q| <= 362 implied by the q floor
D, DIN, F_MLP = 128, 5120, 17408
DELTA = 2 ** 18 * RNG + RNG   # delta = 2^18 hi + lo, both rng


def row(name, terms, why, then, control=False):
    s = sum(terms)
    return dict(relation=name, bound=s, log2=round(math.log2(s), 6), below_2_63=s < LIMIT, control=control,
                bounds_from=why, then=then, n_terms_summed=len(terms))


ROWS = [
    row('in_proj: sum_k a_k W_kj - 2^s x_j - r_j', [DIN * A_PUB * W, 2 ** S_MAX * RNG, R_S],
        'a: admit; W: weight table (linear claim, M3a); x: rng; r: exact [0, 2^s), s <= 24', 'x_j = floor(sum / 2^s)'),
    row('conv: sum_4 tap*x - 2^s c - r', [4 * W * RNG, 2 ** S_MAX * RNG, R_S],
        'tap: wclass; x: rng (in_proj outputs and history); c: rng; r: exact [0, 2^s)', 'c = floor(acc / 2^s)'),
    row('conv gate: tap * x', [W * RNG], 'tap: wclass; x: rng', 'gate product is the integer product'),
    row('SiLU key: c - step (idx - off) - r', [RNG, 16 * 4096, 16 * 2048, 15],
        'c: rng; idx: table key (12 bits); off 2,048; r: [0, 16) by two keys', '|c| < 8 x 2^F: the domain bounds c exactly'),
    row('q/k norm S5: sum x^2 + eps - sigma^2 - e1', [D * SILU ** 2, EPS, SIG ** 2, SIG],
        'x: table (SiLU image, 32,741); sigma, e1: two key12 limbs each', 'with S6: sigma = isqrt(sum x^2 + eps)'),
    row('q/k norm S6: sigma^2 + 2 sigma - sum x^2 - eps - e2', [SIG ** 2, 2 * SIG, D * SILU ** 2, EPS, SIG],
        'as S5; e2: two key12 limbs', 'sigma = isqrt'),
    row('q/k norm S7: Rc sigma + rr - 2^36', [RC * SIG, SIG, 2 ** 36], 'Rc: three key12 limbs; sigma, rr: limbs', 'Rc = floor(2^36 / sigma) (with S8)'),
    row('q/k norm S8: sigma - rr - gap - 1', [SIG, SIG, SIG, 1], 'limbs', 'rr < sigma'),
    row('k: x Rc - 2^24 k - r', [SILU * RC, 2 ** 24 * RNG, 2 ** 24 - 1], 'x: table; Rc: limbs; k: rng; r: two key12', '|k| <= 2^12 (|x| <= sigma)'),
    row('q: 362 Rc x - 2^36 q - r', [362 * RC * SILU, 2 ** 36 * RNG, 2 ** 36 - 1],
        '362: format (round(2^12 / sqrt(128))); x: table; Rc: limbs; q: rng; r: three key12', '|q| <= 362'),
    row('softplus key: ar + dt_bias - step (idx - off) - r', [RNG, W, 16 * 4096, 16 * 2048, 15],
        'ar: rng; dt_bias: wclass (at the in_proj output scale); idx: table key', 'the softplus input is in the domain'),
    row('decay: cA sp - 2^sA g - r', [W * SOFTPLUS, 2 ** S_MAX * RNG, R_S], 'cA: wclass; sp: table (softplus); g: rng; r: exact [0, 2^sA)', 'g = floor(cA sp / 2^sA)'),
    row('recurrence g1 = S a', [RNG * UNIT], 'S: rng; a: table (exp image)', ''),
    row('recurrence P_j = sum_i S_i k_i', [D * RNG * K_IMP], 'S: rng; k: implied', ''),
    row('recurrence g5 = P_j a', [D * RNG * K_IMP * UNIT], 'P_j: row above; a: table', ''),
    row('recurrence: 2^24 (v - M) + r - g5', [2 ** 24 * SILU, 2 ** 24 * RNG, 2 ** 24 - 1, D * RNG * K_IMP * UNIT],
        'v: table (SiLU image); M: rng; r: two key12; g5: row above', 'M = v - floor(g5 / 2^24)'),
    row('recurrence g6 = (v - M) beta', [(SILU + RNG) * UNIT], 'beta: table (sigmoid)', ''),
    row('recurrence: 2^12 delta + r - g6, delta = 2^18 hi + lo', [2 ** 12 * DELTA, 2 ** 12 - 1, (SILU + RNG) * UNIT],
        'hi, lo: rng each; r: key12', 'delta = floor(g6 / 2^12)'),
    row('recurrence g3 = k delta', [K_IMP * DELTA], 'k: implied; delta: both limbs at the edge', ''),
    row("recurrence: 2^12 S' + r - g1 - g3", [2 ** 12 * RNG, 2 ** 12 - 1, RNG * UNIT, K_IMP * DELTA],
        "S': rng; r: key12", "S' = floor(.)"),
    row("output: 2^12 o + r - sum_i S'_i q_i", [2 ** 12 * RNG, 2 ** 12 - 1, D * RNG * Q_IMP], "S': rng; q: implied 362; o: rng", 'o = floor(.)'),
    row('gated norm S5: sum o^2 + eps - sigma^2 - e1', [D * RNG ** 2, EPS, SIG ** 2, SIG], 'o: rng; sigma, e1: limbs', 'sigma = isqrt'),
    row('gated norm S6: sigma^2 + 2 sigma - sum o^2 - eps - e2', [SIG ** 2, 2 * SIG, D * RNG ** 2, EPS, SIG], 'as S5', ''),
    row('gated norm S7: Rc sigma + rr - 2^36', [RC * SIG, SIG, 2 ** 36], 'limbs', 'Rc = floor(2^36 / sigma)'),
    row('gated norm: o Rc - 2^24 w - r', [RNG * RC, 2 ** 24 * RNG, 2 ** 24 - 1], 'o: rng; Rc: limbs; w: rng', '|w| <= 2^12 (implied, not used below)'),
    row('gated norm: s w - 2^12 t - r', [SILU * RNG, 2 ** 12 * RNG, 2 ** 12 - 1], 's: table (SiLU image); w: rng (the implied 2^12 is not used)', 't = floor(s w / 2^12)'),
    row('gated norm: gain t - 2^sg y - r', [W * RNG, 2 ** S_MAX * RNG, R_S], 'gain: wclass; t, y: rng; r: exact [0, 2^sg)', 'y = floor(gain t / 2^sg)'),
    row('out_proj (one head, inner 128): sum_j y_j Wo_jk - out_k', [D * RNG * W, OUT_PUB], 'y: rng; Wo: weight table (product argument); out: admit', 'the head contribution'),
    row('weight cell class: w + 4096 - lo - 2^12 hi', [W, 4096, 4095, 2 ** 12], 'lo: key12; hi: {0, 1} by a key and its complement', 'w in [-4096, 4095] exactly'),
    row('exact 2^s remainder: 2^(s-12) - 1 - r1 - c', [2 ** 12, 1, 4095, 4095], 'r1, c: key12', 'r < 2^s exactly'),
    row('M3a-MLP gate/up: sum_k m_k W - 2^s x - r', [DIN * A_PUB * W, 2 ** S_MAX * RNG, R_S], 'm: admit; W: table; x: rng; r: exact', 'gw, u'),
    row('M3a-MLP: s u - 2^12 h - r (r2)', [SILU * RNG, 2 ** 12 * RNG, 2 ** 12 - 1], 's: table (SiLU of gw); u, h: rng; r: key12', 'h = floor(s u / 2^12)'),
    row('M3a-MLP down (r2): sum_j h_j Wd_jk - 2^s out - r', [F_MLP * RNG * W, 2 ** S_MAX * OUT_PUB, R_S], 'h: rng; Wd: table; out: admit', 'MLP output'),
    row('CONTROL, r1 M3a-MLP down: sum_j (s u)_j Wd_jk (product unrounded)', [F_MLP * SILU * RNG * W, 2 ** S_MAX * OUT_PUB, R_S],
        'the r1 lowering: s u enters the down projection raw', 'wraps: this row must fail (found in r2)', control=True),
    row('CONTROL, #66 M2 at 8ec7c799: cg w - 2^12 y - r with cg = 2^62', [2 ** 62 * 4, 2 ** 12 * OUT_PUB, 4095],
        'cg not bounded at 8ec7c799 (the #66 review alias)', 'wraps: this row must fail', control=True),
]


def exact_class_check():
    """Section B: the review's counterexample to r1's gain floor (fixed 12-bit remainder class at a
    variable shift sg). sg = 8, gain = 1, t = 0, y = -1, r = 256: 2^sg y + r = gain t holds."""
    sg, gain, t, y, r = 8, 1, 0, -1, 256
    eq = (2 ** sg) * y + r == gain * t
    true_floor = (gain * t) // (2 ** sg)
    r1_accepts = eq and 0 <= r < 2 ** 12
    r2_accepts = eq and 0 <= r < 2 ** sg
    # exhaustive at small sizes: for every sg in 1..12, |gain t| < 2^14, the r2 class leaves only the floor
    bad = 0
    for s in range(1, 13):
        for v in range(-2 ** 14, 2 ** 14, 37):
            for yy in (v // 2 ** s - 1, v // 2 ** s, v // 2 ** s + 1):
                rr = v - 2 ** s * yy
                if 0 <= rr < 2 ** s and yy != v // 2 ** s: bad += 1
    return dict(counterexample=dict(sg=sg, gain=gain, t=t, y=y, r=r, relation_holds=eq, true_floor=true_floor),
                r1_class_0_to_2e12_accepts=r1_accepts, r2_class_0_to_2e_sg_accepts=r2_accepts,
                r2_second_solutions_in_sweep=bad, pass_=r1_accepts and not r2_accepts and bad == 0)


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--json'); a = ap.parse_args()
    bad = [r['relation'] for r in ROWS if r['below_2_63'] == r['control']]
    worst = max(r['log2'] for r in ROWS if not r['control'])
    b = exact_class_check()
    res = dict(rows=ROWS, worst_log2=worst, all_m3_relations_below_2_63=not bad,
               controls_wrap=all(not r['below_2_63'] for r in ROWS if r['control']), exact_class=b,
               note='proved from the class edges by exact integer arithmetic (sum of |term| over all terms); not sampled, '
                    'not a machine-checked proof, not a test of a verifier. The weight-cell tie is a random linear '
                    'check in the field and needs no no-wrap row.')
    print(json.dumps(dict(worst_log2=worst, ok=not bad and b['pass_'], controls_wrap=res['controls_wrap'],
                          exact_class_pass=b['pass_'], failed=bad)))
    if a.json: open(a.json, 'w').write(json.dumps(res, indent=1) + '\n')
    raise SystemExit(1 if (bad or not b['pass_']) else 0)


if __name__ == '__main__':
    main()
