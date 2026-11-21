"""Fixtures F46-F135, registered in PREREG.md Amendment 1 after round 1 review, and the
Amendment 2 outcomes for F37-F45. Every number here is synthetic test input, never a forecast.
The original fixtures F01-F45 stay in fixtures.py, unchanged."""
import copy
from fractions import Fraction as Fr

import fixtures as X

v = X.v
MI = "MISSING INPUTS"
COND = "CONDITIONAL"
INEL = "INELIGIBLE"
FIXED = "fixed_size_no_replacement_m"


def unk(unit):
    return {"value": None, "unit": unit, "kind": "unknown", "source": "unknown: test"}


def base():
    """B: a complete fleet-monitoring worksheet (Amendment 1)."""
    return {
        "policy_class": X.FLEET,
        "relation": "synthetic test relation: pinned integer-model exact match (test only)",
        "population": {"definition": "synthetic: every token-delivering request in one epoch",
                       "N": v(12, "request"), "epoch_rule": "ingress sequence index"},
        "sampling": {"scheme": "bernoulli_p", "p": v("1/3", "request_fraction"),
                     "schedule": "fixed_in_advance"},
        "invalidity": {"D": v(2, "request")},
        "soundness_treatment": {"text": "synthetic: perfect rejection of invalid units"},
        "costs": {"I": v(2, "gpu_s_per_request"), "P": v(9, "gpu_s_per_request"),
                  "C": v("1/4", "gpu_s_per_request"), "A": v("1/8", "gpu_s_per_request"),
                  "F": v(6, "gpu_s_per_epoch")},
        "latency": {"deadline_policy": "synthetic: five minutes", "verify_before_action": False,
                    "timeout_policy": "timeout is an audit failure, not a wrong answer"},
        "targets": {"desired_miss_probability": v("1/2", "probability")},
        "deterrence": {"state": "modeled", "enforceable_loss": v(10, "usd"),
                       "cheating_gain": v(1, "usd"),
                       "behavioral_assumptions": "synthetic: risk-neutral sustained cheater"},
        "claims": {"individual_guarantee": False},
    }


def vip():
    """V: B as the vendor-independent class, p=1, verify before action."""
    b = base()
    b["policy_class"] = X.VIP
    b["sampling"]["p"] = v(1, "request_fraction")
    b["latency"]["verify_before_action"] = True
    del b["invalidity"]
    del b["targets"]
    return b


def put(path, val):
    def f(b):
        cur = b
        for key in path[:-1]:
            cur = cur.setdefault(key, {})
        cur[path[-1]] = val
    return f


def drop(path):
    def f(b):
        cur = b
        for key in path[:-1]:
            cur = cur[key]
        del cur[path[-1]]
    return f


def fixed(m):
    return put(["sampling"], {"scheme": FIXED, "m": v(m, "request"), "schedule": "fixed_in_advance"})


def iid(f):
    return put(["invalidity"], {"f": v(f, "request_fraction")})


def ratio(r, conv, f_unit="gpu_s_per_epoch", keep_p=False):
    def f(b):
        c = b["costs"]
        if not keep_p:
            del c["P"]
        c["R"] = v(r, "ratio")
        c["R_convention"] = conv
        c["R_unit_basis"] = "gpu_s/gpu_s"
        c["F"] = v(6, f_unit)
    return f


def make(builder, *changes):
    b = builder()
    for ch in changes:
        ch(b)
    return b


NOT_MODELED = {"state": "not_modeled"}


def twin(fid):
    """T37-T45: the registered input of F37-F45, plus only what the completed schema needs."""
    ws = copy.deepcopy(next(row[1] for row in X.POLICY if row[0] == fid))
    if fid == "F37":
        ws["deterrence"] = {"state": "modeled", "enforceable_loss": v(8, "usd"),
                            "cheating_gain": v(5, "usd"),
                            "behavioral_assumptions": "synthetic: risk-neutral sustained cheater"}
    else:
        ws["deterrence"] = dict(NOT_MODELED)
    if fid in ("F40", "F41", "F42"):
        ws["latency"]["deadline_policy"] = "synthetic"
    return ws


def qd(**kw):
    d = {"q": v(0, "probability"), "K": v(2, "request"), "q_source": "policy_supplied"}
    d.update(kw)
    return {k: val for k, val in d.items() if val is not None}


def dist(**kw):
    return put(["distinguishability"], qd(**kw))


def eps(x):
    return put(["soundness_treatment", "epsilon"], v(x, "probability"))


def obs(kind, counted):
    return put(["observations"], [{"type": kind, "counted_as": counted}])


