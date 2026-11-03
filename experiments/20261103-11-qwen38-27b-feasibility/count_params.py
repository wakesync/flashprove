#!/usr/bin/env python3
"""Count Qwen3.8-27B parameters from safetensors shard HEADERS only (no tensor data).

For each shard listed in the pinned model.safetensors.index.json, fetch bytes 0-7 (header
length, little-endian u64) and then the JSON header with HTTP range requests. Prints one
canonical JSON document on stdout (sorted keys), so repeated runs can be compared by SHA-256.

Also computes, from config numbers stated in docs/model.md section 2, the committed integer
weight count of the Maverick shape that FlashProve proves, and the Qwen / Maverick ratio.
"""
import json, math, re, struct, sys, urllib.request

REPO = "Qwen/Qwen3.8-27B"
REV = "1d4bf0f2ff6012fd82039f2fa52739d0dd7c60c0"
BASE = f"https://huggingface.co/{REPO}/resolve/{REV}/"


def get(url, rng=None):
    h = {"User-Agent": "flashprove-feasibility/1"}
    if rng:
        h["Range"] = rng
    with urllib.request.urlopen(urllib.request.Request(url, headers=h), timeout=60) as r:
        return r.read()


def group(name):
    if name.startswith("model.visual."):
        return "vision"
    if name.startswith("mtp."):
        return "mtp"
    if "embed_tokens" in name:
        return "embedding"
    if name.startswith("lm_head"):
        return "head"
    if ".linear_attn." in name:
        return "text.linear_attn"
    if ".self_attn." in name:
        return "text.full_attn"
    if ".mlp." in name:
        return "text.mlp"
    return "text.norm"


def maverick_committed():
    # docs/model.md section 2/3, full size: L=48, d=5120, n_h=40, n_g=8, dh=128,
    # f=16384, fe=8192, NE=128, V=202048; odd layers MoE (shared + router + 128 routed experts).
    d, L, dq, dkv, f, fe, NE, V = 5120, 48, 40 * 128, 8 * 128, 16384, 8192, 128, 202048
    attn = d * (dq + 2 * dkv) + dq * d
    dense = 3 * d * f
    moe = 3 * d * fe + d * NE + NE * 3 * d * fe
    total = L * attn + (L // 2) * dense + (L // 2) * moe + 2 * V * d
    per_token_macs = L * attn + (L // 2) * dense + (L // 2) * (2 * 3 * d * fe + d * NE) + V * d
    return total, per_token_macs


def main():
    index = json.loads(get(BASE + "model.safetensors.index.json"))
    shards = sorted(set(index["weight_map"].values()))
    tensors = {}
    for sh in shards:
        n = struct.unpack("<Q", get(BASE + sh, "bytes=0-7"))[0]
        hdr = json.loads(get(BASE + sh, f"bytes=8-{7 + n}"))
        for k, v in hdr.items():
            if k != "__metadata__":
                tensors[k] = (v["dtype"], v["shape"])
    assert set(tensors) == set(index["weight_map"]), "index and shard headers disagree"
    groups, dtypes, shapes = {}, {}, {}
    for k, (dt, s) in tensors.items():
        p = math.prod(s)
        g = group(k)
        groups[g] = groups.get(g, 0) + p
        dtypes[dt] = dtypes.get(dt, 0) + 1
        shapes.setdefault(re.sub(r"\.\d+\.", ".N.", k), [dt, s])
    text = sum(v for g, v in groups.items() if g.startswith("text."))
    committed = text + groups["embedding"] + groups["head"]
    # per-token matrix multiply-accumulates of the text path (every text matrix once + head once)
    per_token = text + groups["head"]
    mav_total, mav_tok = maverick_committed()
    out = {
        "repo": REPO,
        "revision": REV,
        "shards": len(shards),
        "tensors": len(tensors),
        "index_total_size_bytes": index["metadata"]["total_size"],
        "dtypes": dtypes,
        "params_by_group": groups,
        "params_total": sum(groups.values()),
        "params_text_decoder": text,
        "params_committed_text": committed,
        "per_token_matrix_macs_text": per_token,
        "maverick_committed_from_docs_model_md": mav_total,
        "maverick_per_token_matrix_macs": mav_tok,
        "ratio_committed_qwen_over_maverick": round(committed / mav_total, 6),
        "ratio_per_token_macs_qwen_over_maverick": round(per_token / mav_tok, 6),
        "tensor_shapes": shapes,
    }
    json.dump(out, sys.stdout, sort_keys=True, indent=1)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
