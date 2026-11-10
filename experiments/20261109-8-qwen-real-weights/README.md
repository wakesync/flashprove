# Real-weight check of the Qwen DeltaNet integer contract, stock versus abliterated (CPU, no proof)

Issue #8, part of #32 and #36. PREREG: [PREREG.md](PREREG.md). Results and verdict: [RESULTS.md](RESULTS.md).

## What this is, in plain language

Earlier Qwen work in this repo (M1, M1b and the M2 design) used made-up weights. This directory runs the same integer arithmetic on the real Qwen3.8-27B weights, for the first layer only. It asks three things:
- do the number ranges that the proofs assume still hold;
- how far is the integer result from the real floating-point model;
- what exactly is different between the stock checkpoint and the abliterated one that we deploy.

**Nothing here is proved.** No proof is built or verified. Every result is a measurement of an integer reference and a float reference, run on the CPU.

- **What the integer path computes:** the M2 contract of `research/operators/qwen_deltanet_m2/head_reference.py`, which calls the M1 staged-floor step of `research/operators/qwen_deltanet/reference.py`. `real_head.py` re-implements it batched over the 48 heads and with F as a parameter. At F = 12 it is checked bit for bit against those files on their own synthetic suite (`real_head.py selfcheck`).
- **What the float path computes:** float64 Transformers semantics. It is checked against the verbatim Transformers functions, run in torch (`xcheck_torch.py`).
- **What a verifier would recompute:** not applicable, because there is no proof. In the M2 design, conv, SiLU, the L2 norm and the gates are verifier-recomputed. Here they are computed the way head_reference computes them (float64 at the table points).
- **Not covered:** layers other than 0, the ablated layers 17 to 51, the full-attention and MLP blocks, built lookup tables, any proof, and FP8.
- **Scope of the conclusions:** the fidelity verdict covers F = 12, 14 and 16 with the M2 lowering, on layer 0 and the 10 frozen prompts, nothing wider. The near-rank-1 structure of the abliteration edit was analysed on 3 of the 70 changed tensors. The arm stored as `norm_only_rel_y` is o rounded to the 2^-F grid, then the integer norm, so it includes the rounding of o (RESULTS 4.4 point 2).

No weight data is in the repo. Only hashes, byte ranges, shapes and derived statistics are.

## Files

| file | what it does |
|---|---|
| `prompts.py`, `prompts.json` | the frozen prompt set (10 prompts, 2,396 tokens) and its token IDs (PREREG commit) |
| `stream_hash.py` | Q2: streams every shard once and sha256-hashes each tensor's byte range on the fly. It keeps nothing and also checks each whole file against the Hub's LFS sha256 |
| `fetch.py` | Q3: range-fetches the layer-0 DeltaNet tensors and the 209 embedding rows used by the prompts into a scratch dir outside the repo, and records every range and sha256 |
| `layout.py` | Q1: layout facts and the shape check against M1/M1b/M2, from the headers recorded by stream_hash.py |
| `diff.py` | Q2: per-tensor diff of the two streaming hash files, plus the cross-check against fetch.py |
| `lowrank.py` | Q5: range-fetches 3 differing matrices from both checkpoints (held in memory) and analyses Delta: SVD energy, shared direction, scaled-projection fit |
| `real_head.py` | Q3/Q4: the integer M2 head on real layer-0 inputs, against the float64 twin and a BF16 emulation, for all 48 heads, at F = 12/14/16. Also `selfcheck` |
| `run_all.sh` | the registered runs and the two secondary arms (taps at 2^F, q unscaled) |
| `summarise.py`, `buckets.py`, `tables.py` | read the jsonl files and write `runs/summary.json`, `runs/buckets.json` and the RESULTS tables |
| `xcheck_torch.py` | runs the verbatim modeling_qwen3_5.py functions (pinned, sha256-checked) in torch, float64 and BF16 eager |
| `weight_stats.py` | layer-0 parameter statistics compared with the synthetic init |
| `cmp_first.py` | checks that the rerun with extra fields reproduced the first run (used once). **It cannot be run from the repo**: it reads `runs/first-run/`, which was never committed, and the first-run copy was not kept. It is kept as a record of the check, not as a reproduce step |

## Reproduce

Requirements: Python 3.12 and numpy (2.4.3 used). `prompts.py` also needs `tokenizers`, and `xcheck_torch.py` needs `torch` (CPU, 2.15.0 used). Network access to huggingface.co, no token. About 350 MB of scratch disk for the cache, and about 2 GB RAM.

