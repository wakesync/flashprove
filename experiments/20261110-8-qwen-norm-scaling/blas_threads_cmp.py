#!/usr/bin/env python3
"""Compare the in_proj hashes of runs/blas-threads.jsonl across thread settings; write runs/blas-threads.json."""
import json
from pathlib import Path
R = Path(__file__).resolve().parent / "runs"
rows = [json.loads(l) for l in open(R / "blas-threads.jsonl")]
ref = rows[-1]  # variable unset = PR #68's setting
res = dict(reference="unset (PR #68 setting), affinity %d" % ref["affinity"], settings=[])
for r in rows:
    diff = sorted(p for p in ref["hashes"] if r["hashes"][p] != ref["hashes"][p])
    res["settings"].append(dict(threads_env=r["threads_env"], affinity=r["affinity"], prompts_differing_from_reference=diff))
(R / "blas-threads.json").write_text(json.dumps(res, indent=1) + "\n"); print(json.dumps(res, indent=1))
