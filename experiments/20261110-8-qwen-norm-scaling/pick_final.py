#!/usr/bin/env python3
"""Name the arm for the abliterated identity rerun, by the PREREG rule: the cheapest passing registered candidate
(counted keys + columns + range cells per head per token, runs/cost.json); if none passes, the registered candidate
with every class in bounds on 480 / 480 pairs and the lowest median rel_y. Prints the arm name; writes runs/final-arm.json."""
import json
from pathlib import Path
R = Path(__file__).resolve().parent / "runs"
s = json.load(open(R / "cand-stock.summary.json")); cost = json.load(open(R / "cost.json"))
c = lambda a: sum(cost[a]["per_head_token"][k] for k in ("keys", "cols", "rcells")) if a in cost else float("inf")
# registered candidates only: X1 to X3 are post-registration (A-2) and cannot be the verdict arm; D-R15 and C3P-S14 are descriptive
reg = [a for a in s if a not in ("C0", "D-R15", "C3P-S14", "X1", "X2", "X3") and s[a].get("n") == 480]
passing = sorted([a for a in reg if s[a]["pass"]], key=c)
inb = sorted([a for a in reg if s[a]["pairs_in_bounds"] == 480], key=lambda a: s[a]["rel_y"]["median"])
arm = passing[0] if passing else (inb[0] if inb else "C0")
(R / "final-arm.json").write_text(json.dumps(dict(arm=arm, rule="cheapest passing" if passing else "none passes: lowest median rel_y among in-bounds arms",
                                                  passing=passing, in_bounds_by_rel_y=inb), indent=1) + "\n")
print(arm)
