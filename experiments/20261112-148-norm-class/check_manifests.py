#!/usr/bin/env python3
"""PR #138's check_manifests.py, adapted (runs dir = this experiment's; reference manifests = PR #124's committed ones,
plus PR #68's diff.json). Writes runs/manifest-check.json. Light, no network."""
import json
from pathlib import Path
HERE = Path(__file__).resolve().parent; R = HERE / "runs"; EXP = HERE.parent
OLD = EXP / "20261111-8-qwen-e2e-agreement" / "runs"
diff = {t["tensor"]: t for t in json.load(open(EXP / "20261109-8-qwen-real-weights" / "runs" / "diff.json"))["tensors"]}
out = {}
mine = {ck: json.load(open(R / f"manifest-{ck}.json")) for ck in ("stock", "abl") if (R / f"manifest-{ck}.json").exists()}
for ck, m in mine.items():
    old = json.load(open(OLD / f"manifest-{ck}.json"))
    both = sorted(set(m["tensors"]) & set(old["tensors"]))
    bad = [n for n in both if m["tensors"][n]["sha256"] != old["tensors"][n]["sha256"]]
    eb = sorted(set(m["embedding_rows"]) & set(old["embedding_rows"]))
    ebad = [k for k in eb if m["embedding_rows"][k]["sha256"] != old["embedding_rows"][k]["sha256"]]
    sha_key = "sha256_stock" if ck == "stock" else "sha256_abl"
    dboth = [n for n in m["tensors"] if n in diff]
    dbad = [n for n in dboth if diff[n][sha_key] != m["tensors"][n]["sha256"]]
    out[ck] = dict(fetched=len(m["tensors"]), vs_pr124_compared=len(both), vs_pr124_mismatch=bad,
                   emb_rows_compared=len(eb), emb_rows_mismatch=ebad, vs_pr68_diff_compared=len(dboth), vs_pr68_diff_mismatch=dbad)
out["all_match"] = bool(mine) and all(not v["vs_pr124_mismatch"] and not v["emb_rows_mismatch"] and not v["vs_pr68_diff_mismatch"] for v in out.values())
(R / "manifest-check.json").write_text(json.dumps(out, indent=1) + "\n"); print(json.dumps(out, indent=1)[:2000])
