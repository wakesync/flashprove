#!/usr/bin/env python3
"""Replace absolute host paths in this directory's run logs with placeholders before commit (<REPO> for the clone,
<SCRATCH> for the scratch directory). Run once, before the files are first committed. Prints what it changed."""
import re, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = str(HERE.parent.parent)
PAT = re.compile(r"/(?:home|Users|root)/[^\s\"']*")

def fix(s):
    s = s.replace(REPO, "<REPO>")
    return PAT.sub(lambda m: "<SCRATCH>/" + m.group(0).rstrip("/").split("/")[-1], s)

n = 0
for p in sorted((HERE / "runs").rglob("*")):
    if not p.is_file() or p.suffix not in (".log", ".jsonl", ".json", ".md", ".txt", ".time"): continue
    t = p.read_text(); u = fix(t)
    if u != t: p.write_text(u); n += 1; print("scrubbed", p.relative_to(HERE))
print("files changed:", n)
