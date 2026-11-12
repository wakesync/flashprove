#!/usr/bin/env python3
"""Replace the scratch directory in the `time -v` header of runs/run.time by <SCRATCH> before commit (as PR #88).
The scratch path is passed on the command line, never stored. Records what changed in runs/scrub-time-path.json."""
import json, sys
from pathlib import Path
R = Path(__file__).resolve().parent / "runs"
f = R / "run.time"; t = f.read_text(); n = t.count(sys.argv[1])
f.write_text(t.replace(sys.argv[1], "<SCRATCH>"))
(R / "scrub-time-path.json").write_text(json.dumps(dict(file="runs/run.time", replaced=n, by="<SCRATCH>",
    note="only the scratch directory argument in the Command being timed line; no number changed"), indent=1) + "\n")
print(n)