```
cd experiments/20261109-8-qwen-real-weights
C=/path/to/scratch          # outside the repo; delete when done

# frozen prompts (needs the stock tokenizer.json, sha256 0997f410...)
curl -L -o $C/tokenizer.json https://huggingface.co/Qwen/Qwen3.8-27B/resolve/37561816e66b5b9153b1b64c10968c18c1e6f4a0/tokenizer.json
python3 prompts.py $C/tokenizer.json prompts.json        # must reproduce prompts.json byte for byte

# Q2: full per-tensor hashes, streamed (about 5 min and 55.6 GB of download per checkpoint, nothing stored)
python3 stream_hash.py stock runs/stream-stock.json
python3 stream_hash.py abl   runs/stream-abl.json
python3 layout.py && python3 diff.py

# Q3 fetch (171 MB per checkpoint)
python3 fetch.py stock $C/cache
python3 fetch.py abl   $C/cache

# integer path == head_reference.py at F = 12 (20 synthetic runs, about 25 s)
python3 real_head.py selfcheck

# Q3/Q4 registered runs + secondary arms (about 15 min on 6 cores)
./run_all.sh $C/cache
python3 summarise.py && python3 buckets.py && python3 tables.py

# Q5 (0.61 GB fetched into memory) and the cross-checks
python3 lowrank.py $C/cache
python3 xcheck_torch.py /path/to/modeling_qwen3_5.py $C/cache stock     # transformers e540ae45, sha256 41a55adc...
python3 weight_stats.py $C/cache stock
```

### Exact-rerun settings

The committed runs used `run_all.sh` as written: `taskset -c 0-5`, one checkpoint at a time, and no BLAS or OpenMP thread variables set (`OPENBLAS_NUM_THREADS`, `OMP_NUM_THREADS` and the like were unset; the runner does not set them and inherits whatever is in the environment). `run_all.sh` is unchanged.

What changing those settings does, from another lane's receipt (lane `qwen-norm-scaling`, files `runs/repro-diff-threads3-stock.json` and `runs/repro-diff-threads3-abl.json` on its branch `research/1109-qwen-norm-scaling`; not committed in this PR, and that lane's PR is not open yet): it reran `real_head.py` with `OPENBLAS_NUM_THREADS=3` and both checkpoints in parallel. Per checkpoint, 473 of 480 rows differed, in float fields only, by at most 4.8e-13 relative; all 13,920 integer fields (range maxima and exact-limb minima) were equal. So:
- integer fields are expected to match bit for bit across thread settings;
- float fields match exactly only with the original settings above, and otherwise to about 1e-12 relative.

The reviewers' exact reruns of all 6,720 rows (RESULTS section 6, A-8) are true for the settings they used; they are not a guarantee for every thread setting.

### Two frozen script labels

Scripts are frozen in this PR. Two labels in them are historical and misleading: the comment at `real_head.py` line 292 says the arm "isolates the norm's own error", and `tables.py` line 10 prints the column header "norm-only". That arm rounds the float64 o to the 2^-F grid and then applies the integer norm, so it includes the rounding of o. The corrected description is in RESULTS section 4.4 point 2. The run-file field name `norm_only_rel_y` is kept unchanged.

`modeling_qwen3_5.py`: `https://raw.githubusercontent.com/huggingface/transformers/e540ae4528889920ce36955d1527036cca9b4ca5/src/transformers/models/qwen3_5/modeling_qwen3_5.py`.

### The exact range requests

Base URLs:
- `https://huggingface.co/Qwen/Qwen3.8-27B/resolve/37561816e66b5b9153b1b64c10968c18c1e6f4a0/<shard>`
- `https://huggingface.co/huihui-ai/Huihui-Qwen3.8-27B-abliterated/resolve/739e3c5b89849f6c238ce1e5b70008612ae42cdd/<shard>`

Each shard header is `Range: bytes=0-7` (u64 little-endian header length n), then `bytes=8-(7+n)`. A tensor with data_offsets [b, e] is at `bytes=(8+n+b)-(8+n+e-1)`.

The header lengths differ between checkpoints (the abliterated ones have no `__metadata__`), so the absolute ranges differ by 24 to 32 bytes. Layer 0 is in shard 1, where n = 45,392 (stock) and 45,360 (abliterated). Examples:

| tensor | stock range | abliterated range | sha256 (both) |
|---|---|---|---|
| layers.0.linear_attn.in_proj_qkv.weight | bytes=1120792-105978391 | bytes=1120760-105978359 | see runs/fetch-stock.json |
| embed_tokens.weight row t (shard 3, n = 144 / 120) | bytes=(152 + 10240 t)-(152 + 10240 t + 10239) | bytes=(128 + 10240 t)-(128 + 10240 t + 10239) | per row in runs/fetch-*.json |

Every range actually sent and every sha256 is in `runs/fetch-stock.json`, `runs/fetch-abl.json` and `runs/fetch-lowrank-*.json`. The per-tensor sha256 of all 1,199 tensors is in `runs/stream-*.json`.

## Not claimed

- No fidelity claim for any layer but 0.
- No claim about the ablated layers' integer behaviour.
- No proof, timing or security claim.
- The range-bound PASS (A1) is at F = 12 on 10 prompts from sequence start. It is not a bound for all inputs.
- Proposed claims are listed in the PR body. None is added to `loop/claims.json`.
