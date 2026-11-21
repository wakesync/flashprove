"""Debug inputs DBG-18 onward (PREREG Amendment 4, debug rule). Not part of any registered
suite and not F01-F141: a base that no registered fixture uses (N=9, p=1/4, D=2, other costs).
Checks the observation rule of Amendment 4 before the registered runs."""
import os
import sys
from fractions import Fraction as Fr

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import worksheet as W  # noqa: E402

PR = "PROOF_REJECTION_NOT_WRONG_ANSWER"
VIP = "vendor_independent_proof_irreversible"


def v(x, u):
    return {"value": str(x), "unit": u, "kind": "synthetic", "source": "synthetic:debug"}


def dbg(*pairs, cls=None):
    ws = {"policy_class": "fleet_monitoring_after_release", "relation": "debug relation",
          "population": {"definition": "debug population", "N": v(9, "request")},
          "sampling": {"scheme": "bernoulli_p", "p": v("1/4", "request_fraction"),
                       "schedule": "fixed_in_advance"},
          "invalidity": {"D": v(2, "request")},
          "soundness_treatment": {"text": "debug"},
          "costs": {"I": v(5, "cpu_s_per_request"), "P": v(8, "cpu_s_per_request"),
                    "C": v(1, "cpu_s_per_request"), "A": v(0, "cpu_s_per_request"),
                    "F": v(18, "cpu_s_per_epoch")},
          "latency": {"deadline_policy": "debug", "verify_before_action": False},
          "targets": {"desired_miss_probability": v("3/5", "probability")},
          "deterrence": {"state": "not_modeled"},
          "claims": {"individual_guarantee": False}}
    if cls == VIP:
        ws["policy_class"] = VIP
        ws["sampling"]["p"] = v(1, "request_fraction")
        ws["latency"]["verify_before_action"] = True
        del ws["invalidity"]
        del ws["targets"]
    if pairs:
        ws["observations"] = [{"type": t, "counted_as": c} for t, c in pairs]
    return ws


ok = True


def expect(name, ws, verdict, codes, **vals):
    global ok
    r = W.evaluate(ws)
    good = r["verdict"] == verdict and r["codes"] == sorted(codes)
    for k, want in vals.items():
        good = good and r.get(k) == want
    if verdict == "MISSING INPUTS":
        good = good and all(r.get(k) is None for k in ("coverage", "miss", "supported_miss",
                                                       "cost_per_request", "normalized_cost"))
    ok &= good
    print(name, "OK" if good else "MISMATCH", r["verdict"], r["codes"], r["coverage"], r["normalized_cost"])


PRW, PRA = ("proof_rejected", "wrong_answer"), ("proof_rejected", "audit_failure")
# 1-(3/4)^2 = 7/16; cost 5+1+0+18/9+8/4 = 10, normalized 2
CTRL = {"coverage": Fr(7, 16), "normalized_cost": Fr(2)}
expect("DBG-18 control, no observation", dbg(), "CONDITIONAL", [], **CTRL)
expect("DBG-19 proof_rejected as wrong_answer", dbg(PRW), "MISSING INPUTS", [PR])
expect("DBG-20 proof_rejected as audit_failure", dbg(PRA), "CONDITIONAL", [], **CTRL)
expect("DBG-21 accepted then refused", dbg(PRA, PRW), "MISSING INPUTS", [PR])
expect("DBG-22 refused then accepted", dbg(PRW, PRA), "MISSING INPUTS", [PR])
expect("DBG-23 refusal and proof rejection as wrong_answer", dbg(("refusal", "wrong_answer"), PRW),
       "MISSING INPUTS", [PR, "TIMEOUT_NOT_PROOF"])
expect("DBG-24 vendor-independent class", dbg(PRW, cls=VIP), "MISSING INPUTS", [PR])
expect("DBG-25 vendor-independent control", dbg(PRA, cls=VIP), "CONDITIONAL", [], coverage=Fr(1))
expect("DBG-26 all three types as audit_failure",
       dbg(("timeout", "audit_failure"), ("refusal", "audit_failure"), PRA), "CONDITIONAL", [], **CTRL)
expect("DBG-27 unknown counted_as", dbg(("proof_rejected", "relation_violation")), "MISSING INPUTS",
       ["BAD_OBSERVATION"])
sys.exit(0 if ok else 1)
