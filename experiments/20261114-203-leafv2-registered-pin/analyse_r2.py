#!/usr/bin/env python3
"""Check the round-2 suite receipts of issue #203 (PREREG amendments A-1 / A-2, after review round 1 of PR #205).

Reads committed files only and writes runs/analysis-r2.json. It does not touch runs/analysis.json, which
belongs to the reviewed head together with runs/evidence-tests-1.json and -2.json.

Inputs: main's receipt (experiments/20261113-189-missing-metadata/runs/evidence-tests-stoprule-20261114.json),
the reviewed head's receipt (runs/evidence-tests-1.json), the two receipts of the changed code
(runs/evidence-tests-r2-1.json, -r2-2.json) and runs/default-mode-main-suite-r2.json (main's own test file
run against the changed code).

Checks: the two new receipts pass in full and are identical; every expectation of the reviewed head's
receipt is present unchanged (all fields) in the new one; main's non-switched expectations are unchanged;
the 23 #191 cases are refused in registered mode; the read-once cases (R1, R2) and the command-line cases
hold; the default-mode receipt is byte-identical to main's. Defeat cases are listed per case with every
reader, and the count of registered-mode defeat cases is written out so that it can be traced.
Exit 0 iff all hold.

Usage (from the top of the tree): analyse_r2.py
"""
import json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
MAIN = ROOT / "experiments/20261113-189-missing-metadata/runs/evidence-tests-stoprule-20261114.json"
OLD = HERE / "runs/evidence-tests-1.json"
R1, R2 = HERE / "runs/evidence-tests-r2-1.json", HERE / "runs/evidence-tests-r2-2.json"
DEFAULT = HERE / "runs/default-mode-main-suite-r2.json"
KEY = ("case", "reader", "run", "expected", "expected_reason", "got", "ok")
REG_READERS = ("summarise-registered", "summarise-registered (in-process, pin seam)", "compare-registered",
               "compare --registered (command line)")


def key(r, fields=KEY):
    return tuple(json.dumps(r.get(k), sort_keys=True) for k in fields)


def count(rs, fields=KEY):
    out = {}
    for r in rs:
        out[key(r, fields)] = out.get(key(r, fields), 0) + 1
    return out


def missing(old, new, fields=KEY):
    have = count(new, fields)
    return [list(k) for k, n in count(old, fields).items() if have.get(k, 0) < n]


