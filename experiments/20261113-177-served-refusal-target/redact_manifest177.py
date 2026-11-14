#!/usr/bin/env python3
"""Publication rule (PREREG): the stock manifest's `embedding_rows` is keyed by token id, so the set of fetched rows would
reveal which tokens occur in the refusal-type replies. Move the full manifest to scratch and keep in runs/ a copy whose
embedding_rows is replaced by a count and sha256(json.dumps(sorted rows, sort_keys=True)) of the full map, which a later
lane holding the scratch copy can check. Tensor entries are unchanged. Run once, before the first commit of runs/.
Usage: redact_manifest177.py <runs/manifest-stock.json> <scratch copy path>"""
import hashlib, json, shutil, sys
from pathlib import Path
src, dst = Path(sys.argv[1]), Path(sys.argv[2])
m = json.load(open(src))
if "embedding_rows_redacted" in m: raise SystemExit("already redacted")
shutil.copy2(src, dst)
er = m["embedding_rows"]
m["embedding_rows"] = {}
m["embedding_rows_redacted"] = dict(count=len(er), sha256_of_full_map=hashlib.sha256(json.dumps(er, sort_keys=True).encode()).hexdigest(),
                                    note="token ids withheld (publication rule, issue #177); "
                                    "per-row sha256 checked against PR #124's committed rows where both exist (runs/manifest-check.json, computed before redaction)")
# As run on 2026-11-13 the script also wrote a field rows_checked_against_pr124 = count (wrong name: only 61 rows
# overlap PR #124); it was renamed by hand to rows_compared_with_pr124_see_manifest_check = 61 before commit, and the
# field was then dropped from this script.
src.write_text(json.dumps(m, indent=1, sort_keys=True) + "\n"); print("redacted", len(er))
