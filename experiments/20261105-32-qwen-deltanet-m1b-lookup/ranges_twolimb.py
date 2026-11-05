#!/usr/bin/env python3
"""M1b H3 range study (integer reference only, no proof): two-limb delta and v at F = 12,
S and M single-limb; secondary arm F = 10 single-limb. Reuses the M1 reference recurrence
(research/operators/qwen_deltanet/reference.py) and the M1 realistic suite unchanged."""
import json, sys, time
from pathlib import Path
import numpy as np
root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(root / 'research/operators/qwen_deltanet'))
import reference as R
B = R.BOUND; STEPS = 1024


def limbs(x):
    hi = np.floor_divide(x, B); lo = x - hi * B
    return hi, lo


def run(seed, dist, F, two_limb):
    toks = R.gen_tokens(seed, dist, STEPS, F)
    S = np.zeros((R.D, R.D), dtype=np.int64); Sf = np.zeros((R.D, R.D))
    mx = dict(S=0, M=0, delta=0, v=0, o=0, delta_hi=0, v_hi=0); viol = {}; div = 0.0
    for t, tok in enumerate(toks):
        M, delta, S, o = R.step(S, tok, F, check=False)
        Sf, _ = R.float_step(Sf, tok)
        v = tok['v']
        for n, x in (('S', S), ('M', M), ('delta', delta), ('v', v), ('o', o)):
            mx[n] = max(mx[n], int(np.abs(x).max()))
        dh, dl = limbs(delta); vh, vl = limbs(v)
        assert (dl >= 0).all() and (dl < B).all() and (vl >= 0).all() and (vl < B).all()
        assert (dh * B + dl == delta).all() and (vh * B + vl == v).all()
        mx['delta_hi'] = max(mx['delta_hi'], int(np.abs(dh).max())); mx['v_hi'] = max(mx['v_hi'], int(np.abs(vh).max()))
        single = ['S', 'M', 'o'] + ([] if two_limb else ['delta', 'v'])
        for n in single:
            if mx[n] >= B and n not in viol: viol[n] = t
        if two_limb:
            for n in ('delta_hi', 'v_hi'):
                if mx[n] >= B and n not in viol: viol[n] = t
        div = max(div, float(np.abs(S / (1 << F) - Sf).max()))
    return dict(seed=seed, dist=dist, F=F, two_limb=two_limb, max_abs=mx, violations_first_step=viol, fits=not viol,
                divergence_vs_float64_max_abs=div)


def main():
    t0 = time.time(); out = dict(steps=STEPS, bound=B, arms={})
    for name, F, tl in (('F12_twolimb', 12, True), ('F10_single', 10, False)):
        rows = [run(s, d, F, tl) for d in ('R1', 'R2', 'R3', 'R4') for s in range(1, 6)]
        out['arms'][name] = dict(runs=rows, fits=sum(r['fits'] for r in rows), of=len(rows))
        print(name, f"{out['arms'][name]['fits']}/{len(rows)} fit")
        for d in ('R1', 'R2', 'R3', 'R4'):
            rs = [r for r in rows if r['dist'] == d]
            print(' ', d, {k: max(r['max_abs'][k] for r in rs) for k in rs[0]['max_abs']}, 'fit', sum(r['fits'] for r in rs), '/5',
                  'div', round(max(r['divergence_vs_float64_max_abs'] for r in rs), 4))
    out['seconds'] = round(time.time() - t0, 1)
    out['H3_pass'] = out['arms']['F12_twolimb']['fits'] == 20
    (Path(__file__).parent / 'runs').mkdir(exist_ok=True)
    (Path(__file__).parent / 'runs/ranges-twolimb.json').write_text(json.dumps(out, indent=1) + '\n')
    print('H3', 'PASS' if out['H3_pass'] else 'FAIL', out['seconds'], 's')


if __name__ == '__main__':
    main()
