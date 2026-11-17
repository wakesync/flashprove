"""Run the amended suite once (PREREG Amendments 1 and 2) and write a canonical JSON report.

F01-F45 come from the unchanged fixtures.py and are compared with their ORIGINAL registration.
F37-F45 are also compared with the outcome registered in Amendment 2.
F46-F135 come from fixtures_r1.py.

Usage: python3 run_suite_r1.py --run K --out runs-r1/run-K.json
Refuses to overwrite an existing output file. Deterministic: no randomness, no timing.
"""
import argparse
import hashlib
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fixtures as X  # noqa: E402
import fixtures_r1 as Y  # noqa: E402
import worksheet as W  # noqa: E402
from run_suite import enc, run as run_original  # noqa: E402

NUMBERS = ("coverage", "miss", "supported_miss", "soundness_lower_bound",
           "cost_per_request", "normalized_cost", "deterrence")


def check_r1(res, verdict, codes, extra):
    ok = res["verdict"] == verdict and res["codes"] == sorted(codes)
    for k, want in extra.items():
        if k == "assumption_contains":
            ok = ok and any(want in a for a in res.get("assumptions", []))
        elif k == "deterrence_product":
            det = res.get("deterrence") or {}
            ok = ok and det.get("P_detect_times_loss") == want
        else:
            ok = ok and res.get(k) == want
    if verdict == Y.MI:
        # Amendment 1 rule 12: a MISSING INPUTS result carries no number at all
        ok = ok and all(res.get(k) is None for k in NUMBERS)
    for k in ("coverage", "miss", "supported_miss", "soundness_lower_bound"):
        if res.get(k) is not None:
            ok = ok and 0 <= res[k] <= 1
    return ok


def run():
    original = run_original()          # F01-F45 against the original registration
    for f in original:
        f["match_original"] = f.pop("match")
    a2 = []
    for fid, verdict, codes in Y.A2:
        ws = next(row[1] for row in X.POLICY if row[0] == fid)
        res = W.evaluate(ws)
        a2.append({"id": fid, "kind": "amendment2", "result": res, "expected_verdict": verdict,
                   "expected_codes": sorted(codes), "match": check_r1(res, verdict, codes, {})})
    new = []
    for fid, ws, verdict, codes, extra in Y.R1:
        res = W.evaluate(ws)
        new.append({"id": fid, "kind": "r1", "result": res, "expected_verdict": verdict,
                    "expected_codes": sorted(codes), "expected_values": extra,
                    "match": check_r1(res, verdict, codes, extra)})
    return original, a2, new


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", type=int, required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    if os.path.exists(a.out):
        sys.exit(f"refusing to overwrite {a.out}")
    original, a2, new = run()
    keep = [f["id"] for f in original if f["match_original"]]
    lost = [f["id"] for f in original if not f["match_original"]]
    f01_f36 = [f"F{i:02d}" for i in range(1, 37)]
    summary = {
        "original_registered": len(original),
        "original_still_matching_original_registration": len(keep),
        "original_not_matching_original_registration": lost,
        "f01_f36_all_match": all(i in keep for i in f01_f36),
        "amendment2_registered": len(a2),
        "amendment2_matched": sum(1 for f in a2 if f["match"]),
        "new_registered": len(new),
        "new_matched": sum(1 for f in new if f["match"]),
        "new_not_matched": [f["id"] for f in new if not f["match"]],
    }
    body = enc({"experiment": "20261117-211-sampling-worksheet", "suite": "amended (round 1)",
                "summary": summary, "original": original, "amendment2": a2, "new": new,
                "all_numbers_synthetic_unless_source_on_main": True})
    canon = json.dumps(body, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(canon.encode()).hexdigest()
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    with open(a.out, "x") as fh:
        json.dump({"run": a.run, "report_sha256": digest, "report": body}, fh, sort_keys=True, indent=1)
        fh.write("\n")
    print(f"run {a.run}: original {summary['original_still_matching_original_registration']}/45 "
          f"(not matching: {lost}); amendment2 {summary['amendment2_matched']}/{len(a2)}; "
          f"new {summary['new_matched']}/{len(new)} (not matched: {summary['new_not_matched']}); "
          f"sha256 {digest}")
    ok = (summary["f01_f36_all_match"] and len(original) == 45 and len(a2) == 9
          and summary["amendment2_matched"] == 9 and len(new) == 90 and summary["new_matched"] == 90)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
