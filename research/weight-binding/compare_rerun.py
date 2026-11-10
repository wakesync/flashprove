#!/usr/bin/env python3
"""Compare the PR #87 rerun of H1 and the count (runs-rerun-pr87/) with the original run files (runs/).

Usage, from the top of the tree:
  python3 research/weight-binding/compare_rerun.py <out.json>
For each file: byte-identical or not; for JSON, the list of keys whose values differ (dotted paths).
Only `seconds` in h1-manifest-demo.json is expected to differ (wall time). Exit 0 iff nothing else differs.
"""
import hashlib, json, sys
from pathlib import Path

E = Path("experiments/20261110-36-weight-binding")
FILES = ["h1-manifest-demo.json", "manifest-stock.json", "manifest-abl.json", "counted.json"]
ALLOWED = {"h1-manifest-demo.json": {"seconds"}}


def diff(a, b, p=""):
    if isinstance(a, dict) and isinstance(b, dict):
        out = []
        for k in sorted(set(a) | set(b)):
            q = p + "." + k if p else k
            if k not in a or k not in b:
                out.append(q)
            else:
                out += diff(a[k], b[k], q)
        return out
    if isinstance(a, list) and isinstance(b, list) and len(a) == len(b):
        out = []
        for i, (x, y) in enumerate(zip(a, b)):
            out += diff(x, y, "%s[%d]" % (p, i))
        return out
    return [] if a == b else [p]


res, bad = {}, False
for f in FILES:
    old, new = (E / "runs" / f).read_bytes(), (E / "runs-rerun-pr87" / f).read_bytes()
    d = diff(json.loads(old), json.loads(new))
    unexpected = [k for k in d if k not in ALLOWED.get(f, set())]
    bad |= bool(unexpected)
    res[f] = dict(sha256_original=hashlib.sha256(old).hexdigest(), sha256_rerun=hashlib.sha256(new).hexdigest(),
                  byte_identical=(old == new), differing_keys=d, unexpected_differences=unexpected)
    if "seconds" in d:
        res[f]["seconds"] = dict(original=json.loads(old)["seconds"], rerun=json.loads(new)["seconds"])
res["verdict"] = "only allowed keys differ" if not bad else "UNEXPECTED DIFFERENCES"
json.dump(res, open(sys.argv[1], "w"), indent=1)
print(json.dumps(res, indent=1))
sys.exit(1 if bad else 0)
