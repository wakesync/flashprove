#!/usr/bin/env python3
"""Replace the scratch-directory prefix in the /usr/bin/time -v headers of runs/*.time with <SCRATCH> before the
files are first committed (same convention as PR #74's runs/*.time). Only the 'Command being timed' line can
contain it. Records the sha256 of each file before and after in runs/scrub-time-paths.json. Nothing else changes.
Usage: scrub_time_paths.py <scratch prefix>"""
import hashlib, json, sys
from pathlib import Path
R = Path(__file__).resolve().parent / "runs"
prefix = sys.argv[1].rstrip("/")
rec = []
for f in sorted(R.glob("*.time")):
    b = f.read_bytes()
    if prefix.encode() not in b:
        continue
    lines = b.decode().split("\n")
    changed = [i for i, l in enumerate(lines) if prefix in l]
    assert all("Command being timed" in lines[i] for i in changed), f
    new = b.replace(prefix.encode(), b"<SCRATCH>")
    rec.append(dict(file=f.name, sha256_before=hashlib.sha256(b).hexdigest(), sha256_after=hashlib.sha256(new).hexdigest(),
                    lines_changed=[i + 1 for i in changed], occurrences=b.count(prefix.encode())))
    f.write_bytes(new)
(R / "scrub-time-paths.json").write_text(json.dumps(dict(note="scratch prefix replaced by <SCRATCH> in the time -v command line only, before first commit", files=rec), indent=1) + "\n")
print(json.dumps(rec, indent=1))
