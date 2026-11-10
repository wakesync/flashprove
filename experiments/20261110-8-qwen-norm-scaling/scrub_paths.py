#!/usr/bin/env python3
"""Replace host paths in the raw run logs under runs/ with placeholders (<SCRATCH>, <REPO>, <HOME>). Only path
strings change; no number is touched. Prints the files it changed. Usage: scrub_paths.py"""
import re
from pathlib import Path
R = Path(__file__).resolve().parent / "runs"
repo = str(Path(__file__).resolve().parents[2]); home = str(Path.home())
n = 0
for f in sorted(R.rglob("*")):
    if not f.is_file() or f.suffix not in (".time", ".log", ".out", ".md", ".json", ".jsonl", ".progress", ".start", ".ran", ".done"): continue
    t = f.read_text(errors="replace")
    u = t.replace(repo + "-scratch", "<SCRATCH>").replace(repo, "<REPO>").replace(home, "<HOME>")
    u = re.sub(r"<HOME>/\.[a-z]+/projects/", "<WORKSPACE>/", u)
    if u != t: f.write_text(u); n += 1; print("scrubbed", f.relative_to(R))
print("files changed:", n)
