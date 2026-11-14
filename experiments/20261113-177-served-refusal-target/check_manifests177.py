#!/usr/bin/env python3
"""Compare this run's fetched tensor sha256 with PR #87's committed per-tensor manifests (experiments/20261110-36-weight-binding,
all 1,199 tensors of each checkpoint) and the embedding rows with PR #124's. Writes runs/manifest-check.json. Light."""
import json
from pathlib import Path
HERE = Path(__file__).resolve().parent; R = HERE / "runs"
B = HERE.parent / "20261110-36-weight-binding" / "runs"; E = HERE.parent / "20261111-8-qwen-e2e-agreement" / "runs"
out = {}
for ck in ("stock", "abl"):
    m = json.load(open(R / f"manifest-{ck}.json"))
    ref = {t["name"]: t["sha256"] for t in json.load(open(B / f"manifest-{ck}.json"))["tensors"]}
    e = json.load(open(E / f"manifest-{ck}.json"))
    both = sorted(set(m["tensors"]) & set(ref)); eb = sorted(set(m["embedding_rows"]) & set(e["embedding_rows"]))
    out[ck] = dict(repo=m["repo"], rev=m["rev"], fetched=len(m["tensors"]), vs_pr87_compared=len(both),
                   vs_pr87_missing=sorted(set(m["tensors"]) - set(ref)),
                   vs_pr87_mismatch=[n for n in both if m["tensors"][n]["sha256"] != ref[n]],
                   emb_rows_fetched=len(m["embedding_rows"]), emb_rows_compared_pr124=len(eb),
                   emb_rows_mismatch=[k for k in eb if m["embedding_rows"][k]["sha256"] != e["embedding_rows"][k]["sha256"]])
out["ok"] = all(not out[c]["vs_pr87_missing"] and not out[c]["vs_pr87_mismatch"] and not out[c]["emb_rows_mismatch"] for c in ("stock", "abl"))
(R / "manifest-check.json").write_text(json.dumps(out, indent=1) + "\n"); print(json.dumps(out, indent=1))
