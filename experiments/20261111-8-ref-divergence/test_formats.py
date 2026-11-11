#!/usr/bin/env python3
"""Self-test of refs.round_to_format against hand values and an independent bit-level BF16 / E4M3 rounder."""
import json

import numpy as np

import refs


def bf16_bits(x32):
    """Independent RNE float32 -> bfloat16 via the classic bias trick on the bit pattern (finite inputs)."""
    u = np.asarray(x32, dtype=np.float32).view(np.uint32).astype(np.uint64)
    u = (u + 0x7FFF + ((u >> 16) & 1)) >> 16 << 16
    return u.astype(np.uint32).view(np.float32).astype(np.float64)


def e4m3_table():
    """All finite non-negative E4M3FN values by enumeration of the bit patterns (exp 0..15, mant 0..7, minus NaN)."""
    vals = []
    for e in range(16):
        for m in range(8):
            if e == 15 and m == 7:
                continue
            vals.append(m / 8 * 2.0 ** -6 if e == 0 else (1 + m / 8) * 2.0 ** (e - 7))
    return np.array(sorted(set(vals)))


def e4m3_ref(v):
    """Nearest in the enumerated table, ties to the even mantissa, saturating."""
    t = e4m3_table()
    out = []
    for x in np.asarray(v, dtype=np.float64):
        a = min(abs(x), 448.0)
        i = np.searchsorted(t, a)
        if i == 0:
            r = t[0]
        elif i == len(t):
            r = t[-1]
        else:
            lo, hi = t[i - 1], t[i]
            if a - lo < hi - a:
                r = lo
            elif hi - a < a - lo:
                r = hi
            else:  # tie: pick the one whose index (= mantissa parity within the ladder) is even
                r = lo if (i - 1) % 2 == 0 else hi
        out.append(np.copysign(r, x))
    return np.array(out)


def main():
    checks = {}
    hand = [(1 + 2.0 ** -8, 1.0), (1 + 3 * 2.0 ** -8, 1 + 2.0 ** -6), (-(1 + 2.0 ** -8), -1.0), (0.0, 0.0)]
    got = refs.bf16(np.array([h[0] for h in hand]))[0]
    checks['bf16_hand'] = bool(np.array_equal(got, [h[1] for h in hand]))
    rng = np.random.Generator(np.random.PCG64(77))
    x = np.concatenate([rng.standard_normal(200000) * 10.0 ** rng.integers(-30, 30, 200000),
                        np.ldexp(rng.integers(-2 ** 16, 2 ** 16, 50000).astype(np.float64), -16)]).astype(np.float32)
    checks['bf16_vs_bits'] = bool(np.array_equal(refs.bf16(x.astype(np.float64))[0], bf16_bits(x)))
    hand8 = [(464.0, 448.0), (1000.0, 448.0), (2.0 ** -10, 0.0), (3 * 2.0 ** -10, 2 * 2.0 ** -9), (1.0625, 1.0),
             (1.1875, 1.25), (-500.0, -448.0)]
    r8, sat, under = refs.round_to_format(np.array([h[0] for h in hand8]), saturate=True, **refs.E4M3)
    checks['e4m3_hand'] = bool(np.array_equal(r8, [h[1] for h in hand8]))
    checks['e4m3_hand_counts'] = [sat, under]
    y = np.concatenate([rng.standard_normal(20000) * 2.0 ** rng.integers(-12, 10, 20000), e4m3_table(),
                        (e4m3_table()[1:] + e4m3_table()[:-1]) / 2])
    checks['e4m3_vs_table'] = bool(np.array_equal(refs.round_to_format(y, saturate=True, **refs.E4M3)[0], e4m3_ref(y)))
    print(json.dumps(checks))
    (refs.HERE / 'runs' / 'format-selftest.json').write_text(json.dumps(checks, indent=2) + '\n')
    assert checks['bf16_hand'] and checks['bf16_vs_bits'] and checks['e4m3_hand'] and checks['e4m3_vs_table']
    assert checks['e4m3_hand_counts'] == [3, 1]


if __name__ == '__main__':
    main()
