"""Offline sampling feasibility and guarantee worksheet (issue #211).

Standard library only. Exact rational arithmetic (fractions.Fraction).
Every numeric input carries a unit, an evidence kind and a source.
Outputs are CONDITIONAL, INELIGIBLE or MISSING INPUTS. Never a launch
recommendation, never a recommended sampling rate.

Formulas are the ones already on main in research/sampled-audit/README.md
(#84). Nothing here estimates a proving cost.
"""
from fractions import Fraction
from math import comb

KINDS = {"measured", "calculated", "extrapolated", "conditional_calculation",
         "policy_supplied", "synthetic", "unknown"}
CLASSES = {"fleet_monitoring_after_release",
           "vendor_independent_proof_irreversible",
           "hardware_trusting_immediate_with_later_review"}
COST_UNITS = {"gpu_s_per_request", "cpu_s_per_request", "wall_s_per_request",
              "usd_per_request"}
R_BASES_OK = {"gpu_s/gpu_s", "cpu_s/cpu_s", "usd/usd"}
R_BASES_DECODE = {"wall_s_stream", "decode_batch1_wall_s"}

# Codes that block any numeric verdict.
MISSING_CODES = {"MISSING_INPUT", "NO_PROVENANCE", "BAD_KIND", "UNIT_UNKNOWN",
                 "UNIT_MISMATCH", "UNKNOWN_COST", "DECODE_RATIO_NOT_GPU_COST",
                 "TOKEN_FRACTION_NOT_REQUEST_FRACTION", "Q_INFERRED_FROM_WEIGHTS",
                 "TIMEOUT_NOT_PROOF", "NO_HW_TRUST_ASSUMPTION", "NO_RELATION",
                 "BAD_CLASS", "D_AND_F_BOTH", "OUT_OF_RANGE"}
INELIGIBLE_CODES = {"SUBSAMPLE_NOT_PROOF", "VERIFY_AFTER_ACTION",
                    "MISS_ABOVE_TARGET", "ADAPTIVE_NOT_IID"}

RELATION_TEXT = ("only under the selected relation: acceptance shows the committed "
                 "output satisfies the pinned relation, not which engine or hardware "
                 "produced it")


def F(s):
    return Fraction(s)


# ---------------------------------------------------------------- formulas

def bernoulli_fixed_d(p, d):
    """Bernoulli selection at rate p, D fixed invalid units: 1-(1-p)^D."""
    return 1 - (1 - p) ** d


def iid_invalidity(p, f, n):
    """Bernoulli selection p, each of N units invalid IID with prob f: 1-(1-pf)^N."""
    return 1 - (1 - p * f) ** n


def no_replacement(n, m, d):
    """Fixed-size uniform sample of m from N without replacement: 1-C(N-D,m)/C(N,m)."""
    return 1 - Fraction(comb(n - d, m), comb(n, m))


def no_replacement_q(n, k, m, q):
    """K changed units each independently rejected with explicit q (#84 README)."""
    miss = sum(Fraction(comb(k, j) * comb(n - k, m - j), comb(n, m)) * (1 - q) ** j
               for j in range(0, min(k, m) + 1))
    return 1 - miss


def soundness_lower_bound(coverage, epsilon):
    return max(Fraction(0), coverage - epsilon)


def cost_per_request(i, c, a, f, n, p, pp):
    """I + C + A + F/N + p*P, all in one cost unit."""
    return i + c + a + Fraction(f) / n + p * pp


def normalized_incremental(i, c, a, f, n, p, r):
    """1 + (C+A+F/N)/I + p*R with R = P/I."""
    return 1 + (c + a + Fraction(f) / n) / i + p * r


def normalized_total_path(i, c, a, f, n, p, r):
    """1 + (C+A+F/N)/I + p*(R-1) with R = (I+P)/I (audited path total)."""
    return 1 + (c + a + Fraction(f) / n) / i + p * (r - 1)


def pct4(v):
    """#84 TABLES.md rounding: research/sampled-audit/report.py:28,40."""
    return f"{float(v) * 100:.4f}%"


