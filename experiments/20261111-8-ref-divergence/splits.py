#!/usr/bin/env python3
"""Seeded float64 input splits for the #8 reference-divergence harness (PREREG section "Splits").

Every run is one seed. One run file holds, in this order, little-endian float64:
  nonlinear  x                      [4096]
  conv       inputs (3 hist + 4 new) [256, 7]   then taps [256, 4]
  l2         x                      [64, 128]
  rms        x                      [64, 256]
  rotary     x                      [64, 256]   then positions [64] (stored as float64 integers)
`python3 splits.py` writes splits/ and splits/MANIFEST.json (SHA-256 per file).
`python3 splits.py --check` regenerates in memory and compares bytes with the committed files.
"""
import argparse
import hashlib
import json
import pathlib

import numpy as np

HERE = pathlib.Path(__file__).resolve().parent
OUT = HERE / 'splits'
SPLITS = {'calibration': range(1, 6), 'heldout': range(1001, 1006), 'stress': range(2001, 2006)}
DEBUG_SEED = 9001  # debug only; never written to splits/, never evidence
LAYOUT = [('nonlinear.x', (4096,)), ('conv.inputs', (256, 7)), ('conv.taps', (256, 4)),
          ('l2.x', (64, 128)), ('rms.x', (64, 256)), ('rotary.x', (64, 256)), ('rotary.position', (64,))]


def truncnorm(rng, sigma, lim, shape, truncate):
    """N(0, sigma^2) entries; with truncate, entries outside [-lim, lim] are redrawn until inside."""
    sigma = np.broadcast_to(np.asarray(sigma, dtype=np.float64), shape)
    z = rng.standard_normal(shape) * sigma
    if truncate:
        bad = np.abs(z) > lim
        while bad.any():
            z[bad] = rng.standard_normal(int(bad.sum())) * sigma[bad]
            bad = np.abs(z) > lim
    return z


def norm_vectors(rng, n, d, stress):
    k = 3.0 if stress else 1.0
    rows = []
    while len(rows) < n:
        s = rng.uniform(0.55, 0.65) * k
        v = truncnorm(rng, s, 0.99, (d,), truncate=not stress)
        if not stress:
            ms = float(np.mean(v * v))
            if not (0.27 <= ms <= 0.95):
                continue
        rows.append(v)
    return np.stack(rows)


def generate(seed, stress):
    rng = np.random.Generator(np.random.PCG64(seed))
    k = 3.0 if stress else 1.0
    t = not stress
    a = {}
    a['nonlinear.x'] = truncnorm(rng, 2.0 * k, 7.9, (4096,), t)
    a['conv.inputs'] = truncnorm(rng, 0.35 * k, 0.99, (256, 7), t)
    a['conv.taps'] = truncnorm(rng, 0.35 * k, 0.99, (256, 4), t)
    a['l2.x'] = norm_vectors(rng, 64, 128, stress)
    a['rms.x'] = norm_vectors(rng, 64, 256, stress)
    a['rotary.x'] = truncnorm(rng, 0.35 * k, 0.99, (64, 256), t)
    a['rotary.position'] = rng.integers(0, 1024, size=64).astype(np.float64)
    for name, shape in LAYOUT:
        assert a[name].shape == shape, name
    return a


def encode(a):
    return b''.join(np.ascontiguousarray(a[name], dtype='<f8').tobytes() for name, _ in LAYOUT)


def decode(data):
    out, off = {}, 0
    for name, shape in LAYOUT:
        n = int(np.prod(shape))
        out[name] = np.frombuffer(data, dtype='<f8', count=n, offset=off).reshape(shape).copy()
        off += 8 * n
    assert off == len(data)
    return out


def load(split, seed):
    path = OUT / f'{split}-s{seed}.f64le'
    data = path.read_bytes()
    manifest = json.loads((OUT / 'MANIFEST.json').read_text())
    assert hashlib.sha256(data).hexdigest() == manifest['files'][path.name]['sha256'], path.name
    return decode(data)


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--check', action='store_true')
    args = p.parse_args()
    files = {}
    for split, seeds in SPLITS.items():
        for seed in seeds:
            files[f'{split}-s{seed}.f64le'] = (split, seed, encode(generate(seed, split == 'stress')))
    manifest = {'format': 'flashprove-8-ref-divergence-splits-v1', 'generator': 'splits.py, numpy PCG64(seed)',
                'numpy': np.__version__, 'layout': [[n, list(s)] for n, s in LAYOUT],
                'files': {k: {'split': s, 'seed': d, 'bytes': len(b), 'sha256': hashlib.sha256(b).hexdigest()}
                          for k, (s, d, b) in sorted(files.items())}}
    text = json.dumps(manifest, indent=2, sort_keys=True) + '\n'
    if args.check:
        for k, (_, _, b) in files.items():
            assert (OUT / k).read_bytes() == b, k
        assert (OUT / 'MANIFEST.json').read_text() == text
    else:
        OUT.mkdir(exist_ok=True)
        for k, (_, _, b) in files.items():
            (OUT / k).write_bytes(b)
        (OUT / 'MANIFEST.json').write_text(text)
    print(json.dumps({'files': len(files), 'check': args.check,
                      'manifest_sha256': hashlib.sha256(text.encode()).hexdigest()}))


if __name__ == '__main__':
    main()