def wall_costs(b):
    b["costs"] = {k: v(x, "wall_s_per_request")
                  for k, x in (("I", 2), ("P", 9), ("C", "1/4"), ("A", "1/8"), ("F", 0))}


QF = fixed(4)          # "q-fixed": B with fixed-size m=4, D=2
UR = ["UNKNOWN_REQUIRED"]
MISSING = ["MISSING_INPUT"]
OOR = ["OUT_OF_RANGE"]
NB = ["NOT_BOOLEAN"]
QU = ["Q_UNSUPPORTED"]
MAT = ["MISS_ABOVE_TARGET"]
P59 = {"coverage": Fr(5, 9)}

# (id, worksheet, verdict, codes, registered values)
R1 = [
    # controls and completed twins of F37-F45
    ("F46", make(base), COND, [], {"coverage": Fr(5, 9), "miss": Fr(4, 9), "supported_miss": Fr(4, 9),
                                   "cost_per_request": Fr(47, 8), "normalized_cost": Fr(47, 16),
                                   "deterrence_product": Fr(50, 9)}),
    ("F47", twin("F37"), COND, [], {"coverage": Fr(7, 8), "miss": Fr(1, 8), "deterrence_product": Fr(7)}),
    ("F48", twin("F38"), INEL, MAT, {"coverage": Fr(7, 8)}),
    ("F49", twin("F39"), INEL, ["ADAPTIVE_NOT_IID"], {"coverage": None}),
    ("F50", twin("F40"), COND, [], {"coverage": Fr(1), "assumption_contains": "only under the selected relation"}),
    ("F51", twin("F41"), INEL, ["SUBSAMPLE_NOT_PROOF"], {}),
    ("F52", twin("F42"), INEL, ["VERIFY_AFTER_ACTION"], {}),
    ("F53", twin("F43"), INEL, ["SUBSAMPLE_NOT_PROOF"], {}),
    ("F54", twin("F44"), MI, ["Q_INFERRED_FROM_WEIGHTS"], {}),
    ("F55", twin("F45"), MI, ["TIMEOUT_NOT_PROOF"], {}),
    # must-fix 1: required schema and unknowns
    ("F56", make(base, put(["sampling", "p"], unk("request_fraction"))), MI, UR, {}),
    ("F57", make(base, put(["targets", "desired_miss_probability"], unk("probability"))), MI, UR, {}),
    ("F58", make(base, put(["invalidity", "D"], unk("request"))), MI, UR, {}),
    ("F59", make(base, put(["invalidity", "D"], None)), MI, MISSING, {}),
    ("F60", make(base, put(["population", "N"], unk("request"))), MI, UR, {}),
    ("F61", make(base, drop(["population", "definition"])), MI, MISSING, {}),
    ("F62", make(base, drop(["latency", "deadline_policy"])), MI, MISSING, {}),
    ("F63", make(base, drop(["deterrence"])), MI, MISSING, {}),
    ("F64", make(base, drop(["deterrence", "behavioral_assumptions"])), MI, MISSING, {}),
    ("F65", make(base, drop(["deterrence", "state"])), MI, MISSING, {}),
    ("F66", make(base, put(["deterrence"], dict(NOT_MODELED))), COND, [], {"coverage": Fr(5, 9), "deterrence": None}),
    ("F67", make(base, fixed(3), iid("1/4")), MI, ["UNSUPPORTED_COMBINATION"], {}),
    ("F68", make(vip), COND, [], {"coverage": Fr(1), "normalized_cost": Fr(95, 16)}),
    ("F69", make(vip, put(["latency", "verify_before_action"], None)), MI, NB, {}),
    ("F70", make(vip, put(["latency", "verify_before_action"], "false")), MI, NB, {}),
    ("F71", make(base, put(["latency", "verify_before_action"], "false")), MI, NB, {}),
    ("F72", make(base, put(["claims", "individual_guarantee"], "yes")), MI, NB, {}),
    ("F73", make(base, obs("refusal", "wrong_answer")), MI, ["TIMEOUT_NOT_PROOF"], {}),
    ("F74", make(base, obs("outage", "audit_failure")), MI, ["BAD_OBSERVATION"], {}),
    ("F75", make(base, drop(["sampling", "schedule"])), MI, MISSING, {}),
    ("F76", make(base, obs("timeout", "audit_failure")), COND, [], dict(P59)),
    ("F77", make(base, put(["soundness_treatment", "epsilon"], unk("probability"))), MI, UR, {}),
    ("F78", make(base, put(["sampling"], ["bernoulli_p"])), MI, ["BAD_SECTION"], {}),
]

