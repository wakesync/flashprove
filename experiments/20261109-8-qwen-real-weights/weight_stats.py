#!/usr/bin/env python3
"""Layer-0 real-weight statistics vs the synthetic assumptions of M1/M1b/M2 (head_reference.gen, reference.Head).
Writes runs/weight-stats.json. Usage: weight_stats.py <cache_dir> <ckpt>"""
import json, sys
import numpy as np
import real_head as RH

L, emb = RH.load_layer(sys.argv[1], sys.argv[2])
A = np.exp(L["linear_attn.A_log"]); dtb = L["linear_attn.dt_bias"]; cw = L["linear_attn.conv1d.weight"][:, 0, :]
gain = L["linear_attn.norm.weight"]; ln = L["input_layernorm.weight"]
dt = np.logaddexp(0, dtb)                                    # softplus(dt_bias): the step size at a = 0
taps_q12 = np.rint(cw * 4096)
E = np.stack(list(emb.values()))
def q(x): return [float(v) for v in np.quantile(x, [0, .01, .5, .99, 1])]
out = dict(
    A=dict(quantiles=q(A), synthetic="U(1, 16)"),
    dt_bias=dict(quantiles=q(dtb), synthetic="log(expm1(dt)), dt log-uniform in [1e-3, 1e-1] (about -6.9 .. -2.25)"),
    softplus_dt_bias=dict(quantiles=q(dt)),
    decay_at_a0=dict(quantiles=q(np.exp(-A * dt)), note="exp(-A softplus(dt_bias)), the decay for in_proj_a output 0"),
    conv_taps=dict(quantiles=q(cw), abs_max=float(np.abs(cw).max()), synthetic="U(-0.5, 0.5)",
                   fraction_rounding_to_zero_at_2_12=float((taps_q12 == 0).mean()),
                   rel_rounding_error_rms_at_2_12=float(np.linalg.norm(taps_q12 / 4096 - cw) / np.linalg.norm(cw)),
                   rel_rounding_error_rms_at_2_16=float(np.linalg.norm(np.rint(cw * 65536) / 65536 - cw) / np.linalg.norm(cw))),
    norm_gain=dict(quantiles=q(gain), synthetic="1.0"),
    input_layernorm_1_plus_w=dict(quantiles=q(1 + ln)),
    embedding_rows=dict(n_rows=int(E.shape[0]), abs_max=float(np.abs(E).max()), rms=float(np.sqrt((E ** 2).mean()))),
)
json.dump(out, open(RH.HERE / "runs" / "weight-stats.json", "w"), indent=1)
print(json.dumps(out, indent=1))
