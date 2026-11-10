#!/usr/bin/env python3
"""Bound ledger for the M3 head relations (DESIGN.md section 6). No proof is built.

Every relation of the lowering is an equation modulo p = 2^64 - 2^32 + 1. It means the integer
equation only if the integer it sums to is below p in absolute value for EVERY value a cheating
prover can put in the cells. This script recomputes, from the bound that is actually enforced on
each cell, the worst magnitude of each relation, and fails if any reaches 2^63.

Where a bound comes from (the `source` of each class):
  format   a constant of the format (a power of two, a table step)
  admit    a public statement word, class bound checked by the verifier at admission
  key      a committed weight: |w| <= 4,096 shown ONCE by the key file's range proof (docs/protocol.md
           6.1 step 2), which the verifier checks on every call. The verifier never sees the weight.
  table    a cell that is the output of a function-table lookup: bounded by the public table's image
  key12    an exact 12-bit lookup key (arm B remainder limb): in [0, 2^12)
  rng      an RNG cell: the approximate range check shows |x| < 2^23 (honest cells are < 2^18)
  implied  a bound that follows from an earlier relation holding over the integers

The review of #66 found a coefficient (cg, the gated norm's derived coefficient) whose bound was
assumed and not enforced, with a modular alias at cg = 2^62. In M3 there is no derived coefficient:
the gain is a committed weight (`key`), SiLU(z) is a `table` cell, and the product is taken in two
floors. The rows 'gated norm: s*w' and 'gated norm: gain*t' below are that fix.

usage: bounds.py [--json out.json]
"""
import argparse, json, math

P_BITS = 63.0   # refuse anything at or above 2^63 (p is just under 2^64; the margin covers the sums below)
F = 12
B = dict(  # log2 of the enforced bound on |value|
    rng=23, key12=12, weight=12, table_silu=15, table_unit=F, pub_a=11, limb24=24, Rc=36, sigma=24,
)
D, DIN, DOUT = 128, 5120, 6144


def lg(n):
    return math.log2(n)


