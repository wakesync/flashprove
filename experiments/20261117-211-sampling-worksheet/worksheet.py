"""Offline sampling feasibility and guarantee worksheet (issue #211).

Standard library only. Exact rational arithmetic (fractions.Fraction).
Every numeric input carries a unit, an evidence kind and a source.
Outputs are CONDITIONAL, INELIGIBLE or MISSING INPUTS. Never a launch
recommendation, never a recommended sampling rate.

Formulas are the ones already on main in research/sampled-audit/README.md
(#84). Nothing here estimates a proving cost.

After round 1 review (PREREG Amendments 1 and 2) the checker fails closed:
every required input is checked for presence, provenance, unit, value form
and numeric domain before any arithmetic, and evaluate() does not raise.
"""
import re
from fractions import Fraction
from math import comb

KINDS = {"measured", "calculated", "extrapolated", "conditional_calculation",
         "policy_supplied", "synthetic", "unknown"}
CLASSES = {"fleet_monitoring_after_release",
           "vendor_independent_proof_irreversible",
           "hardware_trusting_immediate_with_later_review"}
COST_UNITS = {"gpu_s_per_request", "cpu_s_per_request", "wall_s_per_request",
              "usd_per_request"}
# F is an epoch-total cost (Amendment 1): it carries an epoch unit and is divided by N once.
EPOCH_UNITS = {"gpu_s_per_epoch", "cpu_s_per_epoch", "usd_per_epoch"}
LOSS_UNITS = ("usd", "gpu_s", "cpu_s")
SECTIONS = ("population", "sampling", "invalidity", "distinguishability",
            "soundness_treatment", "costs", "latency", "targets", "deterrence", "claims")
OBS_TYPES = ("timeout", "refusal", "proof_rejected")
OBS_COUNTED = ("wrong_answer", "audit_failure")
VIP_CLASS = "vendor_independent_proof_irreversible"
HW_CLASS = "hardware_trusting_immediate_with_later_review"
FIXED_SIZE = "fixed_size_no_replacement_m"
NOT_MODELLED = ["queue and batch effects (a separate unknown, not scaled by p)",
                "all-traffic trace cost (a separate unknown, not scaled by p)"]
# A value is a string: an integer, a fraction a/b, or a plain decimal. Never a JSON number.
VALUE_RE = re.compile(r"-?\d+(/\d+)?|-?\d+\.\d+")
R_BASES_OK = {"gpu_s/gpu_s", "cpu_s/cpu_s", "usd/usd"}
R_BASES_DECODE = {"wall_s_stream", "decode_batch1_wall_s"}

# Codes that block any numeric verdict.
MISSING_CODES = {"MISSING_INPUT", "NO_PROVENANCE", "BAD_KIND", "UNIT_UNKNOWN",
                 "UNIT_MISMATCH", "UNKNOWN_COST", "DECODE_RATIO_NOT_GPU_COST",
                 "TOKEN_FRACTION_NOT_REQUEST_FRACTION", "Q_INFERRED_FROM_WEIGHTS",
                 "TIMEOUT_NOT_PROOF", "NO_HW_TRUST_ASSUMPTION", "NO_RELATION",
                 "BAD_CLASS", "D_AND_F_BOTH", "OUT_OF_RANGE",
                 # added by Amendment 1
                 "BAD_SECTION", "CHECKER_ERROR", "UNKNOWN_REQUIRED", "BAD_VALUE",
                 "NOT_INTEGER", "NOT_BOOLEAN", "BAD_OBSERVATION", "Q_UNSUPPORTED",
                 "UNSUPPORTED_COMBINATION", "COST_SCOPE", "WALL_TIME_NOT_COST",
                 "R_AND_P_BOTH", "LOSS_BASIS_NOT_CONCRETE", "NO_COVERAGE", "NO_COST"}
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


