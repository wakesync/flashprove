#!/usr/bin/env python3
"""Copy a /usr/bin/time -v output into runs/, replacing the clone and scratch paths by <REPO> and <SCRATCH> (as PR #178).
Usage: scrub_time.py <time file> <out name>"""
import re, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent; REPO = HERE.parents[1]
t = Path(sys.argv[1]).read_text().replace(str(REPO), "<REPO>")
t = re.sub(r'(<REPO>\S*\s+)(/\S+)', r'\1<SCRATCH>', t)
(HERE / "runs" / sys.argv[2]).write_text(t); print(t.splitlines()[0])