# (name, log2 worst magnitude, what bounds each factor, what the relation then implies)
ROWS = [
    ('in_proj: sum_k a_k W_kj = 2^s x_j + r_j', max(lg(DIN) + B['pub_a'] + B['weight'], 24 + B['rng']) + 1,
     'a: admit (M3a) or table clamp 2,047 (full model); W: key; x: rng; r: two key12 limbs; shift s <= 24: format',
     'x_j is the rounded projection (integer)'),
    ('conv: acc = sum of 4 tap * x', lg(4) + B['weight'] + B['rng'], 'tap: key; x: rng', 'acc is the integer filter sum'),
    ('conv: 2^12 c + r = acc', max(12 + B['rng'], lg(4) + B['weight'] + B['rng']) + 1, 'c: rng; r: key12', 'c = floor(acc / 2^12)'),
    ('SiLU key: c = step (idx - off) + r', B['rng'] + 1, 'idx: table key (exact, 12 bits); r: key12', '|c| < 8 * 2^F: the lookup domain bounds c exactly'),
    ('q/k norm: sum x^2 + eps = sigma^2 + e1', lg(D) + 2 * B['table_silu'] + 1, 'x: table (SiLU image)', 'sigma = isqrt, with e2'),
    ('q/k norm: 2^36 = Rc sigma + rr', B['Rc'] + B['sigma'] + 1, 'Rc: three key12 limbs; sigma: two key12 limbs', 'Rc = floor(2^36 / sigma)'),
    ('q/k norm: 2^24 k + r = x Rc', max(24 + B['rng'], B['table_silu'] + B['Rc']) + 1, 'k: rng; x: table; Rc: limbs',
     'k = floor(x Rc / 2^24), so |k| <= 2^12 (implied): k and q need no extra range check'),
    ('gate: 2^F g + r = cA * sp', max(F + B['rng'], B['weight'] + 16) + 1, 'cA: key; sp: table (softplus image); g: rng', 'g is the integer decay exponent'),
    ('recurrence: g1 = S * a', B['rng'] + B['table_unit'], 'S: rng; a: table (exp image, in [0, 2^F])', ''),
    ('recurrence: g2 = S * k, P_j = sum_i g2', lg(D) + B['rng'] + 12, 'S: rng; k: implied 2^12', ''),
    ('recurrence: g5 = P_j * a', lg(D) + B['rng'] + 12 + B['table_unit'], 'P_j: sum above; a: table', 'worst gate of the recurrence'),
    ('recurrence: 2^2F (v - M) + r = g5.c', max(2 * F + B['rng'], lg(D) + B['rng'] + 24) + 1, 'M: rng; v: table; r: two key12 limbs', 'M = v - floor(.)'),
    ('recurrence: g6 = (v - M) * beta', B['rng'] + 1 + B['table_unit'], 'beta: table (sigmoid image)', ''),
    ('recurrence: g3 = k * delta', 12 + 18 + B['rng'], 'k: implied; delta = 2^18 hi + lo, hi: rng, lo: rng', ''),
    ('recurrence: 2^F S\' + r = g1.c + g3.c', max(F + B['rng'], 12 + 18 + B['rng']) + 2, "S': rng; r: key12", "S' = floor(.)"),
    ('output: 2^F o + r = sum_i S\' * q', lg(D) + B['rng'] + 12 + 1, "S': rng; q: implied 2^12; o: rng", 'o = floor(.)'),
    ('gated norm: sum o^2 + eps = sigma^2 + e1', lg(D) + 2 * B['rng'] + 1, 'o: rng', 'sigma = isqrt'),
    ('gated norm: 2^24 w + r = o Rc', max(24 + B['rng'], B['rng'] + B['Rc']) + 1, 'o: rng; Rc: limbs; w: rng', '|w| <= 2^12 (implied)'),
    ('gated norm: 2^F t + r = s * w', max(F + B['rng'], B['table_unit'] + B['rng']) + 1, 's: table (SiLU image, |s| <= 4,095); w: rng (2^12 implied)', 't = floor(s w / 2^F), |t| <= 2^12'),
    ('gated norm: 2^sg y + r = gain * t', max(24 + B['rng'], B['weight'] + B['rng']) + 1, 'gain: key (|gain| <= 4,096); t: rng (2^12 implied); y: rng', 'y = floor(gain t / 2^sg): no derived coefficient'),
    ('out_proj: sum_j y_j Wo_jk = out_k', lg(DOUT) + B['rng'] + B['weight'], 'y: rng; Wo: key; out: admit (M3a)', 'the head contribution is the integer sum'),
    ('M2 design, for comparison: 2^F y + r = cg * w with cg = 2^62 (the #66 review alias)', 62 + 12, 'cg: NOT bounded in #66 at 8ec7c799', 'wraps: this row must fail'),
]


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--json'); a = ap.parse_args()
    out = []; bad = []
    for name, bits, why, gives in ROWS:
        ok = bits < P_BITS
        control = name.startswith('M2 design, for comparison')
        out.append(dict(relation=name, log2_worst_magnitude=round(bits, 2), below_2_63=ok, bounds_from=why, then=gives, control=control))
        if ok == control: bad.append(name)
    worst = max(r['log2_worst_magnitude'] for r in out if not r['control'])
    res = dict(rows=out, worst_log2=worst, all_m3_relations_below_2_63=not bad, control_row_wraps=not out[-1]['below_2_63'],
               note='magnitudes are upper bounds from the enforced class bounds; this is arithmetic on the design, not a proof and not a test of a verifier')
    print(json.dumps(dict(worst_log2=worst, ok=not bad, control_row_wraps=res['control_row_wraps'], failed=bad)))
    if a.json: open(a.json, 'w').write(json.dumps(res, indent=1) + '\n')
    raise SystemExit(1 if bad else 0)


if __name__ == '__main__':
    main()
