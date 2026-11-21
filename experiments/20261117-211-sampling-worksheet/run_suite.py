"""Run the registered fixture suite F01-F45 once and write a canonical JSON report.

Usage: python3 run_suite.py --run K --out runs/run-K.json
Refuses to overwrite an existing output file. Deterministic: no randomness, no timing.
"""
import argparse
import hashlib
import json
import os
import sys
from fractions import Fraction

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fixtures as X  # noqa: E402
import worksheet as W  # noqa: E402


def enc(o):
    if isinstance(o, Fraction):
        return f"{o.numerator}/{o.denominator}"
    if isinstance(o, dict):
        return {k: enc(val) for k, val in o.items()}
    if isinstance(o, (list, tuple)):
        return [enc(x) for x in o]
    return o


def check_expect(res, verdict, codes, extra):
    ok = res["verdict"] == verdict and res["codes"] == sorted(codes)
    for k, want in extra.items():
        if k == "assumption_contains":
            ok = ok and any(want in a for a in res.get("assumptions", []))
        else:
            ok = ok and res.get(k) == want
    return ok


def run():
    out = []
    for fid, fn, want in X.FORMULA:
        got = fn()
        out.append({"id": fid, "kind": "formula", "got": got, "expected": want, "match": got == want})
    for fid, n, d, m, pub in X.CELLS84:
        exact = W.no_replacement(n, m, d)
        s = W.pct4(exact)
        out.append({"id": fid, "kind": "cell84", "N": n, "D": d, "m": m, "exact": exact,
                    "formatted": s, "published": pub, "match": s == pub})
    for fid, ws, verdict, codes, extra in X.COST:
        res = X.evaluate_costs_only(ws)
        out.append({"id": fid, "kind": "cost", "result": res, "expected_verdict": verdict,
                    "expected_codes": sorted(codes), "match": check_expect(res, verdict, codes, extra)})
    for fid, ws, verdict, codes, extra in X.POLICY:
        res = W.evaluate(ws)
        out.append({"id": fid, "kind": "policy", "result": res, "expected_verdict": verdict,
                    "expected_codes": sorted(codes), "match": check_expect(res, verdict, codes, extra)})
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", type=int, required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    if os.path.exists(a.out):
        sys.exit(f"refusing to overwrite {a.out}")
    fx = run()
    body = enc({"experiment": "20261117-211-sampling-worksheet", "fixtures": fx,
                "registered_total": 45, "matched": sum(1 for f in fx if f["match"]),
                "all_numbers_synthetic_unless_source_on_main": True})
    canon = json.dumps(body, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(canon.encode()).hexdigest()
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    with open(a.out, "x") as fh:
        json.dump({"run": a.run, "report_sha256": digest, "report": body}, fh, sort_keys=True, indent=1)
        fh.write("\n")
    print(f"run {a.run}: matched {body['matched']}/{len(fx)} sha256 {digest}")
    return 0 if body["matched"] == 45 and len(fx) == 45 else 1


if __name__ == "__main__":
    sys.exit(main())
