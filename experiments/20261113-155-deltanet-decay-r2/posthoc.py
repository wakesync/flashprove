#!/usr/bin/env python3
"""POST HOC, descriptive (PREREG.md Amendment A3): written after the registered verdicts were seen. No threshold,
no verdict. For the table-chain arms U1, U2, U3, per (layer, head, prompt) cell: the largest per-token error
|a_arm - a| over the tokens with float64 g < 1 and over the tokens with g >= 1 separately, the number of tokens with
g >= 1, and g and x at the token of the largest error.

usage: posthoc.py <ar_dir> <out_dir> <fine20.npy>     -> <out_dir>/gband.csv.gz

The arm code (decay_r2.py) and the input checks (registered sha256 list, runs/provenance.json) are used unchanged.
"""
import sys
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import decay_r2 as R
DT, SU = R.DT, R.SU

ARMS = ("U1", "U2", "U3")


def band_rows(arm, layer, pid, ar, A, dtb, T):
    x, g, a = DT.float_decay(ar, A, dtb)
    aa, rej = R.arm_decay(ar, A, dtb, arm, T)
    d = np.abs(aa - a); hi = g >= 1.0; out = []
    for h in range(len(A)):
        dl, dh = d[~hi[:, h], h], d[hi[:, h], h]; t = int(np.argmax(d[:, h]))
        out.append(dict(arm=arm, layer=layer, head=h, prompt=pid, T=ar.shape[0], n_g_ge_1=int(hi[:, h].sum()),
                        e_tok_max_g_lt_1="" if dl.size == 0 else float(dl.max()), e_tok_max_g_ge_1="" if dh.size == 0 else float(dh.max()),
                        e_tok_max=float(d[:, h].max()), g_at_max=float(g[t, h]), x_at_max=float(x[t, h])))
    return out


def main(ar_dir, out_dir, fine20):
    layers, digest = R._open(ar_dir, False)        # registered suite, registered bytes, provenance passed
    T = R.load_tables(fine20); od = Path(out_dir); od.mkdir(parents=True, exist_ok=True); rows = []
    for i, A, dtb, ars in layers:
        for pid in sorted(ars):
            for arm in ARMS: rows += band_rows(arm, i, pid, ars[pid], A, dtb, T)
    R.wcsv(od / "gband.csv.gz", rows); print("gband rows", len(rows))


if __name__ == "__main__":
    try:
        main(*sys.argv[1:4])
    except SU.Incomplete as e:
        print("posthoc.py: REFUSED: " + str(e), file=sys.stderr); sys.exit(2)