def lookup(ws, path):
    cur = ws
    for key in path.split("."):
        cur = cur.get(key) if isinstance(cur, dict) else None
        if cur is None:
            return None
    return cur


def num(ctx, ws, path, units, required=True, integer=False, lo=None, hi=None):
    """Read a numeric input dict {value, unit, kind, source}. Returns Fraction or None.

    Fails closed: absent, no provenance, bad kind, unknown, wrong unit, a value that is
    not a rational string, a non-integer count, or a value outside [lo, hi] all return
    None with a code. Nothing is truncated or clipped.
    """
    cur = lookup(ws, path)
    if cur is None:
        if required:
            ctx.flag("MISSING_INPUT", path)
        return None
    if not isinstance(cur, dict) or not cur.get("kind") or not text_ok(cur.get("source")):
        # the source must be text; a number, a boolean or an object is not provenance
        ctx.flag("NO_PROVENANCE", path)
        return None
    kind = cur["kind"]
    if not isinstance(kind, str) or kind not in KINDS:
        ctx.flag("BAD_KIND", f"{path}={kind}")
        return None
    if kind == "unknown":
        ctx.unknowns.append(path)
        if cur.get("value") is not None:
            ctx.flag("BAD_KIND", f"{path} unknown but has a value")
        if not path.startswith("costs."):
            # an unknown cost is reported as UNKNOWN_COST by eval_costs
            ctx.flag("UNKNOWN_REQUIRED", path)
        return None
    unit = cur.get("unit")
    if not isinstance(unit, str) or unit not in units:
        if unit == "token_fraction" and "request_fraction" in units:
            ctx.flag("TOKEN_FRACTION_NOT_REQUEST_FRACTION", path)
        else:
            ctx.flag("UNIT_UNKNOWN", f"{path} unit={unit}")
        return None
    raw = cur.get("value")
    if not isinstance(raw, str) or not VALUE_RE.fullmatch(raw):
        ctx.flag("BAD_VALUE", f"{path}: value must be a string integer, a/b or decimal")
        return None
    try:
        val = Fraction(raw)
    except (ValueError, ZeroDivisionError):
        ctx.flag("BAD_VALUE", f"{path}: not a rational")
        return None
    if integer and val.denominator != 1:
        ctx.flag("NOT_INTEGER", f"{path}={val}")
        return None
    if (lo is not None and val < lo) or (hi is not None and val > hi):
        ctx.flag("OUT_OF_RANGE", f"{path}={val}")
        return None
    if kind == "synthetic":
        ctx.synthetic.append(path)
    return val


def unit_of(ws, path):
    cur = lookup(ws, path)
    return cur.get("unit") if isinstance(cur, dict) else None


def text_ok(x):
    return isinstance(x, str) and bool(x.strip())


# ---------------------------------------------------------------- cost section

def cost_inputs(ctx, ws, keys):
    """Read cost inputs with their scope. I, P, C, A are per-request costs. F is an
    epoch-total cost (per_epoch unit, divided by N exactly once by the formulas); an F
    that is exactly zero is also accepted in a per-request unit, because zero is the
    same quantity in both scopes. Returns (values, set of resource names seen)."""
    vals, bases = {}, set()
    for k in keys:
        path = f"costs.{k}"
        unit = unit_of(ws, path)
        known = isinstance(unit, str) and unit in (COST_UNITS | EPOCH_UNITS)
        if k == "F":
            val = num(ctx, ws, path, COST_UNITS | EPOCH_UNITS, lo=0)
            if val is not None and unit in COST_UNITS and val != 0:
                ctx.flag("COST_SCOPE", f"{path} is an epoch total: a nonzero F needs a per_epoch unit, got {unit}")
                val = None
        elif known and unit in EPOCH_UNITS:
            ctx.flag("COST_SCOPE", f"{path} is a per-request cost, got {unit}")
            val = None
        else:
            val = num(ctx, ws, path, COST_UNITS, lo=0)
        if k == "I" and val is not None and val == 0:
            ctx.flag("OUT_OF_RANGE", "costs.I must be positive (it is the normalization denominator)")
            val = None
        vals[k] = val
        if known:
            bases.add(unit.rsplit("_per_", 1)[0])
    return vals, bases