def main():
    main_r, old, a, b = (json.loads(p.read_text()) for p in (MAIN, OLD, R1, R2))
    res = a["results"]
    switched = [r for r in main_r["results"] if r["case"].startswith("stop-rule-189-") and r["reader"] == "summarise"]
    kept = [r for r in main_r["results"] if r not in switched]
    all_fields = tuple(sorted({k for r in old["results"] for k in r}))
    old_missing_key = missing(old["results"], res)
    old_missing_all = missing(old["results"], res, all_fields)
    main_missing = missing(kept, res)
    c191 = {}
    for r in res:
        if r["case"].startswith("pin203-191-"):
            c191.setdefault(r["case"][len("pin203-191-"):], []).append(r)
    reg_summ = {c: [x["got"] for x in v if x["reader"] == "summarise-registered"][0] for c, v in c191.items()}
    limits = {r["case"][len("pin203-default-mode-limit-"):]: r["got"] for r in res
              if r["case"].startswith("pin203-default-mode-limit-")}

    # Defeat cases D1 to D12, every reader kept. D3 has no case of its own in the suite: it is the
    # pin203-default-mode-limit-* expectations (default mode), counted separately below.
    defeat = {}
    for r in res:
        if r["case"].startswith("pin203-D"):
            defeat.setdefault(r["case"], []).append(dict(reader=r["reader"], run=r["run"], got=r["got"], ok=r["ok"],
                                                         registered_mode=r["reader"] in REG_READERS))
    # D12 (the honest files copied unchanged) is a correct acceptance, not altered evidence.
    honest_copy = sorted(c for c in defeat if "D12" in c)
    full_pass_reg = sorted(c for c, v in defeat.items() if c not in honest_copy
                           and any(x["registered_mode"] and x["got"] == "PASS" for x in v))
    full_pass_default_only = sorted(c for c, v in defeat.items() if c not in honest_copy and c not in full_pass_reg
                                    and any(not x["registered_mode"] and x["got"] == "PASS" for x in v))
    e_case = [dict(reader=r["reader"], got=r["got"], ok=r["ok"]) for r in res if r["case"].startswith("pin203-E")]

    r2 = [r for r in res if r["case"].startswith("pin203-r2-")]
    before = [r for r in r2 if r["case"].startswith("pin203-r2-changed-before-read-")]
    p6 = [r for r in r2 if r["case"] == "pin203-r2-P6-swapped-after-check"]
    cli = [r for r in r2 if r["case"].startswith("pin203-r2-cli-")]
    slim = lambda rs: [dict(case=r["case"], reader=r["reader"], expected=r["expected"], got=r["got"], ok=r["ok"]) for r in rs]
    new_only = [r for r in res if count(old["results"], all_fields).get(key(r, all_fields), 0) == 0]
    outcomes = lambda d: [(r["case"], r["reader"], r["run"], r["got"], r["ok"]) for r in d["results"]]
    default_same = DEFAULT.read_bytes() == MAIN.read_bytes()

    out = dict(
        note="issue #203, round 2 (PREREG amendments A-1 / A-2 after review round 1 of PR 205): receipt analysis of the "
             "changed code; measured, unreplicated; deterministic file reads, no spread; hash level, NOT A PROOF",
        receipts_of_the_reviewed_head="runs/evidence-tests-1.json, runs/evidence-tests-2.json, runs/analysis.json (kept unchanged)",
        main_receipt=dict(n_cases=main_r["n_cases"], n_checks=main_r["n_checks"], n_pass=main_r["n_pass"]),
        reviewed_head_receipt=dict(n_cases=old["n_cases"], n_checks=old["n_checks"], n_pass=old["n_pass"]),
        receipt_r2_1=dict(n_cases=a["n_cases"], n_checks=a["n_checks"], n_pass=a["n_pass"]),
        receipt_r2_2=dict(n_cases=b["n_cases"], n_checks=b["n_checks"], n_pass=b["n_pass"]),
        receipts_identical_outcomes=outcomes(a) == outcomes(b),
        receipts_byte_identical=R1.read_bytes() == R2.read_bytes(),
        reviewed_head_expectations=len(old["results"]),
        reviewed_head_expectations_kept_all_fields=len(old["results"]) - len(old_missing_all),
        reviewed_head_expectations_kept_outcome_fields=len(old["results"]) - len(old_missing_key),
        reviewed_head_expectations_missing_or_changed=old_missing_all,
        new_expectations=len(new_only), new_cases=sorted({r["case"] for r in new_only}),
        switched_expectations=len(switched),
        non_switched_existing_expectations=len(kept), non_switched_kept_unchanged=len(kept) - len(main_missing),
        non_switched_missing_or_changed=main_missing,
        default_mode_limit_expectations=len(limits),
        default_mode_limit_outcomes=limits,
        default_mode_limit_by_outcome={g: sum(1 for x in limits.values() if x == g) for g in sorted(set(limits.values()))},
        default_mode_full_pass_cases=sorted(c for c, g in limits.items() if g == "PASS"),
        cases_191=len(c191), cases_191_registered_summarise=reg_summ,
        cases_191_registered_refused=sum(g == "refused" for g in reg_summ.values()),
        cases_191_registered_pass=sorted(c for c, g in reg_summ.items() if g == "PASS"),
        cases_191_all_expectations_ok=all(x["ok"] for v in c191.values() for x in v),
        defeat_cases=defeat,
        defeat_cases_in_suite=sorted(defeat),
        defeat_cases_in_suite_n=len(defeat),
        defeat_case_D3_note="D3 (the altered inputs through the default mode) has no case of its own: it is the "
                            "pin203-default-mode-limit-* expectations, counted under default_mode_limit_*",
        defeat_honest_copy_cases=honest_copy,
        defeat_full_pass_on_altered_evidence_registered=full_pass_reg,
        defeat_full_pass_on_altered_evidence_registered_n=len(full_pass_reg),
        defeat_full_pass_default_mode_only=full_pass_default_only,
        pass_union_case=e_case,
        read_once_changed_before_read=slim(before),
        read_once_changed_before_read_refused=sum(r["got"] == "refused" and r["ok"] for r in before),
        read_once_changed_before_read_n=len(before),
        read_once_swapped_after_check=slim(p6),
        read_once_expectations=len(before) + len(p6),
        read_once_expectations_ok=sum(r["ok"] for r in before + p6),
        command_line_refusals=slim(cli), command_line_refusals_ok=sum(r["ok"] for r in cli),
        default_mode_main_suite=dict(file="runs/default-mode-main-suite-r2.json",
                                     byte_identical_to_main_receipt=default_same,
                                     n_checks=json.loads(DEFAULT.read_text())["n_checks"],
                                     n_pass=json.loads(DEFAULT.read_text())["n_pass"]))
    ok = (a["n_pass"] == a["n_checks"] and b["n_pass"] == b["n_checks"] and out["receipts_identical_outcomes"]
          and not old_missing_all and not main_missing and len(c191) == 23 and out["cases_191_registered_refused"] == 23
          and not out["cases_191_registered_pass"] and out["cases_191_all_expectations_ok"]
          and len(before) == 7 and out["read_once_changed_before_read_refused"] == 7
          and len(p6) == 4 and all(r["ok"] for r in p6) and len(cli) == 4 and all(r["ok"] for r in cli)
          and default_same)
    out["all_checks_hold"] = ok
    (HERE / "runs/analysis-r2.json").write_text(json.dumps(out, indent=1, sort_keys=True) + "\n")
    print(json.dumps({k: v for k, v in out.items() if k not in ("defeat_cases", "cases_191_registered_summarise",
                                                                "default_mode_limit_outcomes", "new_cases")}, sort_keys=True))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
