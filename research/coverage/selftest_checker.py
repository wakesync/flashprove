#!/usr/bin/env python3
"""Self-test of check_inventory.py: it must pass on the real inventory and fail on altered copies.

Mutations (each on a fresh in-memory copy of inventory.yaml):
  M1 one site's symbol changed (as if the code were renamed)
  M2 one site's file renamed (as if the file moved)
  M3 a not_enforced row dropped from every open gap
  M4 an unknown enforcement kind
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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json")
    a = ap.parse_args()
    with open(os.path.join(HERE, "inventory.yaml"), encoding="utf-8") as h:
        inv = yaml.safe_load(h)
    root = check_inventory.ROOT
    out = {}
    faults, _ = check_inventory.check(inv, root)
    out["real"] = {"faults": len(faults), "expected": "0"}

    m = copy.deepcopy(inv)
    m["rows"][0]["sites"][0]["symbol"] += " (renamed)"
    out["M1_symbol_changed"] = {"faults": len(check_inventory.check(m, root)[0]), "expected": ">0"}
    m = copy.deepcopy(inv)
    m["rows"][1]["sites"][0]["file"] += ".moved"
    out["M2_file_moved"] = {"faults": len(check_inventory.check(m, root)[0]), "expected": ">0"}
    m = copy.deepcopy(inv)
    gone = next(r["id"] for r in m["rows"] if r["enforcement"] == "not_enforced")
    for g in m["open_gaps"]:
        g["rows"] = [x for x in g["rows"] if x != gone]
    out["M3_gap_dropped"] = {"row": gone, "faults": len(check_inventory.check(m, root)[0]), "expected": ">0"}
    m = copy.deepcopy(inv)
    m["rows"][2]["enforcement"] = "trusted"
    out["M4_unknown_kind"] = {"faults": len(check_inventory.check(m, root)[0]), "expected": ">0"}

    ok = out["real"]["faults"] == 0 and all(v["faults"] > 0 for k, v in out.items() if k != "real")
    out["ok"] = ok
    print(json.dumps(out, indent=1, sort_keys=True))
    if a.json:
        with open(a.json, "w", encoding="utf-8") as h:
            json.dump(out, h, indent=1, sort_keys=True)
            h.write("\n")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
