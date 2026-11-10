#!/usr/bin/env python3
"""Print closed-form column counts / log-lengths for the sweep grid (no fixtures generated)."""
import math, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import kda_scale as K
for bits in (4, 8, 12, 16):
    for d in (2, 4, 8, 16, 32, 64, 128):
        row = []
        for t in (1, 2, 4, 8):
            n = K.columns_formula(d, d, t, 1, bits)
            row.append(f'T{t}:{n}(L{max(7, math.ceil(math.log2(n)))})')
        print(f'bits={bits} d={d}', ' '.join(row))
n = K.columns_formula(128, 128, 1, 64, 12)
print('GLM layer 64 heads x 128x128, 1 token, 12 bits:', n, 'log2', math.log2(n))
