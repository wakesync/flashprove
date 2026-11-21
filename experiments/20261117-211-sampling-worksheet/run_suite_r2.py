"""Run the round 2 suite once (PREREG Amendment 4) and write a canonical JSON report.

F01-F45 come from the unchanged fixtures.py (compared with their ORIGINAL registration; F37-F45
also with the outcome registered in Amendment 2), F46-F135 from the unchanged fixtures_r1.py,
F136-F141 from fixtures_r2.py. The comparison code is the unchanged run_suite_r1.py.

Usage: python3 run_suite_r2.py --run K --out runs-r2/run-K.json
Refuses to overwrite an existing output file. Deterministic: no randomness, no timing.
"""
import argparse
import hashlib
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fixtures_r2 as Z  # noqa: E402
import worksheet as W  # noqa: E402
from run_suite import enc  # noqa: E402
from run_suite_r1 import check_r1, run as run_r1  # noqa: E402


def run():
    original, a2, r1 = run_r1()
    r2 = []
    for fid, ws, verdict, codes, extra in Z.R2:
        res = W.evaluate(ws)
        r2.append({"id": fid, "kind": "r2", "result": res, "expected_verdict": verdict,
                   "expected_codes": sorted(codes), "expected_values": extra,
                   "match": check_r1(res, verdict, codes, extra)})
    return original, a2, r1, r2


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", type=int, required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    if os.path.exists(a.out):
        sys.exit(f"refusing to overwrite {a.out}")
    original, a2, r1, r2 = run()
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
        "r1_registered": len(r1),
        "r1_matched": sum(1 for f in r1 if f["match"]),
        "r1_not_matched": [f["id"] for f in r1 if not f["match"]],
        "r2_registered": len(r2),
        "r2_matched": sum(1 for f in r2 if f["match"]),
        "r2_not_matched": [f["id"] for f in r2 if not f["match"]],
    }
    body = enc({"experiment": "20261117-211-sampling-worksheet", "suite": "round 2 (Amendment 4)",
                "summary": summary, "original": original, "amendment2": a2, "r1": r1, "r2": r2,
                "all_numbers_synthetic_unless_source_on_main": True})
    canon = json.dumps(body, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(canon.encode()).hexdigest()
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    with open(a.out, "x") as fh:
        json.dump({"run": a.run, "report_sha256": digest, "report": body}, fh, sort_keys=True, indent=1)
        fh.write("\n")
    print(f"run {a.run}: original {summary['original_still_matching_original_registration']}/45 "
          f"(not matching: {lost}); amendment2 {summary['amendment2_matched']}/{len(a2)}; "
          f"r1 F46-F135 {summary['r1_matched']}/{len(r1)} (not matched: {summary['r1_not_matched']}); "
          f"r2 F136-F141 {summary['r2_matched']}/{len(r2)} (not matched: {summary['r2_not_matched']}); "
          f"sha256 {digest}")
    ok = (summary["f01_f36_all_match"] and len(original) == 45 and len(a2) == 9
          and summary["amendment2_matched"] == 9 and len(r1) == 90 and summary["r1_matched"] == 90
          and len(r2) == 6 and summary["r2_matched"] == 6)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
