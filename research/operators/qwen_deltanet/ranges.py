#!/usr/bin/env python3
"""H3 range study: integer state growth over 1,024 steps (no proof). Writes ranges.json."""
import json, math, sys, time
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parent))
import reference as R

STEPS = 1024
def run(seed, dist, F):
    toks = R.gen_tokens(seed, dist, STEPS, F)
    S = np.zeros((R.D, R.D), dtype=np.int64); Sf = np.zeros((R.D, R.D))
    mx = dict(S=0, M=0, delta=0, aP=0, o=0); first_over = None; div_max = 0.0; div_rms = 0.0
    for t, tok in enumerate(toks):
        P = tok['k'] @ S
        mx['aP'] = max(mx['aP'], int(np.abs(tok['a'] * P).max()))
        M, delta, S, o = R.step(S, tok, F, check=False)
        Sf, _ = R.float_step(Sf, tok)
        for n, x in (('S', S), ('M', M), ('delta', delta), ('o', o)): mx[n] = max(mx[n], int(np.abs(x).max()))
        if first_over is None and max(mx['S'], mx['M'], mx['delta']) >= R.BOUND: first_over = t
        d = S / (1 << F) - Sf
        div_max = max(div_max, float(np.abs(d).max())); div_rms = float(np.sqrt(np.mean(d * d)))
    bits = {n: int(math.ceil(math.log2(v + 1))) + 1 for n, v in mx.items()}
    return dict(seed=seed, dist=dist, F=F, max_abs=mx, bits_signed=bits, first_step_over_2_18=first_over,
                fits_2_18=first_over is None, state_float_max=float(np.abs(Sf).max()),
                divergence_vs_float64=dict(max_abs=div_max, rms_final=div_rms))

def summ(rows):
    by = {}
    for r in rows: by.setdefault((r['dist'], r['F']), []).append(r)
    lines = []
    for (d, F), rs in sorted(by.items(), key=lambda x: (x[0][1], x[0][0])):
        S = [r['max_abs']['S'] for r in rs]; Mx = [max(r['max_abs']['M'], r['max_abs']['delta']) for r in rs]
        lines.append(f"{d} F={F}: n={len(rs)} max|S| median {int(np.median(S))} min {min(S)} max {max(S)} "
                     f"(signed bits {max(r['bits_signed']['S'] for r in rs)}); max|M|,|delta| {max(Mx)}; "
                     f"max|a*P| {max(r['max_abs']['aP'] for r in rs)}; fits 2^18 {sum(r['fits_2_18'] for r in rs)}/{len(rs)}; "
                     f"state div vs float64 max {max(r['divergence_vs_float64']['max_abs'] for r in rs):.4g}")
    return lines

def main():
    t0 = time.time(); out = dict(steps=STEPS, bound=R.BOUND, realistic=[], stress=[], f_sweep=[])
    for d in ('R1', 'R2', 'R3', 'R4'):
        for s in range(1, 6): out['realistic'].append(run(s, d, 12))
    for d in ('S1', 'S2', 'S3', 'S4'):
        for s in range(1, 6): out['stress'].append(run(s, d, 12))
    for F in (8, 10, 14, 16):
        for d in ('R1', 'R2', 'R3', 'R4'):
            for s in range(1, 6): out['f_sweep'].append(run(s, d, F))
    out['seconds'] = round(time.time() - t0, 1)
    out['H3_pass'] = all(r['fits_2_18'] for r in out['realistic'])
    out['summary'] = summ(out['realistic']) + summ(out['stress']) + summ(out['f_sweep'])
    Path(__file__).with_name('ranges.json').write_text(json.dumps(out, indent=1) + '\n')
    print('\n'.join(out['summary']))
    print('H3', 'PASS' if out['H3_pass'] else 'FAIL', out['seconds'], 's')

if __name__ == '__main__': main()