# ---------------------------------------------------------------- input guard

class Ctx:
    def __init__(self):
        self.codes = set()
        self.synthetic = []
        self.unknowns = []
        self.notes = []

    def flag(self, code, note=None):
        self.codes.add(code)
        if note:
            self.notes.append(f"{code}: {note}")


def num(ctx, ws, path, units, required=True):
    """Read a numeric input dict {value, unit, kind, source}. Returns Fraction or None."""
    cur = ws
    for key in path.split("."):
        cur = cur.get(key) if isinstance(cur, dict) else None
        if cur is None:
            break
    if cur is None:
        if required:
            ctx.flag("MISSING_INPUT", path)
        return None
    if not isinstance(cur, dict) or not cur.get("kind") or not cur.get("source"):
        ctx.flag("NO_PROVENANCE", path)
        return None
    kind = cur["kind"]
    if kind not in KINDS:
        ctx.flag("BAD_KIND", f"{path}={kind}")
        return None
    if kind == "unknown":
        ctx.unknowns.append(path)
        if cur.get("value") is not None:
            ctx.flag("BAD_KIND", f"{path} unknown but has a value")
        return None
    unit = cur.get("unit")
    if unit not in units:
        if unit == "token_fraction" and "request_fraction" in units:
            ctx.flag("TOKEN_FRACTION_NOT_REQUEST_FRACTION", path)
        else:
            ctx.flag("UNIT_UNKNOWN", f"{path} unit={unit}")
        return None
    if kind == "synthetic":
        ctx.synthetic.append(path)
    return F(cur["value"])


def unit_of(ws, path):
    cur = ws
    for key in path.split("."):
        cur = cur.get(key) if isinstance(cur, dict) else None
        if cur is None:
            return None
    return cur.get("unit") if isinstance(cur, dict) else None


def prob_ok(ctx, name, v):
    if v is not None and not (0 <= v <= 1):
        ctx.flag("OUT_OF_RANGE", f"{name}={v}")
        return False
    return v is not None


# ---------------------------------------------------------------- cost section

def eval_costs(ctx, ws, n, p):
    """Returns (cost_per_request, normalized) or (None, None). Blocks on any unit/unknown error."""
    costs = ws.get("costs")
    if costs is None:
        ctx.flag("MISSING_INPUT", "costs")
        return None, None
    if "R" in costs:
        conv = costs.get("R_convention")
        basis = costs.get("R_unit_basis")
        if basis in R_BASES_DECODE:
            ctx.flag("DECODE_RATIO_NOT_GPU_COST",
                     f"R basis {basis} is stream wall time / decode, not a GPU-cost ratio")
            return None, None
        if basis not in R_BASES_OK:
            ctx.flag("UNIT_UNKNOWN", f"R_unit_basis={basis}")
            return None, None
        if conv not in ("incremental", "total_audited_path"):
            ctx.flag("MISSING_INPUT", "costs.R_convention")
            return None, None
        r = num(ctx, ws, "costs.R", {"ratio"})
        base_unit = basis.split("/")[0] + "_per_request"
        vals = {}
        for k in ("I", "C", "A", "F"):
            vals[k] = num(ctx, ws, f"costs.{k}", COST_UNITS)
        units = {unit_of(ws, f"costs.{k}") for k in ("I", "C", "A", "F")
                 if unit_of(ws, f"costs.{k}") in COST_UNITS}
        if len(units) > 1 or (units and units != {base_unit}):
            ctx.flag("UNIT_MISMATCH", f"cost units {sorted(units)} vs R basis {basis}")
        if ctx.unknowns and any(u.startswith("costs.") for u in ctx.unknowns):
            ctx.flag("UNKNOWN_COST", ",".join(u for u in ctx.unknowns if u.startswith("costs.")))
        if r is None or p is None or n is None or any(v is None for v in vals.values()) \
                or ctx.codes & MISSING_CODES:
            return None, None
        fn = normalized_incremental if conv == "incremental" else normalized_total_path
        return None, fn(vals["I"], vals["C"], vals["A"], vals["F"], n, p, r)
    vals = {}
    for k in ("I", "P", "C", "A", "F"):
        vals[k] = num(ctx, ws, f"costs.{k}", COST_UNITS)
    units = {unit_of(ws, f"costs.{k}") for k in ("I", "P", "C", "A", "F")
             if unit_of(ws, f"costs.{k}") in COST_UNITS}
    if len(units) > 1:
        ctx.flag("UNIT_MISMATCH", f"cost units {sorted(units)} cannot be added")
    cost_unknowns = [u for u in ctx.unknowns if u.startswith("costs.")]
    if cost_unknowns:
        ctx.flag("UNKNOWN_COST", ",".join(cost_unknowns))
    if p is None or n is None or any(v is None for v in vals.values()) or ctx.codes & MISSING_CODES:
        return None, None
    cpr = cost_per_request(vals["I"], vals["C"], vals["A"], vals["F"], n, p, vals["P"])
    norm = cpr / vals["I"]
    return cpr, norm


