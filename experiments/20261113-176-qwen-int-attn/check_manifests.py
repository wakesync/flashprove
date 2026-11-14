#!/usr/bin/env python3
"""Compare this run's fetched tensor sha256 with PR #124's committed manifests and with PR #68's diff.json.
Writes runs/manifest-check.json. Light, no network."""
import json
from pathlib import Path
HERE = Path(__file__).resolve().parent; R = HERE / "runs"; EXP = HERE.parent
P124 = EXP / "20261111-8-qwen-e2e-agreement" / "runs"
diff = {t["tensor"]: t for t in json.load(open(EXP / "20261109-8-qwen-real-weights" / "runs" / "diff.json"))["tensors"]}
out = {}
for ck in ("stock", "abl"):
    f = R / f"manifest-{ck}.json"
    if not f.exists(): continue
    m = json.load(open(f)); old = json.load(open(P124 / f"manifest-{ck}.json"))
    both = sorted(set(m["tensors"]) & set(old["tensors"]))
    bad = [n for n in both if m["tensors"][n]["sha256"] != old["tensors"][n]["sha256"]]
    eb = sorted(set(m["embedding_rows"]) & set(old["embedding_rows"]))
    ebad = [k for k in eb if m["embedding_rows"][k]["sha256"] != old["embedding_rows"][k]["sha256"]]
    key = "sha256_stock" if ck == "stock" else "sha256_abl"
    dboth = [n for n in m["tensors"] if n in diff]
    dbad = [n for n in dboth if diff[n][key] != m["tensors"][n]["sha256"]]
    out[ck] = dict(fetched=len(m["tensors"]), vs_pr124_compared=len(both), vs_pr124_mismatch=bad, not_in_pr124=len(set(m["tensors"]) - set(old["tensors"])),
                   emb_rows=len(m["embedding_rows"]), emb_rows_compared=len(eb), emb_rows_mismatch=ebad,
                   vs_pr68_diff_compared=len(dboth), vs_pr68_diff_mismatch=dbad)
(R / "manifest-check.json").write_text(json.dumps(out, indent=1) + "\n"); print(json.dumps(out))
