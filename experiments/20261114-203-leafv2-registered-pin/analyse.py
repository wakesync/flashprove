#!/usr/bin/env python3
"""Check the #203 suite receipts against the PREREG and against main's receipt (issue #203).

Reads committed files only: the two receipts of this experiment and main's receipt
experiments/20261113-189-missing-metadata/runs/evidence-tests-stoprule-20261114.json. Writes runs/analysis.json.

Checks: (C) every expectation in main's receipt other than the 18 switched stop-rule-189-* summarise
expectations appears unchanged (case, reader, run, expected, expected_reason, got, ok) in this receipt;
(B) the 18 switched expectations are present as summarise-registered / refused; (A) every pin203-191-* case
(#191's 23) is refused by summarise-registered and none gives PASS; (D) honest registered PASS single-run;
the two receipts give identical outcomes. Exit 0 iff all hold.

Usage (from the top of the tree): analyse.py
"""
import json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
MAIN = ROOT / "experiments/20261113-189-missing-metadata/runs/evidence-tests-stoprule-20261114.json"
R1, R2 = HERE / "runs/evidence-tests-1.json", HERE / "runs/evidence-tests-2.json"
KEY = ("case", "reader", "run", "expected", "expected_reason", "got", "ok")


def key(r):
    return tuple(json.dumps(r.get(k), sort_keys=True) for k in KEY)


def main():
    old, a, b = (json.loads(p.read_text()) for p in (MAIN, R1, R2))
    switched = [r for r in old["results"] if r["case"].startswith("stop-rule-189-") and r["reader"] == "summarise"]
    kept = [r for r in old["results"] if r not in switched]
    new_keys = {}
    for r in a["results"]:
        new_keys[key(r)] = new_keys.get(key(r), 0) + 1
    old_keys = {}
    for r in kept:
        old_keys[key(r)] = old_keys.get(key(r), 0) + 1
    missing = [k for k, n in old_keys.items() if new_keys.get(k, 0) < n]
    sw_new = [r for r in a["results"] if r["case"].startswith("stop-rule-189-") and r["reader"] == "summarise-registered"]
    sw_ok = (sorted(r["case"] for r in sw_new) == sorted(r["case"] for r in switched)
             and all(r["expected"] == r["got"] == "refused" and r["ok"] for r in sw_new))
    limits = {r["case"][len("pin203-default-mode-limit-"):]: r["got"] for r in a["results"]
              if r["case"].startswith("pin203-default-mode-limit-")}
    c191 = {}
    for r in a["results"]:
        if r["case"].startswith("pin203-191-"):
            c191.setdefault(r["case"][len("pin203-191-"):], []).append(
                dict(reader=r["reader"], run=r["run"], expected=r["expected"], got=r["got"], ok=r["ok"]))
    reg_summ = {c: [x["got"] for x in v if x["reader"] == "summarise-registered"][0] for c, v in c191.items()}
    defeat = {r["case"]: dict(reader=r["reader"], got=r["got"], ok=r["ok"]) for r in a["results"]
              if r["case"].startswith("pin203-D") or r["case"].startswith("pin203-E")}
    honest = [r for r in a["results"] if r["case"] == "pin203-honest-registered"]
    outcomes = lambda d: [(r["case"], r["reader"], r["run"], r["got"], r["ok"]) for r in d["results"]]
    out = dict(
        note="issue #203 receipt analysis, measured, unreplicated; deterministic file reads, no spread",
        main_receipt=dict(n_cases=old["n_cases"], n_checks=old["n_checks"], n_pass=old["n_pass"]),
        receipt_1=dict(n_cases=a["n_cases"], n_checks=a["n_checks"], n_pass=a["n_pass"]),
        receipt_2=dict(n_cases=b["n_cases"], n_checks=b["n_checks"], n_pass=b["n_pass"]),
        receipts_identical_outcomes=outcomes(a) == outcomes(b),
        receipts_byte_identical=R1.read_bytes() == R2.read_bytes(),
        switched_expectations=len(switched), switched_now_refused_registered=sw_ok,
        non_switched_existing_expectations=len(kept), non_switched_kept_unchanged=len(kept) - len(missing),
        non_switched_missing_or_changed=[list(k) for k in missing],
        default_mode_limit_outcomes=limits,
        default_mode_full_pass_cases=sorted(c for c, g in limits.items() if g == "PASS"),
        cases_191=len(c191), cases_191_registered_summarise=reg_summ,
        cases_191_registered_refused=sum(g == "refused" for g in reg_summ.values()),
        cases_191_registered_pass=sorted(c for c, g in reg_summ.items() if g == "PASS"),
        cases_191_all_expectations_ok=all(x["ok"] for v in c191.values() for x in v),
        defeat_cases=defeat,
        defeat_full_pass_on_altered_evidence=sorted(c for c, v in defeat.items()
                                                    if v["got"] == "PASS" and "D12" not in c and "D10" not in c),
        honest_registered=[dict(reader=r["reader"], run=r["run"], got=r["got"], ok=r["ok"]) for r in honest])
    ok = (a["n_pass"] == a["n_checks"] and b["n_pass"] == b["n_checks"] and out["receipts_identical_outcomes"]
          and sw_ok and not missing and len(c191) == 23 and out["cases_191_registered_refused"] == 23
          and not out["cases_191_registered_pass"] and out["cases_191_all_expectations_ok"]
          and all(r["ok"] for r in honest))
    out["all_prereg_checks_hold"] = ok
    (HERE / "runs/analysis.json").write_text(json.dumps(out, indent=1, sort_keys=True) + "\n")
    print(json.dumps({k: v for k, v in out.items() if k not in ("defeat_cases", "cases_191_registered_summarise",
                                                                "default_mode_limit_outcomes")}, sort_keys=True))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
