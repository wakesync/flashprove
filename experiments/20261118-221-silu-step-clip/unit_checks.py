#!/usr/bin/env python3
"""Unit checks U1, U2 (PREREG "Unit checks"), synthetic arrays only (numpy default_rng(0)). U3 (fixture) is in
silu_step_clip.py fixture.

U1: M31-C's s == M31's s (table) bit for bit for every gw in D = [-2^15, 2^15); == M31-S's s (silu_exact) outside D.
U2: M31-T's s == M31-S's s bit for bit for every gw in D; outside D it == silu_exact(clip(gw)), i.e. it differs from
    M31-S only through the clip.
Power checks: inside D off the 2^4 grid, M31-T differs from M31 somewhere (the step is real); outside D, M31-C differs
from M31 somewhere (the clip is real).
Whole function: the arm MLP functions (silu_step_clip.mlp_arm) on a synthetic layer with integer weights reproduce
PR #138 mlp_int / PR #202 mlp_int_S bit for bit where the relations say they must (gw all inside D, on and off the grid;
gw with exits).
Writes unit_checks.json next to this file (or argv[1]). Exit 1 if a required check fails.
"""
import json, sys
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import silu_step_clip as A

S, M, F = A.S, A.M, A.F
LO, HI = A.LO, A.HI
rng = np.random.default_rng(0)
out = {}

# ---- elementwise, synthetic integer gw
parts = [rng.integers(LO, HI, size=200000),                       # inside D, mostly off grid
         16 * rng.integers(LO // 16, HI // 16, size=20000),         # inside D on the 2^4 grid
         np.arange(LO - 40, LO + 40), np.arange(HI - 40, HI + 40),  # both edges
         rng.integers(-2 ** 22, LO, size=20000),                    # below D
         rng.integers(HI, 2 ** 22, size=20000)]                     # above D
gw = np.concatenate(parts).astype(np.float64)
sc, st = A.s_clip_removed(gw), A.s_step_removed(gw)
rel = A.u_relations(gw, sc, st)
inside = (gw >= LO) & (gw < HI)
s_m31 = A.s_table(gw); s_s = S.silu_exact(gw)
rel["power_step_real_T_vs_M31_inside_differ"] = int((st[inside] != s_m31[inside]).sum())
rel["power_clip_real_C_vs_M31_outside_differ"] = int((sc[~inside] != s_m31[~inside]).sum())
rel["low_edge_M31_vs_T_outside_differ"] = int((st[gw < LO] != s_m31[gw < LO]).sum())
rel["high_edge_TS4095"] = float(S.TS[4095]); rel["high_edge_T"] = float(S.silu_exact(np.array([HI - 1.0]))[0])
rel["high_edge_M31_vs_T_outside_differ"] = int((st[gw >= HI] != s_m31[gw >= HI]).sum())
out["elementwise"] = rel

# ---- whole function on a synthetic layer (rms0 replaced by identity for this check only)
T, K, N = 7, 64, 96
saved = F.rms0
F.rms0 = lambda x, w: x
wf = {}
try:
    for name, gscale in (("inside_on_grid", 2), ("inside_off_grid", 3), ("with_exits", 600)):
        if name == "inside_on_grid":
            m = 16.0 * rng.integers(-6, 7, size=(T, K)).astype(np.float64)
        else:
            m = rng.integers(-60, 61, size=(T, K)).astype(np.float64)
        Wg = rng.integers(-gscale, gscale + 1, size=(N, K)).astype(np.float64)
        Wu = rng.integers(-300, 301, size=(N, K)).astype(np.float64)
        Wd = rng.integers(-4095, 4096, size=(K, N)).astype(np.float64)
        L = {"post_attention_layernorm.weight": None, "mlp.gate_proj.weight": Wg, "mlp.up_proj.weight": Wu, "mlp.down_proj.weight": Wd}
        ex = dict(g=0, u=3, d=5)
        x = m / 2.0 ** S.FB
        d31, st31 = M.mlp_int(L, x, ex)
        dS, stS = S.mlp_int_S(L, x, ex)
        dC, stC = A.mlp_arm("M31-C")(L, x, ex)
        dT, stT = A.mlp_arm("M31-T")(L, x, ex)
        dM, _ = A.mlp_arm("M31")(L, x, ex)
        dSS, _ = A.mlp_arm("M31-S")(L, x, ex)
        g = np.floor((np.rint(x * 2 ** S.FB) @ Wg.T) / 2 ** ex["g"])
        exits = int(((g < LO) | (g >= HI)).sum())
        wf[name] = dict(exits=exits, gw_max_abs=float(np.abs(g).max()), on_grid=bool(np.all(g % 16 == 0)),
                        arm_M31_equals_mlp_int=bool(np.array_equal(dM, d31)), arm_M31S_equals_mlp_int_S=bool(np.array_equal(dSS, dS)),
                        C_equals_M31=bool(np.array_equal(dC, d31)), C_equals_S=bool(np.array_equal(dC, dS)),
                        T_equals_S=bool(np.array_equal(dT, dS)), T_equals_M31=bool(np.array_equal(dT, d31)),
                        exit_counts_equal=all((a["n_silu_sat_lo"], a["n_silu_sat_hi"]) == (st31["n_silu_sat_lo"], st31["n_silu_sat_hi"]) for a in (stS, stC, stT)))
finally:
    F.rms0 = saved
out["whole_function"] = wf

e = out["elementwise"]
req = {
    "U1_inside": e["U1_in_mismatch"] == 0 and e["n_inside"] > 0,
    "U1_outside": e["U1_out_mismatch"] == 0 and e["n_outside"] > 0,
    "U2_inside": e["U2_in_mismatch"] == 0,
    "U2_outside_is_clipped_exact": e["U2_out_mismatch_vs_clipped"] == 0,
    "power_step_real": e["power_step_real_T_vs_M31_inside_differ"] > 0,
    "power_clip_real": e["power_clip_real_C_vs_M31_outside_differ"] > 0,
    "wrappers_reproduce_pr138_pr202": all(v["arm_M31_equals_mlp_int"] and v["arm_M31S_equals_mlp_int_S"] for v in wf.values()),
    "inside_on_grid_all_equal": wf["inside_on_grid"]["exits"] == 0 and wf["inside_on_grid"]["on_grid"] and wf["inside_on_grid"]["C_equals_M31"] and wf["inside_on_grid"]["T_equals_S"] and wf["inside_on_grid"]["T_equals_M31"],
    "inside_off_grid_C_is_M31_T_is_S": wf["inside_off_grid"]["exits"] == 0 and wf["inside_off_grid"]["C_equals_M31"] and wf["inside_off_grid"]["T_equals_S"] and not wf["inside_off_grid"]["T_equals_M31"],
    "with_exits_has_exits": wf["with_exits"]["exits"] > 0,
    "exit_counters_identical_across_arms": all(v["exit_counts_equal"] for v in wf.values()),
}
out["required"] = req
out["required_all_true"] = bool(all(req.values()))
out["note"] = ("Synthetic arrays only, numpy default_rng(0). The whole-function cases replace rms0 by the identity (the norm is "
               "not part of the stage under test). 'with_exits' has no required equality: there both arms change s outside D, "
               "and C/T vs M31/S are reported as found.")
p = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE / "unit_checks.json"
p.write_text(json.dumps(out, indent=1) + "\n"); print(json.dumps(out, indent=1))
sys.exit(0 if out["required_all_true"] else 1)
