"""Registered fixtures F01-F45 (PREREG.md). Every number here is synthetic test input
unless a main path is named; synthetic numbers are never production forecasts."""
from fractions import Fraction as Fr

import worksheet as W

SYN = "synthetic:test"


def v(value, unit, kind="synthetic", source=SYN):
    return {"value": str(value), "unit": unit, "kind": kind, "source": source}


def unknown(unit, source="unknown: no Qwen proof or receipt path exists on main"):
    return {"value": None, "unit": unit, "kind": "unknown", "source": source}


def gpu(x):
    return v(x, "gpu_s_per_request")


BASE_COSTS = {"I": gpu(1), "P": gpu(100), "C": gpu("1/100"), "A": gpu(0), "F": gpu(0)}

# ---------------------------------------------------------------- formula fixtures
FORMULA = [
    ("F01", lambda: W.bernoulli_fixed_d(Fr(0), 5), Fr(0)),
    ("F02", lambda: W.bernoulli_fixed_d(Fr(1), 5), Fr(1)),
    ("F03", lambda: W.bernoulli_fixed_d(Fr(1, 10), 0), Fr(0)),
    ("F04", lambda: W.bernoulli_fixed_d(Fr(1, 10), 1), Fr(1, 10)),
    ("F05", lambda: W.bernoulli_fixed_d(Fr(1, 2), 3), Fr(7, 8)),
    ("F06", lambda: W.iid_invalidity(Fr(1, 10), Fr(1, 5), 2), Fr(99, 2500)),
    ("F07", lambda: W.iid_invalidity(Fr(0), Fr(1, 2), 10), Fr(0)),
    ("F08", lambda: W.iid_invalidity(Fr(1), Fr(1), 3), Fr(1)),
    ("F09", lambda: W.iid_invalidity(Fr(1, 2), Fr(0), 7), Fr(0)),
    ("F10", lambda: W.no_replacement(1000, 10, 1), Fr(1, 100)),
    ("F11", lambda: W.no_replacement(1000, 10, 0), Fr(0)),
    ("F12", lambda: W.no_replacement(10, 3, 10), Fr(1)),
    ("F13", lambda: W.no_replacement(10, 0, 4), Fr(0)),
    ("F14", lambda: W.no_replacement(10, 10, 1), Fr(1)),
    ("F15", lambda: W.no_replacement(12, 3, 3), Fr(34, 55)),
    ("F16", lambda: W.no_replacement(12, 3, 6), Fr(10, 11)),
    ("F17", lambda: W.no_replacement_q(2, 1, 1, Fr(1, 2)), Fr(1, 4)),
    ("F18", lambda: W.no_replacement_q(10, 10, 3, Fr(0)), Fr(0)),
    ("F19", lambda: W.soundness_lower_bound(Fr(1, 100), Fr(1, 50)), Fr(0)),
]

# ---------------------------------------------------------------- #84 cells
# Published strings: research/sampled-audit/TABLES.md on main (rounding report.py:28,40).
CELLS84 = [
    ("F20", 1000, 100, 5, "41.0168%"),
    ("F21", 1000, 100, 10, "65.3072%"),
    ("F22", 1000, 10, 50, "40.2689%"),
    ("F23", 1000, 10, 100, "65.3072%"),
    ("F24", 64, 35, 1, "54.6875%"),
    ("F25", 64, 8, 4, "42.1933%"),
    ("F26", 256, 26, 16, "82.9485%"),
]


# ---------------------------------------------------------------- cost fixtures
def cost_ws(costs, p=None):
    return {"population": {"N": v(1000, "request")},
            "sampling": {"scheme": "bernoulli_p", "p": p or v("1/100", "request_fraction")},
            "costs": costs}


def with_costs(**over):
    c = dict(BASE_COSTS)
    c.update(over)
    return c


