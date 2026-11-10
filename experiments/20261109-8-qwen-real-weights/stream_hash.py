#!/usr/bin/env python3
"""Q2: stream every safetensors shard of one checkpoint and sha256 each tensor's byte range on the fly.

Nothing is written to disk except the JSON of hashes. Each shard is read once, front to back, with a
single HTTP GET (no Range: the whole file, so the whole-file sha256 can also be checked against the
LFS sha256 the Hub API reports). Per tensor: sha256 of bytes [8 + header_len + begin, 8 + header_len + end).

Usage: stream_hash.py <stock|abl> <out.json> [shard ...]
"""
import hashlib, json, struct, sys, time, urllib.request

REPOS = {"stock": ("Qwen/Qwen3.8-27B", "37561816e66b5b9153b1b64c10968c18c1e6f4a0"),
         "abl": ("huihui-ai/Huihui-Qwen3.8-27B-abliterated", "739e3c5b89849f6c238ce1e5b70008612ae42cdd")}
CHUNK = 1 << 23
UA = {"User-Agent": "flashprove-real-weights/1"}

def get(url, rng=None):
    h = dict(UA)
    if rng: h["Range"] = rng
    with urllib.request.urlopen(urllib.request.Request(url, headers=h), timeout=120) as r: return r.read()

def lfs_sha(repo, rev):
    meta = json.loads(get(f"https://huggingface.co/api/models/{repo}/revision/{rev}?blobs=true"))
    return {s["rfilename"]: (s.get("lfs") or {}).get("sha256") for s in meta["siblings"]}

def stream_shard(url):
    t0 = time.time()
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=300) as r:
        whole = hashlib.sha256()
        buf = b""
        def need(n):
            nonlocal buf
            while len(buf) < n:
                c = r.read(CHUNK)
                if not c: raise IOError("short read")
                buf += c
        need(8); hl = struct.unpack("<Q", buf[:8])[0]; need(8 + hl)
        header = json.loads(buf[8:8 + hl]); whole.update(buf[:8 + hl]); buf = buf[8 + hl:]
        ts = sorted(((k, v) for k, v in header.items() if k != "__metadata__"), key=lambda kv: kv[1]["data_offsets"][0])
        pos = 0; out = {}
        for name, v in ts:
            b, e = v["data_offsets"]
            if b != pos: raise ValueError(f"gap before {name}: {pos} != {b}")
            h = hashlib.sha256(); left = e - b
            while left:
                if not buf:
                    buf = r.read(CHUNK)
                    if not buf: raise IOError("short read in " + name)
                take = buf[:left]; buf = buf[len(take):]
                h.update(take); whole.update(take); left -= len(take)
            out[name] = dict(sha256=h.hexdigest(), nbytes=e - b, begin=b, end=e, dtype=v["dtype"], shape=v["shape"])
            pos = e
        tail = buf + r.read()
        whole.update(tail)
    return dict(header_len=hl, tensors=out, trailing_bytes=len(tail), file_sha256=whole.hexdigest(),
                file_bytes=8 + hl + pos + len(tail), seconds=round(time.time() - t0, 2))

def main():
    which, outp = sys.argv[1], sys.argv[2]
    repo, rev = REPOS[which]
    base = f"https://huggingface.co/{repo}/resolve/{rev}/"
    idx = json.loads(get(base + "model.safetensors.index.json"))
    shards = sys.argv[3:] or sorted(set(idx["weight_map"].values()))
    lfs = lfs_sha(repo, rev)
    t0 = time.time(); res = {}
    for s in shards:
        r = stream_shard(base + s)
        r["lfs_sha256"] = lfs.get(s); r["lfs_match"] = r["file_sha256"] == lfs.get(s)
        res[s] = r
        print(which, s, len(r["tensors"]), r["file_bytes"], r["seconds"], "lfs_match", r["lfs_match"], flush=True)
        json.dump(dict(repo=repo, rev=rev, shards=res), open(outp, "w"), indent=0)
    out = dict(repo=repo, rev=rev, n_shards=len(res), n_tensors=sum(len(v["tensors"]) for v in res.values()),
               bytes=sum(v["file_bytes"] for v in res.values()), seconds=round(time.time() - t0, 1),
               all_lfs_match=all(v["lfs_match"] for v in res.values()), shards=res)
    json.dump(out, open(outp, "w"), indent=0)
    print(which, "done", out["n_tensors"], out["bytes"], out["seconds"], "all_lfs_match", out["all_lfs_match"])

if __name__ == "__main__": main()
