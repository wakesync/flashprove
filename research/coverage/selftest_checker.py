#!/usr/bin/env python3
"""Self-test of check_inventory.py: it must pass on the real inventory and fail on altered copies.

Mutations (each on a fresh in-memory copy of inventory.yaml):
  M1 one site's symbol changed (as if the code were renamed)
  M2 one site's file renamed (as if the file moved)
  M3 each prover_only / not_enforced row in turn dropped from every open gap (one case per row)
  M4 an unknown enforcement kind on a row
  M5 the same unknown kind on a row AND added to the inventory's declared `kinds` (review of PR #97)
  M6 an unknown category added to the declared `categories` only
  M7 a site's symbol cut to a short fragment ("refuse(")
  M8 a proof_constraint row added to a plain gap (G-01)
  M9 one excluded research directory removed from `excluded` (it is then neither cited nor excluded)
  M10 an `excluded` entry for a directory that does not exist
  M11 the open obligation G-OB2 deleted (review of PR #97, opus round 2)
  M12 OUT-09 dropped from G-OB2 (same review)
  M13 each row fixed in check_inventory.OBLIGATIONS in turn dropped from its group (one case per row)
  M14 OUT-09 relabelled proof_constraint (a fixed obligation row changing kind)
Every case must give at least one fault; the real inventory must give none.
Not tested, because the checker cannot see it: a row moved to another valid kind outside a plain
gap and outside OBLIGATIONS, a disabled check that keeps its text, a row that loses one of two sites.
Usage: python3 research/coverage/selftest_checker.py [--json OUT]
"""
import argparse
import copy
import json
import os
import sys

import yaml

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import check_inventory  # noqa: E402


def nf(m, root):
    return len(check_inventory.check(m, root)[0])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json")
    a = ap.parse_args()
    with open(os.path.join(HERE, "inventory.yaml"), encoding="utf-8") as h:
        inv = yaml.safe_load(h)
    root = check_inventory.ROOT
    out = {}
    out["real"] = {"faults": nf(inv, root), "expected": "0"}

    m = copy.deepcopy(inv)
    m["rows"][0]["sites"][0]["symbol"] += " (renamed)"
    out["M1_symbol_changed"] = {"faults": nf(m, root), "expected": ">0"}
    m = copy.deepcopy(inv)
    m["rows"][1]["sites"][0]["file"] += ".moved"
    out["M2_file_moved"] = {"faults": nf(m, root), "expected": ">0"}
    gap_rows = [r["id"] for r in inv["rows"] if r["enforcement"] in check_inventory.GAP_KINDS]
    m3 = {}
    for gone in gap_rows:
        m = copy.deepcopy(inv)
        for g in m["open_gaps"]:
            g["rows"] = [x for x in g["rows"] if x != gone]
        m3[gone] = nf(m, root)
    out["M3_gap_dropped"] = {"cases": len(m3), "cases_with_faults": sum(1 for v in m3.values() if v > 0),
                             "faults": min(m3.values()) if m3 else 0, "per_row": m3, "expected": ">0 for every row"}
    m = copy.deepcopy(inv)
    m["rows"][2]["enforcement"] = "trusted"
    out["M4_unknown_kind"] = {"faults": nf(m, root), "expected": ">0"}
    m = copy.deepcopy(inv)
    m["rows"][0]["enforcement"] = "trusted"
    m["kinds"] = list(m["kinds"]) + ["trusted"]
    out["M5_unknown_kind_declared"] = {"faults": nf(m, root), "expected": ">0"}
    m = copy.deepcopy(inv)
    m["categories"] = list(m["categories"]) + ["misc"]
    out["M6_category_declared"] = {"faults": nf(m, root), "expected": ">0"}
    m = copy.deepcopy(inv)
    m["rows"][0]["sites"][0]["symbol"] = "refuse("
    out["M7_short_symbol"] = {"faults": nf(m, root), "expected": ">0"}
    m = copy.deepcopy(inv)
    proof_row = next(r["id"] for r in m["rows"] if r["enforcement"] == "proof_constraint")
    next(g for g in m["open_gaps"] if g["id"] == "G-01")["rows"].append(proof_row)
    out["M8_proof_row_in_plain_gap"] = {"row": proof_row, "faults": nf(m, root), "expected": ">0"}
    m = copy.deepcopy(inv)
    dropped = m["excluded"].pop(0)["path"] if m.get("excluded") else None
    out["M9_excluded_dir_dropped"] = {"path": dropped, "faults": nf(m, root) if dropped else 0, "expected": ">0"}
    m = copy.deepcopy(inv)
    m.setdefault("excluded", []).append({"path": "research/operators/no_such_dir", "reason": "test"})
    out["M10_excluded_missing_dir"] = {"faults": nf(m, root), "expected": ">0"}
    m = copy.deepcopy(inv)
    m["open_gaps"] = [g for g in m["open_gaps"] if g["id"] != "G-OB2"]
    out["M11_obligation_G-OB2_deleted"] = {"faults": nf(m, root), "expected": ">0"}
    m = copy.deepcopy(inv)
    g = next(g for g in m["open_gaps"] if g["id"] == "G-OB2")
    g["rows"] = [x for x in g["rows"] if x != "OUT-09"]
    out["M12_OUT-09_dropped_from_G-OB2"] = {"faults": nf(m, root), "expected": ">0"}
    m13 = {}
    for gid, fixed in check_inventory.OBLIGATIONS.items():
        for rid in fixed:
            m = copy.deepcopy(inv)
            g = next(g for g in m["open_gaps"] if g["id"] == gid)
            g["rows"] = [x for x in g["rows"] if x != rid]
            m13[gid + "/" + rid] = nf(m, root)
    out["M13_obligation_row_dropped"] = {"cases": len(m13), "cases_with_faults": sum(1 for v in m13.values() if v > 0),
                                         "faults": min(m13.values()) if m13 else 0, "per_row": m13,
                                         "expected": ">0 for every row"}
    m = copy.deepcopy(inv)
    next(r for r in m["rows"] if r["id"] == "OUT-09")["enforcement"] = "proof_constraint"
    out["M14_OUT-09_kind_changed"] = {"faults": nf(m, root), "expected": ">0"}

    ok = out["real"]["faults"] == 0 and all(v["faults"] > 0 for k, v in out.items() if k != "real")
    ok = ok and out["M3_gap_dropped"]["cases"] == out["M3_gap_dropped"]["cases_with_faults"] > 0
    ok = ok and out["M13_obligation_row_dropped"]["cases"] == out["M13_obligation_row_dropped"]["cases_with_faults"] > 0
    out["ok"] = ok
    print(json.dumps(out, indent=1, sort_keys=True))
    if a.json:
        if os.path.exists(a.json):
            print("refusing to overwrite " + a.json)
            return 2
        with open(a.json, "w", encoding="utf-8") as h:
            json.dump(out, h, indent=1, sort_keys=True)
            h.write("\n")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
