#!/usr/bin/env python3
"""Step 1 checks.
  repro_check.py fetch   : this lane's fetch manifests vs PR #68's committed ones (every sha256 equal), and stock vs abl.
  repro_check.py rows    : this lane's F = 12 rerun rows vs PR #68's committed F = 12 rows, exact equality of parsed JSON.
Writes runs/repro-<what>.json. Exit 1 on any mismatch."""
import json, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
OLD = HERE.parent / "20261109-8-qwen-real-weights" / "runs"
NEW = HERE / "runs"

def fetch():
    out = {}; bad = 0
    for ck in ("stock", "abl"):
        o = json.load(open(OLD / f"fetch-{ck}.json")); n = json.load(open(NEW / f"fetch-{ck}.json"))
        tens = {k: (v["sha256"] == n["tensors"][k]["sha256"], v["range"] == n["tensors"][k]["range"]) for k, v in o["tensors"].items()}
        rows = {k: v["sha256"] == n["embedding_rows"][k]["sha256"] for k, v in o["embedding_rows"].items()}
        extra = sorted(set(n["tensors"]) - set(o["tensors"]))
        r = dict(tensors_compared=len(tens), tensors_equal=sum(a and b for a, b in tens.values()),
                 rows_compared=len(rows), rows_equal=sum(rows.values()),
                 rows_sha256_equal=o["embedding"]["rows_sha256"] == n["embedding"]["rows_sha256"],
                 extra_tensors={k: n["tensors"][k]["sha256"] for k in extra})
        bad += (r["tensors_equal"] != r["tensors_compared"]) + (r["rows_equal"] != r["rows_compared"]) + (not r["rows_sha256_equal"])
        out[ck] = r
    s, a = (json.load(open(NEW / f"fetch-{c}.json")) for c in ("stock", "abl"))
    same = {k: s["tensors"][k]["sha256"] == a["tensors"][k]["sha256"] for k in s["tensors"]}
    out["stock_vs_abl"] = dict(tensors=len(same), identical=sum(same.values()), rows_identical=s["embedding"]["rows_sha256"] == a["embedding"]["rows_sha256"],
                               differing=[k for k, v in same.items() if not v])
    out["mismatches_vs_pr68"] = bad
    return out, bad

def rows():
    out = {}; bad = 0
    for ck in ("stock", "abl"):
        o = [json.loads(l) for l in open(OLD / f"real-{ck}.jsonl")]
        o = [r for r in o if r["F"] == 12]
        n = [json.loads(l) for l in open(NEW / f"repro-real-{ck}.jsonl")]
        key = lambda r: (r["prompt"], r["F"], r.get("head", -1))
        od = {key(r): r for r in o}; nd = {key(r): r for r in n}
        diff = [k for k in od if od[k] != nd.get(k)]
        fields = {}
        for k in diff:
            for f in set(od[k]) | set(nd.get(k, {})):
                if od[k].get(f) != nd.get(k, {}).get(f): fields[f] = fields.get(f, 0) + 1
        out[ck] = dict(pr68_rows=len(od), new_rows=len(nd), identical=len(od) - len(diff), differing=len(diff), differing_fields=fields,
                       extra_new=len(set(nd) - set(od)))
        bad += len(diff) + len(set(nd) - set(od))
    out["mismatches"] = bad
    return out, bad

if __name__ == "__main__":
    what = sys.argv[1]
    res, bad = {"fetch": fetch, "rows": rows}[what]()
    (NEW / f"repro-{what}.json").write_text(json.dumps(res, indent=1) + "\n")
    print(json.dumps(res, indent=1)[:3000])
    sys.exit(1 if bad else 0)