def eval_costs(ctx, ws, n, p):
    """Returns (cost_per_request, normalized) or (None, None). Blocks on any unit/unknown error."""
    costs = ws.get("costs") if isinstance(ws, dict) else None
    if not isinstance(costs, dict):
        ctx.flag("MISSING_INPUT", "costs")
        return None, None
    if n is not None and n <= 0:
        ctx.flag("OUT_OF_RANGE", f"N={n}")
        n = None
    if "R" in costs:
        conv = costs.get("R_convention")
        basis = costs.get("R_unit_basis")
        if isinstance(basis, str) and basis in R_BASES_DECODE:
            ctx.flag("DECODE_RATIO_NOT_GPU_COST",
                     f"R basis {basis} is stream wall time / decode, not a GPU-cost ratio")
            return None, None
        if not isinstance(basis, str) or basis not in R_BASES_OK:
            ctx.flag("UNIT_UNKNOWN", f"R_unit_basis={basis}")
            return None, None
        if conv not in ("incremental", "total_audited_path"):
            ctx.flag("MISSING_INPUT", "costs.R_convention")
            return None, None
        if "P" in costs:
            ctx.flag("R_AND_P_BOTH", "give either P or a ratio R, not both")
        # R = P/I is >= 0; R = (I+P)/I is >= 1
        r = num(ctx, ws, "costs.R", {"ratio"}, lo=0 if conv == "incremental" else 1)
        vals, bases = cost_inputs(ctx, ws, ("I", "C", "A", "F"))
        base = basis.split("/")[0]
        if len(bases) > 1 or (bases and bases != {base}):
            ctx.flag("UNIT_MISMATCH", f"cost units {sorted(bases)} vs R basis {basis}")
        cost_unknowns = [u for u in ctx.unknowns if u.startswith("costs.")]
        if cost_unknowns:
            ctx.flag("UNKNOWN_COST", ",".join(cost_unknowns))
        if r is None or p is None or n is None or any(v is None for v in vals.values()) \
                or ctx.codes & MISSING_CODES:
            return None, None
        fn = normalized_incremental if conv == "incremental" else normalized_total_path
        return None, fn(vals["I"], vals["C"], vals["A"], vals["F"], n, p, r)
    vals, bases = cost_inputs(ctx, ws, ("I", "P", "C", "A", "F"))
    if bases == {"wall_s"}:
        ctx.flag("WALL_TIME_NOT_COST", "wall seconds are latency, not a cost unit")
    elif len(bases) > 1:
        ctx.flag("UNIT_MISMATCH", f"cost units {sorted(bases)} cannot be added")
    cost_unknowns = [u for u in ctx.unknowns if u.startswith("costs.")]
    if cost_unknowns:
        ctx.flag("UNKNOWN_COST", ",".join(cost_unknowns))
    if p is None or n is None or any(v is None for v in vals.values()) or ctx.codes & MISSING_CODES:
        return None, None
    cpr = cost_per_request(vals["I"], vals["C"], vals["A"], vals["F"], n, p, vals["P"])
    norm = cpr / vals["I"]
    return cpr, norm


# ---------------------------------------------------------------- worksheet

