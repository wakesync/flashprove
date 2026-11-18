"""Fixtures F136-F141, registered in PREREG.md Amendment 4 after round 2 review.
Every number here is synthetic test input, never a forecast. F01-F45 stay in fixtures.py
and F46-F135 in fixtures_r1.py, both unchanged."""
from fractions import Fraction as Fr

import fixtures_r1 as Y

MI, COND = Y.MI, Y.COND
PR = "PROOF_REJECTION_NOT_WRONG_ANSWER"


def obs_list(*pairs):
    return Y.put(["observations"], [{"type": t, "counted_as": c} for t, c in pairs])


# (id, worksheet, verdict, codes, registered values)
R2 = [
    ("F136", Y.make(Y.base, obs_list(("proof_rejected", "wrong_answer"))), MI, [PR], {}),
    ("F137", Y.make(Y.base, obs_list(("proof_rejected", "audit_failure"))), COND, [],
     {"coverage": Fr(5, 9), "miss": Fr(4, 9), "normalized_cost": Fr(47, 16)}),
    ("F138", Y.make(Y.base, obs_list(("proof_rejected", "audit_failure"), ("proof_rejected", "wrong_answer"))),
     MI, [PR], {}),
    ("F139", Y.make(Y.base, obs_list(("timeout", "wrong_answer"), ("proof_rejected", "wrong_answer"))),
     MI, [PR, "TIMEOUT_NOT_PROOF"], {}),
    ("F140", Y.make(Y.vip, obs_list(("proof_rejected", "wrong_answer"))), MI, [PR], {}),
    ("F141", Y.make(Y.base, Y.put(["population", "N", "source"], 7)), MI, ["NO_PROVENANCE"], {}),
]
