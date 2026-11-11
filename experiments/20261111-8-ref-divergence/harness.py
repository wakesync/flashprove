#!/usr/bin/env python3
"""Per-operator divergence of the committed qwen_ops integer relations vs SEPARATE BF16 and FP8 references.

Usage (from the repository root):
  python3 experiments/20261111-8-ref-divergence/harness.py calibrate            # writes runs/fp8-scales.json + runs/calibration.jsonl
  python3 experiments/20261111-8-ref-divergence/harness.py run heldout          # needs the committed runs/fp8-scales.json
  python3 experiments/20261111-8-ref-divergence/harness.py run stress
  python3 experiments/20261111-8-ref-divergence/harness.py debug                # seed 9001, writes work/debug.jsonl only
Definitions: PREREG.md. Every split file is checked against splits/MANIFEST.json before use.
"""
import hashlib
import json
import sys
import time

import numpy as np

import refs
import splits

RUNS = refs.HERE / 'runs'
WORK = refs.HERE / 'work'
F32 = np.float32
ROLES = {op: ('nonlinear.x',) for op in refs.NONLINEAR}
ROLES.update({'conv': ('conv.inputs', 'conv.taps'), 'l2': ('l2.x',), 'rms': ('rms.x',), 'rotary': ('rotary.x',)})


def role_key(op, role):
    return f'{op}:{role}'


# ---------------------------------------------------------------- references

def reference(op, a, arm, scales):
    """Returns (output float64 array [n, k], counters dict). arm in fp64 | bf16 | fp8."""
    cnt = dict(fp8_sat=0, fp8_under=0, bf16_over=0)

    def inp(role):
        v = a[role]
        if arm == 'fp64':
            return v
        if arm == 'bf16':
            r, over, _ = refs.bf16(v)
            cnt['bf16_over'] += over
            return r.astype(F32)
        q, sat, under = refs.fp8_quant(v, scales[role_key(op, role)])
        cnt['fp8_sat'] += sat
        cnt['fp8_under'] += under
        return q

    dt = np.float64 if arm == 'fp64' else F32
    if op in refs.NONLINEAR:
        y = refs.nonlinear_f(op, inp('nonlinear.x'), dt)[:, None]
    elif op == 'conv':
        y = refs.conv_f(inp('conv.inputs'), inp('conv.taps'), dt)
    elif op in ('l2', 'rms'):
        y = refs.norm_f(op, inp(f'{op}.x'), dt)
    else:
        ang = refs.rotary_angles(a['rotary.position'], dt)
        cos, sin = np.cos(ang).astype(dt), np.sin(ang).astype(dt)
        if arm != 'fp64':
            cos = refs.bf16(cos)[0].astype(F32)
            sin = refs.bf16(sin)[0].astype(F32)
        y = refs.rotary_f(inp('rotary.x'), cos, sin, dt)
    y = np.asarray(y, dtype=np.float64)
    if arm != 'fp64':
        y, over, _ = refs.bf16(y)
        cnt['bf16_over'] += over
    return y, cnt


def integer(op, a, f):
    """Returns (output float64 [n, k] with NaN rows for out-of-domain norm vectors, counters)."""
    S = 1 << f
    cnt = dict(int_clamps=0, int_ood=0)
    if op in refs.NONLINEAR:
        X, c = refs.to_int(a['nonlinear.x'], f, -8, 8)
        cnt['int_clamps'] += c
        y = refs.int_nonlinear(op, X, f)[:, None]
    elif op == 'conv':
        X, c1 = refs.to_int(a['conv.inputs'], f, -1, 1)
        W, c2 = refs.to_int(a['conv.taps'], f, -1, 1)
        cnt['int_clamps'] += c1 + c2
        y = refs.int_conv(X, W, f)
    elif op in ('l2', 'rms'):
        X, c = refs.to_int(a[f'{op}.x'], f, -1, 1)
        cnt['int_clamps'] += c
        y, key = refs.int_norm(op, X, f)
        bad = (key < 0) | (key >= 4096)
        cnt['int_ood'] = int(bad.sum())
        y = y.astype(np.float64)
        y[bad, :] = np.nan
        return y / S, cnt
    else:
        X, c = refs.to_int(a['rotary.x'], f, -1, 1)
        cnt['int_clamps'] += c
        y = refs.int_rotary(X, a['rotary.position'], f)[:, :64]
    return y.astype(np.float64) / S, cnt


# ---------------------------------------------------------------- metrics

def ratio(num, den):
    if den == 0:
        return 0.0 if num == 0 else float('inf')
    return num / den


def argmax_lowest(v):
    return np.argmax(v, axis=-1)  # numpy returns the first (lowest) index on ties