R1 += [
    # must-fix 2: numeric domains, checked before arithmetic; counts never truncated
    ("F79", make(base, put(["invalidity", "D"], v(13, "request"))), MI, OOR, {}),
    ("F80", make(base, put(["invalidity", "D"], v("5/2", "request"))), MI, ["NOT_INTEGER"], {}),
    ("F81", make(base, put(["invalidity", "D"], v(-1, "request"))), MI, OOR, {}),
    ("F82", make(base, put(["population", "N"], v(0, "request"))), MI, OOR, {}),
    ("F83", make(base, put(["population", "N"], v(-2, "request"))), MI, OOR, {}),
    ("F84", make(base, put(["population", "N"], v("25/2", "request"))), MI, ["NOT_INTEGER"], {}),
    ("F85", make(base, fixed(13)), MI, OOR, {}),
    ("F86", make(base, fixed(-1)), MI, OOR, {}),
    ("F87", make(base, fixed("7/2")), MI, ["NOT_INTEGER"], {}),
    ("F88", make(base, fixed(3), put(["invalidity", "D"], v(13, "request"))), MI, OOR, {}),
    ("F89", make(base, put(["sampling", "p"], v("-1/2", "request_fraction"))), MI, OOR, {}),
    ("F90", make(base, put(["sampling", "p"], v("3/2", "request_fraction"))), MI, OOR, {}),
    ("F91", make(base, iid(2)), MI, OOR, {}),
    ("F92", make(base, put(["targets", "desired_miss_probability"], v(2, "probability"))), MI, OOR, {}),
    ("F93", make(base, eps(-1)), MI, OOR, {}),
    ("F94", make(base, eps(2)), MI, OOR, {}),
    ("F95", make(base, put(["costs", "P"], v(-9, "gpu_s_per_request"))), MI, OOR, {}),
    ("F96", make(base, put(["costs", "I"], v(0, "gpu_s_per_request"))), MI, OOR, {}),
    ("F97", make(base, put(["costs", "P"], v("garbage", "gpu_s_per_request"))), MI, ["BAD_VALUE"], {}),
    ("F98", make(base, put(["costs", "P"], v("1/0", "gpu_s_per_request"))), MI, ["BAD_VALUE"], {}),
    ("F99", make(base, put(["sampling", "p", "value"], 0.1)), MI, ["BAD_VALUE"], {}),
    ("F100", make(base, put(["population", "N", "value"], 12)), MI, ["BAD_VALUE"], {}),
    ("F101", make(base, ratio(-1, "incremental")), MI, OOR, {}),
    ("F102", make(base, ratio("1/2", "total_audited_path")), MI, OOR, {}),
    ("F103", make(base, iid("1/4")), COND, [], {"coverage": Fr(5777672071535, 8916100448256)}),
    ("F104", make(base, QF), COND, [], {"coverage": Fr(19, 33), "miss": Fr(14, 33), "normalized_cost": Fr(47, 16)}),
    # must-fix 3: an explicit q is never dropped
    ("F105", make(base, dist()), MI, QU, {}),
    ("F106", make(base, QF, dist(q=unk("probability"))), MI, UR, {}),
    ("F107", make(base, QF, dist(K=None)), MI, QU, {}),
    ("F108", make(base, dist(q=v("1/100", "probability"), K=None)), MI, QU, {}),
    ("F109", make(base, QF, dist()), INEL, MAT, {"coverage": Fr(0), "miss": Fr(1)}),
    ("F110", make(base, QF, dist(q=v("1/2", "probability")),
                  put(["targets", "desired_miss_probability"], v("3/4", "probability"))),
     COND, [], {"coverage": Fr(41, 132), "miss": Fr(91, 132)}),
    ("F111", make(base, QF, dist(q=v("1/2", "probability"), K=v(3, "request"))), MI, QU, {}),
    ("F112", make(base, QF, dist(q=None)), MI, MISSING, {}),
    ("F113", make(vip, dist(q=v("1/2", "probability"))), MI, QU, {}),
    ("F114", make(base, QF, dist(q=v("3/2", "probability"))), MI, OOR, {}),
]

