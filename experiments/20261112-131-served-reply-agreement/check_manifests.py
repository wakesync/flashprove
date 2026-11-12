#!/usr/bin/env python3
"""Compare this run's fetched tensor and embedding-row sha256 with PR #124's committed manifests (same checkpoints, same
revisions, same fetch code). Writes runs/manifest-check.json. Light."""
import json
from pathlib import Path
HERE = Path(__file__).resolve().parent; R = HERE / "runs"
OLD = HERE.parent / "20261111-8-qwen-e2e-agreement" / "runs"
out = {}
for ck in ("stock", "abl"):
    if not (R / f"manifest-{ck}.json").exists(): continue
    m = json.load(open(R / f"manifest-{ck}.json")); o = json.load(open(OLD / f"manifest-{ck}.json"))
    both = sorted(set(m["tensors"]) & set(o["tensors"]))
    eb = sorted(set(m["embedding_rows"]) & set(o["embedding_rows"]))
    out[ck] = dict(repo=m["repo"], rev=m["rev"], fetched=len(m["tensors"]), vs_pr124_compared=len(both),
                   vs_pr124_not_in_pr124=sorted(set(m["tensors"]) - set(o["tensors"])),
                   vs_pr124_mismatch=[n for n in both if m["tensors"][n]["sha256"] != o["tensors"][n]["sha256"]],
                   emb_rows_fetched=len(m["embedding_rows"]), emb_rows_compared=len(eb),
                   emb_rows_mismatch=[k for k in eb if m["embedding_rows"][k]["sha256"] != o["embedding_rows"][k]["sha256"]])
(R / "manifest-check.json").write_text(json.dumps(out, indent=1) + "\n"); print(json.dumps(out, indent=1))
