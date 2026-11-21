#!/usr/bin/env python3
"""PREREG decode checks D1-D4 on layer 0's NVFP4 experts (no metric, no prompt). Writes runs/decode-check.json.
Usage: decode_check.py <tensor dir> <out.json>"""
import json, os, sys
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import inkcore as ic

P = "model.llm.layers.0.mlp.experts."


def load(tdir, name):
    return open(os.path.join(tdir, P + name + ".bin"), "rb").read()


def check(tdir, kind, rows, cols):
    codes = np.frombuffer(load(tdir, kind + "_weight"), dtype=np.uint8).reshape(128, rows, cols // 2)
    scales = np.frombuffer(load(tdir, kind + "_weight_scale"), dtype=np.uint8).reshape(128, rows, cols // 16)
    amax = ic.f32(load(tdir, kind + "_weight_amax"), (128,))
    den = ic.f32(load(tdir, kind + "_weight_outer_scale_denominator"), (1,))[0]
    sv = ic.F8[scales]
    d2_nan = int(np.isnan(sv).sum())
    d2_neg = int((sv < 0).sum())
    ratio = []
    for e in range(128):
        w = ic.nvfp4_decode(codes[e], scales[e], amax[e] / den)
        ratio.append(float(np.max(np.abs(w)) / amax[e]))
    ratio = np.array(ratio)
    sc_vals = sv[np.isfinite(sv)]
    return dict(kind=kind, codes_shape=list(codes.shape), scale_shape=list(scales.shape),
                d1_blocks_ok=bool(cols // 16 == scales.shape[2] and cols // 2 == codes.shape[2]),
                d2_nan_scales=d2_nan, d2_negative_scales=d2_neg,
                d3_ratio_min=float(ratio.min()), d3_ratio_max=float(ratio.max()),
                d3_ratio_median=float(np.median(ratio)),
                d3_all_in_quarter_to_4=bool(((ratio >= 0.25) & (ratio <= 4)).all()),
                d4_outer_scale_denominator=float(den), amax_min=float(amax.min()), amax_max=float(amax.max()),
                block_scale_min=float(sc_vals.min()), block_scale_max=float(sc_vals.max()),
                block_scale_zero_frac=float((sc_vals == 0).mean()))


def main():
    tdir, out = sys.argv[1], sys.argv[2]
    r = dict(w13=check(tdir, "w13", 2304, 2304), w2=check(tdir, "w2", 2304, 1152))
    r["pass"] = all(v["d1_blocks_ok"] and v["d2_nan_scales"] == 0 and v["d2_negative_scales"] == 0
                    and v["d3_all_in_quarter_to_4"] for v in (r["w13"], r["w2"]))
    json.dump(r, open(out, "w"), indent=1)
    print(json.dumps(r, indent=1))


if __name__ == "__main__":
    main()