TGT = ["targets", "desired_miss_probability"]
R1 += [
    # must-fix 4: the soundness bound reaches the verdict
    ("F115", make(base, eps("1/2")), INEL, MAT,
     {"coverage": Fr(5, 9), "soundness_lower_bound": Fr(1, 18), "supported_miss": Fr(17, 18)}),
    ("F116", make(base, eps("1/100")), COND, [],
     {"soundness_lower_bound": Fr(491, 900), "supported_miss": Fr(409, 900), "deterrence_product": Fr(491, 90)}),
    ("F117", make(base, eps("1/18")), COND, [],
     {"soundness_lower_bound": Fr(1, 2), "supported_miss": Fr(1, 2)}),
    ("F118", make(lambda: twin("F37"), eps("9/10")), INEL, MAT,
     {"coverage": Fr(7, 8), "soundness_lower_bound": Fr(0), "supported_miss": Fr(1)}),
    ("F119", make(vip, eps("1/100")), MI, MISSING, {}),
    ("F120", make(vip, eps("1/100"), put(TGT, v("1/2", "probability"))), COND, [],
     {"coverage": Fr(1), "soundness_lower_bound": Fr(99, 100), "supported_miss": Fr(1, 100)}),
    ("F121", make(vip, eps("1/2"), put(TGT, v("1/4", "probability"))), INEL, MAT,
     {"soundness_lower_bound": Fr(1, 2), "supported_miss": Fr(1, 2)}),
    # must-fix 5: no CONDITIONAL without a computed coverage (F67 is the IID f under fixed-size)
    ("F122", make(base, put(["sampling", "schedule"], "outcome_adaptive")), INEL, ["ADAPTIVE_NOT_IID"],
     {"coverage": None}),
    ("F123", make(base, put(["sampling", "schedule"], "outcome_adaptive"), iid("1/4")), INEL,
     ["ADAPTIVE_NOT_IID"], {"coverage": None}),
    # must-fix 6: cost scope and loss basis (F46 is the nonzero epoch-total F, plain convention)
    ("F124", make(base, put(["costs", "F"], v(6, "gpu_s_per_request"))), MI, ["COST_SCOPE"], {}),
    ("F125", make(base, ratio("9/2", "incremental")), COND, [],
     {"coverage": Fr(5, 9), "normalized_cost": Fr(47, 16)}),
    ("F126", make(base, ratio("11/2", "total_audited_path")), COND, [],
     {"coverage": Fr(5, 9), "normalized_cost": Fr(47, 16)}),
    ("F127", make(base, put(["costs", "F"], v(6, "usd_per_epoch"))), MI, ["UNIT_MISMATCH"], {}),
    ("F128", make(base, put(["costs", "I"], v(2, "gpu_s_per_epoch"))), MI, ["COST_SCOPE"], {}),
    ("F129", make(base, wall_costs), MI, ["WALL_TIME_NOT_COST"], {}),
    ("F130", make(base, ratio("9/2", "incremental", keep_p=True)), MI, ["R_AND_P_BOTH"], {}),
    ("F131", make(base, put(["deterrence", "enforceable_loss"], v(10, "loss_unit")),
                  put(["deterrence", "cheating_gain"], v(1, "loss_unit"))), MI, ["LOSS_BASIS_NOT_CONCRETE"], {}),
    ("F132", make(base, put(["deterrence", "cheating_gain"], v(1, "gpu_s"))), MI, ["UNIT_MISMATCH"], {}),
    ("F133", make(base, put(["deterrence", "enforceable_loss"], unk("usd"))), MI, UR, {}),
    ("F134", make(base, put(["deterrence", "enforceable_loss"], v(-1, "usd"))), MI, OOR, {}),
    ("F135", make(base, ratio("9/2", "incremental", f_unit="gpu_s_per_request")), MI, ["COST_SCOPE"], {}),
]

# Amendment 2: what the fixed checker returns for the original F37-F45 (incomplete worksheets).
# Their original expectations stay in fixtures.py and are reported separately.
NO_NUMBER = {"coverage": None, "miss": None, "normalized_cost": None, "deterrence": None}
A2 = [
    ("F37", MI, ["MISSING_INPUT"]),
    ("F38", MI, ["MISSING_INPUT"]),
    ("F39", MI, ["ADAPTIVE_NOT_IID", "MISSING_INPUT"]),
    ("F40", MI, ["MISSING_INPUT"]),
    ("F41", MI, ["MISSING_INPUT", "SUBSAMPLE_NOT_PROOF"]),
    ("F42", MI, ["MISSING_INPUT", "VERIFY_AFTER_ACTION"]),
    ("F43", MI, ["MISSING_INPUT", "SUBSAMPLE_NOT_PROOF"]),
    ("F44", MI, ["MISSING_INPUT", "Q_INFERRED_FROM_WEIGHTS"]),
    ("F45", MI, ["MISSING_INPUT", "TIMEOUT_NOT_PROOF"]),
]
