#!/usr/bin/env python3
"""Check research/coverage/inventory.yaml against the tree: it fails when a cited site disappears.

Fails (exit 1) if:
  - the inventory's declared `kinds` or `categories` differ from the four kinds and four categories
    fixed in this file (the inventory cannot widen its own schema);
  - a row lacks a field, or has an unknown category, kind or scope, or a duplicate id;
  - a row has no site, a site's symbol is shorter than MIN_SYMBOL characters, a site's file is
    missing, or its symbol no longer occurs in the file;
  - a prover_only or not_enforced row is not listed in any open gap, or a gap names an unknown row;
  - a plain gap (an id not starting with G-OB) names a row that is not prover_only or not_enforced
    (only the open-obligation entries G-OB* may name proof or validation rows);
  - a directory under research/operators/ is neither cited by some row's site nor listed, with a
    reason, under `excluded`; or an `excluded` entry names a directory that does not exist.
Prints counts by category and kind, and with --json writes them as JSON.

What it does not check: that a row's kind is right. A row moved from verifier_validation to
proof_constraint, a site whose code was disabled but kept its text, or a row that lost one of two
sites all pass. The kind is a reviewer's reading, and a review must challenge it.

Usage: python3 research/coverage/check_inventory.py [--inventory PATH] [--root DIR] [--json OUT]
Standard library plus PyYAML (the same dependency as scripts/update-results.py).
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
# The schema is fixed here, not read from the inventory (review of PR #97: an inventory that declared
# a fifth kind used to pass).
KINDS = ("proof_constraint", "verifier_validation", "prover_only", "not_enforced")
CATEGORIES = ("operator", "range_rounding", "input_state", "output")
SCOPES = ("shipped", "research")
GAP_KINDS = ("prover_only", "not_enforced")
MIN_ROWS = 40
MIN_SYMBOL = 12
RESEARCH_DIR = "research/operators"


def check(inv, root):
    faults = []
    if list(inv.get("kinds") or []) != list(KINDS):
        faults.append("declared kinds %r differ from the checker's %r" % (inv.get("kinds"), list(KINDS)))
    if list(inv.get("categories") or []) != list(CATEGORIES):
        faults.append("declared categories %r differ from the checker's %r" % (inv.get("categories"), list(CATEGORIES)))
    rows = inv.get("rows") or []
    ids = set()
    kind_of = {}
    texts = {}
    cited_files = set()
    for r in rows:
        rid = r.get("id", "?")
        for k in NEEDED:
            if k not in r or r[k] in (None, "", []):
                faults.append("%s: field %s missing or empty" % (rid, k))
        if rid in ids:
            faults.append("%s: duplicate id" % rid)
        ids.add(rid)
        kind_of[rid] = r.get("enforcement")
        if r.get("category") not in CATEGORIES:
            faults.append("%s: unknown category %r" % (rid, r.get("category")))
        if r.get("enforcement") not in KINDS:
            faults.append("%s: unknown enforcement kind %r" % (rid, r.get("enforcement")))
        if r.get("scope") not in SCOPES:
            faults.append("%s: unknown scope %r" % (rid, r.get("scope")))
        for s in r.get("sites") or []:
            f, sym = s.get("file"), s.get("symbol")
            if not f or not sym:
                faults.append("%s: a site lacks file or symbol" % rid)
                continue
            cited_files.add(f)
            if len(sym) < MIN_SYMBOL:
                faults.append("%s: symbol %r is shorter than %d characters" % (rid, sym, MIN_SYMBOL))
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
        gid = str(g.get("id"))
        if not g.get("text") or not g.get("rows"):
            faults.append("gap %s: text or rows missing" % gid)
        for rid in g.get("rows") or []:
            if rid not in ids:
                faults.append("gap %s: unknown row %s" % (gid, rid))
            elif not gid.startswith("G-OB") and kind_of.get(rid) not in GAP_KINDS:
                faults.append("gap %s: names %s, which is %s; a plain gap names only prover_only or not_enforced rows"
                              % (gid, rid, kind_of.get(rid)))
            in_gap.add(rid)
    for r in rows:
        if r.get("enforcement") in GAP_KINDS and r.get("id") not in in_gap:
            faults.append("%s: %s but in no open gap" % (r.get("id"), r.get("enforcement")))
    # Research directories: each one is cited or excluded with a reason.
    excluded = {}
    for e in inv.get("excluded") or []:
        p, why = e.get("path"), e.get("reason")
        if not p or not why:
            faults.append("excluded entry %r: path or reason missing" % e)
            continue
        if not os.path.isdir(os.path.join(root, p)):
            faults.append("excluded %s: no such directory" % p)
        excluded[p.rstrip("/")] = why
    rdir = os.path.join(root, RESEARCH_DIR)
    research_dirs = sorted(d for d in os.listdir(rdir) if os.path.isdir(os.path.join(rdir, d))) if os.path.isdir(rdir) else []
    uncovered = []
    for d in research_dirs:
        p = RESEARCH_DIR + "/" + d
        if p in excluded:
            continue
        if not any(f.startswith(p + "/") for f in cited_files):
            uncovered.append(p)
            faults.append("%s: no row cites it and it is not under excluded" % p)
    counts = {
        "rows": len(rows),
        "sites": sum(len(r.get("sites") or []) for r in rows),
        "by_kind": dict(collections.Counter(r.get("enforcement") for r in rows)),
        "by_category": dict(collections.Counter(r.get("category") for r in rows)),
        "by_scope_kind": dict(collections.Counter("%s/%s" % (r.get("scope"), r.get("enforcement")) for r in rows)),
        "open_gaps": len(inv.get("open_gaps") or []),
        "rows_in_gaps": len(in_gap),
        "research_dirs": len(research_dirs),
        "research_dirs_excluded": len([d for d in research_dirs if RESEARCH_DIR + "/" + d in excluded]),
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
        if os.path.exists(a.json):
            print("refusing to overwrite " + a.json)
            return 2
        with open(a.json, "w", encoding="utf-8") as h:
            json.dump({"faults": faults, "counts": counts, "ok": not faults}, h, indent=1, sort_keys=True)
            h.write("\n")
    print("inventory: %s" % ("ok" if not faults else "%d faults" % len(faults)))
    return 0 if not faults else 1


if __name__ == "__main__":
    sys.exit(main())