COST = [
    ("F27", cost_ws(with_costs()), "CONDITIONAL", [], {"cost_per_request": Fr(201, 100), "normalized_cost": Fr(201, 100), "synthetic": True}),
    ("F28", cost_ws({"R": v(100, "ratio"), "R_convention": "incremental", "R_unit_basis": "gpu_s/gpu_s",
                     "I": gpu(1), "C": gpu("1/100"), "A": gpu(0), "F": gpu(0)}),
     "CONDITIONAL", [], {"normalized_cost": Fr(201, 100)}),
    ("F29", cost_ws({"R": v(101, "ratio"), "R_convention": "total_audited_path", "R_unit_basis": "gpu_s/gpu_s",
                     "I": gpu(1), "C": gpu("1/100"), "A": gpu(0), "F": gpu(0)}),
     "CONDITIONAL", [], {"normalized_cost": Fr(201, 100)}),
    ("F30", cost_ws(with_costs(C=v("1/100", "usd_per_request"))), "MISSING INPUTS", ["UNIT_MISMATCH"],
     {"cost_per_request": None, "normalized_cost": None}),
    ("F31", cost_ws(with_costs(C=v("1/100", "wall_s_per_request"))), "MISSING INPUTS", ["UNIT_MISMATCH"],
     {"cost_per_request": None, "normalized_cost": None}),
    ("F32", cost_ws(with_costs(P=unknown("gpu_s_per_request"))), "MISSING INPUTS", ["UNKNOWN_COST"],
     {"cost_per_request": None, "unknowns": ["costs.P"]}),
    ("F33", cost_ws(with_costs(C=unknown("gpu_s_per_request"))), "MISSING INPUTS", ["UNKNOWN_COST"],
     {"cost_per_request": None, "unknowns": ["costs.C"]}),
    ("F34", cost_ws(with_costs(I={"value": "1", "unit": "gpu_s_per_request", "kind": "synthetic"})),
     "MISSING INPUTS", ["NO_PROVENANCE"], {"cost_per_request": None}),
    # 0.46 = experiments/20261112-7-plain-inference-baseline/RESULTS.md:84 (decode at batch 1,
    # route wall seconds of one stream on a shared card). Refused as GPU-cost R.
    ("F35", cost_ws({"R": v("23/50", "ratio", kind="conditional_calculation",
                            source="experiments/20261112-7-plain-inference-baseline/RESULTS.md:84"),
                     "R_convention": "incremental", "R_unit_basis": "wall_s_stream",
                     "I": gpu(1), "C": gpu("1/100"), "A": gpu(0), "F": gpu(0)}),
     "MISSING INPUTS", ["DECODE_RATIO_NOT_GPU_COST"], {"normalized_cost": None}),
    ("F36", cost_ws(with_costs(), p=v("1/100", "token_fraction")), "MISSING INPUTS",
     ["TOKEN_FRACTION_NOT_REQUEST_FRACTION"], {"cost_per_request": None}),
]


def evaluate_costs_only(ws):
    ctx = W.Ctx()
    n = W.num(ctx, ws, "population.N", {"request"})
    p = W.num(ctx, ws, "sampling.p", {"request_fraction"})
    cpr, norm = W.eval_costs(ctx, ws, n, p)
    if ctx.codes & W.MISSING_CODES:
        verdict, cpr, norm = "MISSING INPUTS", None, None
    else:
        verdict = "CONDITIONAL"
    return {"verdict": verdict, "codes": sorted(ctx.codes), "cost_per_request": cpr,
            "normalized_cost": norm, "synthetic": bool(ctx.synthetic),
            "unknowns": sorted(ctx.unknowns)}


