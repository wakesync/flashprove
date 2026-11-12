#!/usr/bin/env python3
"""Compare this run's tensor sha256 with PR #88's committed manifests, and abl vs stock against PR #68's diff.json
(which tensors must be identical). Writes runs/manifest-check.json. Light."""
import json
from pathlib import Path
HERE = Path(__file__).resolve().parent; R = HERE / "runs"; EXP = HERE.parent
Q1 = EXP / "20261110-8-qwen-q1-deep-fidelity" / "runs"
diff = {t["tensor"]: t for t in json.load(open(EXP / "20261109-8-qwen-real-weights" / "runs" / "diff.json"))["tensors"]}
out = {}
mine = {ck: json.load(open(R / f"manifest-{ck}.json")) for ck in ("stock", "abl") if (R / f"manifest-{ck}.json").exists()}
for ck, m in mine.items():
    old = json.load(open(Q1 / f"manifest-{ck}.json"))
    both = sorted(set(m["tensors"]) & set(old["tensors"]))
    bad = [n for n in both if m["tensors"][n]["sha256"] != old["tensors"][n]["sha256"]]
    eb = sorted(set(m["embedding_rows"]) & set(old["embedding_rows"]))
    ebad = [k for k in eb if m["embedding_rows"][k]["sha256"] != old["embedding_rows"][k]["sha256"]]
    sha_key = "sha256_stock" if ck == "stock" else "sha256_abl"
    dboth = [n for n in m["tensors"] if n in diff]
    dbad = [n for n in dboth if diff[n][sha_key] != m["tensors"][n]["sha256"]]
    out[ck] = dict(fetched=len(m["tensors"]), vs_pr88_compared=len(both), vs_pr88_mismatch=bad,
                   emb_rows_compared=len(eb), emb_rows_mismatch=ebad, vs_pr68_diff_compared=len(dboth), vs_pr68_diff_mismatch=dbad)
if len(mine) == 2:
    s, a = mine["stock"]["tensors"], mine["abl"]["tensors"]
    common = sorted(set(s) & set(a))
    same = [n for n in common if s[n]["sha256"] == a[n]["sha256"]]
    differ = [n for n in common if s[n]["sha256"] != a[n]["sha256"]]
    expect_differ = [n for n in common if n in diff and not diff[n]["same"]]
    out["abl_vs_stock"] = dict(common=len(common), identical=len(same), different=len(differ),
                               different_as_pr68=sorted(differ) == sorted(expect_differ))
(R / "manifest-check.json").write_text(json.dumps(out, indent=1) + "\n"); print(json.dumps(out, indent=1)[:2000])
