"""Debug fixtures DBG-01..03 (PREREG Runs). Not part of the registered suite."""
import os
import sys
from fractions import Fraction as Fr

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fixtures as X  # noqa: E402
import worksheet as W  # noqa: E402

ok = True
a = W.bernoulli_fixed_d(Fr(1, 3), 2)
print("DBG-01", a, a == Fr(5, 9))
ok &= a == Fr(5, 9)
b = W.no_replacement(5, 2, 1)
print("DBG-02", b, b == Fr(2, 5))
ok &= b == Fr(2, 5)
ws = X.cost_ws(X.with_costs(C=X.v("1/100", "apples")))
r = X.evaluate_costs_only(ws)
print("DBG-03", r["verdict"], r["codes"])
ok &= "UNIT_UNKNOWN" in r["codes"] and r["verdict"] == "MISSING INPUTS"
sys.exit(0 if ok else 1)
