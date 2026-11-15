#!/usr/bin/env python3
"""Unit checks before the registered run (PREREG "Setup"), synthetic arrays only (numpy default_rng(0)).

1. M31-S equals PR #138's mlp_int bit for bit where every gw is a multiple of 2^4 inside the table domain [-2^15, 2^15):
   (a) every table row: silu_exact(16 (i - 2048)) == TS[i] for i in 0..4095 (exhaustive);
   (b) whole function on synthetic arrays built so that gw is on the grid and in the domain;
   (c) power check: off the grid or outside the domain the two do differ somewhere.
2. M31-W equals mlp_int bit for bit when the float weights are exact at their exponent (W = k / 2^e, |k| <= 4095, with
   max |k| chosen so that PR #138's exponent() returns e), on synthetic arrays with the real rms0 and a random gain.
Writes unit_checks.json next to this file (or to argv[1]). Exit 1 if a required equality fails.
"""
import json, sys
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import mlp_stage as S

M, F = S.M, S.F
FB = S.FB
out = {}

# ---- 1a exhaustive table rows
i = np.arange(4096, dtype=np.float64)
gw_grid = 16.0 * (i - 2048)
se = S.silu_exact(gw_grid)
diff = np.where(se != S.TS)[0]
out["1a_table_rows"] = dict(rows=4096, equal_rows=int(4096 - diff.size), differing_rows=[int(v) for v in diff[:50]],
                           differing_detail=[dict(i=int(k), gw=float(gw_grid[k]), table=float(S.TS[k]), exact=float(se[k])) for k in diff[:50]])

# ---- 1b whole function, gw on the grid and in the domain
rng = np.random.default_rng(0)
T, K, N = 7, 64, 96
gain = rng.normal(size=K) * 0.1


def setup_on_grid():
    # integer m (multiples of 16 so that gw = m . Wg is a multiple of 16 with ex_g = 0), mf = m / 2^12 exactly
    # rms0 is the identity for this check only (the norm is not part of the stage under test), restored after
    m = 16.0 * rng.integers(-6, 7, size=(T, K)).astype(np.float64)
    Wg = rng.integers(-2, 3, size=(N, K)).astype(np.float64)
    Wu = rng.integers(-300, 301, size=(N, K)).astype(np.float64)
    Wd = rng.integers(-4095, 4096, size=(K, N)).astype(np.float64)
    return m / 2.0 ** FB, Wg, Wu, Wd


mf, Wg, Wu, Wd = setup_on_grid()
L = {"post_attention_layernorm.weight": None, "mlp.gate_proj.weight": Wg, "mlp.up_proj.weight": Wu, "mlp.down_proj.weight": Wd}
ex = dict(g=0, u=3, d=5)
saved = F.rms0
F.rms0 = lambda x, w: x
try:
    d0, st0 = M.mlp_int(L, mf, ex)
    d1, st1 = S.mlp_int_S(L, mf, ex)
    gw = np.floor((np.rint(mf * 2 ** FB) @ Wg.T) / 2 ** ex["g"])
    on_grid = bool(np.all(gw % 16 == 0)); in_dom = bool(np.all((gw >= -2 ** 15) & (gw < 2 ** 15)))
    out["1b_function_on_grid"] = dict(gw_on_grid=on_grid, gw_in_domain=in_dom, gw_max_abs=float(np.abs(gw).max()),
                                      n_hidden=int(gw.size), bit_equal=bool(np.array_equal(d0, d1)),
                                      sat_counts_equal=(st0["n_silu_sat_lo"], st0["n_silu_sat_hi"]) == (st1["n_silu_sat_lo"], st1["n_silu_sat_hi"]))
    # ---- 1c power: off-grid (ex_g = 0, m not multiples of 16) and out of domain (one big gate row)
    m2 = rng.integers(-2000, 2001, size=(T, K)).astype(np.float64)
    Wg2 = rng.integers(-40, 41, size=(N, K)).astype(np.float64)
    L2 = dict(L, **{"mlp.gate_proj.weight": Wg2})
    a, _ = M.mlp_int(L2, m2 / 2.0 ** FB, ex); b, stb = S.mlp_int_S(L2, m2 / 2.0 ** FB, ex)
    out["1c_power_offgrid_and_outside"] = dict(differ=bool(not np.array_equal(a, b)), silu_domain_exits=stb["n_silu_sat_lo"] + stb["n_silu_sat_hi"])
