"""Debug inputs DBG-04 onward (PREREG Amendment 1, debug rule). Not part of any registered
suite and not F01-F135: a different base (N=7, p=1/5, D=3, other costs) and malformed inputs
generated from it. Checks that the fixed checker refuses and never raises."""
import copy
import os
import sys
from fractions import Fraction as Fr

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import worksheet as W  # noqa: E402


def v(x, u):
    return {"value": str(x), "unit": u, "kind": "synthetic", "source": "synthetic:debug"}


def dbg():
    return {"policy_class": "fleet_monitoring_after_release", "relation": "debug relation",
            "population": {"definition": "debug population", "N": v(7, "request")},
            "sampling": {"scheme": "bernoulli_p", "p": v("1/5", "request_fraction"),
                         "schedule": "fixed_in_advance"},
            "invalidity": {"D": v(3, "request")},
            "soundness_treatment": {"text": "debug"},
            "costs": {"I": v(4, "cpu_s_per_request"), "P": v(20, "cpu_s_per_request"),
                      "C": v(1, "cpu_s_per_request"), "A": v(0, "cpu_s_per_request"),
                      "F": v(14, "cpu_s_per_epoch")},
            "latency": {"deadline_policy": "debug", "verify_before_action": False},
            "targets": {"desired_miss_probability": v("3/5", "probability")},
            "deterrence": {"state": "not_modeled"},
            "claims": {"individual_guarantee": False}}


def mod(path, val):
    b = dbg()
    cur = b
    for key in path[:-1]:
        cur = cur[key]
    cur[path[-1]] = val
    return b


ok = True


def expect(name, ws, verdict, codes=None, **vals):
    global ok
    r = W.evaluate(ws)
    good = r["verdict"] == verdict and (codes is None or r["codes"] == sorted(codes))
    for k, want in vals.items():
        good = good and r.get(k) == want
    ok &= good
    print(name, "OK" if good else "MISMATCH", r["verdict"], r["codes"], r["coverage"], r["normalized_cost"])


# 1-(4/5)^3 = 61/125; cost 4+1+0+14/7+20/5 = 11, normalized 11/4
expect("DBG-04 control", dbg(), "CONDITIONAL", [], coverage=Fr(61, 125), normalized_cost=Fr(11, 4))
expect("DBG-05 D>N", mod(["invalidity", "D"], v(8, "request")), "MISSING INPUTS", ["OUT_OF_RANGE"])
expect("DBG-06 D=3/2", mod(["invalidity", "D"], v("3/2", "request")), "MISSING INPUTS", ["NOT_INTEGER"])
expect("DBG-07 N=0", mod(["population", "N"], v(0, "request")), "MISSING INPUTS", ["OUT_OF_RANGE"])
expect("DBG-08 value float", mod(["sampling", "p", "value"], 0.2), "MISSING INPUTS", ["BAD_VALUE"])
expect("DBG-09 adaptive", mod(["sampling", "schedule"], "outcome_adaptive"), "INELIGIBLE", ["ADAPTIVE_NOT_IID"])
expect("DBG-10 q on bernoulli", mod(["distinguishability"], {"q": v("1/3", "probability")}),
       "MISSING INPUTS", ["Q_UNSUPPORTED"])
expect("DBG-11 F per request", mod(["costs", "F"], v(14, "cpu_s_per_request")), "MISSING INPUTS", ["COST_SCOPE"])
# epsilon 2/5: lower 61/125-50/125 = 11/125, supported miss 114/125 > 3/5
expect("DBG-12 epsilon", mod(["soundness_treatment", "epsilon"], v("2/5", "probability")),
       "INELIGIBLE", ["MISS_ABOVE_TARGET"], soundness_lower_bound=Fr(11, 125), supported_miss=Fr(114, 125))
expect("DBG-13 verify string", mod(["latency", "verify_before_action"], "true"), "MISSING INPUTS", ["NOT_BOOLEAN"])
expect("DBG-14 no deterrence", {k: x for k, x in dbg().items() if k != "deterrence"},
       "MISSING INPUTS", ["MISSING_INPUT"])
expect("DBG-15 not a dict", ["x"], "MISSING INPUTS", ["BAD_SECTION"])
# found by the generated inputs below on the first debug run: a non-text source was accepted
expect("DBG-16 source is a number", mod(["population", "N", "source"], 7), "MISSING INPUTS", ["NO_PROVENANCE"])
expect("DBG-17 source is true", mod(["costs", "P", "source"], True), "MISSING INPUTS", ["NO_PROVENANCE"])

# malformed inputs generated from the debug base: the checker must return, never raise, and
# never emit a probability outside [0, 1]. A CONDITIONAL is legitimate only where the junk
# is a valid entry: any non-empty text in a text field, or true for verify_before_action.
TEXT_FIELDS = ("relation", "definition", "text", "deadline_policy", "source")
JUNK = [None, "", "abc", "1/0", "-1", "1e3", 0.5, 7, True, [], {}, {"value": "1"}, "nan", "inf", " 1"]
paths = []


def walk(node, path):
    for key, val in node.items():
        paths.append(path + [key])
        if isinstance(val, dict):
            walk(val, path + [key])


walk(dbg(), [])
count = raised = conditional = unexpected = bad_prob = 0
for path in paths:
    for junk in JUNK:
        ws = mod(path, copy.deepcopy(junk))
        count += 1
        try:
            r = W.evaluate(ws)
        except Exception as ex:  # must not happen
            raised += 1
            print("RAISED", path, repr(junk), type(ex).__name__)
            continue
        if "CHECKER_ERROR" in r["codes"]:
            raised += 1
            print("CHECKER_ERROR", path, repr(junk), r["notes"])
        if r["verdict"] == "CONDITIONAL":
            conditional += 1
            valid = (isinstance(junk, str) and junk.strip() and path[-1] in TEXT_FIELDS) or \
                (path[-1] == "verify_before_action" and junk is True)
            if not valid:
                unexpected += 1
                print("UNEXPECTED CONDITIONAL", path, repr(junk))
        for k in ("coverage", "miss", "supported_miss", "soundness_lower_bound"):
            if r[k] is not None and not (0 <= r[k] <= 1):
                bad_prob += 1
print(f"generated {count} raised_or_checker_error {raised} conditional_valid_text {conditional - unexpected} "
      f"unexpected_conditional {unexpected} bad_probability {bad_prob}")
ok &= raised == 0 and bad_prob == 0 and unexpected == 0
sys.exit(0 if ok else 1)
