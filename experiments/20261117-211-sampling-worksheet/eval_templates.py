"""Evaluate the three blank policy templates. Expected: MISSING INPUTS for each.
Usage: python3 eval_templates.py --out runs/templates.json (refuses overwrite)."""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import worksheet as W  # noqa: E402
from run_suite import enc  # noqa: E402


def strip_nulls(o):
    """A null numeric field means 'not supplied'."""
    if isinstance(o, dict):
        return {k: strip_nulls(v) for k, v in o.items() if v is not None}
    return o


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    if os.path.exists(a.out):
        sys.exit(f"refusing to overwrite {a.out}")
    with open(os.path.join(HERE, "templates.json")) as fh:
        t = json.load(fh)["templates"]
    res = {name: enc(W.evaluate(strip_nulls(ws))) for name, ws in sorted(t.items())}
    with open(a.out, "x") as fh:
        json.dump(res, fh, sort_keys=True, indent=1)
        fh.write("\n")
    for name, r in res.items():
        print(name, r["verdict"], r["codes"], "unknowns:", r["unknowns"])
    return 0 if all(r["verdict"] == "MISSING INPUTS" for r in res.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