def _report(ctx, cls, claims, coverage=None, miss=None, supported=None, lower=None,
            cpr=None, norm=None, deter=None, eps_given=False):
    """Decide the verdict from the collected codes and build the result."""
    probs = [x for x in (coverage, miss, supported, lower) if x is not None]
    if any(not (0 <= x <= 1) for x in probs):
        ctx.flag("CHECKER_ERROR", "a probability left [0, 1]")
    if not ctx.codes:
        # a CONDITIONAL needs a computed coverage and a computed normalized cost
        if coverage is None:
            ctx.flag("NO_COVERAGE", "no supported formula produced a coverage")
        if norm is None:
            ctx.flag("NO_COST", "no normalized cost was computed")
    if ctx.codes - INELIGIBLE_CODES:
        # any code that is not an eligibility code blocks every number
        verdict = "MISSING INPUTS"
        coverage = miss = supported = lower = cpr = norm = deter = None
    elif ctx.codes:
        verdict = "INELIGIBLE"
    else:
        verdict = "CONDITIONAL"
    assumptions = [RELATION_TEXT, "selection randomness unpredictable to the provider and "
                   "drawn after the population is closed", "population independently enumerated"]
    if coverage is not None:
        assumptions.append("coverage is a per-population-window probability, not a "
                           "per-request guarantee, conditional on the invalid count or rate")
    if lower is not None and eps_given:
        assumptions.append("the miss target is compared with the supported bound "
                           "1 - max(0, coverage - epsilon), not with the nominal miss")
    if cls == HW_CLASS:
        assumptions.append("immediate service rests on: " + str(claims.get("hardware_trust_assumption", "")))
    return {"verdict": verdict, "codes": sorted(ctx.codes), "coverage": coverage, "miss": miss,
            "supported_miss": supported, "soundness_lower_bound": lower,
            "cost_per_request": cpr, "normalized_cost": norm, "deterrence": deter,
            "assumptions": assumptions, "synthetic_inputs": sorted(ctx.synthetic),
            "synthetic": bool(ctx.synthetic), "unknowns": sorted(ctx.unknowns),
            "not_modelled": list(NOT_MODELLED), "notes": ctx.notes}


def evaluate(ws):
    """Evaluate one worksheet. Returns a dict with verdict, sorted codes and exact values.
    Never raises: a malformed worksheet is MISSING INPUTS with a code."""
    try:
        return _evaluate(ws)
    except Exception as ex:  # backstop only; no known input reaches it
        ctx = Ctx()
        ctx.flag("CHECKER_ERROR", type(ex).__name__)
        return _report(ctx, None, {})