# ---------------------------------------------------------------- policy fixtures
def policy(cls, **over):
    ws = {
        "policy_class": cls,
        "relation": "synthetic test relation: pinned integer-model exact match (test only)",
        "population": {"definition": "synthetic: every token-delivering request in one epoch",
                       "N": v(1000, "request"), "epoch_rule": "ingress sequence index"},
        "sampling": {"scheme": "bernoulli_p", "p": v("1/2", "request_fraction"),
                     "schedule": "fixed_in_advance"},
        "invalidity": {"D": v(3, "request")},
        "soundness_treatment": {"text": "synthetic: perfect rejection of invalid units (q=1)"},
        "costs": dict(BASE_COSTS),
        "latency": {"deadline_policy": "synthetic", "verify_before_action": False,
                    "timeout_policy": "timeout is an audit failure, not a wrong answer"},
        "targets": {"desired_miss_probability": v("1/4", "probability")},
        "claims": {"individual_guarantee": False, "hardware_trust_assumption": ""},
    }
    for k, val in over.items():
        ws[k] = val
    return ws


FLEET = "fleet_monitoring_after_release"
VIP = "vendor_independent_proof_irreversible"
HW = "hardware_trusting_immediate_with_later_review"
HW_CLAIMS = {"individual_guarantee": False,
             "hardware_trust_assumption": "synthetic test: attested hardware serves immediately"}
NOREPL = {"scheme": "fixed_size_no_replacement_m", "m": v(100, "request"), "schedule": "fixed_in_advance"}

POLICY = [
    ("F37", policy(FLEET, deterrence={"enforceable_loss": v(8, "loss_unit"), "cheating_gain": v(5, "loss_unit"),
                                      "behavioral_assumptions": "synthetic: risk-neutral sustained cheater"}),
     "CONDITIONAL", [], {"coverage": Fr(7, 8), "miss": Fr(1, 8)}),
    ("F38", policy(FLEET, targets={"desired_miss_probability": v("1/10", "probability")}),
     "INELIGIBLE", ["MISS_ABOVE_TARGET"], {"coverage": Fr(7, 8)}),
    ("F39", policy(FLEET, sampling={"scheme": "bernoulli_p", "p": v("1/2", "request_fraction"),
                                    "schedule": "outcome_adaptive", "lifetime_formula_requested": True}),
     "INELIGIBLE", ["ADAPTIVE_NOT_IID"], {"coverage": None}),
    ("F40", policy(VIP, sampling={"scheme": "bernoulli_p", "p": v(1, "request_fraction"), "schedule": "fixed_in_advance"},
                   latency={"verify_before_action": True}, invalidity={}),
     "CONDITIONAL", [], {"coverage": Fr(1), "assumption_contains": "only under the selected relation"}),
    ("F41", policy(VIP, sampling={"scheme": "bernoulli_p", "p": v("99/100", "request_fraction"), "schedule": "fixed_in_advance"},
                   latency={"verify_before_action": True}, invalidity={}),
     "INELIGIBLE", ["SUBSAMPLE_NOT_PROOF"], {}),
    ("F42", policy(VIP, sampling={"scheme": "bernoulli_p", "p": v(1, "request_fraction"), "schedule": "fixed_in_advance"},
                   latency={"verify_before_action": False}, invalidity={}),
     "INELIGIBLE", ["VERIFY_AFTER_ACTION"], {}),
    ("F43", policy(HW, sampling=dict(NOREPL), invalidity={"D": v(10, "request")},
                   targets={"desired_miss_probability": v("1/2", "probability")},
                   claims=dict(HW_CLAIMS, individual_guarantee=True)),
     "INELIGIBLE", ["SUBSAMPLE_NOT_PROOF"], {}),
    ("F44", policy(HW, sampling=dict(NOREPL), invalidity={"D": v(10, "request")},
                   targets={"desired_miss_probability": v("1/2", "probability")}, claims=dict(HW_CLAIMS),
                   distinguishability={"q": v("1/2", "probability"), "q_source": "changed_weight_count"}),
     "MISSING INPUTS", ["Q_INFERRED_FROM_WEIGHTS"], {}),
    ("F45", policy(HW, sampling=dict(NOREPL), invalidity={"D": v(10, "request")},
                   targets={"desired_miss_probability": v("1/2", "probability")}, claims=dict(HW_CLAIMS),
                   observations=[{"type": "timeout", "counted_as": "wrong_answer"}]),
     "MISSING INPUTS", ["TIMEOUT_NOT_PROOF"], {}),
]
