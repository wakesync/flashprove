#!/usr/bin/env python3
"""Check the claim ledger: README results block, CLAIMS.md and research/results.yaml agree.

  python3 scripts/check-claims.py     exit 0 if consistent, 1 otherwise

Checks, reading the rendered markdown (not re-rendering it):
  - CLAIMS.md exists and has exactly one row per results.yaml id, in the same order;
  - every README results-block row has a CLAIMS.md row with the same title;
  - every evidence path in CLAIMS.md (and the README link) exists in the checkout;
  - the replication label in CLAIMS.md matches results.yaml, and a row that is
    unreplicated says "unreplicated" in its README and CLAIMS.md status cell;
  - a "replicated" row's replicated_by resolves: another result id in results.yaml, or a
    tracked repo path that exists (free text is refused). It checks the receipt exists,
    not what it says;
  - no public text outside the generated block (README.md, and every .md under docs/
    and guide/) says "independent measurements" / "two independent", or
    "independent(ly) replicated" on a line that does not name a file-backed replication.
Limits (see the PR #29 body): values are not matched to their sources (a wrong number
that fits its spread passes); the phrase guard is a fixed regex list, so a paraphrase
passes, and a line carrying an allowlist token (REPLICATED_OK) is exempt.
Run python3 scripts/update-results.py first if CLAIMS.md or the README block is stale.
"""
import os
import re
import subprocess
import sys

import yaml

ROOT = subprocess.run(["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True, check=True).stdout.strip()
SRC = os.path.join(ROOT, "research", "results.yaml")
README = os.path.join(ROOT, "README.md")
CLAIMS = os.path.join(ROOT, "CLAIMS.md")
PUBLIC_DIRS = ["docs", "guide"]  # every tracked .md under these, plus README.md outside the block
BEGIN_RE = re.compile(r"<!-- results:begin\b[^>]*-->")
END = "<!-- results:end -->"
LINK_RE = re.compile(r"\]\(([^)]+)\)")
# "independent measurements" is never allowed in public text; "independent replication" only on a line
# that names a row whose replication receipt is a file (see REPLICATED_OK).
MEASUREMENTS_RE = re.compile(r"independent(ly)? measure\w*|two independent", re.I)
REPLICATION_RE = re.compile(r"independent(ly)? replicat\w*", re.I)
REPLICATED_OK = ("replication-1", "PR #26", "PR #3", "separate clone")


def tracked(rel):
    return os.path.exists(os.path.join(ROOT, rel)) and subprocess.run(
        ["git", "-C", ROOT, "ls-files", "--error-unmatch", "--", rel], capture_output=True).returncode == 0


def public_text():
    out = subprocess.run(["git", "-C", ROOT, "ls-files", "--", *(f"{d}/*.md" for d in PUBLIC_DIRS)],
                         capture_output=True, text=True, check=True).stdout.split()
    return ["README.md", *sorted(p for p in out if os.path.exists(os.path.join(ROOT, p)))]


def split_row(line):
    # split a markdown table row on unescaped pipes
    cells = re.split(r"(?<!\\)\|", line.strip())[1:-1]
    return [c.strip().replace("\\|", "|") for c in cells]


def table_rows(text):
    return [split_row(ln) for ln in text.splitlines()
            if ln.startswith("| ") and not ln.startswith("|---") and not ln.startswith("| Result |")
            and not ln.startswith("| id |")]


def main():
    errs = []
    doc = yaml.safe_load(open(SRC))
    results = doc.get("results") or []
    by_id = {r["id"]: r for r in results}

    if not os.path.exists(CLAIMS):
        print("check-claims: FAIL\n  CLAIMS.md missing: run python3 scripts/update-results.py", file=sys.stderr)
        return 1
    claims = table_rows(open(CLAIMS).read())
    ids = [c[0].strip("`") for c in claims if c]
    if ids != [r["id"] for r in results]:
        errs.append(f"CLAIMS.md ids {ids} != results.yaml ids {[r['id'] for r in results]}")
    for c in claims:
        if len(c) != 6:
            errs.append(f"CLAIMS.md: malformed row {c[:1]}")
            continue
        cid, claim, status, rep, ev, _pr = c
        cid = cid.strip("`")
        r = by_id.get(cid)
        if not r:
            errs.append(f"CLAIMS.md: {cid} not in results.yaml")
            continue
        if not claim.startswith(r["title"]):
            errs.append(f"CLAIMS.md: {cid} claim text does not start with its title")
        if rep.split(" ")[0] != r.get("replication"):
            errs.append(f"CLAIMS.md: {cid} replication {rep!r} != results.yaml {r.get('replication')!r}")
        if r.get("replication") == "unreplicated" and "unreplicated" not in status:
            errs.append(f"CLAIMS.md: {cid} is unreplicated but its status cell does not say so")
        if r.get("replication") == "replicated":
            by = r.get("replicated_by")
            if not by:
                errs.append(f"{cid}: replicated without replicated_by")
            elif by == cid or not (by in by_id or tracked(by)):
                errs.append(f"{cid}: replicated_by {by!r} is not another result id or a tracked repo path")
        paths = LINK_RE.findall(ev)
        if not paths:
            errs.append(f"CLAIMS.md: {cid} has no evidence link")
        for p in paths:
            if not os.path.exists(os.path.join(ROOT, p)):
                errs.append(f"CLAIMS.md: {cid} evidence path missing: {p}")

    text = open(README).read()
    m = BEGIN_RE.search(text)
    if not m or END not in text[m.end():]:
        errs.append("README.md: results markers not found")
        block, outside = "", text
    else:
        block = text[m.end(): text.index(END, m.end())]
        outside = text[: m.start()] + text[text.index(END, m.end()) + len(END):]
    titles = {r["title"]: r for r in results}
    readme_rows = table_rows(block)
    if len(readme_rows) != len(results):
        errs.append(f"README block has {len(readme_rows)} rows, results.yaml {len(results)}")
    for row in readme_rows:
        if len(row) != 5:
            errs.append(f"README block: malformed row {row[:1]}")
            continue
        r = titles.get(row[0])
        if not r:
            errs.append(f"README block: row {row[0]!r} has no CLAIMS.md / results.yaml entry")
            continue
        if r.get("replication") == "unreplicated" and "unreplicated" not in row[1]:
            errs.append(f"README block: {r['id']} is unreplicated but its status cell does not say so")
        for p in LINK_RE.findall(row[4]):
            if not os.path.exists(os.path.join(ROOT, p)):
                errs.append(f"README block: {r['id']} evidence path missing: {p}")

    scanned = public_text()
    for rel in scanned:
        path = os.path.join(ROOT, rel)
        if not os.path.exists(path):
            continue
        body = outside if rel == "README.md" else open(path).read()
        for ln, line in enumerate(body.splitlines(), 1):
            if MEASUREMENTS_RE.search(line):
                errs.append(f"{rel}: line {ln} claims independent measurements: {line.strip()[:100]}")
            elif REPLICATION_RE.search(line) and not any(k in line for k in REPLICATED_OK):
                errs.append(f"{rel}: line {ln} claims independent replication without a file receipt: {line.strip()[:100]}")

    if errs:
        print("check-claims: FAIL", *errs, sep="\n  ", file=sys.stderr)
        return 1
    n_unrep = sum(r.get("replication") == "unreplicated" for r in results)
    print(f"check-claims: ok ({len(results)} claims, {n_unrep} unreplicated, README block and CLAIMS.md agree, evidence paths exist, "
          f"replicated_by resolves, {len(scanned)} public .md files scanned)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
