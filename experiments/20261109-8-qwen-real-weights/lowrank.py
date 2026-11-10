#!/usr/bin/env python3
"""Q5: what abliteration changed, on three differing matrices (one per family) fetched from both checkpoints by
HTTP range request: layer 17 mlp.down_proj, layer 17 linear_attn.out_proj, layer 19 self_attn.o_proj (first
differing layer of each family). For Delta = W_abl - W_stock (BF16 values, exact in float64):
  - singular values of Delta (via eigenvalues of Delta Delta^T, 5120 x 5120), energy share of the top 1..4
  - the top left singular vector r (output / residual direction) and its cosine across the three matrices
  - the rank-1 projection model W_abl ~= (I - r r^T) W_stock: relative residual, and the BF16 rounding floor
Writes runs/lowrank.json and runs/fetch-lowrank-<ckpt>.json (ranges + sha256, comparable with stream-*.json).
Usage: lowrank.py <cache_dir>"""
import hashlib, json, math, struct, sys, time
from pathlib import Path
import numpy as np
import fetch as FE

HERE = Path(__file__).resolve().parent
P = "model.language_model."
NAMES = [P + "layers.17.mlp.down_proj.weight", P + "layers.17.linear_attn.out_proj.weight", P + "layers.19.self_attn.o_proj.weight"]

def grab(ckpt, cache):
    repo, rev = FE.REPOS[ckpt]; base = f"https://huggingface.co/{repo}/resolve/{rev}/"
    wm = json.loads(FE.get(base + "model.safetensors.index.json"))["weight_map"]
    man = {}; out = {}
    for n in NAMES:
        sh = wm[n]; hl = struct.unpack("<Q", FE.get(base + sh, "bytes=0-7"))[0]
        h = json.loads(FE.get(base + sh, f"bytes=8-{7 + hl}"))[n]; b, e = h["data_offsets"]
        lo, hi = 8 + hl + b, 8 + hl + e - 1
        data = FE.get(base + sh, f"bytes={lo}-{hi}"); assert len(data) == e - b
        man[n] = dict(shard=sh, range=f"bytes={lo}-{hi}", nbytes=len(data), shape=h["shape"], sha256=hashlib.sha256(data).hexdigest())
        raw = np.frombuffer(data, dtype="<u2").astype(np.uint32) << 16
        out[n] = raw.view(np.float32).reshape(h["shape"]).astype(np.float64)
        print(ckpt, n, len(data), flush=True)
    (HERE / "runs" / f"fetch-lowrank-{ckpt}.json").write_text(json.dumps(dict(repo=repo, rev=rev, tensors=man), indent=1) + "\n")
    return out

def main():
    t0 = time.time()
    Ws, Wa = grab("stock", sys.argv[1]), grab("abl", sys.argv[1])
    stream = {ck: json.load(open(HERE / "runs" / f"stream-{ck}.json")) for ck in ("stock", "abl")}
    res = dict(matrices={}); rs = {}
    for n in NAMES:
        S, A = Ws[n], Wa[n]; Dl = A - S
        G = Dl @ Dl.T                                                   # (5120, 5120)
        ev, U = np.linalg.eigh(G); ev = np.clip(ev[::-1], 0, None); U = U[:, ::-1]
        sv = np.sqrt(ev); E = ev.sum()
        r = U[:, 0]; rs[n] = r
        Ahat = S - np.outer(r, r @ S)                                   # (I - r r^T) W_stock
        # BF16 floor: round the rank-1 model to BF16 and compare with the published abliterated tensor
        from real_head import bf16
        Ahat_b = bf16(Ahat)
        # scaled projection W_abl ~= W_stock - alpha r r^T W_stock, alpha by least squares (alpha = 1 is plain projection)
        Pm = np.outer(r, r @ S); alpha = float(-(Dl * Pm).sum() / (Pm * Pm).sum())
        Ahat2 = S - alpha * Pm; Ahat2_b = bf16(Ahat2)
        # rank-1 truncation of Delta itself (what is left is the BF16 rounding of W_abl)
        u1 = U[:, 0]; Dl1 = np.outer(u1, u1 @ Dl)
        res["matrices"][n] = dict(
            shape=list(S.shape), changed_entries=int((Dl != 0).sum()), entries=int(Dl.size),
            rel_delta=float(np.linalg.norm(Dl) / np.linalg.norm(S)),
            top_singular_values=[float(x) for x in sv[:6]], energy_top1=float(ev[0] / E), energy_top4=float(ev[:4].sum() / E),
            rank1_projection_rel_residual=float(np.linalg.norm(A - Ahat) / np.linalg.norm(Dl)),
            rank1_projection_bf16_exact_fraction=float((Ahat_b == A).mean()),
            rank1_projection_bf16_rel_residual=float(np.linalg.norm(A - Ahat_b) / np.linalg.norm(Dl)),
            r_norm_check=float(np.linalg.norm(r)),
            alpha_fit=alpha, scaled_projection_rel_residual=float(np.linalg.norm(A - Ahat2) / np.linalg.norm(Dl)),
            scaled_projection_bf16_exact_fraction=float((Ahat2_b == A).mean()),
            delta_rank1_truncation_rel_residual=float(np.linalg.norm(Dl - Dl1) / np.linalg.norm(Dl)),
            bf16_half_ulp_rms_of_W_abl=float(np.sqrt(np.mean((np.abs(A) * 2.0 ** -8 / 2) ** 2 / 3)) * math.sqrt(A.size) / np.linalg.norm(Dl)),
            stream_sha_match={ck: stream[ck]["shards"][json.load(open(HERE / "runs" / f"fetch-lowrank-{ck}.json"))["tensors"][n]["shard"]]["tensors"][n]["sha256"]
                              == json.load(open(HERE / "runs" / f"fetch-lowrank-{ck}.json"))["tensors"][n]["sha256"] for ck in ("stock", "abl")})
        print(n, json.dumps(res["matrices"][n]), flush=True)
    ks = list(rs)
    res["direction_cosine"] = {f"{i}~{j}": float(abs(rs[ks[i]] @ rs[ks[j]])) for i in range(3) for j in range(i + 1, 3)}
    res["seconds"] = round(time.time() - t0, 1)
    (HERE / "runs" / "lowrank.json").write_text(json.dumps(res, indent=1) + "\n")
    print(json.dumps(res["direction_cosine"]), res["seconds"])

if __name__ == "__main__": main()
