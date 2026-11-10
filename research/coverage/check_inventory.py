#!/usr/bin/env python3
"""Check research/coverage/inventory.yaml against the tree, so that the inventory cannot rot silently.

Fails (exit 1) if:
  - a row lacks a field, or has an unknown category, kind or scope, or a duplicate id;
  - a row has no site, or a site's file is missing, or its symbol no longer occurs in the file;
  - a prover_only or not_enforced row is not listed in any open gap, or a gap names an unknown row.
Prints counts by category and kind, and with --json writes them as JSON.

Usage: python3 research/coverage/check_inventory.py [--inventory PATH] [--root DIR] [--json OUT]
Standard library plus PyYAML (the same dependency as scripts/update-results.py).
A site check says that the cited code is still there; it does not say that the code is correct.
"""
import argparse
import collections
import json
import os
import sys

import yaml

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
NEEDED = ("id", "category", "scope", "element", "relation", "enforcement", "sites")
SCOPES = ("shipped", "research")
GAP_KINDS = ("prover_only", "not_enforced")
MIN_ROWS = 40


def check(inv, root):
    faults = []
    kinds, cats = inv.get("kinds") or [], inv.get("categories") or []
    rows = inv.get("rows") or []
    ids = set()
    texts = {}
    for r in rows:
        rid = r.get("id", "?")
        for k in NEEDED:
            if k not in r or r[k] in (None, "", []):
                faults.append("%s: field %s missing or empty" % (rid, k))
        if rid in ids:
            faults.append("%s: duplicate id" % rid)
        ids.add(rid)
        if r.get("category") not in cats:
            faults.append("%s: unknown category %r" % (rid, r.get("category")))
        if r.get("enforcement") not in kinds:
            faults.append("%s: unknown enforcement kind %r" % (rid, r.get("enforcement")))
        if r.get("scope") not in SCOPES:
            faults.append("%s: unknown scope %r" % (rid, r.get("scope")))
        for s in r.get("sites") or []:
            f, sym = s.get("file"), s.get("symbol")
            if not f or not sym:
                faults.append("%s: a site lacks file or symbol" % rid)
                continue
            path = os.path.join(root, f)
            if path not in texts:
                try:
                    with open(path, encoding="utf-8", errors="replace") as h:
                        texts[path] = h.read()
                except OSError:
                    texts[path] = None
            if texts[path] is None:
                faults.append("%s: file %s is missing" % (rid, f))
            elif sym not in texts[path]:
                faults.append("%s: symbol %r no longer occurs in %s" % (rid, sym, f))
    if len(rows) < MIN_ROWS:
        faults.append("only %d rows, fewer than %d" % (len(rows), MIN_ROWS))
    in_gap = set()
    for g in inv.get("open_gaps") or []:
        if not g.get("text") or not g.get("rows"):
            faults.append("gap %s: text or rows missing" % g.get("id"))
        for rid in g.get("rows") or []:
            if rid not in ids:
                faults.append("gap %s: unknown row %s" % (g.get("id"), rid))
            in_gap.add(rid)
    for r in rows:
        if r.get("enforcement") in GAP_KINDS and r.get("id") not in in_gap:
            faults.append("%s: %s but in no open gap" % (r.get("id"), r.get("enforcement")))
    counts = {
        "rows": len(rows),
        "sites": sum(len(r.get("sites") or []) for r in rows),
        "by_kind": dict(collections.Counter(r.get("enforcement") for r in rows)),
        "by_category": dict(collections.Counter(r.get("category") for r in rows)),
        "by_scope_kind": dict(collections.Counter("%s/%s" % (r.get("scope"), r.get("enforcement")) for r in rows)),
        "open_gaps": len(inv.get("open_gaps") or []),
        "rows_in_gaps": len(in_gap),
    }
    return faults, counts


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--inventory", default=os.path.join(HERE, "inventory.yaml"))
    ap.add_argument("--root", default=ROOT)
    ap.add_argument("--json")
    a = ap.parse_args(argv)
    with open(a.inventory, encoding="utf-8") as h:
        inv = yaml.safe_load(h)
    faults, counts = check(inv, a.root)
    for f in faults:
        print("FAULT: " + f)
    print(json.dumps(counts, sort_keys=True))
    if a.json:
        with open(a.json, "w", encoding="utf-8") as h:
            json.dump({"faults": faults, "counts": counts, "ok": not faults}, h, indent=1, sort_keys=True)
            h.write("\n")
    print("inventory: %s" % ("ok" if not faults else "%d faults" % len(faults)))
    return 0 if not faults else 1


if __name__ == "__main__":
    sys.exit(main())
