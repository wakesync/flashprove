#!/usr/bin/env python3
"""Replace the scratch path in runs/run.time (written by /usr/bin/time -v before commit) with <SCRATCH>."""
import re
from pathlib import Path
p = Path(__file__).resolve().parent / "runs" / "run.time"
t = p.read_text(); n = re.sub(r"(record\.py run )\S+( runs)", r"\1<SCRATCH>\2", t)
assert n != t
p.write_text(n); print(n.splitlines()[0])