finally:
    F.rms0 = saved

# ---- 2 float weights exact at their exponent
T2, K2, N2 = 9, 256, 128
x = rng.normal(size=(T2, K2)) * 3.0
gain2 = rng.normal(size=K2) * 0.2
res2 = {}
WF, WI, EX = {}, {}, {}
for k, n, e in (("g", "gate", 13), ("u", "up", 12), ("d", "down", 11)):
    shape = (N2, K2) if k != "d" else (K2, N2)
    ki = rng.integers(-4095, 4096, size=shape).astype(np.float64)
    ki.flat[0] = 4095.0                                  # max |k| = 4095 so exponent(max|W|) = e exactly
    WF[k] = ki / 2.0 ** e
    EX[k] = M.exponent(float(np.abs(WF[k]).max()))
    WI[k] = WF[k].copy(); conv = M.to_int_inplace(WI[k])
    res2[k] = dict(e_set=e, e_exponent=EX[k], e_conv=conv["e"], int_equals_k=bool(np.array_equal(WI[k], ki)))
Lf = {"post_attention_layernorm.weight": gain2, "mlp.gate_proj.weight": WF["g"], "mlp.up_proj.weight": WF["u"], "mlp.down_proj.weight": WF["d"]}
Li = {"post_attention_layernorm.weight": gain2, "mlp.gate_proj.weight": WI["g"], "mlp.up_proj.weight": WI["u"], "mlp.down_proj.weight": WI["d"]}
dw, stw = S.mlp_W(Lf, x, EX)
di, sti = M.mlp_int(Li, x, EX)
keys = ["m", "gw", "u", "s", "h", "acc_down", "out", "n_silu_sat_lo", "n_silu_sat_hi", "n_h_ge_2e18"]
out["2_float_weights_exact"] = dict(weights=res2, bit_equal=bool(np.array_equal(dw, di)),
                                    stats_equal={kk: stw[kk] == sti[kk] for kk in keys},
                                    silu_domain_exits=sti["n_silu_sat_lo"] + sti["n_silu_sat_hi"])
# power: inexact float weights (perturbed off the 2^-e grid) must differ somewhere
Lp = dict(Lf, **{"mlp.gate_proj.weight": WF["g"] + rng.normal(size=WF["g"].shape) * 2.0 ** -(EX["g"] + 2)})
dp, _ = S.mlp_W(Lp, x, EX)
out["2_power_inexact_weights_differ"] = bool(not np.array_equal(dp, di))

req = [out["1b_function_on_grid"]["gw_on_grid"], out["1b_function_on_grid"]["gw_in_domain"], out["1b_function_on_grid"]["bit_equal"],
       out["1c_power_offgrid_and_outside"]["differ"],
       all(v["e_set"] == v["e_exponent"] == v["e_conv"] and v["int_equals_k"] for v in res2.values()),
       out["2_float_weights_exact"]["bit_equal"], out["2_power_inexact_weights_differ"]]
out["required_all_true"] = bool(all(req))
out["note"] = ("1a lists table rows where float64 silu disagrees with the pinned Q256 table (a disagreement would be a finding, "
               "not a fix). 1b runs the whole function with the norm replaced by the identity (check only).")
p = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE / "unit_checks.json"
p.write_text(json.dumps(out, indent=1) + "\n"); print(json.dumps(out, indent=1))
sys.exit(0 if out["required_all_true"] else 1)
