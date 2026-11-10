#!/usr/bin/env python3
"""Q2: per-tensor diff of the two streaming hash files, plus the cross-check against the Q3 range fetches.
Writes runs/diff.json and prints a summary. Usage: diff.py"""
import json, re, collections
from pathlib import Path
HERE = Path(__file__).resolve().parent
R = HERE / "runs"
S = json.load(open(R / "stream-stock.json")); A = json.load(open(R / "stream-abl.json"))

def flat(d):
    return {t: dict(v, shard=s) for s, sh in d["shards"].items() for t, v in sh["tensors"].items()}
fs, fa = flat(S), flat(A)
assert set(fs) == set(fa) and len(fs) == 1199

def family(t):
    m = re.match(r"model\.language_model\.layers\.(\d+)\.(.*)", t)
    if m: return int(m.group(1)), m.group(2)
    if t.startswith("mtp."): return "mtp", re.sub(r"layers\.\d+\.", "", t[4:])
    if t.startswith("model.visual."): return "visual", "visual"
    return "top", t

rows = []
for t in sorted(fs):
    a, b = fs[t], fa[t]
    same = a["sha256"] == b["sha256"] and a["nbytes"] == b["nbytes"]
    L, fam = family(t)
    rows.append(dict(tensor=t, layer=L, family=fam, same=same, nbytes=a["nbytes"], shape=a["shape"], dtype=a["dtype"],
                     sha256_stock=a["sha256"], sha256_abl=b["sha256"], shard=a["shard"]))
diff = [r for r in rows if not r["same"]]
by_fam = collections.Counter(r["family"] for r in diff)
layers = sorted({r["layer"] for r in diff if isinstance(r["layer"], int)})
other = sorted({str(r["layer"]) for r in diff if not isinstance(r["layer"], int)})
fam_all = collections.Counter(r["family"] for r in rows if isinstance(r["layer"], int))
# per-layer families that differ
per_layer = collections.defaultdict(list)
for r in diff:
    if isinstance(r["layer"], int): per_layer[r["layer"]].append(r["family"])
pattern = collections.Counter(tuple(sorted(v)) for v in per_layer.values())
# cross-check with Q3 range fetches
xc = []
for ck, flat_ in (("stock", fs), ("abl", fa)):
    man = json.load(open(R / f"fetch-{ck}.json"))
    for t, m in man["tensors"].items():
        xc.append(dict(ckpt=ck, tensor=t, equal=m["sha256"] == flat_[t]["sha256"]))
summary = dict(
    n_tensors=len(rows), n_identical=len(rows) - len(diff), n_different=len(diff),
    bytes_total=sum(r["nbytes"] for r in rows), bytes_different=sum(r["nbytes"] for r in diff),
    params_different=sum(r["nbytes"] // 2 for r in diff),
    different_by_family=dict(by_fam), layers_with_differences=layers, non_layer_groups_different=other,
    per_layer_pattern={"+".join(k): v for k, v in pattern.items()},
    stream_seconds=dict(stock=S["seconds"], abl=A["seconds"]), stream_bytes=dict(stock=S["bytes"], abl=A["bytes"]),
    all_lfs_match=dict(stock=S["all_lfs_match"], abl=A["all_lfs_match"]),
    crosscheck=dict(n=len(xc), equal=sum(x["equal"] for x in xc)),
    layer0_and_embedding_identical=all(r["same"] for r in rows if r["layer"] == 0 or "embed_tokens" in r["tensor"]))
json.dump(dict(summary=summary, tensors=rows, crosscheck=xc), open(R / "diff.json", "w"), indent=0)
print(json.dumps(summary, indent=1))
