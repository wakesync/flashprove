#!/usr/bin/env python3
"""Extract selected /usr/bin/time -v fields (no command line, no paths) from <scratch>/run.time into runs/run-time.json.
Usage: time_summary.py <run.time>"""
import json, re, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
tv = Path(sys.argv[1]).read_text()
KEYS = ("Elapsed (wall clock) time (h:mm:ss or m:ss)", "Maximum resident set size (kbytes)", "User time (seconds)",
        "System time (seconds)", "Percent of CPU this job got", "Exit status")
out = {}
for k in KEYS:
    m = re.search(re.escape(k) + r":\s*(.*)", tv); out[k] = m.group(1).strip() if m else None
(HERE / "runs" / "run-time.json").write_text(json.dumps(out, indent=1) + "\n"); print(json.dumps(out))
