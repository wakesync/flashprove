# RESULTS: 20261103-11-qwen38-27b-feasibility

Verdict against the pre-registered threshold: **PASS** (both conditions hold).
Write-up: [research/ports/qwen3.8-27b/FEASIBILITY.md](../../research/ports/qwen3.8-27b/FEASIBILITY.md).

## Kill criterion

Not triggered. The pinned config has no routed experts (dense FFN in every layer), the pinned
Transformers reference is available and cited by line, and no file over 5 GB was fetched (only
config/index/README and the JSON headers of the 18 shards).

## Runs

`run5.sh` ran `count_params.py` 5 times against revision `1d4bf0f2ff6012fd82039f2fa52739d0dd7c60c0`.
All 5 outputs are byte-identical: SHA-256 `bd6e4556d9a2bb1508a7e0f25424c33a4aaafceb38315af5878815137f8898e1`
(`runs/SHA256SUMS`). Deterministic count, so variance is zero by construction; the 5 runs check that
the remote headers did not change during the lane.

## Numbers (from `runs/run1.json`)

| quantity | value |
|---|---|
| shards / tensors / dtype | 18 / 1,199 / all BF16 |
| total parameters (incl. vision and MTP) | 27,781,427,952 |
| text decoder (48 Gated DeltaNet + 16 full-attention layers, 64 dense FFNs, norms) | 24,353,201,664 |
| of which: FFN / DeltaNet mixers / full-attention mixers / norms | 17,112,760,320 / 5,562,051,072 / 1,677,729,792 / 660,480 |
| embedding / output head (untied) | 1,271,398,400 / 1,271,398,400 |
| MTP head (excluded from a first port) | 424,699,392 |
| vision encoder (excluded from a first port) | 460,730,096 |
| committed set as in docs/model.md section 3 (decoder + embedding + head) | 26,895,998,464 |
| Maverick committed set, from docs/model.md section 2 shape numbers | 400,711,352,320 |
| **ratio committed Qwen / Maverick** | **0.0671** (threshold <= 0.25) |
| per-token matrix MACs, Qwen (every decoder matrix + head) | 25,624,600,064 |
| per-token matrix MACs, Maverick (top-1 routed + shared on MoE layers) | 16,149,708,800 |
| ratio per-token MACs Qwen / Maverick | 1.587 (not part of the threshold) |

## New operator families (from FEASIBILITY.md sections 2 and 4)

| model | new families with no counterpart in docs/model.md sections 5-8 |
|---|---|
| Qwen3.8-27B | **7** |
| GLM-5.3-Flash | 11 |
| DeepSeek-V4.1-Flash | 12 |

Condition (a) 7 < 11: holds. Condition (b) 0.0671 <= 0.25: holds. **PASS.**

Counting rule (fixed in FEASIBILITY.md section 4 before tallying): one family = one new kind of
constraint or table in the integer relation; a new shape of an existing gadget (e.g. a matmul of a new
size, SwiGLU of a new width) is not a family. GLM and DeepSeek counts are taken from the prior
feasibility notes and their pinned configs; they are a lower bound (each of those families may split
further), which only strengthens (a).

## What this does not show

No proof was run. The prove-cost and host-memory figures in FEASIBILITY.md section 3 are estimates by
scaling the Maverick timed runs, labelled as such. The integer approximation's fidelity to the BF16
model is not measured (no weights downloaded).