def _evaluate(ws):
    ctx = Ctx()
    if not isinstance(ws, dict):
        ctx.flag("BAD_SECTION", "worksheet is not an object")
        return _report(ctx, None, {})
    bad = [s for s in SECTIONS if s in ws and not isinstance(ws[s], dict)]
    obs = ws.get("observations", [])
    if not isinstance(obs, list) or any(not isinstance(o, dict) for o in obs):
        bad.append("observations")
    if bad:
        ctx.flag("BAD_SECTION", ",".join(bad))
        return _report(ctx, None, {})

    cls = ws.get("policy_class")
    if not isinstance(cls, str) or cls not in CLASSES:
        ctx.flag("BAD_CLASS", str(cls))
        cls = None
    if not text_ok(ws.get("relation")):
        ctx.flag("NO_RELATION")

    pop = ws.get("population", {})
    if not text_ok(pop.get("definition")):
        ctx.flag("MISSING_INPUT", "population.definition")
    n = num(ctx, ws, "population.N", {"request"}, integer=True, lo=1)

    samp = ws.get("sampling", {})
    scheme = samp.get("scheme")
    schedule = samp.get("schedule")
    p = m = None
    if scheme == "bernoulli_p":
        p = num(ctx, ws, "sampling.p", {"request_fraction"}, lo=0, hi=1)
    elif scheme == FIXED_SIZE:
        m = num(ctx, ws, "sampling.m", {"request"}, integer=True, lo=0, hi=n)
        if m is not None and n is not None:
            p = m / n
    else:
        ctx.flag("MISSING_INPUT", "sampling.scheme")
    if schedule == "outcome_adaptive":
        ctx.flag("ADAPTIVE_NOT_IID",
                 "an outcome-adaptive schedule has no lifetime plug-in or IID formula")
    elif schedule != "fixed_in_advance":
        ctx.flag("MISSING_INPUT", "sampling.schedule")

    inv = ws.get("invalidity", {})
    has_d, has_f = "D" in inv, "f" in inv
    if has_d and has_f:
        ctx.flag("D_AND_F_BOTH")
    d = num(ctx, ws, "invalidity.D", {"request"}, integer=True, lo=0, hi=n) if has_d else None
    f = num(ctx, ws, "invalidity.f", {"request_fraction"}, lo=0, hi=1) if has_f else None
    if not has_d and not has_f and cls != VIP_CLASS:
        ctx.flag("MISSING_INPUT", "invalidity.D or invalidity.f")
    if has_f and not has_d and scheme == FIXED_SIZE:
        ctx.flag("UNSUPPORTED_COMBINATION",
                 "an IID f has no registered formula under the fixed-size scheme")

    # an explicit q is used by the one registered q formula or refused; never dropped
    dist = ws.get("distinguishability", {})
    q = k = None
    use_q = False
    if "q" in dist:
        if dist.get("q_source") == "changed_weight_count":
            ctx.flag("Q_INFERRED_FROM_WEIGHTS", "q may not be inferred from changed-weight counts")
        else:
            q = num(ctx, ws, "distinguishability.q", {"probability"}, lo=0, hi=1)
            if "K" in dist:
                k = num(ctx, ws, "distinguishability.K", {"request"}, integer=True, lo=0, hi=n)
            if cls == VIP_CLASS or scheme != FIXED_SIZE or "K" not in dist or has_f \
                    or (d is not None and k is not None and d != k):
                ctx.flag("Q_UNSUPPORTED", "q is only supported with the fixed-size scheme, "
                         "a K, and K equal to invalidity.D")
            else:
                use_q = True
    elif "K" in dist:
        ctx.flag("MISSING_INPUT", "distinguishability.q (K given without q)")

    st = ws.get("soundness_treatment", {})
    eps = None
    has_eps = "epsilon" in st
    if has_eps:
        eps = num(ctx, ws, "soundness_treatment.epsilon", {"probability"}, lo=0, hi=1)
    if not text_ok(st.get("text")):
        ctx.flag("MISSING_INPUT", "soundness_treatment.text")

    lat = ws.get("latency", {})
    if not text_ok(lat.get("deadline_policy")):
        ctx.flag("MISSING_INPUT", "latency.deadline_policy")
    vba = lat.get("verify_before_action")
    if "verify_before_action" not in lat:
        ctx.flag("MISSING_INPUT", "latency.verify_before_action")
    elif not isinstance(vba, bool):
        ctx.flag("NOT_BOOLEAN", "latency.verify_before_action")

    claims = ws.get("claims", {})
    ig = claims.get("individual_guarantee")
    if "individual_guarantee" not in claims:
        ctx.flag("MISSING_INPUT", "claims.individual_guarantee")
    elif not isinstance(ig, bool):
        ctx.flag("NOT_BOOLEAN", "claims.individual_guarantee")
    if cls == HW_CLASS and not text_ok(claims.get("hardware_trust_assumption")):
        ctx.flag("NO_HW_TRUST_ASSUMPTION")

    for o in obs:
        kind, counted = o.get("type"), o.get("counted_as")
        if kind not in OBS_TYPES or counted not in OBS_COUNTED:
            ctx.flag("BAD_OBSERVATION", f"type={kind} counted_as={counted}")
        elif kind in ("timeout", "refusal") and counted == "wrong_answer":
            ctx.flag("TIMEOUT_NOT_PROOF", "a timeout/refusal is not proof of a wrong answer")

    # deterrence: a declared state is required; loss and gain share one concrete basis
    det = ws.get("deterrence")
    loss = gain = None
    modeled = False
    if det is None:
        ctx.flag("MISSING_INPUT", "deterrence")
    elif det.get("state") == "modeled":
        modeled = True
        if not text_ok(det.get("behavioral_assumptions")):
            ctx.flag("MISSING_INPUT", "deterrence.behavioral_assumptions")
        lu = unit_of(ws, "deterrence.enforceable_loss")
        gu = unit_of(ws, "deterrence.cheating_gain")
        if "loss_unit" in (lu, gu):
            ctx.flag("LOSS_BASIS_NOT_CONCRETE", "loss and gain need one concrete unit "
                     "(usd, gpu_s or cpu_s), not the generic loss_unit")
        else:
            loss = num(ctx, ws, "deterrence.enforceable_loss", set(LOSS_UNITS), lo=0)
            gain = num(ctx, ws, "deterrence.cheating_gain", set(LOSS_UNITS), lo=0)
            if lu in LOSS_UNITS and gu in LOSS_UNITS and lu != gu:
                ctx.flag("UNIT_MISMATCH", f"deterrence loss in {lu}, gain in {gu}")
    elif det.get("state") != "not_modeled":
        ctx.flag("MISSING_INPUT", "deterrence.state (modeled or not_modeled)")

    # class rules
    if cls == VIP_CLASS:
        if p is not None and p < 1:
            ctx.flag("SUBSAMPLE_NOT_PROOF", "a specific irreversible decision needs p=1")
        if vba is False:
            ctx.flag("VERIFY_AFTER_ACTION", "verification must complete before the action")
    elif ig is True and p is not None and p < 1:
        ctx.flag("SUBSAMPLE_NOT_PROOF", "p<1 cannot guarantee a specific answer")

    # coverage: exactly one registered formula, selected explicitly; no fallback
    coverage = None
    if schedule == "fixed_in_advance":
        if cls == VIP_CLASS:
            if p is not None and p == 1:
                coverage = Fraction(1)
        elif "q" in dist:
            if use_q and None not in (q, k, m, n, d):
                coverage = no_replacement_q(int(n), int(k), int(m), q)
        elif d is not None and scheme == "bernoulli_p" and p is not None:
            coverage = bernoulli_fixed_d(p, int(d))
        elif d is not None and scheme == FIXED_SIZE and m is not None and n is not None:
            coverage = no_replacement(int(n), int(m), int(d))
        elif f is not None and scheme == "bernoulli_p" and p is not None and n is not None:
            coverage = iid_invalidity(p, f, int(n))

    # the supported bound, not the nominal miss, is what the target is compared with
    miss = lower = supported = None
    if coverage is not None:
        miss = 1 - coverage
        if not has_eps:
            supported = miss
        elif eps is not None:
            lower = soundness_lower_bound(coverage, eps)
            supported = 1 - lower

    target = None
    if cls != VIP_CLASS or has_eps:
        target = num(ctx, ws, "targets.desired_miss_probability", {"probability"}, lo=0, hi=1)

    cpr, norm = eval_costs(ctx, ws, n, p)

    if not (ctx.codes - INELIGIBLE_CODES) and target is not None and supported is not None \
            and supported > target:
        ctx.flag("MISS_ABOVE_TARGET", f"supported miss {supported} > target {target}")

    deter = None
    pd = lower if has_eps else coverage
    if modeled and loss is not None and gain is not None and pd is not None:
        deter = {"P_detect_times_loss": pd * loss, "cheating_gain": gain,
                 "condition_holds": pd * loss > gain,
                 "loss_basis": unit_of(ws, "deterrence.enforceable_loss"),
                 "assumptions": det.get("behavioral_assumptions", ""),
                 "note": "recorded only, under the declared behavioral assumptions; "
                         "not a fact, not a verdict input"}

    return _report(ctx, cls, claims, coverage, miss, supported, lower, cpr, norm, deter, has_eps)