def metrics(op, y_int, y_ref, y64):
    keep = ~np.isnan(y_int).any(axis=-1)
    yi, yr, y0 = y_int[keep], y_ref[keep], y64[keep]
    d_ir, d_r0, d_i0 = (yi - yr).ravel(), (yr - y0).ravel(), (yi - y0).ravel()
    rms = lambda d: float(np.sqrt(np.mean(d * d))) if d.size else float('nan')
    mx = lambda d: float(np.max(np.abs(d))) if d.size else float('nan')
    m = dict(n=int(d_ir.size), vectors=int(keep.sum()),
             max_int_ref=mx(d_ir), rms_int_ref=rms(d_ir), max_ref_fp64=mx(d_r0), rms_ref_fp64=rms(d_r0),
             max_int_fp64=mx(d_i0), rms_int_fp64=rms(d_i0),
             sign_flips=int((yi * yr < 0).sum()))
    m['R_max'] = ratio(m['max_int_ref'], m['max_ref_fp64'])
    m['R_rms'] = ratio(m['rms_int_ref'], m['rms_ref_fp64'])
    if op in refs.NONLINEAR:
        m['argmax_flips'] = None
        m['argmax_n'] = 0
    else:
        m['argmax_flips'] = int((argmax_lowest(yi) != argmax_lowest(yr)).sum())
        m['argmax_n'] = int(yi.shape[0])
    return m


def evaluate(split, seed, a, scales):
    rows = []
    for op in refs.OPS:
        y64, _ = reference(op, a, 'fp64', scales)
        refs_out = {arm: reference(op, a, arm, scales) for arm in ('bf16', 'fp8')}
        for f in refs.FS:
            y_int, icnt = integer(op, a, f)
            for arm, (y_ref, rcnt) in refs_out.items():
                row = dict(split=split, seed=seed, op=op, F=f, arm=arm)
                row.update(metrics(op, y_int, y_ref, y64))
                row.update(icnt)
                row.update(rcnt)
                rows.append(row)
    return rows


def amax_scales(split):
    amax = {}
    for seed in splits.SPLITS[split]:
        a = splits.load(split, seed)
        for op, roles in ROLES.items():
            for role in roles:
                k = role_key(op, role)
                amax[k] = max(amax.get(k, 0.0), float(np.max(np.abs(a[role]))))
    return {k: dict(amax=v, scale=float(np.float32(448.0 / v))) for k, v in sorted(amax.items())}


def write_rows(path, rows):
    with open(path, 'w') as fh:
        for r in rows:
            fh.write(json.dumps(r, sort_keys=True) + '\n')


def run_split(split, scales):
    rows = []
    for seed in splits.SPLITS[split]:
        t0 = time.process_time()
        r = evaluate(split, seed, splits.load(split, seed), scales)
        for x in r:
            x['cpu_s_seed'] = round(time.process_time() - t0, 3)
        rows += r
        print(json.dumps(dict(split=split, seed=seed, rows=len(r), cpu_s=round(time.process_time() - t0, 3))), flush=True)
    return rows


def main():
    RUNS.mkdir(exist_ok=True)
    mode = sys.argv[1]
    if mode == 'debug':
        WORK.mkdir(exist_ok=True)
        a = splits.generate(splits.DEBUG_SEED, stress=False)
        sc = {role_key(op, role): 448.0 / float(np.max(np.abs(a[role]))) for op, roles in ROLES.items() for role in roles}
        rows = evaluate('debug', splits.DEBUG_SEED, a, sc)
        write_rows(WORK / 'debug.jsonl', rows)
        for r in rows:
            if r['F'] == 12:
                print(r['op'], r['arm'], 'R_max=%.3g' % r['R_max'], 'int_ref=%.3g' % r['max_int_ref'],
                      'ref_64=%.3g' % r['max_ref_fp64'], 'clamps', r['int_clamps'], 'ood', r['int_ood'],
                      'sat', r['fp8_sat'], 'sign', r['sign_flips'], 'argmax', r['argmax_flips'])
        return
    if mode == 'calibrate':
        scales = amax_scales('calibration')
        doc = dict(rule='s = float32(448 / amax), amax over all 5 calibration runs, per op and input role',
                   manifest_sha256=hashlib.sha256((splits.OUT / 'MANIFEST.json').read_bytes()).hexdigest(),
                   scales=scales)
        (RUNS / 'fp8-scales.json').write_text(json.dumps(doc, indent=2, sort_keys=True) + '\n')
        split = 'calibration'
    else:
        split = sys.argv[2]
        assert split in ('heldout', 'stress')
    doc = json.loads((RUNS / 'fp8-scales.json').read_text())
    scales = {k: v['scale'] for k, v in doc['scales'].items()}
    rows = run_split(split, scales)
    write_rows(RUNS / f'{split}.jsonl', rows)
    print(json.dumps(dict(split=split, rows=len(rows))))


if __name__ == '__main__':
    main()
