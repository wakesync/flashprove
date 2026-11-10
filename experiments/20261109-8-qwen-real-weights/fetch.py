#!/usr/bin/env python3
"""Q3 fetch: HTTP range requests for the layer-0 DeltaNet tensors and the embedding rows of the prompt tokens.

Writes raw bytes to <cache>/<ckpt>/ (outside the repo, never committed) and a manifest to
runs/fetch-<ckpt>.json with, for every piece: shard file, absolute byte range (inclusive, as sent in
the Range header), byte count and sha256. For whole tensors the sha256 is comparable with the
streaming hash of stream_hash.py (an independent second read of the same bytes).

Usage: fetch.py <stock|abl> <cache_dir> [extra tensor names ...]
"""
import hashlib, json, os, struct, sys, time, urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPOS = {"stock": ("Qwen/Qwen3.8-27B", "37561816e66b5b9153b1b64c10968c18c1e6f4a0"),
         "abl": ("huihui-ai/Huihui-Qwen3.8-27B-abliterated", "739e3c5b89849f6c238ce1e5b70008612ae42cdd")}
P = "model.language_model."
LAYER0 = [P + "layers.0.input_layernorm.weight"] + [P + "layers.0.linear_attn." + n for n in (
    "A_log", "conv1d.weight", "dt_bias", "in_proj_a.weight", "in_proj_b.weight", "in_proj_qkv.weight",
    "in_proj_z.weight", "norm.weight")]
EMB = P + "embed_tokens.weight"
UA = {"User-Agent": "flashprove-real-weights/1"}

def get(url, rng=None, tries=4):
    h = dict(UA)
    if rng: h["Range"] = rng
    for i in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=h), timeout=300) as r:
                if r.status in (401, 403): raise SystemExit(f"gated or forbidden: {url} ({r.status}); stop, do not look for credentials")
                return r.read()
        except urllib.error.HTTPError as e:
            if e.code in (401, 403): raise SystemExit(f"gated or forbidden: {url} ({e.code}); stop, do not look for credentials")
            if i == tries - 1: raise
        except Exception:
            if i == tries - 1: raise
        time.sleep(2 * (i + 1))

def main():
    which, cache = sys.argv[1], Path(sys.argv[2]) / sys.argv[1]
    names = LAYER0 + sys.argv[3:]
    cache.mkdir(parents=True, exist_ok=True)
    repo, rev = REPOS[which]
    base = f"https://huggingface.co/{repo}/resolve/{rev}/"
    wm = json.loads(get(base + "model.safetensors.index.json"))["weight_map"]
    hdrs = {}
    def header(shard):
        if shard not in hdrs:
            n = struct.unpack("<Q", get(base + shard, "bytes=0-7"))[0]
            hdrs[shard] = (n, json.loads(get(base + shard, f"bytes=8-{7 + n}")))
        return hdrs[shard]
    man = dict(repo=repo, rev=rev, tensors={}, embedding_rows={})
    t0 = time.time()
    for name in names:
        shard = wm[name]; hl, h = header(shard); b, e = h[name]["data_offsets"]
        lo, hi = 8 + hl + b, 8 + hl + e - 1
        data = get(base + shard, f"bytes={lo}-{hi}")
        assert len(data) == e - b, (name, len(data), e - b)
        (cache / (name + ".bin")).write_bytes(data)
        man["tensors"][name] = dict(shard=shard, range=f"bytes={lo}-{hi}", nbytes=len(data), dtype=h[name]["dtype"],
                                    shape=h[name]["shape"], sha256=hashlib.sha256(data).hexdigest())
        print(which, name, len(data), flush=True)
    prompts = json.load(open(HERE / "prompts.json"))
    ids = sorted({t for p in prompts["prompts"] for t in p["token_ids"]})
    shard = wm[EMB]; hl, h = header(shard); b, e = h[EMB]["data_offsets"]
    V, d = h[EMB]["shape"]; row = (e - b) // V; assert row == d * 2
    def one(t):
        lo = 8 + hl + b + t * row; data = get(base + shard, f"bytes={lo}-{lo + row - 1}")
        assert len(data) == row
        return t, lo, data
    with ThreadPoolExecutor(8) as ex: rows = list(ex.map(one, ids))
    blob = bytearray()
    for t, lo, data in rows:
        man["embedding_rows"][str(t)] = dict(range=f"bytes={lo}-{lo + row - 1}", sha256=hashlib.sha256(data).hexdigest())
        blob += data
    (cache / "embed_rows.bin").write_bytes(bytes(blob))
    (cache / "embed_rows.ids.json").write_text(json.dumps(ids))
    man["embedding"] = dict(tensor=EMB, shard=shard, row_bytes=row, n_rows=len(ids),
                            rows_sha256=hashlib.sha256(bytes(blob)).hexdigest())
    man["seconds"] = round(time.time() - t0, 1)
    man["bytes_fetched"] = sum(v["nbytes"] for v in man["tensors"].values()) + len(blob)
    (HERE / "runs" / f"fetch-{which}.json").write_text(json.dumps(man, indent=1) + "\n")
    print(which, "done", man["bytes_fetched"], man["seconds"])

if __name__ == "__main__": main()
