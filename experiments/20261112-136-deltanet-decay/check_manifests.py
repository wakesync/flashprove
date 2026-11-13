#!/usr/bin/env python3
"""sha256 of every tensor and embedding row fetched here vs PR #124's committed manifests -> runs/manifest-check.json"""
import json
from pathlib import Path
HERE = Path(__file__).resolve().parent; R = HERE / "runs"
P124 = HERE.parent / "20261111-8-qwen-e2e-agreement" / "runs"
out = {}
for ck in ("stock", "abl"):
    mine = json.load(open(R / f"manifest-{ck}.json")); ref = json.load(open(P124 / f"manifest-{ck}.json"))
    t_both = [n for n in mine["tensors"] if n in ref["tensors"]]
    t_eq = sum(mine["tensors"][n]["sha256"] == ref["tensors"][n]["sha256"] for n in t_both)
    e_both = [n for n in mine.get("embedding_rows", {}) if n in ref.get("embedding_rows", {})]
    e_eq = sum(mine["embedding_rows"][n]["sha256"] == ref["embedding_rows"][n]["sha256"] for n in e_both)
    out[ck] = dict(repo=mine["repo"], rev=mine["rev"], same_rev=mine["rev"] == ref["rev"], tensors_fetched=len(mine["tensors"]),
                   tensors_in_pr124=len(t_both), tensors_equal=t_eq, not_in_pr124=sorted(set(mine["tensors"]) - set(ref["tensors"])),
                   embedding_rows_fetched=len(mine.get("embedding_rows", {})), embedding_rows_in_pr124=len(e_both), embedding_rows_equal=e_eq)
out["all_equal"] = all(v["tensors_equal"] == v["tensors_in_pr124"] and v["embedding_rows_equal"] == v["embedding_rows_in_pr124"] and v["same_rev"] for v in out.values() if isinstance(v, dict))
(R / "manifest-check.json").write_text(json.dumps(out, indent=1) + "\n"); print(json.dumps(out, indent=1))
