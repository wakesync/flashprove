#!/usr/bin/env python3
"""Generate one parametric KDA fixture: gen.py D_K D_V TOKENS HEADS BITS SEED OUT.bin
Prints one JSON line (sizes, reference/FP32 divergence). No downloads, no weights."""
import json, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import kda_scale as K

d_k, d_v, tokens, heads, bits, seed = map(int, sys.argv[1:7]); out = sys.argv[7]
t0 = time.monotonic()
try:
    B, report = K.build(seed, d_k, d_v, tokens, heads, bits)
except K.Overflow as e:
    print(json.dumps(dict(d_k=d_k, d_v=d_v, tokens=tokens, heads=heads, bits=bits, seed=seed, overflow=str(e),
                          columns=K.columns_formula(d_k, d_v, tokens, heads, bits))))
    sys.exit(3)
sizes = K.write_fixture(B, out, dict(d_k=d_k, d_v=d_v, tokens=tokens, heads=heads, bits=bits))
assert sizes['columns'] == K.columns_formula(d_k, d_v, tokens, heads, bits), 'column formula'
print(json.dumps(dict(d_k=d_k, d_v=d_v, tokens=tokens, heads=heads, bits=bits, seed=seed, gen_seconds=round(time.monotonic() - t0, 3), **sizes, **report)))