# ---------------------------------------------------------------- worksheet

def evaluate(ws):
    """Evaluate one worksheet. Returns a dict with verdict, sorted codes and exact values."""
    ctx = Ctx()
    cls = ws.get("policy_class")
    if cls not in CLASSES:
        ctx.flag("BAD_CLASS", str(cls))
    relation = (ws.get("relation") or "").strip()
    if not relation:
        ctx.flag("NO_RELATION")
    n = num(ctx, ws, "population.N", {"request"})
    samp = ws.get("sampling", {})
    scheme = samp.get("scheme")
    schedule = samp.get("schedule", "fixed_in_advance")
    p = None
    m = None
    if scheme == "bernoulli_p":
        p = num(ctx, ws, "sampling.p", {"request_fraction"})
        prob_ok(ctx, "p", p)
    elif scheme == "fixed_size_no_replacement_m":
        m = num(ctx, ws, "sampling.m", {"request"})
        if m is not None and n is not None:
            p = m / n
    else:
        ctx.flag("MISSING_INPUT", "sampling.scheme")
    inv = ws.get("invalidity", {})
    if "D" in inv and "f" in inv:
        ctx.flag("D_AND_F_BOTH")
    d = num(ctx, ws, "invalidity.D", {"request"}, required=False) if "D" in inv else None
    f = num(ctx, ws, "invalidity.f", {"request_fraction"}, required=False) if "f" in inv else None
    if "D" not in inv and "f" not in inv and cls != "vendor_independent_proof_irreversible":
        ctx.flag("MISSING_INPUT", "invalidity.D or invalidity.f")
    dist = ws.get("distinguishability", {})
    q = None
    if "q" in dist:
        if dist.get("q_source") == "changed_weight_count":
            ctx.flag("Q_INFERRED_FROM_WEIGHTS", "q may not be inferred from changed-weight counts")
        else:
            q = num(ctx, ws, "distinguishability.q", {"probability"})
            prob_ok(ctx, "q", q)
    eps = None
    if "epsilon" in ws.get("soundness_treatment", {}):
        eps = num(ctx, ws, "soundness_treatment.epsilon", {"probability"})
    if not ws.get("soundness_treatment", {}).get("text"):
        ctx.flag("MISSING_INPUT", "soundness_treatment.text")
    lat = ws.get("latency", {})
    if "verify_before_action" not in lat:
        ctx.flag("MISSING_INPUT", "latency.verify_before_action")
    for obs in ws.get("observations", []):
        if obs.get("type") == "timeout" and obs.get("counted_as") == "wrong_answer":
            ctx.flag("TIMEOUT_NOT_PROOF", "a timeout/refusal is not proof of a wrong answer")
    claims = ws.get("claims", {})
    if cls == "hardware_trusting_immediate_with_later_review" and \
            not (claims.get("hardware_trust_assumption") or "").strip():
        ctx.flag("NO_HW_TRUST_ASSUMPTION")

    full = p is not None and p == 1

    # class rules
    if cls == "vendor_independent_proof_irreversible":
        if p is not None and p < 1:
            ctx.flag("SUBSAMPLE_NOT_PROOF", "a specific irreversible decision needs p=1")
        if lat.get("verify_before_action") is False:
            ctx.flag("VERIFY_AFTER_ACTION", "verification must complete before the action")
    else:
        if claims.get("individual_guarantee") is True and p is not None and p < 1:
            ctx.flag("SUBSAMPLE_NOT_PROOF", "p<1 cannot guarantee a specific answer")

    coverage = None
    if schedule == "outcome_adaptive":
        if samp.get("lifetime_formula_requested") or "f" in inv:
            ctx.flag("ADAPTIVE_NOT_IID",
                     "an outcome-adaptive schedule has no lifetime plug-in or IID formula")
    elif schedule != "fixed_in_advance":
        ctx.flag("MISSING_INPUT", "sampling.schedule")
    else:
        if cls == "vendor_independent_proof_irreversible" and full:
            coverage = Fraction(1)
        elif q is not None and m is not None and n is not None and "K" in dist:
            k = num(ctx, ws, "distinguishability.K", {"request"})
            if k is not None:
                coverage = no_replacement_q(int(n), int(k), int(m), q)
        elif d is not None and scheme == "bernoulli_p" and p is not None:
            coverage = bernoulli_fixed_d(p, int(d))
        elif d is not None and m is not None and n is not None:
            coverage = no_replacement(int(n), int(m), int(d))
        elif f is not None and scheme == "bernoulli_p" and p is not None and n is not None:
            coverage = iid_invalidity(p, f, int(n))
    lower = soundness_lower_bound(coverage, eps) if coverage is not None and eps is not None else None

    cpr, norm = eval_costs(ctx, ws, n, p)

    target = None
    if cls != "vendor_independent_proof_irreversible":
        target = num(ctx, ws, "targets.desired_miss_probability", {"probability"})
    miss = (1 - coverage) if coverage is not None else None
    if target is not None and miss is not None and not (ctx.codes & MISSING_CODES):
        if miss > target:
            ctx.flag("MISS_ABOVE_TARGET", f"miss {miss} > target {target}")

    deter = None
    det = ws.get("deterrence")
    if det:
        loss = num(ctx, ws, "deterrence.enforceable_loss", {"loss_unit"}, required=False)
        gain = num(ctx, ws, "deterrence.cheating_gain", {"loss_unit"}, required=False)
        pd = lower if lower is not None else coverage
        if loss is not None and gain is not None and pd is not None:
            deter = {"P_detect_times_loss": pd * loss, "cheating_gain": gain,
                     "condition_holds": pd * loss > gain,
                     "assumptions": det.get("behavioral_assumptions", ""),
                     "note": "recorded only, under the declared behavioral assumptions; "
                             "not a fact, not a verdict input"}

    if ctx.codes & MISSING_CODES:
        verdict = "MISSING INPUTS"
        cpr = norm = None
    elif ctx.codes & INELIGIBLE_CODES:
        verdict = "INELIGIBLE"
    else:
        verdict = "CONDITIONAL"
    assumptions = [RELATION_TEXT, "selection randomness unpredictable to the provider and "
                   "drawn after the population is closed", "population independently enumerated"]
    if coverage is not None:
        assumptions.append("coverage is a per-population-window probability, not a "
                           "per-request guarantee, conditional on the invalid count or rate")
    if cls == "hardware_trusting_immediate_with_later_review":
        assumptions.append("immediate service rests on: " + claims.get("hardware_trust_assumption", ""))
    return {"verdict": verdict, "codes": sorted(ctx.codes), "coverage": coverage, "miss": miss,
            "soundness_lower_bound": lower, "cost_per_request": cpr, "normalized_cost": norm,
            "deterrence": deter, "assumptions": assumptions, "synthetic_inputs": sorted(ctx.synthetic),
            "synthetic": bool(ctx.synthetic), "unknowns": sorted(ctx.unknowns), "notes": ctx.notes}
